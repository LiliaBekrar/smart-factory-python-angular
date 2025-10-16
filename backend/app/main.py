# app/main.py
"""
🌍 Smart Factory API — FastAPI
==============================
Application principale :
- Configure l'API FastAPI
- Applique automatiquement les migrations Alembic au démarrage
- (Optionnel) Lance les seeds si SEED_ON_START=true
- Redirige la racine ("/" et "/doc") vers /docs
- Configure CORS et expose toutes les routes
"""

from typing import List
from datetime import datetime, timedelta, timezone
import subprocess

from fastapi import FastAPI, Query, Depends, HTTPException, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc

# 🧩 Imports internes
from app.db import SessionLocal
from app.models import Machine, WorkOrder, ProductionEvent, User
from app.schemas import (
    MachineOut, WorkOrderOut, KPIOut,
    ActivityItemOut, UserOut, SignupIn, LoginIn, TokenOut,
    MachineCreate, MachineUpdate,
    DashboardSummaryOut, DashboardKPIOut, DashboardActivityItemOut,
    EventCreate, EventOut,
)
from app.security import hash_password, verify_password, create_access_token, decode_token
from app.settings import settings  # pour SEED_ON_START


# -------------------------------------------------
# ⚙️ Configuration de l'application FastAPI
# -------------------------------------------------
app = FastAPI(
    title="Smart Factory API",
    docs_url="/docs",
    redoc_url=None,        # on désactive ReDoc
    openapi_url="/openapi.json",
)

# Middleware CORS → autorise le front Angular à appeler l’API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ en production : remplace par l’URL exacte de ton site
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# -------------------------------------------------
# 🚀 Migrations + Seeds (au démarrage)
# -------------------------------------------------
@app.on_event("startup")
def run_startup_scripts():
    """Exécuté automatiquement au démarrage du serveur Render."""

    # --- 1️⃣ Appliquer les migrations Alembic ---
    try:
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        print("✅ Alembic migrations applied.")
    except Exception as e:
        print(f"⚠️ Alembic migration failed: {e}")

    # --- 2️⃣ Lancer les seeds si SEED_ON_START=true ---
    if getattr(settings, "seed_on_start", False):
        try:
            print("🌱 Seeding initial data...")
            subprocess.run(["python", "-m", "app.seed"], check=True)
            print("✅ Seed completed.")
        except Exception as e:
            print(f"⚠️ Seed failed: {e}")


# -------------------------------------------------
# 🗃️ Dépendance DB (Session)
# -------------------------------------------------
def get_db():
    """Crée une session SQLAlchemy et la ferme après utilisation."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------
# 🔐 Authentification & rôles
# -------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Récupère l'utilisateur courant à partir du token JWT."""
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

def require_role(*roles: str):
    """Vérifie que l'utilisateur courant a l'un des rôles demandés."""
    def _dep(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user
    return _dep


# -------------------------------------------------
# 🌡️ Healthcheck (utile pour Render)
# -------------------------------------------------
@app.get("/health")
def health():
    """Vérifie que l'API est en ligne."""
    return {"status": "ok"}


# -------------------------------------------------
# 💡 Exemple de route : Machines (lecture)
# -------------------------------------------------
@app.get("/machines", response_model=List[MachineOut])
def list_machines(db: Session = Depends(get_db)):
    """Renvoie toutes les machines enregistrées."""
    return db.query(Machine).all()

@app.get("/machines/{machine_id}", response_model=MachineOut)
def get_machine(machine_id: int, db: Session = Depends(get_db)):
    """Renvoie le détail d'une machine."""
    m = db.query(Machine).get(machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")
    return m


# -------------------------------------------------
# 🧮 KPIs — Calculs de performance qualité
# -------------------------------------------------
@app.get("/machines/{machine_id}/kpis", response_model=KPIOut)
def machine_kpis(
    machine_id: int,
    minutes: int = Query(60, ge=1, le=24*60),
    db: Session = Depends(get_db),
):
    """KPIs qualité/performance pour une machine donnée sur `minutes`."""
    since = datetime.utcnow() - timedelta(minutes=minutes)
    sums = (
        db.query(
            func.sum(case((ProductionEvent.event_type == "good",  ProductionEvent.qty), else_=0)).label("good_sum"),
            func.sum(case((ProductionEvent.event_type == "scrap", ProductionEvent.qty), else_=0)).label("scrap_sum"),
        )
        .filter(ProductionEvent.machine_id == machine_id, ProductionEvent.happened_at >= since)
        .one()
    )
    good = int(sums.good_sum or 0)
    scrap = int(sums.scrap_sum or 0)
    trs = (good / (good + scrap) * 100) if (good + scrap) > 0 else 0.0
    return KPIOut(good=good, scrap=scrap, trs=round(trs, 1))


# -------------------------------------------------
# 🔁 Redirections automatiques
# -------------------------------------------------
@app.get("/", include_in_schema=False)
def redirect_root():
    """Quand on visite la racine, on redirige vers /docs."""
    return RedirectResponse(url="/docs")

@app.get("/doc", include_in_schema=False)
def redirect_doc():
    """Redirige /doc (sans s) vers /docs."""
    return RedirectResponse(url="/docs")


# -------------------------------------------------
# 🧭 Debug : liste des routes
# -------------------------------------------------
@app.get("/routes")
def list_routes():
    """Affiche toutes les routes de l'application."""
    out = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            out.append({"path": r.path, "methods": list(r.methods)})
    return out

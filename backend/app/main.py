# app/main.py
"""
🌍 Smart Factory API — FastAPI (version commentée)
--------------------------------------------------
Ce module :
- instancie l'app FastAPI et active CORS,
- applique les migrations Alembic au démarrage (pratique sur Render Free),
- peut lancer les seeds au démarrage si SEED_ON_START=true,
- expose l'ensemble de tes routes (auth, machines, kpis, events, dashboard...).
"""

from typing import List
from datetime import datetime, timedelta, timezone
import subprocess

from fastapi import FastAPI, Query, Depends, HTTPException, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse


from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc

# 🔌 Accès DB (sync)
from app.db import SessionLocal
# 🧱 Modèles ORM
from app.models import Machine, WorkOrder, ProductionEvent, User
# 📨 Schémas Pydantic (entrées / sorties)
from app.schemas import (
    MachineOut, WorkOrderOut, KPIOut,
    ActivityItemOut, UserOut, SignupIn, LoginIn, TokenOut,
    MachineCreate, MachineUpdate,
    DashboardSummaryOut, DashboardKPIOut, DashboardActivityItemOut,
    EventCreate, EventOut,
)
# 🔐 Sécurité (hash, vérif, JWT)
from app.security import hash_password, verify_password, create_access_token, decode_token
# ⚙️ Settings (pour lire SEED_ON_START, etc.)
from app.settings import settings


# -------------------------------------------------
# ⚙️ App & middlewares
# -------------------------------------------------
# - docs_url: chemin vers Swagger UI
# - redoc_url: doc ReDoc (tu la conserves comme dans ta version)
# - openapi_url: endpoint du JSON OpenAPI
app = FastAPI(
    title="Smart Factory API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS large (pour démo). En prod, remplace "*" par l'URL exacte de ton front.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# -------------------------------------------------
# 🚀 Démarrage : migrations + (optionnel) seeds
# -------------------------------------------------
# Sur Render Free, il est pratique d'appliquer les migrations
# au démarrage si tu ne peux pas utiliser Pre/Post-Deploy hooks.
@app.on_event("startup")
def on_startup():
    # 1) Appliquer les migrations Alembic
    try:
        # Exécute : alembic upgrade head
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        print("✅ Alembic migrations applied.")
    except Exception as e:
        # N'empêche pas l'app de démarrer (mais log l'erreur)
        print(f"⚠️ Alembic migration failed: {e}")

    # 2) (Optionnel) Lancer les seeds si SEED_ON_START=true
    #    -> variable d'env lue via app.settings.settings
    if getattr(settings, "seed_on_start", False):
        try:
            print("🌱 Seeding initial data...")
            # On lance un module Python : app/seed_data.py (doit exister)
            subprocess.run(["python", "-m", "app.seed"], check=True)
            print("✅ Seed completed.")
        except Exception as e:
            print(f"⚠️ Seed failed: {e}")


# -------------------------------------------------
# 🗃️ DB session (dépendance FastAPI)
# -------------------------------------------------
def get_db():
    """
    Ouvre une session SQLAlchemy pour la requête puis la ferme.
    À utiliser comme Depends dans les routes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------
# 🔐 Auth helpers (JWT + rôles)
# -------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Décode le JWT, récupère l'utilisateur en BDD.
    Lève 401 si token invalide ou user introuvable.
    """
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

def require_role(*roles: str):
    """
    Dépendance qui impose que l'utilisateur courant ait l'un des rôles donnés.
    Ex: @Depends(require_role("operator","admin"))
    """
    def _dep(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user
    return _dep


# -------------------------------------------------
# 🌡️ Health
# -------------------------------------------------
@app.get("/health")
def health():
    """Endpoint simple pour vérifier que l'API répond."""
    return {"status": "ok"}


# -------------------------------------------------
# 🏭 Machines (lecture)
# -------------------------------------------------
@app.get("/machines", response_model=List[MachineOut])
def list_machines(db: Session = Depends(get_db)):
    """Liste toutes les machines."""
    return db.query(Machine).all()

@app.get("/machines/{machine_id}", response_model=MachineOut)
def get_machine(machine_id: int, db: Session = Depends(get_db)):
    """Détail d'une machine par id."""
    m = db.query(Machine).get(machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")
    return m


# -------------------------------------------------
# 📈 KPIs (machine & global)
# -------------------------------------------------
@app.get("/machines/{machine_id}/kpis", response_model=KPIOut)
def machine_kpis(
    machine_id: int,
    minutes: int = Query(60, ge=1, le=24*60),
    db: Session = Depends(get_db),
):
    """
    KPIs qualité/perf pour une machine sur `minutes` (défaut 60).
    Renvoie: { good, scrap, trs }.
    """
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

@app.get("/kpis/global", response_model=KPIOut)
def kpis_global(
    minutes: int = Query(60, ge=1, le=24*60),
    db: Session = Depends(get_db),
):
    """
    KPIs globaux toutes machines sur `minutes` (défaut 60).
    Renvoie: { good, scrap, trs }.
    """
    since = datetime.utcnow() - timedelta(minutes=minutes)
    sums = (
        db.query(
            func.sum(case((ProductionEvent.event_type == "good",  ProductionEvent.qty), else_=0)).label("good_sum"),
            func.sum(case((ProductionEvent.event_type == "scrap", ProductionEvent.qty), else_=0)).label("scrap_sum"),
        )
        .filter(ProductionEvent.happened_at >= since)
        .one()
    )
    good = int(sums.good_sum or 0)
    scrap = int(sums.scrap_sum or 0)
    trs = (good / (good + scrap) * 100) if (good + scrap) > 0 else 0.0
    return KPIOut(good=good, scrap=scrap, trs=round(trs, 1))


# -------------------------------------------------
# 📰 Activity feed
# -------------------------------------------------
@app.get("/activities/recent", response_model=List[ActivityItemOut])
def recent_activities(
    limit: int = Query(50, ge=1, le=500),
    minutes: int | None = Query(None, ge=1, le=24*60),  # minutes optionnel
    db: Session = Depends(get_db),
):
    """
    Si `minutes` est absent → renvoie simplement les `limit` derniers événements (toutes périodes).
    """
    q = (
        db.query(ProductionEvent, Machine.code, Machine.name, WorkOrder.number)
        .join(Machine, Machine.id == ProductionEvent.machine_id)
        .outerjoin(WorkOrder, WorkOrder.id == ProductionEvent.work_order_id)
    )
    if minutes is not None:
        since = datetime.utcnow() - timedelta(minutes=minutes)
        q = q.filter(ProductionEvent.happened_at >= since)

    q = q.order_by(desc(ProductionEvent.happened_at)).limit(limit)

    items: List[ActivityItemOut] = []
    for ev, machine_code, machine_name, wo_number in q.all():
        items.append(ActivityItemOut(
            id=ev.id, machine_id=ev.machine_id,
            machine_code=machine_code, machine_name=machine_name,
            work_order_id=ev.work_order_id, work_order_number=wo_number,
            event_type=ev.event_type, qty=ev.qty, notes=ev.notes, happened_at=ev.happened_at
        ))
    return items

@app.get("/machines/{machine_id}/activity", response_model=List[ActivityItemOut])
def machine_activity(
    machine_id: int,
    limit: int = Query(50, ge=1, le=500),
    minutes: int = Query(120, ge=1, le=24*60),
    db: Session = Depends(get_db),
):
    """Activité récente d'une machine sur une fenêtre glissante en minutes."""
    m = db.get(Machine, machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")

    since = datetime.utcnow() - timedelta(minutes=minutes)
    q = (
        db.query(ProductionEvent, WorkOrder.number)
        .outerjoin(WorkOrder, WorkOrder.id == ProductionEvent.work_order_id)
        .filter(ProductionEvent.machine_id == machine_id, ProductionEvent.happened_at >= since)
        .order_by(desc(ProductionEvent.happened_at))
        .limit(limit)
    )

    items: List[ActivityItemOut] = []
    for ev, wo_number in q.all():
        dt = ev.happened_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        items.append(ActivityItemOut(
            id=ev.id, machine_id=ev.machine_id,
            machine_code=m.code, machine_name=m.name,
            work_order_id=ev.work_order_id, work_order_number=wo_number,
            event_type=ev.event_type, qty=ev.qty, notes=ev.notes, happened_at=dt
        ))
    return items


# -------------------------------------------------
# 🔐 Auth: signup / login / me
# -------------------------------------------------
@app.post("/auth/signup", response_model=UserOut)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    """Inscription d'un nouvel utilisateur (rôle par défaut: operator)."""
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(email=body.email, hashed_password=hash_password(body.password), role="operator")
    db.add(user); db.commit(); db.refresh(user)
    return user

@app.post("/auth/login", response_model=TokenOut)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login via OAuth2 password (username=email). Renvoie un JWT."""
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Bad credentials")
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenOut(access_token=token)

@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """Renvoie le profil de l'utilisateur courant."""
    return user


# -------------------------------------------------
# 🛠️ Machines: CRUD avec règles d’édition
# -------------------------------------------------
def _ensure_can_edit_machine(user: User, m: Machine) -> None:
    """
    Règle métier:
      - admin/chef : toujours OK
      - operator   : OK seulement si m.created_by == user.id
    """
    if user.role in ("admin", "chef"):
        return
    if m.created_by != user.id:
        raise HTTPException(status_code=403, detail="You can only edit/delete your own machines")

@app.post("/machines", response_model=MachineOut)
def create_machine(
    body: MachineCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("operator", "chef", "admin")),
):
    """Créer une machine (code unique)."""
    if db.query(Machine).filter(Machine.code == body.code).first():
        raise HTTPException(status_code=400, detail="Machine code already exists")
    m = Machine(**body.model_dump(), created_by=user.id)
    db.add(m); db.commit(); db.refresh(m)
    return m

@app.patch("/machines/{machine_id}", response_model=MachineOut)
def update_machine(
    machine_id: int,
    body: MachineUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("operator", "chef", "admin")),
):
    """Met à jour une machine si l'utilisateur y est autorisé."""
    m = db.query(Machine).get(machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")

    _ensure_can_edit_machine(user, m)

    data = body.model_dump(exclude_unset=True)
    if "code" in data:
        exists = db.query(Machine).filter(Machine.code == data["code"], Machine.id != machine_id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Machine code already exists")

    for k, v in data.items():
        setattr(m, k, v)

    db.commit(); db.refresh(m)
    return m

@app.delete("/machines/{machine_id}")
def delete_machine(
    machine_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("operator", "chef", "admin")),
):
    """Supprime une machine si autorisé."""
    m = db.query(Machine).get(machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")

    _ensure_can_edit_machine(user, m)

    db.delete(m); db.commit()
    return {"ok": True}


# -------------------------------------------------
# 📊 Dashboard synthèse
# -------------------------------------------------
@app.get("/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(
    limit_recent: int = Query(5, ge=1, le=50),
    minutes: int = Query(60, ge=5, le=24*60),
    db: Session = Depends(get_db),
):
    """
    Renvoie un résumé global (nb machines, états, TRS moyen sur la fenêtre,
    et derniers événements).
    """
    since = datetime.utcnow() - timedelta(minutes=minutes)

    total = db.query(func.count(Machine.id)).scalar() or 0
    running = db.query(func.count(Machine.id)).filter(Machine.status == "running").scalar() or 0
    stopped = db.query(func.count(Machine.id)).filter(Machine.status == "stopped").scalar() or 0

    sums = (
        db.query(
            func.sum(case((ProductionEvent.event_type == "good",  ProductionEvent.qty), else_=0)).label("good_sum"),
            func.sum(case((ProductionEvent.event_type == "scrap", ProductionEvent.qty), else_=0)).label("scrap_sum"),
        )
        .filter(ProductionEvent.happened_at >= since)
        .one()
    )
    good = sums.good_sum or 0
    scrap = sums.scrap_sum or 0
    trs_avg_last_hour = float(round((good / (good + scrap) * 100), 1)) if (good + scrap) > 0 else 0.0

    q = (
        db.query(ProductionEvent, Machine.code, Machine.name, WorkOrder.number)
        .join(Machine, Machine.id == ProductionEvent.machine_id)
        .outerjoin(WorkOrder, WorkOrder.id == ProductionEvent.work_order_id)
        .filter(ProductionEvent.happened_at >= since)
        .order_by(desc(ProductionEvent.happened_at))
        .limit(limit_recent)
    )
    recent = [
        DashboardActivityItemOut(
            id=ev.id, machine_code=machine_code, machine_name=machine_name,
            event_type=ev.event_type, qty=ev.qty, happened_at=ev.happened_at,
            work_order_number=wo_number
        )
        for (ev, machine_code, machine_name, wo_number) in q.all()
    ]

    return DashboardSummaryOut(
        kpis=DashboardKPIOut(
            total_machines=total, running=running, stopped=stopped, trs_avg_last_hour=trs_avg_last_hour
        ),
        recent=recent,
    )


# -------------------------------------------------
# 🧾 Events opérateur / chef
# -------------------------------------------------
@app.post("/events", response_model=EventOut, status_code=201)
def create_event(
    payload: EventCreate = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("operator", "chef", "admin")),
):
    """Créer un événement de production (good/scrap/stop)."""
    if payload.event_type not in {"good", "scrap", "stop"}:
        raise HTTPException(status_code=400, detail="event_type must be one of: good|scrap|stop")
    if payload.qty < 0:
        raise HTTPException(status_code=400, detail="qty must be >= 0")

    m = db.query(Machine).get(payload.machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")

    if payload.work_order_id is not None:
        wo = db.query(WorkOrder).get(payload.work_order_id)
        if not wo:
            raise HTTPException(status_code=404, detail="Work order not found")

    ev = ProductionEvent(
        machine_id=payload.machine_id,
        work_order_id=payload.work_order_id,
        event_type=payload.event_type,
        qty=payload.qty if payload.event_type in {"good", "scrap"} else 0,
        notes=payload.notes,
        happened_at=payload.happened_at or datetime.utcnow(),
    )
    db.add(ev); db.commit(); db.refresh(ev)
    return ev

@app.get("/events/{event_id}", response_model=EventOut)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("operator", "chef", "admin")),
):
    """Détail d'un événement par id."""
    ev = db.query(ProductionEvent).get(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    return ev

@app.get("/events", response_model=List[EventOut])
def list_events(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    machine_id: int | None = None,
    event_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("operator", "chef", "admin")),
):
    """Liste paginée/filtrée des événements."""
    q = db.query(ProductionEvent)
    if machine_id is not None:
        q = q.filter(ProductionEvent.machine_id == machine_id)
    if event_type is not None:
        q = q.filter(ProductionEvent.event_type == event_type)
    if since is not None:
        q = q.filter(ProductionEvent.happened_at >= since)
    if until is not None:
        q = q.filter(ProductionEvent.happened_at <= until)
    return q.order_by(desc(ProductionEvent.happened_at)).offset(offset).limit(limit).all()


# -------------------------------------------------
# 🧭 Debug: routes
# -------------------------------------------------
@app.get("/routes")
def list_routes():
    """Liste toutes les routes exposées (utile en debug)."""
    out = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            out.append({"path": r.path, "methods": list(r.methods)})
    return out


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

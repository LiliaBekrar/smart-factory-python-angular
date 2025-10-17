# app/main.py
"""
🌍 Smart Factory API — FastAPI (version commentée)
--------------------------------------------------
Ce module :
- instancie l'app FastAPI et active CORS,
- applique les migrations Alembic au démarrage (pratique sur Render Free),
- peut lancer les seeds au démarrage si SEED_ON_START=true,
- backfill d'un mois + 24h récentes,
- démarre un simulateur qui ajoute 1–3 événements par minute,
- expose l'ensemble des routes (auth, machines, kpis, events, dashboard...).
"""

from typing import List
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Query, Depends, HTTPException, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse

from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc

# ⚙️ Settings & simulateur
from app.settings import settings
from app.simulate import backfill_month_and_day, simulation_minutely_loop

# 🔌 Accès DB (sync)
from app.db import SessionLocal
# 🧱 Modèles ORM
from app.models import Machine, WorkOrder, ProductionEvent, User
# 📨 Schémas Pydantic (entrées / sorties)
from app.schemas import (
    MachineOut, KPIOut, ActivityItemOut, UserOut, SignupIn, TokenOut,
    MachineCreate, MachineUpdate,
    DashboardSummaryOut, DashboardKPIOut, DashboardActivityItemOut,
    EventCreate, EventOut,
)
# 🔐 Sécurité (hash, vérif, JWT)
from app.security import hash_password, verify_password, create_access_token, decode_token


# -------------------------------------------------
# ⚙️ App & middlewares
# -------------------------------------------------
app = FastAPI(
    title="Smart Factory API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS large pour démo. En prod: passe l’URL exacte du front.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# -------------------------------------------------
# 🚀 Démarrage : migrations + seeds + simulateur
# -------------------------------------------------
@app.on_event("startup")
def on_startup():
    import subprocess
    import asyncio
    from pathlib import Path
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    # 0) Localise l'alembic.ini (racine = backend/)
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_ini = backend_dir / "alembic.ini"

    def log_alembic_heads() -> List[str]:
        """Retourne et log la liste des heads Alembic trouvés côté code."""
        cfg = Config(str(alembic_ini))
        script = ScriptDirectory.from_config(cfg)
        heads = list(script.get_heads())
        print(f"🔎 Alembic heads ({len(heads)}): {heads}")
        return heads

    heads = log_alembic_heads()

    # Si plusieurs heads → NE PAS tenter de migrer ni de seeder.
    if len(heads) > 1:
        print("❌ Plusieurs heads détectés. Corrige d'abord les migrations (merge).")
        print("   ➜ Ajoute une migration de merge avec down_revision = (head1, head2, ...)")
        return

    migrated_ok = False

    # 1) Migrations Alembic (en forçant le bon ini avec -c)
    try:
        cmd = ["alembic", "-c", str(alembic_ini), "upgrade", "head"]
        print(f"▶️  Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        print("✅ Alembic migrations applied.")
        migrated_ok = True
    except Exception as e:
        print(f"⚠️ Alembic migration failed: {e}")

    # 2) Seeds (optionnel)
    if migrated_ok and getattr(settings, "seed_on_start", False):
        try:
            print("🌱 Seeding initial data...")
            subprocess.run(["python", "-m", "app.seed"], check=True)
            print("✅ Seed completed.")
        except Exception as e:
            print(f"⚠️ Seed failed: {e}")

    # 3) Backfill historique (30j + 24h) — idempotent
    if migrated_ok:
        try:
            n30, n24 = backfill_month_and_day()
            print(f"🧪 Backfill → ajoutés: 30j={n30}, 24h={n24}")
        except Exception as e:
            print(f"⚠️ Backfill error: {e}")

    # 4) Simulation continue (toutes les X secondes)
    if migrated_ok and getattr(settings, "simulate_enabled", True):
        try:
            asyncio.create_task(
                simulation_minutely_loop(
                    min_per_tick=getattr(settings, "simulate_min_per_tick", 1),
                    max_per_tick=getattr(settings, "simulate_max_per_tick", 3),
                    interval_seconds=getattr(settings, "simulate_interval_seconds", 60),
                )
            )
            print("▶️ Simulation continue démarrée (boucle minute).")
        except Exception as e:
            print(f"⚠️ Simulation loop error: {e}")


# -------------------------------------------------
# 🗃️ DB session (dépendance FastAPI)
# -------------------------------------------------
def get_db():
    """Ouvre une session SQLAlchemy pour la requête puis la ferme."""
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
    """Décode le JWT, récupère l'utilisateur en BDD. 401 si invalide."""
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

def require_role(*roles: str):
    """Dépendance qui impose que l'utilisateur ait l'un des rôles donnés."""
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
    return {"status": "ok"}


# -------------------------------------------------
# 🏭 Machines (lecture)
# -------------------------------------------------
@app.get("/machines", response_model=List[MachineOut])
def list_machines(db: Session = Depends(get_db)):
    return db.query(Machine).all()

@app.get("/machines/{machine_id}", response_model=MachineOut)
def get_machine(machine_id: int, db: Session = Depends(get_db)):
    m = db.get(Machine, machine_id)
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
    """KPIs qualité/perf pour une machine sur `minutes` (défaut 60)."""
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
    """KPIs globaux toutes machines sur `minutes` (défaut 60)."""
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
    Si `minutes` est absent → renvoie simplement les `limit` derniers événements.
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
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(email=body.email, hashed_password=hash_password(body.password), role="operator")
    db.add(user); db.commit(); db.refresh(user)
    return user

@app.post("/auth/login", response_model=TokenOut)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Bad credentials")
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenOut(access_token=token)

@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
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
    m = db.get(Machine, machine_id)
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
    m = db.get(Machine, machine_id)
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
    """Résumé global (nb machines, états, TRS moyen, derniers événements)."""
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
    if payload.event_type not in {"good", "scrap", "stop"}:
        raise HTTPException(status_code=400, detail="event_type must be one of: good|scrap|stop")
    if payload.qty < 0:
        raise HTTPException(status_code=400, detail="qty must be >= 0")

    m = db.get(Machine, payload.machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")

    if payload.work_order_id is not None:
        wo = db.get(WorkOrder, payload.work_order_id)
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
    ev = db.get(ProductionEvent, event_id)
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

"""
Smart Factory API — FastAPI
===========================

Objectif
--------
API de suivi de production (machines, OF, événements) avec authentification JWT.
Ce fichier **main.py** instancie l'application FastAPI, déclare les middlewares,
les dépendances (DB, auth), puis expose les endpoints (santé, lecture, KPI,
flux d'activité, auth, CRUD machines).

Pour la reprise
---------------
- **Stack :** FastAPI, SQLAlchemy ORM, OAuth2 (Password flow) + JWT.
- **Entrée :** ce module (``uvicorn app.main:app --reload``).
- **DB session :** via ``get_db()`` (yield + close).
- **Auth :** ``OAuth2PasswordBearer``; extraction user via ``get_current_user``.
- **Rôles :** décorateur ``require_role("chef", "admin", ...)`` pour protéger
  des routes.
- **Modèles :** ORM (``app.models``) et schémas Pydantic (``app.schemas``).

Conventions
-----------
- **UTC partout** pour les timestamps (``datetime.utcnow()``). Si besoin de TZ,
  convertir côté client ou remplacer par des objets aware (``timezone.utc``).
- **Calculs SQL-first** (ex: KPI) pour limiter le trafic et profiter d'index DB.
- **Docstrings** sur chaque route : *quoi*, *comment*, *hypothèses*.
- **Erreurs** normalisées FastAPI (``HTTPException``) + codes clairs.

Démarrage rapide
----------------
1) Créer l'env : ``python -m venv .venv && source .venv/bin/activate``
2) Dépendances : ``pip install -r requirements.txt``
3) Variables : copier ``.env.example`` en ``.env`` (SECRET_KEY, DB_URL, ...)
4) Lancer : ``uvicorn app.main:app --reload`` puis ouvrir ``/docs``.

Notes pour l'industrialisation
------------------------------
- **SQLAlchemy 2.x :** ``Session.get(Model, id)`` est préféré à ``query.get()``.
  Ici on laisse ``query.get()`` pour compat mais voir les TODO plus bas.
- **Sécurité :** CORS est ouvert sur ``*`` pour faciliter le dev. Restreindre
  ``allow_origins`` en prod.
- **Logs / Observabilité :** envisager un middleware de logging (correlation-id)
  et une route ``/metrics`` (Prometheus) si nécessaire.
"""

from typing import List
from datetime import datetime, timedelta

from fastapi import FastAPI, Query, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc

from app.db import SessionLocal
from app.models import Machine, WorkOrder, ProductionEvent, User
from app.schemas import (
    MachineOut,
    WorkOrderOut,
    KPIOut,
    ActivityItemOut,
    UserOut,
    SignupIn,
    LoginIn,
    TokenOut,
    MachineCreate,
    MachineUpdate,
    DashboardSummaryOut,
    DashboardKPIOut,
    DashboardActivityItemOut,
)
from app.security import hash_password, verify_password, create_access_token, decode_token


# -------------------------
# App & middlewares
# -------------------------
app = FastAPI(
    title="Smart Factory API",
    docs_url="/docs",          # Swagger UI
    redoc_url="/redoc",        # ReDoc
    openapi_url="/openapi.json",
)

# ⚠️ En prod, limiter allow_origins aux domaines connus (ex: https://factory.example.com)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# -------------------------
# DB session dependency
# -------------------------

def get_db():
    """Fournit une session SQLAlchemy par requête.

    Usage :
        def route(db: Session = Depends(get_db)):
            ...

    Garantit la fermeture de la session (``finally: db.close()``).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------
# Dépendances d'auth & rôles
# -------------------------

# OAuth2 Password flow (voir /auth/login). Swagger place l'email dans "username".
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Résout l'utilisateur courant depuis le JWT Bearer.

    - Décode le token via ``decode_token`` (signature + expiration).
    - Récupère l'utilisateur en DB par ``sub`` (id).
    - Lève 401 si token invalide / utilisateur introuvable.
    """
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(*roles: str):
    """Fabrique une dépendance qui restreint l'accès aux rôles fournis.

    Exemple :
        user: User = Depends(require_role("chef", "admin"))
    """

    def _dep(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return _dep


# -------------------------
# Health
# -------------------------

@app.get("/health")
def health():
    """Vérifie la disponibilité de l'API (liveness)."""
    return {"status": "ok"}


# -------------------------
# Machines & WorkOrders (lecture)
# -------------------------

@app.get("/machines", response_model=List[MachineOut])
def list_machines(db: Session = Depends(get_db)):
    """Retourne la liste des machines (lecture simple, sans pagination)."""
    return db.query(Machine).all()


@app.get("/work_orders", response_model=List[WorkOrderOut])
def list_work_orders(db: Session = Depends(get_db)):
    """Retourne la liste des ordres de fabrication (OF)."""
    return db.query(WorkOrder).all()


# -------------------------
# KPIs (dernière heure)
# -------------------------

@app.get("/machines/{machine_id}/kpis", response_model=KPIOut)
def machine_kpis(machine_id: int, db: Session = Depends(get_db)):
    """KPIs sur la **dernière heure** pour une machine donnée.

    Définitions :
      - ``throughput_last_hour`` : somme des pièces 'good' (``qty``) sur 60 min.
      - ``trs`` : % qualité = ``good / (good + scrap) * 100``.

    Implémentation :
      - Calcul côté SQL via ``CASE WHEN`` + ``SUM`` pour efficacité.
      - Les événements considérés sont ceux avec ``happened_at >= now - 1h``.

    Remarques :
      - Si ``good + scrap == 0``, ``trs`` vaut 0.0 pour éviter division par 0.
      - Les timestamps sont en UTC (``datetime.utcnow()``).
    """
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)

    sums = (
        db.query(
            func.sum(
                case((ProductionEvent.event_type == "good", ProductionEvent.qty), else_=0)
            ).label("good_sum"),
            func.sum(
                case((ProductionEvent.event_type == "scrap", ProductionEvent.qty), else_=0)
            ).label("scrap_sum"),
        )
        .filter(
            ProductionEvent.machine_id == machine_id,
            ProductionEvent.happened_at >= one_hour_ago,
        )
        .one()
    )

    good = sums.good_sum or 0
    scrap = sums.scrap_sum or 0
    trs = (good / (good + scrap) * 100) if (good + scrap) > 0 else 0.0

    return KPIOut(throughput_last_hour=int(good), trs=round(trs, 1))


# -------------------------
# Activity feed
# -------------------------

@app.get("/activities/recent", response_model=List[ActivityItemOut])
def recent_activities(
    limit: int = Query(50, ge=1, le=500),
    minutes: int = Query(120, ge=1, le=24 * 60),
    db: Session = Depends(get_db),
):
    """Flux d'activité **toutes machines** sur *N* dernières minutes.

    - ``limit`` borne le nombre d'items renvoyés (défaut 50, max 500).
    - Joint ``Machine`` (pour ``code``) et ``WorkOrder`` (optionnel) pour enrichir.
    - Tri décroissant sur ``happened_at``.
    """
    since = datetime.utcnow() - timedelta(minutes=minutes)

    q = (
        db.query(ProductionEvent, Machine.code, Machine.name, WorkOrder.number)
        .join(Machine, Machine.id == ProductionEvent.machine_id)
        .outerjoin(WorkOrder, WorkOrder.id == ProductionEvent.work_order_id)
        .filter(ProductionEvent.happened_at >= since)
        .order_by(desc(ProductionEvent.happened_at))
        .limit(limit)
    )

    items: List[ActivityItemOut] = []
    for ev, machine_code, machine_name, wo_number in q.all():
        items.append(
            ActivityItemOut(
                id=ev.id,
                machine_id=ev.machine_id,
                machine_code=machine_code,
                machine_name=machine_name,
                work_order_id=ev.work_order_id,
                work_order_number=wo_number,
                event_type=ev.event_type,
                qty=ev.qty,
                notes=ev.notes,
                happened_at=ev.happened_at,
            )
        )
    return items


@app.get("/machines/{machine_id}/activity", response_model=List[ActivityItemOut])
def machine_activity(
    machine_id: int,
    limit: int = Query(50, ge=1, le=500),
    minutes: int = Query(120, ge=1, le=24 * 60),
    db: Session = Depends(get_db),
):
    """Historique d'une **machine** sur *N* dernières minutes (trié récent→ancien)."""
    since = datetime.utcnow() - timedelta(minutes=minutes)

    q = (
        db.query(ProductionEvent, WorkOrder.number)
        .outerjoin(WorkOrder, WorkOrder.id == ProductionEvent.work_order_id)
        .filter(
            ProductionEvent.machine_id == machine_id,
            ProductionEvent.happened_at >= since,
        )
        .order_by(desc(ProductionEvent.happened_at))
        .limit(limit)
    )

    # TODO(SQLAlchemy 2.x) : préférer ``db.get(Machine, machine_id)`` si disponible.
    m = db.query(Machine).get(machine_id)
    machine_code = m.code if m else None

    items: List[ActivityItemOut] = []
    for ev, wo_number in q.all():
        items.append(
            ActivityItemOut(
                id=ev.id,
                machine_id=ev.machine_id,
                machine_code=machine_code,
                work_order_id=ev.work_order_id,
                work_order_number=wo_number,
                event_type=ev.event_type,
                qty=ev.qty,
                notes=ev.notes,
                happened_at=ev.happened_at,
            )
        )
    return items


# -------------------------
# Auth: signup / login / me
# -------------------------

@app.post("/auth/signup", response_model=UserOut)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    """Inscription simple (email + mot de passe).

    - Refuse si l'email existe déjà (HTTP 400).
    - Rôle par défaut : ``chef`` (adapter selon besoins).
    - Stocke le mot de passe **haché** (``hash_password``).
    """
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(email=body.email, hashed_password=hash_password(body.password), role="chef")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=TokenOut)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Login OAuth2 Password flow.

    Swagger place l'**email** dans ``username`` (comportement attendu d'OAuth2PasswordRequestForm).
    Si les identifiants sont valides, renvoie un JWT ``access_token`` portant
    ``sub`` (id user) et ``role``.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Bad credentials")
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenOut(access_token=token)


@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """Retourne le profil de l'utilisateur authentifié."""
    return user


# -------------------------
# Machines: CRUD (protégé pour chef/admin)
# -------------------------

@app.post("/machines", response_model=MachineOut)
def create_machine(
    body: MachineCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("chef", "admin")),
):
    """Crée une machine (rôles requis : ``chef`` ou ``admin``).

    - Unicité du ``code`` machine garantie (HTTP 400 sinon).
    - Retourne l'entité créée.
    """
    if db.query(Machine).filter(Machine.code == body.code).first():
        raise HTTPException(status_code=400, detail="Machine code already exists")
    m = Machine(**body.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@app.patch("/machines/{machine_id}", response_model=MachineOut)
def update_machine(
    machine_id: int,
    body: MachineUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("chef", "admin")),
):
    """Met à jour les champs d'une machine (patch partiel).

    - Vérifie l'existence (404) puis l'unicité de ``code`` si modifié (400).
    - Applique uniquement les champs fournis (``exclude_unset=True``).
    """
    # TODO(SQLAlchemy 2.x) : ``m = db.get(Machine, machine_id)`` si API 2.0.
    m = db.query(Machine).get(machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")

    data = body.model_dump(exclude_unset=True)
    if "code" in data:
        exists = db.query(Machine).filter(Machine.code == data["code"], Machine.id != machine_id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Machine code already exists")

    for k, v in data.items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return m


@app.delete("/machines/{machine_id}")
def delete_machine(
    machine_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("chef", "admin")),
):
    """Supprime une machine (retour ``{"ok": true}``)."""
    # TODO(SQLAlchemy 2.x) : ``m = db.get(Machine, machine_id)`` si possible.
    m = db.query(Machine).get(machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")
    db.delete(m)
    db.commit()
    return {"ok": True}

@app.get("/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(
    limit_recent: int = Query(5, ge=1, le=50),
    minutes: int = Query(60, ge=5, le=24*60),
    db: Session = Depends(get_db),
):
    """
    Résumé global pour le Dashboard :
      - total machines / running / stopped
      - TRS moyen (dernière heure)
      - N dernières activités
    """
    since = datetime.utcnow() - timedelta(minutes=minutes)

    # 1) Compteurs machines
    total = db.query(func.count(Machine.id)).scalar() or 0
    running = db.query(func.count(Machine.id)).filter(Machine.status == "running").scalar() or 0
    stopped = db.query(func.count(Machine.id)).filter(Machine.status == "stopped").scalar() or 0

    # 2) TRS moyen dernière heure (good / (good+scrap) * 100)
    sums = (
        db.query(
            func.sum(
                case((ProductionEvent.event_type == "good", ProductionEvent.qty), else_=0)
            ).label("good_sum"),
            func.sum(
                case((ProductionEvent.event_type == "scrap", ProductionEvent.qty), else_=0)
            ).label("scrap_sum"),
        )
        .filter(ProductionEvent.happened_at >= since)
        .one()
    )
    good = sums.good_sum or 0
    scrap = sums.scrap_sum or 0
    trs_avg_last_hour = float(round((good / (good + scrap) * 100), 1)) if (good + scrap) > 0 else 0.0

    # 3) Activités récentes
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
            id=ev.id,
            machine_code=machine_code,
            machine_name=machine_name,
            event_type=ev.event_type,
            qty=ev.qty,
            happened_at=ev.happened_at,
            work_order_number=wo_number,
        )
        for (ev, machine_code, machine_name, wo_number) in q.all()
    ]

    return DashboardSummaryOut(
        kpis=DashboardKPIOut(
            total_machines=total,
            running=running,
            stopped=stopped,
            trs_avg_last_hour=trs_avg_last_hour,
        ),
        recent=recent,
    )

# -------------------------
# Debug: liste des routes
# -------------------------

@app.get("/routes")
def list_routes():
    """Expose les chemins/verbres HTTP enregistrés (debug/outillage)."""
    out = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            out.append({"path": r.path, "methods": list(r.methods)})
    return out

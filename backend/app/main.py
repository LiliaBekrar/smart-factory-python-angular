"""
Smart Factory API — FastAPI
===========================

Objectif
--------
API de suivi de production (machines, OF, événements) avec authentification JWT.
Ce fichier instancie l'app FastAPI, déclare middlewares/dépendances et expose
les routes (santé, lecture, KPI, flux d'activité, auth, CRUD machines, dashboard).

Pour la reprise
---------------
- Stack : FastAPI, SQLAlchemy ORM, OAuth2 (Password flow) + JWT.
- Entrée : `uvicorn app.main:app --reload`.
- DB session : via `get_db()` (yield + close).
- Auth : `OAuth2PasswordBearer`; utilisateur courant via `get_current_user`.
- Rôles : décorateur `require_role("chef", "admin", ...)`.
- Modèles : ORM (`app.models`) + schémas Pydantic (`app.schemas`).

Conventions
-----------
- UTC partout pour les timestamps (`datetime.utcnow()`).
- Calculs SQL-first (ex: KPI) pour limiter trafic réseau et exploiter les index.
- Docstrings sur chaque route (quoi/comment/hypothèses).
- Erreurs normalisées FastAPI (`HTTPException`) + codes clairs.

Démarrage rapide
----------------
1) `python -m venv .venv && source .venv/bin/activate`
2) `pip install -r requirements.txt`
3) Copier `.env.example` en `.env` (SECRET_KEY, DB_URL, ...)
4) `uvicorn app.main:app --reload` puis ouvrir `/docs`.

Notes d'industrialisation
-------------------------
- SQLAlchemy 2.x : `Session.get(Model, id)` préféré à `query.get()`.
- Sécurité : CORS ouvert sur `*` en dev → restreindre en prod.
- Observabilité : ajouter middleware de logging / route `/metrics` si besoin.
"""

# --- Imports standards ---
from typing import List                 # types génériques (List[...] pour les réponses)
from datetime import datetime, timedelta # horodatage UTC + fenêtres de temps

# --- Imports FastAPI ---
from fastapi import FastAPI, Query, Depends, HTTPException, status, Body   # app, paramètres, DI, erreurs
from fastapi.middleware.cors import CORSMiddleware                   # CORS pour front séparé (dev)
from fastapi.routing import APIRoute                                 # introspection des routes
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm  # OAuth2 (password flow)

# --- Imports SQLAlchemy ---
from sqlalchemy.orm import Session                 # type de session
from sqlalchemy import func, case, desc            # agrégations & helpers SQL

# --- Accès DB / modèles / schémas / sécurité (modules maison) ---
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
    EventCreate,
    EventOut
)
from app.security import hash_password, verify_password, create_access_token, decode_token

# --- Utilitaire pour lancer Alembic au démarrage (utile sur Render gratuit) ---
import subprocess


# -------------------------
# App & middlewares
# -------------------------
# Instancie l'application FastAPI (point d'entrée uvicorn: app.main:app)
app = FastAPI(
    title="Smart Factory API",   # titre affiché dans Swagger
    docs_url="/docs",           # UI Swagger (documentation interactive)
    redoc_url="/redoc",         # UI ReDoc (documentation alternative)
    openapi_url="/openapi.json" # schéma OpenAPI brut (JSON)
)

# Applique automatiquement les migrations Alembic au démarrage de l'app.
# Utile sur certains PaaS gratuits (ex: Render) où il n'y a pas de phase de build dédiée.
@app.on_event("startup")
def run_migrations():
    """Tente d'exécuter `alembic upgrade head` au boot de l'API.
    - Essai 1: via la CLI `alembic` (si accessible dans le PATH)
    - Essai 2: via `python -m alembic` (fallback)
    - En cas d'échec: log de l'erreur mais on ne bloque pas le démarrage.
    """
    try:
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        print("✅ Alembic migrations applied (alembic upgrade head).")
    except Exception as e1:
        try:
            subprocess.run(["python", "-m", "alembic", "upgrade", "head"], check=True)
            print("✅ Alembic migrations applied via python -m.")
        except Exception as e2:
            print(f"⚠️ Alembic migration failed: {e1} / fallback: {e2}")

# Middleware CORS: autorise les requêtes depuis d'autres origines (ex: frontend local)
# ⚠️ En production, remplacer ["*"] par la/les URL(s) front autorisées
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # autorise toutes les origines en dev
    allow_methods=["*"],   # autorise toutes les méthodes HTTP
    allow_headers=["*"],   # autorise tous les headers (dont Authorization)
    allow_credentials=True  # permet d'envoyer cookies/credentials
)


# -------------------------
# Dépendance DB (une session par requête)
# -------------------------

def get_db():
    """Crée une session SQLAlchemy et garantit sa fermeture.

    Utilisation typique dans une route:
        def route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()  # ouvre une nouvelle session DB
    try:
        yield db         # injecte la session dans la route appelante
    finally:
        db.close()       # ferme proprement quoi qu'il arrive (évite fuite de connexions)


# -------------------------
# Authentification & Rôles
# -------------------------
# Schéma OAuth2 (password flow) pour récupérer le token Bearer depuis le header Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Résout l'utilisateur courant à partir du JWT Bearer.

    Étapes:
    - Décoder le token (signature/expiration) via `decode_token`.
    - Lire `sub` (id utilisateur) dans le payload.
    - Charger l'utilisateur correspondant en base.
    - Lever 401 si token invalide ou utilisateur introuvable.
    """
    payload = decode_token(token)  # décode le JWT (retourne un dict ou None)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()  # récupère l'utilisateur par id
    if not user:  # si aucun utilisateur ne correspond
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user  # renvoie l'entité User (sera sérialisée via Pydantic si utilisée comme response_model)


def require_role(*roles: str):
    """Fabrique une dépendance qui restreint l'accès aux rôles fournis.

    Exemple d'usage dans une route protégée:
        user: User = Depends(require_role("chef", "admin"))
    """
    def _dep(user: User = Depends(get_current_user)):
        # Vérifie que le rôle de l'utilisateur courant fait partie des rôles autorisés
        if user.role not in roles:
            # 403 = utilisateur authentifié mais non autorisé (droits insuffisants)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user  # renvoie l'utilisateur pour que la route puisse l'exploiter si besoin

    return _dep  # renvoie la fonction de dépendance à FastAPI


# -------------------------
# Healthcheck (liveness)
# -------------------------
@app.get("/health")
def health():
    """Renvoie un petit JSON pour indiquer que l'API est vivante."""
    return {"status": "ok"}


# -------------------------
# Lecture Machines & WorkOrders
# -------------------------
@app.get("/machines", response_model=List[MachineOut])
def list_machines(db: Session = Depends(get_db)):
    """Retourne la liste des machines (sans pagination pour simplifier)."""
    return db.query(Machine).all()  # SELECT * FROM machines


@app.get("/work_orders", response_model=List[WorkOrderOut])
def list_work_orders(db: Session = Depends(get_db)):
    """Retourne la liste des ordres de fabrication (OF)."""
    return db.query(WorkOrder).all()  # SELECT * FROM work_orders


# -------------------------
# KPIs (dernière heure)
# -------------------------
@app.get("/machines/{machine_id}/kpis", response_model=KPIOut)
def machine_kpis(machine_id: int, db: Session = Depends(get_db)):
    """Calcule les KPIs d'une machine sur la **dernière heure**.

    Définitions:
    - `throughput_last_hour` = somme des pièces "good" (qty) sur 60 minutes.
    - `trs` = % qualité = good / (good + scrap) * 100.

    Implémentation:
    - Calcul côté SQL via `SUM(CASE WHEN ...)` pour meilleures perfs.
    - Fenêtre = événements avec `happened_at >= now - 1h` (UTC).
    """
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)  # borne basse de la fenêtre de calcul

    # Construction de la requête d'agrégation
    sums = (
        db.query(
            # Somme des qty quand event_type == 'good'
            func.sum(case((ProductionEvent.event_type == "good", ProductionEvent.qty), else_=0)).label("good_sum"),
            # Somme des qty quand event_type == 'scrap'
            func.sum(case((ProductionEvent.event_type == "scrap", ProductionEvent.qty), else_=0)).label("scrap_sum"),
        )
        .filter(
            ProductionEvent.machine_id == machine_id,           # on cible la machine demandée
            ProductionEvent.happened_at >= one_hour_ago,        # on limite à la dernière heure
        )
        .one()  # on attend une seule ligne de résultat
    )

    good = sums.good_sum or 0   # si None → 0
    scrap = sums.scrap_sum or 0 # si None → 0
    trs = (good / (good + scrap) * 100) if (good + scrap) > 0 else 0.0  # évite division par zéro

    # On renvoie un objet Pydantic KPIOut (sera auto‑sérialisé en JSON)
    return KPIOut(throughput_last_hour=int(good), trs=round(trs, 1))


# -------------------------
# Activity feed (toutes machines)
# -------------------------
@app.get("/activities/recent", response_model=List[ActivityItemOut])
def recent_activities(
    limit: int = Query(50, ge=1, le=500),        # nombre max d'items à renvoyer (borne 1..500)
    minutes: int = Query(120, ge=1, le=24*60),   # fenêtre temporelle (en minutes)
    db: Session = Depends(get_db),
):
    """Retourne les derniers événements (toutes machines) sur N minutes.

    - Joint `Machine` pour récupérer `code` (affichage plus parlant côté front).
    - `WorkOrder` est une jointure externe (outerjoin) car un event peut ne pas avoir d'OF.
    - Tri décroissant sur `happened_at`.
    """
    since = datetime.utcnow() - timedelta(minutes=minutes)  # borne basse de la fenêtre

    # Requête avec jointures pour enrichir chaque event
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
    return items  # FastAPI sérialise la liste d'objets Pydantic en JSON


# -------------------------
# Activity feed (une machine)
# -------------------------
@app.get("/machines/{machine_id}/activity", response_model=List[ActivityItemOut])
def machine_activity(
    machine_id: int,
    limit: int = Query(50, ge=1, le=500),
    minutes: int = Query(120, ge=1, le=24 * 60),
    db: Session = Depends(get_db),
):
    """Retourne l'historique d'une machine sur N minutes (du plus récent au plus ancien)."""
    since = datetime.utcnow() - timedelta(minutes=minutes)

    # Requête: pour chaque event de la machine, on récupère éventuellement le n° d'OF
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

    # Récupère le code machine pour enrichir la sortie (non strictement nécessaire, mais pratique)
    # NOTE (SQLAlchemy 2.x): `db.get(Machine, machine_id)` est l'API moderne.
    m = db.query(Machine).get(machine_id)
    machine_code = m.code if m else None

    items: List[ActivityItemOut] = []
    for ev, wo_number in q.all():
        items.append(
            ActivityItemOut(
                id=ev.id,
                machine_id=ev.machine_id,
                machine_code=machine_code,       # on réutilise le code si trouvé
                work_order_id=ev.work_order_id,
                work_order_number=wo_number,     # peut être None
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
    """
    Endpoint d'inscription (création d'un utilisateur).
    - Reçoit un email et un mot de passe (dans le body JSON).
    - Vérifie que l'email n'est pas déjà utilisé.
    - Crée un utilisateur avec rôle par défaut = "operator".
    - Stocke le mot de passe de manière sécurisée (haché).
    - Retourne l'utilisateur créé (sans le mot de passe).
    """

    # Vérifier si l'email existe déjà en base (unicité métier)
    if db.query(User).filter(User.email == body.email).first():
        # Si oui → renvoyer une erreur 400 (Bad Request)
        raise HTTPException(status_code=400, detail="Email already exists")

    # Créer un nouvel utilisateur (NE JAMAIS stocker le mdp en clair)
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),  # on hache le mot de passe, jamais en clair
        role="operator"  # rôle par défaut : opérateur (pas chef/admin)
    )

    # Sauvegarder en base
    db.add(user)      # ajoute l'objet à la session
    db.commit()       # pousse l'INSERT en DB
    db.refresh(user)  # recharge depuis la DB (récupère id, timestamps, etc.)

    return user  # FastAPI utilisera UserOut pour masquer champs sensibles


@app.post("/auth/login", response_model=TokenOut)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Endpoint de login (OAuth2 password flow).
    - Swagger met l'email dans `username` (convention OAuth2PasswordRequestForm).
    - Vérifie les identifiants (email + mot de passe).
    - Si OK → génère un JWT portant `sub` (id utilisateur) et `role`.
    - Retourne `access_token` (type `bearer`).
    """

    # 1) Récupérer l'utilisateur par email (username côté formulaire OAuth2)
    user = db.query(User).filter(User.email == form_data.username).first()

    # 2) Vérifier l'existence et le mot de passe (haché)
    if not user or not verify_password(form_data.password, user.hashed_password):
        # 401: non authentifié (identifiants incorrects)
        raise HTTPException(status_code=401, detail="Bad credentials")

    # 3) Créer un token JWT (payload minimal: sub=id, role=rôle)
    token = create_access_token({"sub": str(user.id), "role": user.role})

    # 4) Retourner le token (Pydantic TokenOut sérialise en JSON)
    return TokenOut(access_token=token)


@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """Retourne le profil de l'utilisateur authentifié (décodé depuis le JWT)."""
    return user


# -------------------------
# Machines: CRUD (protégé pour chef/admin)
# -------------------------
@app.post("/machines", response_model=MachineOut)
def create_machine(
    body: MachineCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("chef", "admin")),  # accès restreint par rôles
):
    """Crée une machine.

    - Vérifie l'unicité du `code` (400 si déjà pris).
    - Sauvegarde et retourne l'entité créée.
    """

    # Unicité du code machine
    if db.query(Machine).filter(Machine.code == body.code).first():
        raise HTTPException(status_code=400, detail="Machine code already exists")

    # Création à partir du schéma Pydantic (décompacte en kwargs)
    m = Machine(**body.model_dump())

    # Persistance
    db.add(m)
    db.commit()
    db.refresh(m)

    return m  # sera sérialisé via MachineOut

@app.get("/machines/{machine_id}", response_model=MachineOut)
def get_machine(machine_id: int, db: Session = Depends(get_db)):
    m = db.query(Machine).get(machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")
    return m



@app.patch("/machines/{machine_id}", response_model=MachineOut)
def update_machine(
    machine_id: int,
    body: MachineUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("chef", "admin")),  # accès restreint
):
    """Met à jour une machine (PATCH partiel).

    - 404 si la machine n'existe pas.
    - Vérifie l'unicité du `code` si modifié.
    - Applique uniquement les champs fournis (`exclude_unset=True`).
    """

    # Récupération de la machine (NOTE: en SQLAlchemy 2.x, préférer db.get(Model, id))
    m = db.query(Machine).get(machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")

    # On ne met à jour que les champs présents dans la requête
    data = body.model_dump(exclude_unset=True)

    # Si `code` est dans les updates, vérifier qu'il n'est pas utilisé par une autre machine
    if "code" in data:
        exists = db.query(Machine).filter(Machine.code == data["code"], Machine.id != machine_id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Machine code already exists")

    # Appliquer les modifications sur l'objet ORM
    for k, v in data.items():
        setattr(m, k, v)

    # Sauvegarder
    db.commit()
    db.refresh(m)

    return m


@app.delete("/machines/{machine_id}")
def delete_machine(
    machine_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("chef", "admin")),  # accès restreint
):
    """Supprime une machine. Retourne `{ "ok": True }` si succès."""

    # Cherche la machine à supprimer
    m = db.query(Machine).get(machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")

    # Supprime puis commit
    db.delete(m)
    db.commit()

    return {"ok": True}


# -------------------------
# Dashboard (agrégats + flux récent)
# -------------------------
@app.get("/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(
    limit_recent: int = Query(5, ge=1, le=50),   # nombre d'événements récents à renvoyer
    minutes: int = Query(60, ge=5, le=24*60),    # fenêtre pour TRS/activités
    db: Session = Depends(get_db),
):
    """Résumé global pour un dashboard simple.

    Contient:
    - total machines / running / stopped
    - TRS moyen dernière heure (approx: good/(good+scrap)*100)
    - N dernières activités (enrichies)
    """

    since = datetime.utcnow() - timedelta(minutes=minutes)  # borne basse

    # 1) Compteurs machines (simples agrégations)
    total = db.query(func.count(Machine.id)).scalar() or 0
    running = db.query(func.count(Machine.id)).filter(Machine.status == "running").scalar() or 0
    stopped = db.query(func.count(Machine.id)).filter(Machine.status == "stopped").scalar() or 0

    # 2) TRS moyen (global sur la fenêtre)
    sums = (
        db.query(
            func.sum(case((ProductionEvent.event_type == "good", ProductionEvent.qty), else_=0)).label("good_sum"),
            func.sum(case((ProductionEvent.event_type == "scrap", ProductionEvent.qty), else_=0)).label("scrap_sum"),
        )
        .filter(ProductionEvent.happened_at >= since)
        .one()
    )
    good = sums.good_sum or 0
    scrap = sums.scrap_sum or 0
    trs_avg_last_hour = float(round((good / (good + scrap) * 100), 1)) if (good + scrap) > 0 else 0.0

    # 3) Activités récentes (jointures pour enrichir chaque event)
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

    # Assemblage de la réponse de synthèse
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
# Operator: saisir / consulter un événement de production
# -------------------------

@app.post("/events", response_model=EventOut, status_code=201)
def create_event(
    # Body JSON validé par Pydantic (voir EventCreate dans app/schemas.py)
    payload: EventCreate = Body(...),

    # Session DB injectée par dépendance (ouverte/fermée proprement par get_db)
    db: Session = Depends(get_db),

    # Authz: restreint l'accès aux rôles "operator", "chef" ou "admin"
    user: User = Depends(require_role("operator", "chef", "admin")),
):
    """
    Crée un événement de production saisi par un opérateur.

    Règles métier (simples) :
      - event_type ∈ {"good","scrap","stop"}
      - qty >= 0 ; pour "stop", qty sera forcée à 0
      - machine_id doit exister ; work_order_id est optionnel mais doit exister si fourni
      - happened_at : par défaut = maintenant en UTC
      - notes : facultatif (commentaire libre)
    """

    # --- 1) Validation métier légère sur le type d'événement
    if payload.event_type not in {"good", "scrap", "stop"}:
        # 400 = mauvaise requête (données invalides)
        raise HTTPException(status_code=400, detail="event_type must be one of: good|scrap|stop")

    # --- 2) Validation quantité (pas de quantité négative)
    if payload.qty < 0:
        raise HTTPException(status_code=400, detail="qty must be >= 0")

    # --- 3) La machine doit exister (clé étrangère)
    m = db.query(Machine).get(payload.machine_id)
    if not m:
        # 404 = ressource non trouvée (machine inconnue)
        raise HTTPException(status_code=404, detail="Machine not found")

    # --- 4) L’OF est optionnel, mais s’il est passé il doit exister
    if payload.work_order_id is not None:
        wo = db.query(WorkOrder).get(payload.work_order_id)
        if not wo:
            raise HTTPException(status_code=404, detail="Work order not found")

    # --- 5) Timestamp : si non fourni, on prend l'instant présent (UTC)
    happened_at = payload.happened_at or datetime.utcnow()

    # --- 6) Normalisation de qty : pour un "stop", on force qty=0
    normalized_qty = payload.qty if payload.event_type in {"good", "scrap"} else 0

    # --- 7) Construction de l'objet ORM à persister
    ev = ProductionEvent(
        machine_id=payload.machine_id,
        work_order_id=payload.work_order_id,
        event_type=payload.event_type,
        qty=normalized_qty,
        notes=payload.notes,
        happened_at=happened_at,
    )

    # --- 8) Persistance : add → commit → refresh pour récupérer l'ID
    db.add(ev)
    db.commit()
    db.refresh(ev)

    # --- 9) Retourne l'objet créé ; FastAPI utilise EventOut pour la sérialisation
    return ev


@app.get("/events/{event_id}", response_model=EventOut)
def get_event(
    # event_id provient du chemin (path parameter)
    event_id: int,

    # Session DB
    db: Session = Depends(get_db),

    # Accès protégé : un opérateur (ou chef/admin) peut consulter le détail
    user: User = Depends(require_role("operator", "chef", "admin")),
):
    """
    Retourne le détail d'un événement de production existant (par son id).
    """
    # --- 1) Recherche en base par clé primaire
    ev = db.query(ProductionEvent).get(event_id)

    # --- 2) Si non trouvé → 404
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")

    # --- 3) Retour (sérialisé via EventOut)
    return ev
@app.get("/events", response_model=List[EventOut])
def list_events(
    # Limite le nombre de résultats (par défaut 50, max 500)
    limit: int = Query(50, ge=1, le=500),

    # Offset pour pagination (par défaut 0 → première page)
    offset: int = Query(0, ge=0),

    # Filtrer par machine (optionnel)
    machine_id: int | None = None,

    # Filtrer par type d’événement ("good", "scrap", "stop")
    event_type: str | None = None,

    # Filtrer depuis une certaine date/heure
    since: datetime | None = None,

    # Filtrer jusqu’à une certaine date/heure
    until: datetime | None = None,

    # Session DB
    db: Session = Depends(get_db),

    # Authz: accessible aux opérateurs, chefs et admin
    user: User = Depends(require_role("operator", "chef", "admin")),
):
    """
    Liste les événements de production avec filtres et pagination.

    - `limit` : max de résultats par page
    - `offset` : décalage pour parcourir les pages
    - `machine_id` : filtre par machine spécifique
    - `event_type` : filtre par type (good|scrap|stop)
    - `since` / `until` : borne temporelle
    """

    # --- 1) Construire la requête SQLAlchemy de base
    q = db.query(ProductionEvent)

    # --- 2) Appliquer les filtres si fournis
    if machine_id is not None:
        q = q.filter(ProductionEvent.machine_id == machine_id)

    if event_type is not None:
        q = q.filter(ProductionEvent.event_type == event_type)

    if since is not None:
        q = q.filter(ProductionEvent.happened_at >= since)

    if until is not None:
        q = q.filter(ProductionEvent.happened_at <= until)

    # --- 3) Tri décroissant sur la date (plus récent en premier)
    q = q.order_by(desc(ProductionEvent.happened_at))

    # --- 4) Appliquer pagination : offset + limit
    events = q.offset(offset).limit(limit).all()

    # --- 5) Retourner la liste (FastAPI va sérialiser avec EventOut)
    return events


# -------------------------
# Debug: inspection des routes
# -------------------------
@app.get("/routes")
def list_routes():
    """Expose la liste des routes et leurs méthodes (outil de debug pratique)."""
    out = []  # liste de dicts { path, methods }
    for r in app.routes:  # itère sur toutes les routes enregistrées dans l'app
        if isinstance(r, APIRoute):  # on ne garde que les routes HTTP (ignore websockets, etc.)
            out.append({"path": r.path, "methods": list(r.methods)})  # ex: {"/machines", ["GET"]}
    return out  # JSON simple utilisable pour du tooling (inspections rapides)

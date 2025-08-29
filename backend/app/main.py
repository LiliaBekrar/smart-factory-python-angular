# backend/app/main.py
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
from app.schemas import MachineOut, WorkOrderOut, KPIOut, ActivityItemOut,UserOut, SignupIn, LoginIn, TokenOut, MachineCreate, MachineUpdate
from app.security import hash_password, verify_password, create_access_token, decode_token


# -------------------------
# App & middlewares
# -------------------------
app = FastAPI(
    title="Smart Factory API",
    docs_url="/docs",          # Swagger UI
    redoc_url="/redoc",        # ReDoc
    openapi_url="/openapi.json"
)

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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------
# Dépendances d'auth & rôles
# -------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

def require_role(*roles: str):
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
    return {"status": "ok"}


# -------------------------
# Machines & WorkOrders
# -------------------------
@app.get("/machines", response_model=List[MachineOut])
def list_machines(db: Session = Depends(get_db)):
    return db.query(Machine).all()

@app.get("/work_orders", response_model=List[WorkOrderOut])
def list_work_orders(db: Session = Depends(get_db)):
    return db.query(WorkOrder).all()


# -------------------------
# KPIs (dernière heure)
# -------------------------
@app.get("/machines/{machine_id}/kpis", response_model=KPIOut)
def machine_kpis(machine_id: int, db: Session = Depends(get_db)):
    """
    KPIs sur la dernière heure :
      - throughput_last_hour : pièces 'good' produites (somme qty)
      - trs : % qualité = good / (good + scrap) * 100
    Calculé côté SQL pour l’efficacité.
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
    """Flux d'activité récent (toutes machines) sur N dernières minutes (trié du plus récent)."""
    since = datetime.utcnow() - timedelta(minutes=minutes)

    q = (
        db.query(ProductionEvent, Machine.code, WorkOrder.number)
        .join(Machine, Machine.id == ProductionEvent.machine_id)
        .outerjoin(WorkOrder, WorkOrder.id == ProductionEvent.work_order_id)
        .filter(ProductionEvent.happened_at >= since)
        .order_by(desc(ProductionEvent.happened_at))
        .limit(limit)
    )

    items: List[ActivityItemOut] = []
    for ev, machine_code, wo_number in q.all():
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


@app.get("/machines/{machine_id}/activity", response_model=List[ActivityItemOut])
def machine_activity(
    machine_id: int,
    limit: int = Query(50, ge=1, le=500),
    minutes: int = Query(120, ge=1, le=24 * 60),
    db: Session = Depends(get_db),
):
    """Historique d'une machine sur N dernières minutes (trié du plus récent)."""
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
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(email=body.email, hashed_password=hash_password(body.password), role="chef")
    db.add(user); db.commit(); db.refresh(user)
    return user

@app.post("/auth/login", response_model=TokenOut)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # Swagger met l'email dans "username" (c'est normal pour OAuth2)
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Bad credentials")
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenOut(access_token=token)


@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
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
    if db.query(Machine).filter(Machine.code == body.code).first():
        raise HTTPException(status_code=400, detail="Machine code already exists")
    m = Machine(**body.model_dump())
    db.add(m); db.commit(); db.refresh(m)
    return m

@app.patch("/machines/{machine_id}", response_model=MachineOut)
def update_machine(
    machine_id: int,
    body: MachineUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("chef", "admin")),
):
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
    db.commit(); db.refresh(m)
    return m

@app.delete("/machines/{machine_id}")
def delete_machine(
    machine_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("chef", "admin")),
):
    m = db.query(Machine).get(machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")
    db.delete(m); db.commit()
    return {"ok": True}


# -------------------------
# Debug: liste des routes
# -------------------------
@app.get("/routes")
def list_routes():
    out = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            out.append({"path": r.path, "methods": list(r.methods)})
    return out

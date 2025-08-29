# backend/app/main.py
from typing import List
from datetime import datetime, timedelta

from fastapi import FastAPI, Query, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc

from app.db import SessionLocal
from app.models import Machine, WorkOrder, ProductionEvent
from app.schemas import MachineOut, WorkOrderOut, KPIOut, ActivityItemOut


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
# Debug: liste des routes (à retirer plus tard si tu veux)
# -------------------------
@app.get("/routes")
def list_routes():
    out = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            out.append({"path": r.path, "methods": list(r.methods)})
    return out

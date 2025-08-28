from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Machine, WorkOrder, ProductionEvent

app = FastAPI(title="Smart Factory API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True
)

@app.get("/health")
def health():
    return {"status": "ok"}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/machines")
def list_machines(db: Session = Depends(get_db)):
    return db.query(Machine).all()

@app.get("/work_orders")
def list_work_orders(db: Session = Depends(get_db)):
    return db.query(WorkOrder).all()

from datetime import datetime, timedelta
from sqlalchemy import func

@app.get("/machines/{machine_id}/kpis")
def machine_kpis(machine_id: int, db: Session = Depends(get_db)):
    """
    KPIs sur la dernière heure :
      - throughput_last_hour : pièces 'good' produites sur 60 min (débit 1h)
      - trs : % qualité = good / (good + scrap) * 100
    Calculé côté SQL (SUM) pour l'efficacité.
    """
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)

    # SUM(good) et SUM(scrap) sur la dernière heure, pour cette machine
    sums = (
        db.query(
            func.sum(func.case((ProductionEvent.event_type == "good", ProductionEvent.qty), else_=0)).label("good_sum"),
            func.sum(func.case((ProductionEvent.event_type == "scrap", ProductionEvent.qty), else_=0)).label("scrap_sum"),
        )
        .filter(
            ProductionEvent.machine_id == machine_id,
            ProductionEvent.happened_at >= one_hour_ago,
        )
        .one()
    )
    good = sums.good_sum or 0
    scrap = sums.scrap_sum or 0

    throughput = good
    trs = (good / (good + scrap) * 100) if (good + scrap) > 0 else 0.0

    return {"throughput_last_hour": throughput, "trs": round(trs, 1)}

# backend/app/seed.py
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from .db import SessionLocal
from .models import User, Machine, WorkOrder, ProductionEvent
from .security import hash_password

def upsert_user(db: Session, email: str, password: str, role: str = "chef") -> User:
    u = db.query(User).filter(User.email == email).first()
    if u:
        return u
    u = User(email=email, hashed_password=hash_password(password), role=role)
    db.add(u); db.commit(); db.refresh(u)
    return u

def upsert_machine(db: Session, code: str, name: str, status: str, target_rate_per_hour: int) -> Machine:
    m = db.query(Machine).filter(Machine.code == code).first()
    if m:
        # on synchronise les champs utiles au passage
        m.name = name
        m.status = status
        m.target_rate_per_hour = target_rate_per_hour
        db.commit(); db.refresh(m)
        return m
    m = Machine(code=code, name=name, status=status, target_rate_per_hour=target_rate_per_hour)
    db.add(m); db.commit(); db.refresh(m)
    return m

def upsert_work_order(db: Session, number: str, client: str, part_ref: str, target_qty: int) -> WorkOrder:
    w = db.query(WorkOrder).filter(WorkOrder.number == number).first()
    if w:
        return w
    w = WorkOrder(number=number, client=client, part_ref=part_ref, target_qty=target_qty)
    db.add(w); db.commit(); db.refresh(w)
    return w

def add_event_if_missing(db: Session, *, machine_id: int, work_order_id: int | None,
                         event_type: str, qty: int, happened_at: datetime, notes: str | None = None):
    """Évite les doublons exacts (machine, OF, type, qty, seconde proche)."""
    exists = (
        db.query(ProductionEvent)
          .filter(
              ProductionEvent.machine_id == machine_id,
              (ProductionEvent.work_order_id == work_order_id) if work_order_id is not None else ProductionEvent.work_order_id.is_(None),
              ProductionEvent.event_type == event_type,
              ProductionEvent.qty == qty,
              # Postgres: compare à la seconde près pour simplifier
              func.date_trunc("second", ProductionEvent.happened_at) == func.date_trunc("second", happened_at),
          )
          .first()
    )
    if exists:
        return
    ev = ProductionEvent(
        machine_id=machine_id,
        work_order_id=work_order_id,
        event_type=event_type,
        qty=qty,
        happened_at=happened_at,
        notes=notes,
    )
    db.add(ev)
    db.commit()

def run():
    db = SessionLocal()
    try:
        # 1) User chef
        chef = upsert_user(db, email="chef@test.fr", password="pass1234", role="chef")

        # 2) Machines (upsert par code)
        m1 = upsert_machine(db, code="CNC-01", name="Fraiseuse Mazak", status="running", target_rate_per_hour=40)
        m2 = upsert_machine(db, code="CNC-02", name="Tour Haas",      status="running", target_rate_per_hour=55)
        m3 = upsert_machine(db, code="CNC-03", name="5 axes DMG",     status="setup",   target_rate_per_hour=30)

        # 3) Work orders (upsert par number)
        w1 = upsert_work_order(db, number="OF-2025-0001", client="ACME",   part_ref="P-12", target_qty=200)
        w2 = upsert_work_order(db, number="OF-2025-0002", client="Globex", part_ref="R-77", target_qty=120)

        # 4) Quelques events récents
        now = datetime.utcnow()
        for args in [
            dict(machine_id=m1.id, work_order_id=w1.id, event_type="good",  qty=3, happened_at=now - timedelta(minutes=30), notes="Lancement"),
            dict(machine_id=m1.id, work_order_id=w1.id, event_type="good",  qty=2, happened_at=now - timedelta(minutes=10)),
            dict(machine_id=m1.id, work_order_id=w1.id, event_type="scrap", qty=1, happened_at=now - timedelta(minutes=5),  notes="Bavure"),
            dict(machine_id=m2.id, work_order_id=w2.id, event_type="good",  qty=4, happened_at=now - timedelta(minutes=20)),
            dict(machine_id=m2.id, work_order_id=w2.id, event_type="good",  qty=2, happened_at=now - timedelta(minutes=3)),
            dict(machine_id=m3.id, work_order_id=None,  event_type="stop",  qty=0, happened_at=now - timedelta(minutes=1),  notes="Chgt d’outils"),
        ]:
            add_event_if_missing(db, **args)

        print("✅ Seed OK : user+machines+work_orders+events")
    finally:
        db.close()

if __name__ == "__main__":
    run()

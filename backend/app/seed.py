from datetime import datetime, timedelta, date
from .db import SessionLocal
from .models import Machine, WorkOrder, ProductionEvent

def seed():
    db = SessionLocal()
    try:
        # Machines
        if db.query(Machine).count() == 0:
            m1 = Machine(name="Fraiseuse Mazak", code="CNC-01", status="running", target_rate_per_hour=40)
            m2 = Machine(name="Tour Haas",      code="CNC-02", status="running", target_rate_per_hour=55)
            m3 = Machine(name="5 axes DMG",     code="CNC-03", status="setup",   target_rate_per_hour=30)
            db.add_all([m1, m2, m3])
            db.flush()  # obtenir les IDs

            # Work orders
            if db.query(WorkOrder).count() == 0:
                w1 = WorkOrder(number="OF-2025-0001", client="ACME", part_ref="P-12", target_qty=200, due_on=date.today()+timedelta(days=7))
                w2 = WorkOrder(number="OF-2025-0002", client="Globex", part_ref="R-77", target_qty=120, due_on=date.today()+timedelta(days=3))
                db.add_all([w1, w2])
                db.flush()

                now = datetime.utcnow()
                # Quelques événements récents pour faire vivre les KPI
                events = [
                    ProductionEvent(machine_id=m1.id, work_order_id=w1.id, event_type="good", qty=3, happened_at=now - timedelta(minutes=30)),
                    ProductionEvent(machine_id=m1.id, work_order_id=w1.id, event_type="good", qty=2, happened_at=now - timedelta(minutes=10)),
                    ProductionEvent(machine_id=m1.id, work_order_id=w1.id, event_type="scrap", qty=1, happened_at=now - timedelta(minutes=5)),
                    ProductionEvent(machine_id=m2.id, work_order_id=w2.id, event_type="good", qty=4, happened_at=now - timedelta(minutes=20)),
                    ProductionEvent(machine_id=m2.id, work_order_id=w2.id, event_type="good", qty=2, happened_at=now - timedelta(minutes=3)),
                    ProductionEvent(machine_id=m3.id, work_order_id=None,  event_type="stop", qty=0, happened_at=now - timedelta(minutes=1)),
                ]
                db.add_all(events)

            db.commit()
            print("Seed OK (machines, work_orders, events).")
        else:
            print("Seed ignoré : données déjà présentes.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()

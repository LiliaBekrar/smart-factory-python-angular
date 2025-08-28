import random, time
from datetime import datetime
from .db import SessionLocal
from .models import ProductionEvent, Machine, WorkOrder

def simulate():
    """
    Boucle infinie (Ctrl+C pour arrêter) :
    - choisit une machine et un OF existants
    - insère toutes les 30s un event (good majoritaire, un peu de scrap, rarement un stop)
    """
    db = SessionLocal()
    try:
        m = db.query(Machine).order_by(Machine.id.asc()).first()
        w = db.query(WorkOrder).order_by(WorkOrder.id.asc()).first()
        if not m or not w:
            print("⚠️ Pas de Machine ou WorkOrder. Lance d'abord le seed.")
            return

        while True:
            ev_type = random.choices(
                population=["good", "scrap", "stop"],
                weights=[0.8, 0.15, 0.05],  # 80% good, 15% scrap, 5% stop
                k=1
            )[0]
            qty = 1 if ev_type in ("good", "scrap") else 0
            ev = ProductionEvent(
                machine_id=m.id,
                work_order_id=w.id,
                event_type=ev_type,
                qty=qty,
                happened_at=datetime.utcnow(),
            )
            db.add(ev)
            db.commit()
            print(f"[simulate] {ev_type} qty={qty} @ {ev.happened_at.isoformat()}")
            time.sleep(30)
    finally:
        db.close()

if __name__ == "__main__":
    simulate()

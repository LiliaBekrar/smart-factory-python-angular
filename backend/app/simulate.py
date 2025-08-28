import random
import time
from datetime import datetime
from .db import SessionLocal
from .models import ProductionEvent, Machine, WorkOrder

TICK_SECONDS = 30  # tu peux réduire à 5 pour tester

def simulate():
    # Utilise un context manager pour garantir fermeture/rollback propre
    with SessionLocal() as db:
        w = db.query(WorkOrder).order_by(WorkOrder.id.asc()).first()
        if not w:
            print("⚠️ Pas de WorkOrder. Lance le seed.")
            return

        while True:
            machines = db.query(Machine).filter(Machine.status == "running").all()
            if not machines:
                print("⚠️ Pas de machine 'running'.")
                time.sleep(TICK_SECONDS)
                continue

            try:
                for m in machines:
                    ev_type = random.choices(
                        ["good", "scrap", "stop"], weights=[0.8, 0.15, 0.05]
                    )[0]
                    qty = 1 if ev_type in ("good", "scrap") else 0
                    now = datetime.utcnow()

                    # Log avant insert (utilise 'now', pas 'ev')
                    print(f"[simulate] Machine={m.name} type={ev_type} qty={qty} @ {now.isoformat()}Z")

                    db.add(ProductionEvent(
                        machine_id=m.id,
                        work_order_id=w.id,
                        event_type=ev_type,
                        qty=qty,
                        happened_at=now
                    ))

                db.commit()
                print(f"[simulate] tick ✓ → {len(machines)} machines alimentées")
            except Exception as e:
                db.rollback()
                print(f"[simulate] ❌ rollback: {e!r}")

            time.sleep(TICK_SECONDS)

if __name__ == "__main__":
    simulate()

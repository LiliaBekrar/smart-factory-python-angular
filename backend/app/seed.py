# app/seed.py
from datetime import datetime, timedelta, date
import random
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert  # pour ON CONFLICT DO NOTHING
from sqlalchemy import select, func

from .db import SessionLocal
from .models import Machine, WorkOrder, ProductionEvent, User
from .security import hash_password


def seed():
    db: Session = SessionLocal()
    try:
        # Log : vérifie qu'on cible la bonne base
        print("Seeding DB ->", db.get_bind().url)

        # --- Utilisateurs (idempotent) ---
        users_payload = [
            {"email": "admin@test.fr", "hashed_password": hash_password("pass1234"), "role": "admin"},
            {"email": "chef@test.fr",  "hashed_password": hash_password("pass1234"), "role": "chef"},
            {"email": "op@test.fr",    "hashed_password": hash_password("pass1234"), "role": "operator"},
        ]

        # Insère chaque user s'il manque (nécessite un index/contrainte unique sur users.email)
        for u in users_payload:
            stmt = insert(User).values(**u).on_conflict_do_nothing(index_elements=["email"])
            db.execute(stmt)
        total_users = db.scalar(select(func.count()).select_from(User))
        print(f"✔ users ok (présents: {total_users}) – admin/chef/op créés si manquants")

        # --- Machines ---
        if db.scalar(select(func.count()).select_from(Machine)) == 0:
            ms = [
                Machine(name="Fraiseuse Mazak", code="CNC-01", status="running", target_rate_per_hour=40),
                Machine(name="Tour Haas",       code="CNC-02", status="running", target_rate_per_hour=55),
                Machine(name="5 axes DMG",      code="CNC-03", status="setup",   target_rate_per_hour=30),
                Machine(name="Centre Hermle",   code="CNC-04", status="stopped", target_rate_per_hour=25),
                Machine(name="Robot Fanuc",     code="ROB-01", status="running", target_rate_per_hour=80),
            ]
            db.add_all(ms)
            db.flush()
            print(f"✔ {len(ms)} machines")
        else:
            print("↳ machines déjà présentes")

        # --- OF ---
        if db.scalar(select(func.count()).select_from(WorkOrder)) == 0:
            w1 = WorkOrder(number="OF-2025-0001", client="ACME",    part_ref="P-12", target_qty=200, due_on=date.today()+timedelta(days=7))
            w2 = WorkOrder(number="OF-2025-0002", client="Globex",  part_ref="R-77", target_qty=120, due_on=date.today()+timedelta(days=3))
            w3 = WorkOrder(number="OF-2025-0003", client="Initech", part_ref="K-03", target_qty=500, due_on=date.today()+timedelta(days=14))
            db.add_all([w1, w2, w3])
            db.flush()
            print("✔ 3 work orders")
        else:
            print("↳ work orders déjà présents")

        # --- Événements (répartis sur 30 jours) ---
        if db.scalar(select(func.count()).select_from(ProductionEvent)) == 0:
            machines = db.query(Machine).all()
            wos = db.query(WorkOrder).all()
            now = datetime.utcnow()
            events: list[ProductionEvent] = []

            def add_ev(m, wo, kind, qty, minutes_ago, note=None):
                events.append(ProductionEvent(
                    machine_id=m.id,
                    work_order_id=wo.id if wo else None,
                    event_type=kind,  # "good"|"scrap"|"stop"
                    qty=qty,
                    notes=note,
                    happened_at=now - timedelta(minutes=minutes_ago),
                ))

            rng = random.Random(42)
            for day in range(0, 30):
                for m in machines:
                    for _ in range(rng.randint(3, 6)):
                        kind = rng.choices(["good", "scrap", "stop"], weights=[0.75, 0.15, 0.10])[0]
                        qty  = rng.randint(1, 8) if kind in ("good", "scrap") else 0
                        wo   = rng.choice(wos + [None])
                        minutes_ago = day * 24 * 60 + rng.randint(0, 24 * 60 - 1)
                        note = None
                        if kind == "scrap":
                            note = rng.choice(["copeau long", "outil usé", "mauvaise cote", "bavure"])
                        if kind == "stop":
                            note = rng.choice(["changement d'outil", "maintenance", "pause", "alimentation matière"])
                        add_ev(m, wo, kind, qty, minutes_ago, note)

            db.add_all(events)
            print(f"✔ {len(events)} événements")
        else:
            print("↳ événements déjà présents, pas de duplication")

        db.commit()
        print("✅ Seed OK (users + machines + OF + events)")

    except Exception as e:
        db.rollback()
        print("❌ Seed échoué → rollback :", repr(e))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()

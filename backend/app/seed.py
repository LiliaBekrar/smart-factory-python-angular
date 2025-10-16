# ============================================================
# app/seed.py
# ------------------------------------------------------------
# 🌱 Script de “seed” (pré-remplissage) de la base de données.
# - Crée les utilisateurs de base (admin, chef, opérateur)
# - Ajoute des machines, ordres de fabrication et événements
# - S’exécute automatiquement au démarrage si SEED_ON_START=True
# ============================================================

from datetime import datetime, timedelta, date
import random
import traceback
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text

from .db import SessionLocal
from .models import Machine, WorkOrder, ProductionEvent, User
from .security import hash_password

from .security import pwd_context
import app.security as sec
print("🔒 [seed] Passlib schemes =", pwd_context.schemes())
print("📦 [seed] security module file =", sec.__file__)


def seed():
    """
    Initialise la base avec des données réalistes :
    - 3 utilisateurs
    - 5 machines
    - 3 ordres de fabrication
    - un historique d’événements répartis sur 30 jours
    """

    # Ouvre une session SQLAlchemy
    db: Session = SessionLocal()

    try:
        # ------------------------------------------------------------
        # 🧩 LOG DÉBUT : Affiche la base cible
        # ------------------------------------------------------------
        try:
            current_db = db.execute(text("SELECT current_database() AS name")).mappings().first()
            print("Seeding DB →", db.get_bind().url)
            print("→ Current database:", current_db["name"] if current_db else "inconnue")
        except Exception:
            print("Seeding DB →", db.get_bind().url, "(no DB name query)")

        # ------------------------------------------------------------
        # 👥 1) Utilisateurs (idempotent)
        # ------------------------------------------------------------
        users_payload = [
            {"email": "admin@test.fr", "hashed_password": hash_password("pass1234"), "role": "admin"},
            {"email": "chef@test.fr",  "hashed_password": hash_password("pass1234"), "role": "chef"},
            {"email": "op@test.fr",    "hashed_password": hash_password("pass1234"), "role": "operator"},
        ]

        created_users = 0
        for u in users_payload:
            # On vérifie avant d’insérer → évite erreur sans contrainte UNIQUE
            exists = db.query(User).filter(User.email == u["email"]).first()
            if not exists:
                db.add(User(**u))
                created_users += 1

        db.flush()  # Écrit les changements dans la transaction sans commit
        total_users = db.scalar(select(func.count()).select_from(User))
        print(f"✔ Utilisateurs → ajoutés: {created_users}, total en base: {total_users}")

        # ------------------------------------------------------------
        # ⚙️ 2) Machines
        # ------------------------------------------------------------
        if db.scalar(select(func.count()).select_from(Machine)) == 0:
            machines = [
                Machine(name="Fraiseuse Mazak", code="CNC-01", status="running", target_rate_per_hour=40),
                Machine(name="Tour Haas",       code="CNC-02", status="running", target_rate_per_hour=55),
                Machine(name="5 axes DMG",      code="CNC-03", status="setup",   target_rate_per_hour=30),
                Machine(name="Centre Hermle",   code="CNC-04", status="stopped", target_rate_per_hour=25),
                Machine(name="Robot Fanuc",     code="ROB-01", status="running", target_rate_per_hour=80),
            ]
            db.add_all(machines)
            db.flush()
            print(f"✔ {len(machines)} machines créées")
        else:
            print("↳ Machines déjà présentes → rien ajouté")

        # ------------------------------------------------------------
        # 🧾 3) Ordres de fabrication (WorkOrders)
        # ------------------------------------------------------------
        if db.scalar(select(func.count()).select_from(WorkOrder)) == 0:
            orders = [
                WorkOrder(number="OF-2025-0001", client="ACME",    part_ref="P-12", target_qty=200, due_on=date.today() + timedelta(days=7)),
                WorkOrder(number="OF-2025-0002", client="Globex",  part_ref="R-77", target_qty=120, due_on=date.today() + timedelta(days=3)),
                WorkOrder(number="OF-2025-0003", client="Initech", part_ref="K-03", target_qty=500, due_on=date.today() + timedelta(days=14)),
            ]
            db.add_all(orders)
            db.flush()
            print(f"✔ {len(orders)} ordres de fabrication créés")
        else:
            print("↳ WorkOrders déjà présents → rien ajouté")

        # ------------------------------------------------------------
        # 🏭 4) Événements de production
        # ------------------------------------------------------------
        if db.scalar(select(func.count()).select_from(ProductionEvent)) == 0:
            machines = db.query(Machine).all()
            work_orders = db.query(WorkOrder).all()
            now = datetime.utcnow()
            events: list[ProductionEvent] = []

            rng = random.Random(42)
            for day in range(30):  # 30 derniers jours
                for m in machines:
                    for _ in range(rng.randint(3, 6)):  # 3 à 6 événements par jour et par machine
                        kind = rng.choices(["good", "scrap", "stop"], weights=[0.75, 0.15, 0.10])[0]
                        qty = rng.randint(1, 8) if kind in ("good", "scrap") else 0
                        wo = rng.choice(work_orders + [None])
                        minutes_ago = day * 24 * 60 + rng.randint(0, 24 * 60 - 1)

                        # Notes optionnelles
                        note = None
                        if kind == "scrap":
                            note = rng.choice(["copeau long", "outil usé", "mauvaise cote", "bavure"])
                        elif kind == "stop":
                            note = rng.choice(["changement d'outil", "maintenance", "pause", "alimentation matière"])

                        events.append(ProductionEvent(
                            machine_id=m.id,
                            work_order_id=wo.id if wo else None,
                            event_type=kind,
                            qty=qty,
                            happened_at=now - timedelta(minutes=minutes_ago),
                            notes=note,
                        ))

            db.add_all(events)
            print(f"✔ {len(events)} événements créés")
        else:
            print("↳ Événements déjà présents → pas de duplication")

        # ------------------------------------------------------------
        # 💾 Validation finale
        # ------------------------------------------------------------
        db.commit()
        print("✅ Seed terminé avec succès (users + machines + OF + events)")

    except Exception as e:
        # En cas d’erreur → rollback complet et affichage détaillé
        db.rollback()
        print("❌ Seed échoué → rollback :", repr(e))
        traceback.print_exc()
        raise
    finally:
        db.close()
        print("🔚 Session fermée proprement")


# ------------------------------------------------------------
# ⚙️ Si exécuté directement (python -m app.seed)
# ------------------------------------------------------------
if __name__ == "__main__":
    seed()

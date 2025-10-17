# app/simulate.py
"""
Simulateur d’activité :
- Backfill 30 jours (toutes 3h)
- Backfill 24h (toutes 5–10 min, plus dense près de maintenant)
- Boucle minute : 1 à 3 événements/minute à l’instant présent
Heure de référence : Europe/Paris → converti en UTC naïf pour la DB.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import random
import asyncio

from sqlalchemy.orm import Session
from sqlalchemy import func, select

from .db import SessionLocal
from .models import ProductionEvent, Machine, WorkOrder

PARIS = ZoneInfo("Europe/Paris")

# RNG déterministe pour des runs reproductibles (change la seed si tu veux)
_rng = random.Random(42)


# -----------------------------
# Utilitaires temps & conversion
# -----------------------------
def paris_now() -> datetime:
    """Datetime aware sur Europe/Paris."""
    return datetime.now(PARIS)

def to_utc_naive(dt_paris: datetime) -> datetime:
    """Europe/Paris (aware) → UTC naive (sans tzinfo) pour coller au schéma DB."""
    return dt_paris.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


# -----------------------------
# Helpers DB
# -----------------------------
def _ensure_work_order(db: Session) -> WorkOrder:
    """Récupère un WO ou en crée un “tampon” si absent."""
    wo = db.query(WorkOrder).order_by(WorkOrder.id.asc()).first()
    if wo:
        return wo
    wo = WorkOrder(number="OF-SIM", client="SIM", part_ref="SIM", target_qty=999999)
    db.add(wo)
    db.flush()
    return wo

def _pick_event() -> tuple[str, int, str | None]:
    """
    Retourne (event_type, qty, note) avec distribution réaliste.
    - good  : 75%
    - scrap : 15% (qty 1–5 + note défaut)
    - stop  : 10% (qty 0 + note arrêt)
    """
    kind = _rng.choices(["good", "scrap", "stop"], weights=[0.75, 0.15, 0.10])[0]
    note = None
    if kind == "good":
        qty = _rng.randint(1, 5)
    elif kind == "scrap":
        qty = _rng.randint(1, 3)
        note = _rng.choice(["copeau long", "outil usé", "mauvaise cote", "bavure"])
    else:
        qty = 0
        note = _rng.choice(["changement d'outil", "maintenance", "pause", "alimentation matière"])
    return kind, qty, note


# -----------------------------
# Génération d’événements
# -----------------------------
def _insert_events_at(db: Session, at_paris: datetime, machines: list[Machine], wo: WorkOrder) -> int:
    """
    Insère 1 événement par machine au timestamp donné (Paris), converti en UTC naïf.
    Retourne le nombre créé.
    """
    when_utc = to_utc_naive(at_paris)
    created = 0
    for m in machines:
        kind, qty, note = _pick_event()
        db.add(ProductionEvent(
            machine_id=m.id,
            work_order_id=wo.id,
            event_type=kind,
            qty=qty,
            notes=note,
            happened_at=when_utc,
        ))
        created += 1
    return created


# -----------------------------
# Backfill (à lancer au démarrage)
# -----------------------------
def backfill_month_and_day() -> tuple[int, int]:
    """
    - Si peu/aucune activité récente, crée un historique pour 30 jours + 24h.
    - 30 jours : points toutes 3h
    - 24h : points toutes 5 à 10 minutes
    Retourne (n_events_30j, n_events_24h).
    """
    now_p = paris_now()
    with SessionLocal() as db:
        wo = _ensure_work_order(db)

        # On ne backfill que si la dernière heure est vide (évite la duplication à chaque cold start)
        since_1h = to_utc_naive(now_p - timedelta(hours=1))
        recent_count = db.scalar(
            select(func.count(ProductionEvent.id)).where(ProductionEvent.happened_at >= since_1h)
        ) or 0

        if recent_count > 0:
            print(f"🧪 Backfill sauté (activité récente trouvée: {recent_count} events ≥ now-1h).")
            return (0, 0)

        machines = db.query(Machine).filter(Machine.status.in_(["running", "setup"])).all()
        if not machines:
            print("⚠️ Backfill: aucune machine (running/setup). Abandon.")
            return (0, 0)

        # ---- 30 jours précédents : toutes les 3 heures
        created_30d = 0
        start_30d = now_p - timedelta(days=30)
        t = start_30d
        while t < now_p - timedelta(days=1):  # on s'arrête à la veille (les 24h seront détaillées ensuite)
            created_30d += _insert_events_at(db, t, machines, wo)
            t += timedelta(hours=3)
        db.commit()
        print(f"📦 Backfill 30j → +{created_30d} events")

        # ---- 24h précédentes : toutes 5–10 minutes (plus dense)
        created_24h = 0
        start_24h = now_p - timedelta(hours=24)
        t = start_24h
        while t < now_p:
            created_24h += _insert_events_at(db, t, machines, wo)
            # pas d’intervalle fixe pour éviter l’uniformité
            t += timedelta(minutes=_rng.randint(5, 10))
        db.commit()
        print(f"📦 Backfill 24h → +{created_24h} events")

        return (created_30d, created_24h)


# -----------------------------
# Boucle minute (pendant que l’instance est réveillée)
# -----------------------------
async def simulation_minutely_loop(min_per_tick: int = 1, max_per_tick: int = 3, interval_seconds: int = 60):
    """
    Toutes les `interval_seconds`, insère 1–3 événements *à maintenant (Paris)*,
    sur des machines au hasard parmi celles en running/setup.
    """
    assert 1 <= min_per_tick <= max_per_tick
    while True:
        try:
            with SessionLocal() as db:
                machines = db.query(Machine).filter(Machine.status.in_(["running", "setup"])).all()
                if not machines:
                    print("[simulate] aucune machine running/setup → dodo")
                else:
                    wo = _ensure_work_order(db)
                    now_p = paris_now()
                    n = _rng.randint(min_per_tick, max_per_tick)
                    chosen = _rng.sample(machines, k=min(n, len(machines)))
                    created = 0
                    for m in chosen:
                        # un event par machine choisie
                        kind, qty, note = _pick_event()
                        db.add(ProductionEvent(
                            machine_id=m.id,
                            work_order_id=wo.id,
                            event_type=kind,
                            qty=qty,
                            notes=note,
                            happened_at=to_utc_naive(now_p),
                        ))
                        created += 1
                    db.commit()
                    print(f"[simulate] +{created} event(s) @ {now_p.isoformat()} (Europe/Paris)")
        except Exception as e:
            print(f"[simulate] ❌ {e!r}")

        await asyncio.sleep(interval_seconds)


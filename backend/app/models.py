# app/models.py
# ==========================================================
# Modèles SQLAlchemy pour Smart Factory
# - User            : comptes & rôles
# - Machine         : machines de production
# - WorkOrder       : ordres de fabrication (OF)
# - ProductionEvent : événements (good/scrap/stop)
# ==========================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
    Index,
    text,  # <- pour CURRENT_TIMESTAMP côté base
)
from sqlalchemy.orm import relationship

from .db import Base


# ----------------------------------------------------------
# 👤 User (auth simple + rôles)
# ----------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    # Email unique + non null
    email = Column(String, unique=True, nullable=False)

    # Mot de passe haché (tu utilises pbkdf2_sha256 dans security.py)
    hashed_password = Column(String, nullable=False)

    # operator | chef | admin
    role = Column(String, nullable=False, default="operator")

    # 💡 IMPORTANT : créé le timestamp côté base par défaut
    # - server_default=CURRENT_TIMESTAMP évite l'erreur NOT NULL si l'INSERT n'envoie pas created_at
    # - nécessite une migration si la colonne n'existe pas encore en DB
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),  # Postgres & SQLite OK
    )

    # relation inverse: un user peut "posséder" des machines (créées par lui)
    machines = relationship(
        "Machine",
        back_populates="owner",
        cascade="save-update, merge",
    )

    # (Optionnel) index explicite — l'unicité est déjà sur la colonne
    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
    )


# ----------------------------------------------------------
# 🏭 Machine
# ----------------------------------------------------------
class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True)

    name = Column(String, nullable=False)
    code = Column(String, unique=True, nullable=False)

    # running | stopped | setup (tu avais 'setup' par défaut → on garde)
    status = Column(String, nullable=False, default="setup")

    # cadence cible / heure
    target_rate_per_hour = Column(Integer, nullable=False, default=0)

    # Qui a créé cette machine ? (permet de limiter le CRUD des opérateurs)
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps (facultatif mais pratique pour trier/requêter)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # relations
    owner = relationship("User", back_populates="machines", foreign_keys=[created_by])
    events = relationship("ProductionEvent", back_populates="machine")

    __table_args__ = (
        Index("ix_machines_code", "code", unique=True),
        Index("ix_machines_status", "status"),
    )


# ----------------------------------------------------------
# 📄 WorkOrder (OF)
# ----------------------------------------------------------
class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True)

    number = Column(String, unique=True, nullable=False)  # ex: OF-2025-0001
    client = Column(String)
    part_ref = Column(String)
    target_qty = Column(Integer, nullable=False, default=0)
    due_on = Column(Date)

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # relations
    events = relationship("ProductionEvent", back_populates="work_order")

    __table_args__ = (
        Index("ix_work_orders_number", "number", unique=True),
        Index("ix_work_orders_due_on", "due_on"),
    )


# ----------------------------------------------------------
# 📈 ProductionEvent
# ----------------------------------------------------------
class ProductionEvent(Base):
    __tablename__ = "production_events"

    id = Column(Integer, primary_key=True)

    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True)

    # good | scrap | stop
    event_type = Column(String, nullable=False)

    # quantité produite (0 si stop)
    qty = Column(Integer, nullable=False, default=0)

    # note optionnelle (tu avais String → on garde pour ne pas casser de migration)
    notes = Column(String)

    # horodatage de l’événement (par défaut maintenant côté app)
    happened_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # relations
    machine = relationship("Machine", back_populates="events")
    work_order = relationship("WorkOrder", back_populates="events")

    # index perf: requêtes "par machine, triées par date"
    __table_args__ = (
        Index("ix_production_events_machine_happened", "machine_id", "happened_at"),
    )

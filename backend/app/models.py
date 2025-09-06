# app/models.py
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from .db import Base

# -------------------------
# User (auth simple + rôles)
# -------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)          # email unique
    hashed_password = Column(String, nullable=False)             # mot de passe haché (bcrypt)
    role = Column(String, nullable=False, default="operator")    # operator|chef|admin

    # relation inverse: un user peut "posséder" des machines (créées par lui)
    machines = relationship("Machine", back_populates="owner", cascade="save-update, merge")


# -------------------------
# Machine
# -------------------------
class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True, nullable=False)
    status = Column(String, nullable=False, default="setup")  # running|stopped|setup
    target_rate_per_hour = Column(Integer, nullable=False, default=0)

    # 👇 nouveau : qui a créé cette machine ? (permet de limiter le CRUD pour opérateurs)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # relations
    owner = relationship("User", back_populates="machines", foreign_keys=[created_by])
    events = relationship("ProductionEvent", back_populates="machine")


# -------------------------
# WorkOrder (OF)
# -------------------------
class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True)
    number = Column(String, unique=True, nullable=False)  # ex: OF-2025-0001
    client = Column(String)
    part_ref = Column(String)
    target_qty = Column(Integer, nullable=False, default=0)
    due_on = Column(Date)

    # relations
    events = relationship("ProductionEvent", back_populates="work_order")


# -------------------------
# ProductionEvent
# -------------------------
class ProductionEvent(Base):
    __tablename__ = "production_events"

    id = Column(Integer, primary_key=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True)
    event_type = Column(String, nullable=False)  # good|scrap|stop
    qty = Column(Integer, nullable=False, default=0)
    notes = Column(String)
    happened_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # relations
    machine = relationship("Machine", back_populates="events")
    work_order = relationship("WorkOrder", back_populates="events")

    # index perf: requêtes "par machine, triées par date"
    __table_args__ = (
        Index("ix_production_events_machine_happened", "machine_id", "happened_at"),
    )

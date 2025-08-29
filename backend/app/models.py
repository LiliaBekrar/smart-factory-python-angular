from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True, nullable=False)
    status = Column(String, nullable=False)  # running|stopped|setup
    target_rate_per_hour = Column(Integer, nullable=False, default=0)

    # relations
    events = relationship("ProductionEvent", back_populates="machine")

class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True)
    number = Column(String, unique=True, nullable=False)  # OF-2025-0001
    client = Column(String)
    part_ref = Column(String)
    target_qty = Column(Integer, nullable=False, default=0)
    due_on = Column(Date)

    # relations
    events = relationship("ProductionEvent", back_populates="work_order")

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

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="operator")  # operator|chef|admin
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

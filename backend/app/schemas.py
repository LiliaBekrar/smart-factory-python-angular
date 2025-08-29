from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime, date

# --- Machine ---
class MachineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    status: str
    target_rate_per_hour: int

# --- WorkOrder ---
class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: str
    client: str | None = None
    part_ref: str | None = None
    target_qty: int
    due_on: date | None = None

# --- KPI (pas lié à une table, juste une sortie calculée) ---
class KPIOut(BaseModel):
    throughput_last_hour: int
    trs: float

# --- Activity (flux d’événements) ---
class ActivityItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    machine_id: int
    machine_code: str | None = None
    work_order_id: int | None = None
    work_order_number: str | None = None
    event_type: str
    qty: int
    notes: str | None = None
    happened_at: datetime

# -------- Users / Auth --------
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    role: str

class SignupIn(BaseModel):
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

# -------- Machines (CRUD) --------
class MachineCreate(BaseModel):
    name: str
    code: str
    status: str = "setup"
    target_rate_per_hour: int = 0

class MachineUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    status: str | None = None
    target_rate_per_hour: int | None = None

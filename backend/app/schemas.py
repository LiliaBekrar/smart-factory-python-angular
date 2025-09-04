"""
Schemas Pydantic (FastAPI)
==========================

Objectif
--------
Définir les **modèles d'échange API** (entrées/sorties). Ces schémas assurent :
- Validation / sérialisation des payloads.
- Séparation claire entre **ORM models** (SQLAlchemy) et **DTO/API**.
- Documentation automatique Swagger (types, champs, valeurs par défaut).

Conventions
-----------
- ``model_config = ConfigDict(from_attributes=True)`` permet d'instancier depuis
  un ORM object (ex: ``UserOut.from_orm(user)``).
- Suffixes :
  - ``Out`` → payloads de sortie (API → client).
  - ``In`` → payloads d'entrée (client → API).
  - ``Create``/``Update`` → entrées CRUD.
- Champs optionnels typés avec ``| None`` (nullable ou non fourni).

Organisation
------------
- **Machines** : sorties et CRUD.
- **WorkOrders** : sortie.
- **KPI** : valeurs calculées (non liées directement à une table).
- **Activity** : flux d'événements enrichis.
- **Users/Auth** : login/signup/token.
- **Dashboard** : agrégats pour affichage global (KPIs + activité récente).
"""

from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime, date
from typing import List


# -------------------------
# Machine
# -------------------------
class MachineOut(BaseModel):
    """Sortie machine (lecture API)."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    status: str
    target_rate_per_hour: int


# -------------------------
# WorkOrder
# -------------------------
class WorkOrderOut(BaseModel):
    """Sortie ordre de fabrication (OF)."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: str
    client: str | None = None
    part_ref: str | None = None
    target_qty: int
    due_on: date | None = None


# -------------------------
# KPI (sorties calculées)
# -------------------------
class KPIOut(BaseModel):
    """KPI machine sur dernière période (ex: dernière heure)."""
    throughput_last_hour: int  # nb pièces good
    trs: float                 # taux de qualité good/(good+scrap)


# -------------------------
# Activity (flux d’événements)
# -------------------------
class ActivityItemOut(BaseModel):
    """Événement de production enrichi (machine + OF)."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    machine_id: int
    machine_code: str | None = None
    machine_name: str
    work_order_id: int | None = None
    work_order_number: str | None = None
    event_type: str  # "good" | "scrap" | "stop" (cf. modèle ProductionEvent)
    qty: int
    notes: str | None = None
    happened_at: datetime


# -------------------------
# Users / Auth
# -------------------------
class UserOut(BaseModel):
    """Sortie profil utilisateur (id + email + rôle)."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    role: str


class SignupIn(BaseModel):
    """Entrée inscription (POST /auth/signup)."""
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    """Entrée login (POST /auth/login)."""
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    """Sortie login : JWT access token."""
    access_token: str
    token_type: str = "bearer"


# -------------------------
# Machines (CRUD)
# -------------------------
class MachineCreate(BaseModel):
    """Entrée création machine."""
    name: str
    code: str
    status: str = "setup"  # valeur par défaut : machine non encore démarrée
    target_rate_per_hour: int = 0


class MachineUpdate(BaseModel):
    """Entrée update machine (patch partiel)."""
    name: str | None = None
    code: str | None = None
    status: str | None = None
    target_rate_per_hour: int | None = None


# -------------------------
# Dashboard (agrégats)
# -------------------------
class DashboardKPIOut(BaseModel):
    """KPIs agrégés pour dashboard global."""
    total_machines: int
    running: int
    stopped: int
    trs_avg_last_hour: float  # moyenne TRS sur dernière heure


class DashboardActivityItemOut(BaseModel):
    """Événement simplifié pour dashboard (flux récent)."""
    id: int
    machine_code: str | None
    machine_name: str
    event_type: str
    qty: int
    happened_at: datetime
    work_order_number: str | None = None


class DashboardSummaryOut(BaseModel):
    """Résumé dashboard = KPIs globaux + activité récente."""
    kpis: DashboardKPIOut
    recent: List[DashboardActivityItemOut]

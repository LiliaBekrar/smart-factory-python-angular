"""
Schemas Pydantic (FastAPI)
==========================

Ce fichier définit les *schémas Pydantic* utilisés dans l’API.
Ces schémas servent à :
- Valider les données envoyées/reçues par l’API.
- Assurer la conversion entre les objets ORM (SQLAlchemy) et les objets de sortie API.
- Générer automatiquement la documentation Swagger (types, descriptions, champs).

Convention de nommage :
- `Out`    → payload de sortie (API → client).
- `In`     → payload d’entrée (client → API).
- `Create` → entrée pour créer un objet.
- `Update` → entrée pour mettre à jour un objet.
"""

# Import de la base Pydantic (librairie de validation et typage).
from pydantic import BaseModel, ConfigDict, EmailStr
# Import de types standards Python.
from datetime import datetime, date
from typing import List


# -------------------------
# Machine
# -------------------------
class MachineOut(BaseModel):
    """Données envoyées au client lorsqu’on lit une machine via l’API."""
    # Autorise la création du schéma directement à partir d’un objet SQLAlchemy (ORM).
    model_config = ConfigDict(from_attributes=True)

    # Champs qui seront retournés
    id: int                        # identifiant unique machine
    name: str                      # nom lisible de la machine
    code: str                      # code unique machine
    status: str                    # état actuel (ex: running, stopped)
    target_rate_per_hour: int      # cadence cible par heure
    created_by: int | None = None

# -------------------------
# Machines (CRUD)
# -------------------------
class MachineCreate(BaseModel):
    """Payload d’entrée pour créer une machine."""
    name: str
    code: str
    status: str = "setup"          # valeur par défaut = machine non démarrée
    target_rate_per_hour: int = 0  # valeur par défaut = 0


class MachineUpdate(BaseModel):
    """Payload d’entrée pour mettre à jour une machine (PATCH partiel)."""
    # Tous les champs sont optionnels pour permettre un update partiel
    name: str | None = None
    code: str | None = None
    status: str | None = None
    target_rate_per_hour: int | None = None

# -------------------------
# WorkOrder
# -------------------------
class WorkOrderOut(BaseModel):
    """Données envoyées lorsqu’on lit un Ordre de Fabrication (OF)."""
    model_config = ConfigDict(from_attributes=True)

    id: int                        # identifiant unique
    number: str                    # numéro d’OF
    client: str | None = None      # nom du client (optionnel)
    part_ref: str | None = None    # référence de la pièce (optionnel)
    target_qty: int                # quantité à produire
    due_on: date | None = None     # date d’échéance prévue (optionnelle)


# -------------------------
# KPI (sorties calculées)
# -------------------------
class KPIOut(BaseModel):
    """Indicateurs calculés (non liés à une table SQL)."""
    good: int
    scrap: int      # nombre de pièces bonnes produites sur la dernière heure
    trs: float                     # Taux de Rendement Synthétique (qualité, dispo, perf)


# -------------------------
# Activity (flux d’événements)
# -------------------------
class ActivityItemOut(BaseModel):
    """Événement de production enrichi (machine + OF lié)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: int
    machine_code: str | None = None
    machine_name: str
    work_order_id: int | None = None
    work_order_number: str | None = None
    event_type: str                # "good" | "scrap" | "stop"
    qty: int                       # quantité associée à l’événement
    notes: str | None = None       # remarque éventuelle (ex: panne)
    happened_at: datetime          # date/heure de l’événement


# -------------------------
# Users / Auth
# -------------------------
class UserOut(BaseModel):
    """Données d’un utilisateur retournées par l’API (profil)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr                # email valide
    role: str                      # rôle (admin, opérateur, etc.)


class SignupIn(BaseModel):
    """Payload d’entrée pour inscription (POST /auth/signup)."""
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    """Payload d’entrée pour login (POST /auth/login)."""
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    """Payload de sortie après login (JWT)."""
    access_token: str              # jeton JWT
    token_type: str = "bearer"     # type de token (par défaut "bearer")

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "operator"  # operator|chef|admin

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    role: str | None = None


# -------------------------
# Dashboard (agrégats)
# -------------------------
class DashboardKPIOut(BaseModel):
    """KPIs globaux du dashboard (toutes machines)."""
    total_machines: int            # nombre total de machines
    running: int                   # machines en marche
    stopped: int                   # machines arrêtées
    trs_avg_last_hour: float       # TRS moyen sur la dernière heure


class DashboardActivityItemOut(BaseModel):
    """Événement simplifié affiché dans le dashboard (flux récent)."""
    id: int
    machine_code: str | None
    machine_name: str
    event_type: str
    qty: int
    happened_at: datetime
    work_order_number: str | None = None


class DashboardSummaryOut(BaseModel):
    """Résumé du dashboard (KPIs + activité récente)."""
    kpis: DashboardKPIOut
    recent: List[DashboardActivityItemOut]


# -------------------------
# Production Events (saisie opérateur)
# -------------------------
class EventCreate(BaseModel):
    """Payload d’entrée pour créer un événement de production."""
    machine_id: int
    work_order_id: int | None = None
    event_type: str                # "good" | "scrap" | "stop"
    qty: int = 0                   # par défaut = 0
    happened_at: datetime | None = None
    notes: str | None = None


class EventOut(BaseModel):
    """Payload de sortie pour un événement enregistré en base."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: int
    work_order_id: int | None
    event_type: str
    qty: int
    notes: str | None
    happened_at: datetime

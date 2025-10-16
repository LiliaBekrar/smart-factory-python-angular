# ============================================================
# app/settings.py
# ------------------------------------------------------------
# ⚙️ Configuration centrale de l'application
# Gérée via pydantic-settings : combine .env (local)
# et variables d'environnement (Render, Docker, etc.)
# ============================================================

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# ------------------------------------------------------------
# 📁 Racine du projet
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # ---------------------------------------------------------
    # 🗄️ Base de données
    # ---------------------------------------------------------
    database_url: str = Field(
        default=f"sqlite:///{(BASE_DIR / 'smart_factory.db').as_posix()}",
        description="Database URL (SQLite local ou PostgreSQL/Neon sur Render)",
    )

    # ---------------------------------------------------------
    # 🔐 JWT / Sécurité
    # ---------------------------------------------------------
    secret_key: str = Field(
        default="dev-secret",
        description="Clé secrète pour signer les JWT",
    )
    access_token_expire_minutes: int = Field(
        default=60,
        description="Durée de vie du token d'accès (en minutes)",
    )

    # ---------------------------------------------------------
    # 🌱 Drapeaux d'environnement
    # ---------------------------------------------------------
    seed_on_start: bool = Field(
        default=False,  # en prod, à activer manuellement sur Render si besoin
        description="Si vrai → exécute app.seed au démarrage",
    )
    debug: bool = Field(
        default=True,
        description="Active le mode debug (FastAPI + logs verbeux)",
    )

    # ---------------------------------------------------------
    # ⚙️ Configuration Pydantic
    # ---------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",               # charge .env localement si dispo
        env_file_encoding="utf-8",     # gère accents et caractères spéciaux
        env_file_optional=True,        # n'oblige pas .env (utile sur Render)
        extra="ignore",                # ignore les variables inconnues
        case_sensitive=False,          # pas de distinction maj/min (Render friendly)
    )


# ------------------------------------------------------------
# Instance unique importable dans tout le projet
# ------------------------------------------------------------
settings = Settings()

# 🔍 Petit log de debug local (ne s'affiche pas sur Render sauf DEBUG=True)
if settings.debug:
    print("🧩 [settings] Configuration chargée :")
    print(f"   DATABASE_URL   = {settings.database_url}")
    print(f"   SEED_ON_START  = {settings.seed_on_start}")
    print(f"   DEBUG           = {settings.debug}")
    print(f"   SECRET_KEY len  = {len(settings.secret_key)} chars")

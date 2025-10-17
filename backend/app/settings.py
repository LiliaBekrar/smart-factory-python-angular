# app/settings.py
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    # 🗄️ Base de données
    database_url: str = Field(
        default=f"sqlite:///{(BASE_DIR / 'smart_factory.db').as_posix()}",
        description="Database URL (SQLite local ou PostgreSQL/Neon sur Render)",
    )

    # 🔐 JWT / Sécurité
    secret_key: str = Field(
        default="dev-secret",
        description="Clé secrète pour signer les JWT",
    )
    access_token_expire_minutes: int = Field(
        default=60,
        description="Durée de vie du token d'accès (en minutes)",
    )

    # 🌱 Drapeaux d'environnement
    seed_on_start: bool = Field(
        default=False,
        description="Si vrai → exécute app.seed au démarrage",
    )
    debug: bool = Field(
        default=True,
        description="Active le mode debug (FastAPI + logs verbeux)",
    )

    # ⚙️ Simulation (pilotables par env)
    simulate_enabled: bool = Field(default=True, description="Active la simulation d'événements")
    simulate_interval_seconds: int = Field(default=60, description="Intervalle entre ticks de simulation")
    simulate_min_per_tick: int = Field(default=1, description="Min d'événements par tick")
    simulate_max_per_tick: int = Field(default=3, description="Max d'événements par tick")

    # ⚙️ Config Pydantic
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_file_optional=True,
        extra="ignore",
        case_sensitive=False,
    )

settings = Settings()

if settings.debug:
    print("🧩 [settings] Configuration chargée :")
    print(f"   DATABASE_URL   = {settings.database_url}")
    print(f"   SEED_ON_START  = {settings.seed_on_start}")
    print(f"   DEBUG           = {settings.debug}")
    print(f"   SECRET_KEY len  = {len(settings.secret_key)} chars")

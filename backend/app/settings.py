from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Racine du projet
BASE_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    # -------------------------------------------------
    # 🗄️ Base de données
    # -------------------------------------------------
    # URL par défaut = SQLite local (utile en dev)
    database_url: str = Field(
        default=f"sqlite:///{(BASE_DIR / 'smart_factory.db').as_posix()}",
        description="Database URL (SQLite local ou PostgreSQL/Neon sur Render)",
    )

    # -------------------------------------------------
    # 🔐 JWT / Sécurité
    # -------------------------------------------------
    secret_key: str = Field(default="dev-secret", description="JWT secret key")
    access_token_expire_minutes: int = Field(default=60)

    # -------------------------------------------------
    # 🌱 Drapeaux d'environnement
    # -------------------------------------------------
    seed_on_start: bool = Field(
        default=True,
        description="Si vrai → exécute app.seed au démarrage (Render Free)",
    )
    debug: bool = Field(default=True)

    # -------------------------------------------------
    # ⚙️ Configuration Pydantic
    # -------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",        # charge automatiquement .env localement
        extra="ignore",
        case_sensitive=False,
    )

# Instance globale
settings = Settings()

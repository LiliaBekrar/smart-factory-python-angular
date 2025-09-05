from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    # --- Base de données ---
    database_url: str = Field(
        default=f"sqlite:///{(BASE_DIR / 'smart_factory.db').as_posix()}"
    )

    # --- JWT ---
    secret_key: str = Field(default="dev-secret")
    access_token_expire_minutes: int = Field(default=60)

    # --- Divers ---
    seed_on_start: bool = Field(default=False)
    debug: bool = Field(default=True)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

settings = Settings()

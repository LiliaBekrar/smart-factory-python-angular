from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./smart_factory.db"  # fallback pour dev
    SECRET_KEY: str = "dev-secret"                 # valeur par défaut en dev
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60          # par défaut 60 min

    # Pydantic v2: lit .env et ignore les champs non déclarés
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",            # <- évite l'erreur 'extra_forbidden'
        case_sensitive=False,
    )

# instance unique
settings = Settings()

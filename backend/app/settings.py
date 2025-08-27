from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./smart_factory.db"  # fallback pour dev

    class Config:
        env_file = ".env"

settings = Settings()

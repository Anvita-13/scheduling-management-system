import json
from functools import lru_cache
from typing import Annotated, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "College Scheduling Management System"
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/scheduling"
    SECRET_KEY: str = "change-me-in-.env"  # never commit a real secret
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    BCRYPT_ROUNDS: int = 12
    # NoDecode: accept a plain comma-separated string from .env (parsed by the validator below);
    # a JSON list such as ["http://a","http://b"] is accepted too.
    CORS_ORIGINS: Annotated[List[str], NoDecode] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # True on a shared public demo: nobody can change the sample accounts' names, e-mails or passwords.
    LOCK_ACCOUNT_CHANGES: bool = False

    DEFAULT_CLASS_CAPACITY: int = 30
    DEFAULT_MIN_CREDITS: int = 12
    DEFAULT_MAX_CREDITS: int = 24

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalise_database_url(cls, v: str) -> str:
        # Hosting providers hand out `postgres://` or `postgresql://`; SQLAlchemy needs the driver named explicitly.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg2://" + v[len(prefix):]
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

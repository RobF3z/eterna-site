from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379"
    secret_key: str
    openai_api_key: str = ""
    elevenlabs_api_key: str = ""  # Phase 2 — slot reserved
    r2_access_key: str = ""
    r2_secret_key: str = ""
    r2_bucket_name: str = ""
    sentry_dsn: str = ""
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

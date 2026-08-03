"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    application_name: str = "AegisOps AI"
    version: str = "0.1.0"
    description: str = "Human-supervised crisis recommendation API"

    environment: str = "development"
    debug: bool = False

    api_v1_str: str = "/api/v1"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    secret_key: str = Field(default="CHANGE_ME_TO_A_COMPLEX_SECRET", env="SECRET_KEY")
    access_token_expire_minutes: int = 60 * 24 * 8
    algorithm: str = "HS256"

    database_url: str = "sqlite:///./aegisops.db"
    knowledge_base_path: Path = Path(__file__).parent.parent / "knowledge"
    rate_limit: str = "100/minute"

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
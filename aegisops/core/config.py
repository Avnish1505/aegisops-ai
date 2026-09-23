"""Application configuration.

Every field is read from an ``AEGISOPS_``-prefixed environment variable (case-insensitive),
for example ``AEGISOPS_DATABASE_URL`` or ``aegisops_debug``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    application_name: str = "AegisOps AI"
    version: str = "0.1.0"
    description: str = "Human-supervised crisis recommendation API"

    environment: str = "development"
    debug: bool = False

    api_v1_str: str = "/api/v1"
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    secret_key: str = "CHANGE_ME_TO_A_COMPLEX_SECRET"
    access_token_expire_minutes: int = 60 * 24 * 8
    algorithm: str = "HS256"

    database_url: str = "sqlite:///./aegisops.db"
    knowledge_base_path: Path = REPOSITORY_ROOT / "knowledge"
    rate_limit: str = "100/minute"

    model_config = SettingsConfigDict(
        env_prefix="AEGISOPS_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_comma_separated_origins(cls, value: object) -> object:
        """Accept ``a,b`` from the environment as well as a list from code."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

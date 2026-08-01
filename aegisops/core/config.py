"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    # Application
    application_name: str = "AegisOps AI"
    version: str = "0.1.0"
    description: str = "Human-supervised crisis recommendation API"
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")

    # API
    api_v1_str: str = "/api/v1"
    cors_origins: list[AnyHttpUrl] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # Security
    secret_key: str = Field(default="CHANGE_ME_TO_A_COMPLEX_SECRET", env="SECRET_KEY")
    access_token_expire_minutes: int = 60 * 24 * 8  # 8 days
    algorithm: str = "HS256"

    # Database
    database_url: str = Field(
        default="sqlite:///./aegisops.db",
        env="DATABASE_URL",
        description="Database connection URL",
    )

    # Knowledge base
    knowledge_base_path: Path = Path(__file__).parent.parent / "knowledge"

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @classmethod
    def from_environment(cls) -> Settings:
        """Create settings instance from environment variables."""
        return cls()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

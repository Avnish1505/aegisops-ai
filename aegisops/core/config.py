"""Application configuration.

Every field is read from an ``AEGISOPS_``-prefixed environment variable (case-insensitive),
for example ``AEGISOPS_DATABASE_URL`` or ``aegisops_debug``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
# Published development key: create_app refuses to use it outside development and tests.
DEFAULT_SECRET_KEY = "aegisops-development-only-hs256-key-do-not-deploy"


class Settings(BaseSettings):
    application_name: str = "AegisOps AI"
    version: str = "0.1.0"
    description: str = "Human-supervised crisis recommendation API"

    # Safe default: development-only features (such as minting tokens) need an explicit opt-in.
    environment: str = "production"
    debug: bool = False

    api_v1_str: str = "/api/v1"
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    secret_key: str = DEFAULT_SECRET_KEY
    jwt_algorithm: Literal["HS256", "RS256"] = "HS256"
    jwt_jwks_url: str | None = None
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_role_claim: str = "role"
    jwt_leeway_s: int = 30
    dev_token_ttl_s: int = 8 * 60 * 60

    database_url: str = "sqlite:///./aegisops.db"
    knowledge_base_path: Path = REPOSITORY_ROOT / "knowledge"
    rate_limit: str = "100/minute"
    # OSRM base URL (e.g. http://osrm:5000). Unset: straight-line travel times.
    osrm_url: str | None = None
    osrm_profile: str = "driving"

    # LLM (aegisops/llm/client.py): any OpenAI-compatible endpoint; NVIDIA NIM by default.
    llm_base_url: str = "https://integrate.api.nvidia.com/v1"
    llm_model: str = "nvidia/llama-3.1-nemotron-70b-instruct"
    llm_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("AEGISOPS_LLM_API_KEY", "NVIDIA_API_KEY")
    )
    llm_provider: Literal["auto", "nvidia", "openai"] = "auto"
    llm_timeout_s: float = 60.0
    llm_max_retries: int = 2
    # Cost estimates only. NIM's hosted API runs on trial credits without a per-token price, so
    # the default is the OpenRouter list price for meta-llama/llama-3.3-70b-instruct on
    # 2026-09-23 (USD per million tokens). Set your own for other providers.
    llm_price_in_usd_per_mtok: float = 0.10
    llm_price_out_usd_per_mtok: float = 0.32
    # Record/replay LLM HTTP traffic (tests, the CI smoke eval): off | record | replay.
    llm_cassette_mode: Literal["off", "record", "replay"] = "off"
    llm_cassette_dir: Path | None = None

    # OpenTelemetry: OTLP/HTTP base URL (e.g. Arize Phoenix at http://phoenix:6006). Unset means
    # no exporter, and the OpenTelemetry API stays a no-op.
    otel_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AEGISOPS_OTEL_ENDPOINT", "OTEL_EXPORTER_OTLP_ENDPOINT"),
    )
    otel_service_name: str = "aegisops-api"

    # Committed evaluation outputs (reports/*.json) served to the console's Evals page.
    reports_dir: Path = REPOSITORY_ROOT / "reports"

    # Hazard-feed ingestion (aegisops/ingestion/worker.py).
    ingest_sachet_rss_url: str = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"
    ingest_usgs_url: str = (
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    )
    ingest_gdacs_url: str = (
        "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist=EQ;TC;FL;VO;DR;WF"
    )
    ingest_sachet_interval_min: int = 5
    ingest_usgs_interval_min: int = 5
    ingest_gdacs_interval_min: int = 15
    ingest_max_cap_per_poll: int = 100
    ingest_timeout_s: float = 20.0
    ingest_user_agent: str = (
        "AegisOps research platform (non-operational; github.com/Avnish1505/aegisops-ai)"
    )

    model_config = SettingsConfigDict(
        env_prefix="AEGISOPS_",
        populate_by_name=True,
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

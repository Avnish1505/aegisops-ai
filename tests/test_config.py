from pathlib import Path

import pytest
from auth_helpers import bearer
from fastapi.testclient import TestClient

from aegisops.api.app import create_app
from aegisops.core.config import Settings


def test_settings_read_aegisops_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGISOPS_DEBUG", "true")
    monkeypatch.setenv("AEGISOPS_DATABASE_URL", "sqlite:////tmp/prefixed.db")
    monkeypatch.setenv("AEGISOPS_RATE_LIMIT", "5/minute")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.debug is True
    assert settings.database_url == "sqlite:////tmp/prefixed.db"
    assert settings.rate_limit == "5/minute"


def test_settings_ignore_unprefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/unprefixed.db")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.debug is False
    assert settings.database_url == "sqlite:///./aegisops.db"


def test_settings_prefix_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("aegisops_environment", "staging")

    assert Settings(_env_file=None).environment == "staging"  # type: ignore[call-arg]


def test_cors_origins_accept_comma_separated_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AEGISOPS_CORS_ORIGINS", "http://localhost:5173, https://console.example.test ,"
    )

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.cors_origins == ["http://localhost:5173", "https://console.example.test"]


def test_knowledge_base_path_is_repository_knowledge_directory() -> None:
    path = Settings(_env_file=None).knowledge_base_path  # type: ignore[call-arg]

    assert path == Path(__file__).resolve().parents[1] / "knowledge"
    assert sorted(path.glob("*.md"))


def test_app_retrieves_from_configured_knowledge_base(tmp_path: Path) -> None:
    (tmp_path / "only.md").write_text("configured corpus marker", encoding="utf-8")
    app = create_app(
        Settings(environment="test", database_url="sqlite://", knowledge_base_path=tmp_path)
    )

    response = TestClient(app, headers=bearer()).post(
        "/api/v1/decisions?engine=llm_rag", json={"seed": 1}
    )

    descriptions = [item["description"] for item in response.json()["evidence"]]
    assert descriptions and all("configured corpus marker" in text for text in descriptions)

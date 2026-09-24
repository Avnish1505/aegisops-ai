"""Public demo: fixed identities with server-set roles, and the sandbox reset."""

from pathlib import Path

import jwt
import pytest
from alembic import command
from alembic.config import Config
from auth_helpers import APPROVE
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from aegisops.api.app import create_app
from aegisops.core.config import Settings
from backend.db.models import Approval, Decision, Event, Exercise, IntakeReport
from backend.demo_reset import reset_demo

SECRET = "demo-test-secret-key-that-is-long-enough-000000"


def _settings(database_url: str = "sqlite://", **extra: object) -> Settings:
    return Settings(environment="demo", database_url=database_url, secret_key=SECRET,
                    demo_reset_interval_min=0, **extra)


@pytest.fixture()
def database(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'demo.db'}"
    config = Config(str(Path(__file__).parents[1] / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return url


def test_demo_refuses_the_published_development_key() -> None:
    with pytest.raises(RuntimeError, match="development default"):
        create_app(Settings(environment="demo", database_url="sqlite://"))


def test_demo_tokens_only_for_fixed_identities_with_server_set_roles(database: str) -> None:
    client = TestClient(create_app(_settings(database)))

    operator = client.post("/api/v1/demo/token", json={"sub": "demo-operator", "role": "admin"})
    stranger = client.post("/api/v1/demo/token", json={"sub": "mallory"})
    dev = client.post("/api/v1/dev/token", json={"sub": "x", "role": "admin"})

    claims = jwt.decode(operator.json()["access_token"], SECRET, algorithms=["HS256"])
    assert claims["sub"] == "demo-operator" and claims["role"] == "operator"
    assert operator.json()["expires_in"] == 7200
    assert stranger.status_code == 422 and dev.status_code == 404


def test_reset_wipes_visitor_changes_and_reseeds(database: str) -> None:
    settings = _settings(database)
    reset_demo(settings)
    client = TestClient(create_app(settings))
    tokens = {sub: client.post("/api/v1/demo/token", json={"sub": sub}).json()["access_token"]
              for sub in ("demo-operator", "demo-approver")}
    decision = client.post("/api/v1/decisions", json={"seed": 3},
                           headers={"Authorization": f"Bearer {tokens['demo-operator']}"}).json()
    client.post(f"/api/v1/decisions/{decision['decision_id']}/disposition", json=APPROVE,
                headers={"Authorization": f"Bearer {tokens['demo-approver']}"})

    seeded = reset_demo(settings)

    with Session(create_engine(database)) as session:
        count = lambda model: session.scalar(select(func.count()).select_from(model))  # noqa: E731
        assert (count(Decision), count(Approval), count(Exercise)) == (1, 0, 1)
        assert count(IntakeReport) == 10
        assert session.get(Decision, seeded) is not None
        types = [e.type for e in session.scalars(select(Event).order_by(Event.id))]
    assert types[:2] == ["decision_created", "verification_completed"]
    status = client.get("/api/v1/status",
                        headers={"Authorization": f"Bearer {tokens['demo-operator']}"}).json()
    assert status["demo"]["interval_min"] == 0 and status["demo"]["next_reset_at"]

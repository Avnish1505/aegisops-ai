from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from aegisops.api.app import create_app
from aegisops.application.scenario_service import generate_scenario
from aegisops.core.config import Settings
from aegisops.domain.models import Scenario
from aegisops.infrastructure.rule_based_engine import RuleBasedDecisionEngine
from backend.db.models import Approval, AuditLog, Decision
from backend.seed import DEMO_SEED, seed


def _migrated_client(tmp_path: Path) -> tuple[TestClient, str]:
    database_url = f"sqlite:///{tmp_path / 'aegisops.db'}"
    config = Config(str(Path(__file__).parents[1] / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return (
        TestClient(
            create_app(
                Settings(
                    environment="test",
                    database_url=database_url,
                    cors_origins=("http://testserver",),
                )
            )
        ),
        database_url,
    )


def _approved_scenario() -> dict[str, object]:
    return {
        "scenario_id": "SCEN-approved",
        "incidents": [
            {
                "id": "INC-1",
                "type": "medical",
                "severity": "low",
                "location": [0, 0],
                "people_affected": 1,
                "reported_at_min": 0,
                "resources_needed": {"ambulance": 1},
            }
        ],
        "resources": [
            {
                "id": "RES-1",
                "type": "ambulance",
                "location": [0, 0],
                "available": True,
            }
        ],
    }


def _blocked_scenario() -> dict[str, object]:
    return {
        "scenario_id": "SCEN-blocked",
        "incidents": [
            {
                "id": "INC-1",
                "type": "medical",
                "severity": "critical",
                "location": [0, 0],
                "people_affected": 1,
                "reported_at_min": 0,
                "resources_needed": {"ambulance": 1},
            }
        ],
        "resources": [],
    }


def test_persists_decision_approval_and_audit(tmp_path: Path) -> None:
    client, database_url = _migrated_client(tmp_path)

    decision_response = client.post("/api/v1/decisions", json={"scenario": _approved_scenario()})
    assert decision_response.status_code == 200
    decision_id = decision_response.json()["decision_id"]
    disposition_response = client.post(
        f"/api/v1/decisions/{decision_id}/disposition",
        json={"action": "approve", "reason": "Synthetic scenario reviewed."},
    )

    assert disposition_response.status_code == 200
    with Session(create_engine(database_url)) as session:
        decision = session.get(Decision, decision_id)
        approval = session.scalar(select(Approval).where(Approval.decision_id == decision_id))
        audit = session.scalar(
            select(AuditLog).where(
                AuditLog.record_id == str(decision_id), AuditLog.action == "decision_approved"
            )
        )

    assert decision is not None
    assert approval is not None and approval.approved is True
    assert audit is not None
    assert audit.change_data == {
        "actor": "operator",
        "action": "approve",
        "reason": "Synthetic scenario reviewed.",
    }
    assert audit.timestamp is not None


def test_blocked_decision_cannot_be_approved_or_create_disposition(tmp_path: Path) -> None:
    client, database_url = _migrated_client(tmp_path)

    decision_response = client.post("/api/v1/decisions", json={"scenario": _blocked_scenario()})
    assert decision_response.status_code == 200
    decision_id = decision_response.json()["decision_id"]
    assert decision_response.json()["status"] == "blocked"
    disposition_response = client.post(
        f"/api/v1/decisions/{decision_id}/disposition",
        json={"action": "approve", "reason": "Attempted approval."},
    )

    assert disposition_response.status_code == 409
    with Session(create_engine(database_url)) as session:
        approval = session.scalar(select(Approval).where(Approval.decision_id == decision_id))
        disposition_audit = session.scalar(
            select(AuditLog).where(
                AuditLog.record_id == str(decision_id), AuditLog.action == "decision_approved"
            )
        )

    assert approval is None
    assert disposition_audit is None


def test_migrations_target_database_from_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "from-settings.db"
    monkeypatch.setenv("AEGISOPS_DATABASE_URL", f"sqlite:///{database_path}")

    command.upgrade(Config(str(Path(__file__).parents[1] / "backend" / "alembic.ini")), "head")

    assert "decisions" in inspect(create_engine(f"sqlite:///{database_path}")).get_table_names()


def test_get_decision_returns_full_record_and_approvals(tmp_path: Path) -> None:
    client, _ = _migrated_client(tmp_path)
    created = client.post("/api/v1/decisions", json={"scenario": _approved_scenario()}).json()
    decision_id = created["decision_id"]
    client.post(
        f"/api/v1/decisions/{decision_id}/disposition",
        json={"action": "approve", "reason": "Synthetic scenario reviewed."},
    )

    response = client.get(
        f"/api/v1/decisions/{decision_id}", headers={"Authorization": "Bearer role:viewer"}
    )

    assert response.status_code == 200
    record = response.json()
    scenario = Scenario.model_validate(_approved_scenario())
    assert record["scenario"] == scenario.model_dump(mode="json")
    assert record["scenario_sha256"] == scenario.sha256()
    for field in (
        "engine",
        "status",
        "assignments",
        "unmet_requirements",
        "safety_findings",
        "evidence",
        "decision_trace",
        "prompt_version",
        "model_version",
    ):
        assert record[field] == created[field], field
    assert [(a["action"], a["actor"]) for a in record["approvals"]] == [
        ("approve", "development-operator")
    ]


def test_stored_decision_replays_to_the_same_plan(tmp_path: Path) -> None:
    client, _ = _migrated_client(tmp_path)
    decision_id = client.post("/api/v1/decisions", json={"seed": 11}).json()["decision_id"]

    record = client.get(f"/api/v1/decisions/{decision_id}").json()
    stored_scenario = Scenario.model_validate(record["scenario"])
    replayed = RuleBasedDecisionEngine().recommend(stored_scenario).model_dump(mode="json")

    assert stored_scenario.sha256() == record["scenario_sha256"]
    assert replayed["assignments"] == record["assignments"]
    assert replayed["unmet_requirements"] == record["unmet_requirements"]
    assert replayed["safety_findings"] == record["safety_findings"]


def test_get_unknown_decision_returns_404(tmp_path: Path) -> None:
    client, _ = _migrated_client(tmp_path)

    assert client.get("/api/v1/decisions/999").status_code == 404


def test_seed_records_one_demo_decision_and_is_idempotent(tmp_path: Path) -> None:
    client, database_url = _migrated_client(tmp_path)

    first = seed(database_url)
    second = seed(database_url)

    assert first is not None
    assert second is None
    record = client.get(f"/api/v1/decisions/{first}").json()
    assert record["scenario"] == generate_scenario(seed=DEMO_SEED).model_dump(mode="json")
    assert record["status"] in {"blocked", "requires_human_approval"}

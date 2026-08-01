from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from aegisops.api.app import create_app
from aegisops.core.config import Settings
from backend.db.models import Approval, AuditLog, Decision


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

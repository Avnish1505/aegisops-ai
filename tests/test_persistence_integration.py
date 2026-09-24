from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from auth_helpers import APPROVE, bearer
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from aegisops.api.app import create_app
from aegisops.application.scenario_service import generate_scenario
from aegisops.core.config import Settings
from aegisops.domain.models import Scenario
from aegisops.planning.solver import SolverDecisionEngine, solve
from aegisops.planning.travel import TravelTimeMatrix
from aegisops.verification.models import TextDraft
from aegisops.verification.verifier import verify
from backend.db.models import Approval, Decision, Event
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
            ),
            headers=bearer("alice", "operator"),
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
                "location": {"lat": 26.8, "lon": 80.9},
                "people_affected": 1,
                "reported_at_min": 0,
                "resources_needed": {"ambulance": 1},
            }
        ],
        "resources": [
            {
                "id": "RES-1",
                "type": "ambulance",
                "location": {"lat": 26.8, "lon": 80.9},
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
                "location": {"lat": 26.8, "lon": 80.9},
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
        json={**APPROVE, "reason": "Synthetic scenario reviewed."},
        headers=bearer("bob", "approver"),
    )

    assert disposition_response.status_code == 200
    with Session(create_engine(database_url)) as session:
        decision = session.get(Decision, decision_id)
        approval = session.scalar(select(Approval).where(Approval.decision_id == decision_id))
        events = session.scalars(select(Event).order_by(Event.id)).all()

    assert decision is not None
    assert approval is not None and approval.approved is True
    assert [event.type for event in events] == [
        "decision_created",
        "verification_completed",
        "disposition_recorded",
    ]
    assert events[2].payload["action"] == "approve"
    assert events[2].payload["reason"] == "Synthetic scenario reviewed."
    assert events[2].payload["decision_id"] == decision_id


def test_blocked_decision_cannot_be_approved_or_create_disposition(tmp_path: Path) -> None:
    client, database_url = _migrated_client(tmp_path)

    decision_response = client.post("/api/v1/decisions", json={"scenario": _blocked_scenario()})
    assert decision_response.status_code == 200
    decision_id = decision_response.json()["decision_id"]
    assert decision_response.json()["status"] == "blocked"
    disposition_response = client.post(
        f"/api/v1/decisions/{decision_id}/disposition",
        json={**APPROVE, "reason": "Attempted approval."},
        headers=bearer("bob", "approver"),
    )

    assert disposition_response.status_code == 409
    with Session(create_engine(database_url)) as session:
        approval = session.scalar(select(Approval).where(Approval.decision_id == decision_id))
        dispositions = session.scalars(
            select(Event).where(Event.type == "disposition_recorded")
        ).all()

    assert approval is None
    assert dispositions == []


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
        json={**APPROVE, "reason": "Synthetic scenario reviewed."},
        headers=bearer("bob", "approver"),
    )

    response = client.get(f"/api/v1/decisions/{decision_id}", headers=bearer("vic", "viewer"))

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
    assert record["proposer_sub"] == "alice"
    assert [(a["action"], a["actor"]) for a in record["approvals"]] == [("approve", "bob")]


def test_stored_decision_replays_and_reverifies_to_the_same_result(tmp_path: Path) -> None:
    client, _ = _migrated_client(tmp_path)
    decision_id = client.post("/api/v1/decisions", json={"seed": 11}).json()["decision_id"]

    record = client.get(f"/api/v1/decisions/{decision_id}").json()
    scenario = Scenario.model_validate(record["scenario"])
    matrix = TravelTimeMatrix.model_validate(record["travel_times"])
    replayed = solve(scenario, matrix)
    plan = SolverDecisionEngine().result_from_solve(scenario, replayed)
    report = verify(
        plan,
        scenario,
        reference_plan=replayed,
        travel_times=matrix,
        text_drafts=[TextDraft.model_validate(draft) for draft in record["drafts"]],
    )

    assert scenario.sha256() == record["scenario_sha256"]
    assert [a.model_dump(mode="json") for a in replayed.assignments] == record["assignments"]
    assert report.model_dump(mode="json") == record["verification"]


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

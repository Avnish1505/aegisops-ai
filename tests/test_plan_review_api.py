"""Plan review backend: required reason codes, baseline without constraints, re-verification."""

import pytest
from auth_helpers import bearer
from fastapi.testclient import TestClient

from aegisops.api.app import create_app
from aegisops.core.config import Settings
from backend.db.models import Approval, Decision, Event

OPERATOR, APPROVER = bearer("olive", "operator"), bearer("bob", "approver")


def _client() -> TestClient:
    return TestClient(create_app(Settings(environment="test", database_url="sqlite://")))


def _decision(client: TestClient, **body: object) -> dict:
    return client.post("/api/v1/decisions", json=body or {"seed": 3}, headers=OPERATOR).json()


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        ({"action": "approve"}, "reason_code"),
        ({"action": "reject", "reason_code": "reviewed_as_proposed"}, "not a reason code for"),
        ({"action": "approve", "reason_code": "eta_incorrect"}, "not a reason code for approve"),
        ({"action": "reject", "reason_code": "other"}, "needs an explanation"),
        ({"action": "reject", "reason_code": "other", "reason": "  "}, "needs an explanation"),
    ],
)
def test_every_disposition_needs_a_reason_code_that_fits_the_action(
    payload: dict, fragment: str
) -> None:
    client = _client()
    decision_id = _decision(client)["decision_id"]

    response = client.post(f"/api/v1/decisions/{decision_id}/disposition", json=payload,
                           headers=APPROVER)

    assert response.status_code == 422
    assert fragment in response.text


def test_reason_code_is_stored_on_the_approval_and_in_the_hashed_event() -> None:
    client = _client()
    decision = _decision(client)
    decision_id = decision["decision_id"]

    response = client.post(f"/api/v1/decisions/{decision_id}/disposition",
                           json={"action": "reject", "reason_code": "eta_incorrect"},
                           headers=APPROVER)

    assert response.status_code == 200 and response.json()["reason_code"] == "eta_incorrect"
    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        approval = session.query(Approval).filter_by(decision_id=decision_id).one()
        event = session.query(Event).filter_by(type="disposition_recorded").one()
    assert approval.reason_code == "eta_incorrect"
    assert event.payload["reason_code"] == "eta_incorrect"
    stored = client.get(f"/api/v1/decisions/{decision_id}", headers=OPERATOR).json()
    assert stored["approvals"][0]["reason_code"] == "eta_incorrect"


def test_reason_codes_endpoint_lists_both_actions() -> None:
    codes = _client().get("/api/v1/reason-codes").json()

    assert "eta_incorrect" in codes["reject"] and "reviewed_as_proposed" in codes["approve"]


def test_baseline_without_constraints_matches_an_unconstrained_plan() -> None:
    client = _client()
    decision_id = _decision(client)["decision_id"]

    body = client.get(f"/api/v1/decisions/{decision_id}/baseline", headers=OPERATOR).json()

    assert body["constraints"] == 0 and body["same_as_plan"] is True
    assert body["only_in_plan"] == [] and body["only_in_baseline"] == []
    assert body["objective"] == pytest.approx(body["plan_objective"])


def test_baseline_shows_what_an_exclude_constraint_changed() -> None:
    client = _client()
    first = _decision(client)
    used = first["assignments"][0]["resource_id"]
    constrained = _decision(client, scenario=first["scenario"],
                            constraints=[{"kind": "exclude_unit", "unit_id": used}])

    body = client.get(f"/api/v1/decisions/{constrained['decision_id']}/baseline",
                      headers=OPERATOR).json()

    assert body["constraints"] == 1 and body["same_as_plan"] is False
    assert used in {pair["resource_id"] for pair in body["only_in_baseline"]}
    assert used not in {pair["resource_id"] for pair in body["only_in_plan"]}
    assert body["plan_objective"] >= body["objective"]


def test_reverify_reproduces_the_stored_report_and_is_audited() -> None:
    client = _client()
    decision_id = _decision(client)["decision_id"]

    body = client.post(f"/api/v1/decisions/{decision_id}/reverify", headers=bearer("v", "viewer"))

    result = body.json()
    assert result["matches"] is True and result["differing_checks"] == []
    assert result["scenario_sha256_matches"] is True
    events = client.get(f"/api/v1/events?decision_id={decision_id}", headers=OPERATOR).json()
    assert events[0]["type"] == "reverification_run" and events[0]["actor"] == "v"


def test_reverify_catches_a_travel_time_edited_in_the_database() -> None:
    client = _client()
    decision_id = _decision(client)["decision_id"]
    with client.app.state.session_factory.begin() as session:  # type: ignore[attr-defined]
        decision = session.get(Decision, decision_id)
        assert decision is not None and decision.assignments
        edited = [dict(a) for a in decision.assignments]
        edited[0]["travel_minutes"] = float(edited[0]["travel_minutes"]) + 30  # type: ignore[arg-type]
        decision.assignments = edited

    result = client.post(f"/api/v1/decisions/{decision_id}/reverify", headers=OPERATOR).json()

    assert result["matches"] is False
    assert "travel_time_matches" in result["differing_checks"]
    assert result["recomputed"]["verdict"] == "blocked"


def test_unknown_decision_is_404_for_baseline_and_reverify() -> None:
    client = _client()

    assert client.get("/api/v1/decisions/99/baseline", headers=OPERATOR).status_code == 404
    assert client.post("/api/v1/decisions/99/reverify", headers=OPERATOR).status_code == 404


def test_validation_errors_name_the_field_but_never_echo_submitted_values() -> None:
    client = _client()
    decision_id = _decision(client)["decision_id"]

    response = client.post(f"/api/v1/decisions/{decision_id}/disposition",
                           json={"action": "reject", "reason_code": "SECRET-CODE-123"},
                           headers=APPROVER)

    assert response.status_code == 422
    assert response.json()["errors"][0]["message"].startswith("'SECRET-CODE-123' is not")
    # The code is quoted back by our own message; the raw input field is not.
    assert "input" not in response.json()["errors"][0]


def test_constraint_sources_are_stored_next_to_their_constraints() -> None:
    client = _client()
    first = _decision(client)
    unit = first["assignments"][0]["resource_id"]
    source = {"note": f"{unit} ko rok ke rakho", "quote": "rok ke rakho"}

    made = _decision(client, scenario=first["scenario"],
                     constraints=[{"kind": "exclude_unit", "unit_id": unit}],
                     constraint_sources=[source])
    mismatched = client.post("/api/v1/decisions", headers=OPERATOR, json={
        "scenario": first["scenario"], "constraints": [], "constraint_sources": [source]})

    assert made["constraint_sources"] == [source]
    assert first["constraint_sources"] == []
    assert mismatched.status_code == 422

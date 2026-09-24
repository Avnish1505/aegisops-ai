"""User study: task construction, counterbalancing, sessions, timing and the CSV export."""

import csv
import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from auth_helpers import bearer
from fastapi.testclient import TestClient

from aegisops.api.app import create_app
from aegisops.core.config import Settings
from aegisops.domain.models import Scenario
from aegisops.planning.travel import StraightLineProvider
from aegisops.study.results import score
from aegisops.study.tasks import SETS, TaskSpec, build_task, session_plan
from backend.db.models import Exercise

EXERCISE = Scenario.model_validate_json(
    (Path(__file__).parents[1] / "evals" / "data" / "lucknow_exercise_v1.json").read_text()
)
EXPECTED_CHECK = {"wrong_eta": "travel_time_matches", "phantom_unit": "unit_exists",
                  "sitrep_mismatch": "draft_numbers_match_state"}


@pytest.mark.parametrize(("set_name", "position"),
                         [(s, p) for s in SETS for p in range(1, 7)])
def test_clean_tasks_pass_and_injected_tasks_fail_their_check(set_name: str, position: int) -> None:
    spec = TaskSpec(set_name, position, SETS[set_name][position - 1])

    _, outcome = build_task(EXERCISE, spec, StraightLineProvider())

    failed = {check.id for check in outcome.verification.failed()}
    if spec.error is None:
        assert failed == set() and outcome.result.status.value == "requires_human_approval"
    else:
        assert EXPECTED_CHECK[spec.error] in failed
        assert outcome.result.status.value == "blocked"


def test_sets_have_three_errors_each_of_every_kind() -> None:
    for errors in SETS.values():
        assert sorted(e for e in errors if e) == ["phantom_unit", "sitrep_mismatch", "wrong_eta"]


def test_counterbalancing_alternates_interface_order_and_set() -> None:
    first = {n: (session_plan(n)[0].ui, session_plan(n)[0].spec.set_name) for n in range(1, 5)}

    assert first == {1: ("legacy", "A"), 2: ("console", "B"), 3: ("legacy", "B"),
                     4: ("console", "A")}
    for n in range(1, 5):
        plan = session_plan(n)
        assert [t.order for t in plan] == list(range(1, 13))
        assert {t.ui for t in plan[:6]} != {t.ui for t in plan[6:]}
        assert {t.spec.set_name for t in plan[:6]} != {t.spec.set_name for t in plan[6:]}


def test_scoring_times_decisions_and_counts_a_catch_only_with_the_right_code() -> None:
    start = datetime(2026, 9, 24, 6, 0, 0, tzinfo=UTC)
    common = dict(participant="P01", participant_number=1, order=2, ui="legacy", task="A2",
                  injected_error="wrong_eta", expected_action="reject",
                  expected_reason="eta_incorrect", decision_id=9, started_at=start)

    right = score(**common, action="reject", reason_code="eta_incorrect",  # type: ignore[arg-type]
                  decided_at=datetime(2026, 9, 24, 6, 0, 42, 500000))
    vague = score(**common, action="reject", reason_code="better_plan_needed",  # type: ignore[arg-type]
                  decided_at=datetime(2026, 9, 24, 6, 1, 0))
    open_ = score(**common, action=None, reason_code=None, decided_at=None)  # type: ignore[arg-type]

    assert (right.correct, right.caught, right.time_to_decision_s) == (True, True, 42.5)
    assert (vague.correct, vague.caught) == (True, False)
    assert (open_.correct, open_.caught, open_.time_to_decision_s) == (None, None, None)


def _client() -> TestClient:
    client = TestClient(create_app(Settings(environment="test", database_url="sqlite://")))
    with client.app.state.session_factory.begin() as session:  # type: ignore[attr-defined]
        session.add(Exercise(id="EX", name="x", description="x",
                             scenario=EXERCISE.model_dump(mode="json"),
                             scenario_sha256=EXERCISE.sha256()))
    return client


def test_a_session_runs_twelve_tasks_and_exports_the_results() -> None:
    client = _client()
    moderator, participant = bearer("olive", "operator"), bearer("alice", "approver")

    created = client.post("/api/v1/study/sessions", json={"participant": "P01"},
                          headers=moderator).json()
    again = client.post("/api/v1/study/sessions", json={"participant": "P01"}, headers=moderator)
    tasks = created["tasks"]
    first, second = tasks[0], tasks[1]  # A1 (clean) then A2 (wrong ETA), both in legacy
    client.post(f"/api/v1/study/tasks/{first['id']}/start", headers=participant)
    client.post(f"/api/v1/decisions/{first['decision_id']}/disposition", headers=participant,
                json={"action": "approve", "reason_code": "reviewed_as_proposed"})
    client.post(f"/api/v1/study/tasks/{second['id']}/start", headers=participant)
    client.post(f"/api/v1/decisions/{second['decision_id']}/disposition", headers=participant,
                json={"action": "reject", "reason_code": "eta_incorrect"})
    export = client.get("/api/v1/study/export.csv", headers=moderator)
    rows = list(csv.DictReader(io.StringIO(export.text)))

    assert again.status_code == 409
    assert len(tasks) == 12 and [t["ui"] for t in tasks[:6]] == ["legacy"] * 6
    stored = client.get(f"/api/v1/decisions/{first['decision_id']}", headers=moderator).json()
    assert stored["proposer_sub"] == "study-proposer"
    assert export.headers["content-type"].startswith("text/csv") and len(rows) == 12
    assert (rows[0]["task"], rows[0]["correct"], rows[0]["caught"]) == ("A1", "True", "")
    assert (rows[1]["task"], rows[1]["caught"]) == ("A2", "True")
    assert float(rows[1]["time_to_decision_s"]) >= 0
    assert rows[2]["action"] == "" and rows[2]["time_to_decision_s"] == ""


def test_participant_codes_are_validated() -> None:
    response = _client().post("/api/v1/study/sessions", json={"participant": "alice"},
                              headers=bearer("olive", "operator"))

    assert response.status_code == 422

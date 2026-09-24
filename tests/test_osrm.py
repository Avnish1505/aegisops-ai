"""OSRMProvider against a recorded response from the Lucknow graph. No network access."""

import json
from pathlib import Path

import httpx
import pytest
from auth_helpers import bearer
from fastapi.testclient import TestClient

from aegisops.api.app import create_app
from aegisops.application.decision_service import DecisionService
from aegisops.core.config import Settings
from aegisops.domain.models import Scenario
from aegisops.planning.osrm import OSRMProvider
from aegisops.planning.travel import StraightLineProvider
from aegisops.verification.verifier import verify

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "osrm" / "table_lucknow.json").read_text()
)
SCENARIO = Scenario.model_validate(FIXTURE["scenario"])
BASE = "http://osrm.test:5000"


class Recorder:
    """httpx transport that replays the recorded table response and counts requests."""

    def __init__(self, response: httpx.Response | None = None, error: Exception | None = None):
        self.requests: list[httpx.Request] = []
        self._response = response
        self._error = error

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        return self._response or httpx.Response(200, json=FIXTURE["response"])


def _provider(recorder: Recorder) -> OSRMProvider:
    return OSRMProvider(BASE, client=httpx.Client(transport=httpx.MockTransport(recorder)))


def test_table_request_uses_lon_lat_order_and_sources_destinations() -> None:
    recorder = Recorder()

    _provider(recorder).matrix(SCENARIO)

    request = recorder.requests[0]
    assert request.url.path == FIXTURE["request"]["path"]
    assert dict(request.url.params) == FIXTURE["request"]["params"]
    assert request.url.path.split("/")[-1].startswith("80.921900,26.832000;")


def test_durations_become_minutes_per_resource_and_incident() -> None:
    matrix = _provider(Recorder()).matrix(SCENARIO)

    durations = FIXTURE["response"]["durations"]
    assert matrix.provider == "osrm-driving"
    assert matrix.degraded is False
    assert matrix.get("RES-charbagh-boat", "INC-aminabad") == pytest.approx(durations[0][0] / 60)
    assert matrix.get("RES-aliganj-amb", "INC-chowk") == pytest.approx(durations[2][1] / 60)


def test_matrices_are_cached_by_input_hash() -> None:
    recorder = Recorder()
    provider = _provider(recorder)
    moved = SCENARIO.model_copy(
        update={
            "resources": [
                SCENARIO.resources[0].model_copy(
                    update={"location": SCENARIO.resources[0].location.model_copy(
                        update={"lat": 26.8321})}
                ),
                *SCENARIO.resources[1:],
            ]
        }
    )

    first = provider.matrix(SCENARIO)
    second = provider.matrix(SCENARIO)
    provider.matrix(moved)

    assert first is second
    assert len(recorder.requests) == 2
    assert provider.cache_key(SCENARIO) != provider.cache_key(moved)


@pytest.mark.parametrize(
    "recorder",
    [
        Recorder(error=httpx.ConnectError("connection refused")),
        Recorder(response=httpx.Response(503, text="overloaded")),
        Recorder(response=httpx.Response(200, json={"code": "InvalidQuery", "message": "x"})),
        Recorder(response=httpx.Response(200, text="not json")),
    ],
    ids=["down", "http-503", "osrm-error", "garbage"],
)
def test_osrm_failure_falls_back_to_straight_line_and_is_marked_degraded(
    recorder: Recorder,
) -> None:
    provider = _provider(recorder)

    matrix = provider.matrix(SCENARIO)
    provider.matrix(SCENARIO)

    straight = StraightLineProvider().matrix(SCENARIO)
    assert matrix.degraded is True
    assert matrix.degraded_reason is not None and "OSRM unavailable" in matrix.degraded_reason
    assert matrix.minutes == straight.minutes
    assert len(recorder.requests) == 2  # degraded results are never cached


def test_unroutable_pairs_fall_back_per_pair_and_mark_degraded() -> None:
    body = json.loads(json.dumps(FIXTURE["response"]))
    body["durations"][1][0] = None

    matrix = _provider(Recorder(response=httpx.Response(200, json=body))).matrix(SCENARIO)

    straight = StraightLineProvider().matrix(SCENARIO)
    assert matrix.degraded is True
    assert "could not route 1 of 6" in (matrix.degraded_reason or "")
    assert matrix.get("RES-hazratganj-amb", "INC-aminabad") == straight.get(
        "RES-hazratganj-amb", "INC-aminabad"
    )
    assert matrix.get("RES-charbagh-boat", "INC-aminabad") == pytest.approx(181.7 / 60)


def test_solver_plans_on_osrm_and_verifier_rechecks_against_it() -> None:
    outcome = DecisionService({}, _provider(Recorder())).decide(SCENARIO)

    boat = next(a for a in outcome.result.assignments if a.resource_id == "RES-charbagh-boat")
    assert boat.travel_minutes == pytest.approx(181.7 / 60, abs=0.01)
    assert outcome.verification.check("travel_time_matches").passed
    assert "osrm-driving" in outcome.verification.check("travel_time_matches").message
    assert outcome.verification.check("travel_times_not_degraded").passed


def test_a_straight_line_eta_is_rejected_when_osrm_is_the_reference() -> None:
    outcome = DecisionService({}, _provider(Recorder())).decide(SCENARIO)
    straight = StraightLineProvider().matrix(SCENARIO)
    plan = outcome.result.model_copy(
        update={
            "assignments": [
                a.model_copy(update={"travel_minutes": straight.get(a.resource_id, a.incident_id)})
                for a in outcome.result.assignments
            ]
        }
    )
    report = verify(
        plan, SCENARIO, reference_plan=outcome.reference, travel_times=outcome.travel_times
    )

    assert "travel_time_matches" in report.blocking_check_ids


def test_api_shows_the_degraded_flag_when_osrm_is_down() -> None:
    provider = _provider(Recorder(error=httpx.ConnectError("down")))
    app = create_app(
        Settings(environment="test", database_url="sqlite://"), travel_provider=provider
    )

    body = TestClient(app, headers=bearer()).post(
        "/api/v1/decisions", json={"scenario": FIXTURE["scenario"]}
    ).json()

    assert body["travel_degraded"] is True
    assert "OSRM unavailable" in body["travel_degraded_reason"]
    failed = {c["id"]: c for c in body["verification"]["checks"] if not c["passed"]}
    assert failed["travel_times_not_degraded"]["severity"] == "high"


def test_settings_select_osrm_when_a_url_is_configured() -> None:
    from aegisops.planning.providers import default_travel_provider

    assert isinstance(default_travel_provider(Settings(osrm_url=BASE)), OSRMProvider)
    assert isinstance(default_travel_provider(Settings()), StraightLineProvider)

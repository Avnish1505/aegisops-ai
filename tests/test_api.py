from auth_helpers import bearer
from fastapi.testclient import TestClient

from aegisops.api.app import create_app
from aegisops.core.config import Settings


def _client() -> TestClient:
    return TestClient(
        create_app(
            Settings(
                environment="test",
                debug=True,
                cors_origins=("http://testserver",),
                database_url="sqlite://",
            )
        ),
        headers=bearer(),
    )


def test_scenario_endpoint_is_reproducible_and_sets_request_id() -> None:
    client = _client()
    first = client.get("/api/v1/scenarios?seed=7", headers={"X-Request-ID": "trace-7"})
    second = client.get("/api/v1/scenarios?seed=7")

    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.headers["X-Request-ID"] == "trace-7"
    assert first.headers["X-Content-Type-Options"] == "nosniff"


def test_decision_endpoint_rejects_unknown_request_fields() -> None:
    response = _client().post("/api/v1/decisions", json={"seed": 2, "unexpected": True})

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed."


def test_decision_endpoint_is_advisory_only() -> None:
    response = _client().post("/api/v1/decisions", json={"seed": 3})

    assert response.status_code == 200
    assert response.json()["requires_human_approval"] is True
    assert response.json()["status"] in {"blocked", "requires_human_approval"}


def test_decision_endpoint_selects_rule_based_engine() -> None:
    response = _client().post("/api/v1/decisions?engine=rule_based", json={"seed": 3})

    assert response.status_code == 200
    assert response.json()["engine"] == "rule_based_baseline_v1"


def test_decision_endpoint_selects_llm_rag_engine(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    response = _client().post("/api/v1/decisions?engine=llm_rag", json={"seed": 3})

    assert response.status_code == 200
    assert response.json()["engine"] == "nvidia_nim_v1"
    assert response.json()["status"] == "blocked"


def test_decision_endpoint_rejects_unknown_engine() -> None:
    response = _client().post("/api/v1/decisions?engine=unknown", json={"seed": 3})

    assert response.status_code == 422



def test_legacy_prototype_routes_are_removed() -> None:
    client = _client()

    assert client.get("/health").status_code == 404
    assert client.get("/scenario?seed=3").status_code == 404
    assert client.post("/simulate", json={"seed": 3}).status_code == 404


def test_decision_reports_coverage_not_advisory_confidence() -> None:
    body = _client().post("/api/v1/decisions", json={"seed": 3}).json()

    assert 0.0 <= body["coverage"] <= 1.0
    assert "advisory_confidence" not in body


def test_every_engine_returns_a_verification_report_and_sitrep() -> None:
    client = _client()
    for engine in ("solver", "rule_based", "llm_rag"):
        body = client.post(f"/api/v1/decisions?engine={engine}", json={"seed": 5}).json()

        assert body["verification"]["verdict"] in {"pass", "blocked"}
        assert {check["id"] for check in body["verification"]["checks"]} >= {
            "unit_exists",
            "travel_time_matches",
            "human_approval_required",
        }
        assert body["drafts"][0]["kind"] == "sitrep"
        assert body["requires_human_approval"] is True


def test_solver_is_the_default_engine_and_passes_its_own_verification() -> None:
    body = _client().post("/api/v1/decisions", json={"seed": 5}).json()

    assert body["engine"] == "cp_sat_v1"
    assert body["solve_status"] == "optimal"
    assert body["objective"] == body["reference_objective"]
    assert [c["id"] for c in body["verification"]["checks"] if not c["passed"]] == []


def test_conflicting_constraints_block_with_an_explanation() -> None:
    scenario = _client().get("/api/v1/scenarios?seed=5").json()
    unit = scenario["resources"][0]
    constraints = [
        {"kind": "exclude_unit", "unit_id": unit["id"]},
        {
            "kind": "reserve",
            "resource_type": unit["type"],
            "count": 1,
            "zone": {
                "id": "pin",
                "min_x": unit["location"][0],
                "min_y": unit["location"][1],
                "max_x": unit["location"][0],
                "max_y": unit["location"][1],
            },
        },
    ]

    body = _client().post(
        "/api/v1/decisions", json={"scenario": scenario, "constraints": constraints}
    ).json()

    assert body["status"] == "blocked"
    assert body["solve_status"] == "infeasible"
    assert "constraints_feasible" in body["verification"]["blocking_check_ids"]
    assert len(body["infeasibility"]["conflicting_constraints"]) == 2


def test_unknown_constraint_kind_is_rejected() -> None:
    response = _client().post(
        "/api/v1/decisions", json={"seed": 1, "constraints": [{"kind": "teleport"}]}
    )

    assert response.status_code == 422

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
        )
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

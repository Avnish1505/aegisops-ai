"""SITREP and CAP drafts: model prose, verified numbers, never published. LLM replies mocked."""

import json

import httpx2
from pydantic import SecretStr

from aegisops.application.scenario_service import generate_scenario
from aegisops.communication.reporter import Reporter
from aegisops.core.config import Settings
from aegisops.ingestion.cap import parse_cap
from aegisops.llm.client import LLMClient
from aegisops.planning.solver import SolverDecisionEngine, solve
from aegisops.planning.travel import StraightLineProvider

SCENARIO = generate_scenario(seed=42)
MATRIX = StraightLineProvider().matrix(SCENARIO)
PLAN = SolverDecisionEngine().result_from_solve(SCENARIO, solve(SCENARIO, MATRIX))
FIRST = PLAN.assignments[0]
ETA = f"{MATRIX.get(FIRST.resource_id, FIRST.incident_id):.1f}"
ASSIGNED = len(PLAN.assignments)


def _client(*replies: dict) -> LLMClient:
    queue = list(replies)

    def handler(request: httpx2.Request) -> httpx2.Response:
        reply = queue.pop(0)
        return httpx2.Response(200, json={
            "id": "c", "object": "chat.completion", "created": 1, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": json.dumps(reply)}}],
            "usage": {"prompt_tokens": 900, "completion_tokens": 250, "total_tokens": 1150},
        })

    return LLMClient(
        Settings(environment="test", llm_api_key=SecretStr("k"), llm_max_retries=0),
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )


def _sections(summary: str) -> dict:
    return {
        "situation_summary": summary,
        "objectives": ["Reach every reported incident with the nearest suitable unit."],
        "actions": [f"{FIRST.incident_id}: {FIRST.resource_id} ETA {ETA} min."],
        "resource_summary": [f"Units assigned {ASSIGNED}."],
        "safety": ["Crews avoid standing water near live wires."],
    }


CAP_TEXT = {
    "headline": "Exercise: response units moving to flooded areas",
    "description": f"Units assigned {ASSIGNED}.",
    "instruction": "Stay indoors and away from floodwater.",
}


def test_compliant_llm_drafts_pass_the_numeric_check() -> None:
    drafts = Reporter(_client(_sections("Response under way."), CAP_TEXT)).draft(PLAN, SCENARIO,
                                                                                MATRIX)

    assert drafts.sitrep.source == "llm" and drafts.sitrep.numbers_verified
    assert "SITUATION SUMMARY:" in drafts.sitrep.document
    assert "CURRENT AND PLANNED OBJECTIVES:" in drafts.sitrep.document
    assert drafts.cap.source == "llm" and drafts.cap.numbers_verified
    assert len(drafts.records) == 2


def test_a_wrong_or_unattributed_number_fails_the_draft() -> None:
    wrong = _sections("Response under way.")
    wrong["actions"] = [f"{FIRST.incident_id}: {FIRST.resource_id} ETA {float(ETA) + 6:.1f} min."]
    unattributed = _sections("About 25 people are waiting on rooftops.")

    for sections in (wrong, unattributed):
        drafts = Reporter(_client(sections, CAP_TEXT)).draft(PLAN, SCENARIO, MATRIX)
        assert drafts.sitrep.numbers_verified is False
        assert drafts.sitrep.mismatches


def test_cap_is_a_valid_cap_1_2_draft_that_is_never_published() -> None:
    drafts = Reporter(_client(_sections("x."), CAP_TEXT)).draft(PLAN, SCENARIO, MATRIX)

    alert = parse_cap(drafts.cap.document.encode("utf-8"))
    assert alert.status == "Draft" and alert.scope == "Private"
    assert alert.infos[0].headline == CAP_TEXT["headline"]
    assert len(alert.infos[0].areas[0].circles) == len(SCENARIO.incidents)
    assert drafts.cap.published is False and drafts.sitrep.published is False


def test_without_a_model_the_verified_template_is_used() -> None:
    drafts = Reporter(None).draft(PLAN, SCENARIO, MATRIX)

    assert (drafts.sitrep.source, drafts.cap.source) == ("template", "template")
    assert drafts.sitrep.numbers_verified and drafts.cap.numbers_verified
    assert parse_cap(drafts.cap.document.encode("utf-8")).status == "Draft"


def test_drafts_endpoint_returns_unpublished_drafts_and_records_an_event() -> None:
    from auth_helpers import bearer
    from fastapi.testclient import TestClient

    from aegisops.api.app import create_app

    app = create_app(Settings(environment="test", database_url="sqlite://", llm_api_key=None))
    client = TestClient(app, headers=bearer())
    decision_id = client.post("/api/v1/decisions", json={"seed": 42}).json()["decision_id"]

    body = client.post(f"/api/v1/decisions/{decision_id}/drafts").json()
    chain = client.get("/api/v1/audit/verify").json()

    assert body["sitrep"]["published"] is False and body["cap"]["published"] is False
    assert body["sitrep"]["numbers_verified"] is True
    assert "<status>Draft</status>" in body["cap"]["document"]
    assert chain["ok"] is True and chain["events_checked"] == 3

"""One decision, one trace: read -> plan (travel, solve, propose, verify) -> decide -> drafts.

The steps are separate HTTP requests; the trace is carried by the W3C traceparent the read step
returns and the plan step stores on the decision. Spans go to an in-memory exporter here.
"""

import json

import httpx2
import pytest
from auth_helpers import bearer
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import SecretStr

from aegisops.api.app import create_app
from aegisops.core.config import Settings
from aegisops.llm.client import LLMClient
from aegisops.telemetry import configure_tracing

REPORT = "Charbagh station ke peeche kamar tak pani, lagbhag 35 log chhat par fanse hain."
READER_REPLY = {
    "language": "hinglish",
    "incident_type": {"value": "flood", "quote": "kamar tak pani"},
    "location": {"value": "Charbagh station", "quote": "Charbagh station ke peeche"},
    "people_count": {"value": 35, "quote": "lagbhag 35 log"},
    "needs": [],
    "signals": [{"signal": "trapped", "quote": "chhat par fanse hain"}],
}
SITREP_REPLY = {"situation_summary": "Response under way.", "objectives": ["Reach everyone."],
                "actions": ["Units moving."], "resource_summary": ["Units assigned."],
                "safety": ["Avoid live wires."]}
CAP_REPLY = {"headline": "Exercise alert", "description": "Units are responding.",
             "instruction": "Stay indoors."}


@pytest.fixture(scope="module")
def exporter() -> InMemorySpanExporter:
    memory = InMemorySpanExporter()
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
    provider.add_span_processor(SimpleSpanProcessor(memory))
    return memory


def _llm() -> LLMClient:
    def handler(request: httpx2.Request) -> httpx2.Response:
        system = json.loads(request.content)["messages"][0]["content"]
        reply = (READER_REPLY if system.startswith("You extract facts")
                 else SITREP_REPLY if "situation report" in system else CAP_REPLY)
        return httpx2.Response(200, json={
            "id": "c", "object": "chat.completion", "created": 1, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": json.dumps(reply)}}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 80, "total_tokens": 480},
        })

    return LLMClient(
        Settings(environment="test", llm_api_key=SecretStr("k"), llm_max_retries=0),
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )


def _by_trace(spans: tuple[ReadableSpan, ...], trace_id: int) -> list[str]:
    return [span.name for span in spans if span.context and span.context.trace_id == trace_id]


def test_read_plan_verify_decide_and_communicate_share_one_trace(
    exporter: InMemorySpanExporter,
) -> None:
    exporter.clear()
    app = create_app(Settings(environment="test", database_url="sqlite://"), llm_client=_llm())
    operator = TestClient(app, headers=bearer("olive", "operator"))
    approver = TestClient(app, headers=bearer("bob", "approver"))

    read = operator.post("/api/v1/intake/read", json={"report": REPORT})
    traceparent = read.json()["traceparent"]
    decision = operator.post(
        "/api/v1/decisions", json={"seed": 7}, headers={"traceparent": traceparent}
    ).json()
    decision_id = decision["decision_id"]
    approver.post(f"/api/v1/decisions/{decision_id}/disposition",
                  json={"action": "reject", "reason": "trace test"})
    operator.post(f"/api/v1/decisions/{decision_id}/drafts")

    assert read.headers["traceparent"] == traceparent
    trace_id = int(traceparent.split("-")[1], 16)
    names = _by_trace(exporter.get_finished_spans(), trace_id)
    for expected in ("aegisops.read", "chat nvidia/llama-3.1-nemotron-70b-instruct",
                     "aegisops.plan", "execute_tool travel_matrix", "execute_tool cp_sat_solve",
                     "execute_tool propose", "execute_tool verify", "aegisops.decide",
                     "aegisops.communicate"):
        assert expected in names, expected
    assert names.count("aegisops.plan") == 1
    assert decision["traceparent"].split("-")[1] == traceparent.split("-")[1]


def test_step_spans_carry_genai_and_decision_attributes(exporter: InMemorySpanExporter) -> None:
    exporter.clear()
    app = create_app(Settings(environment="test", database_url="sqlite://"), llm_client=_llm())

    decision = TestClient(app, headers=bearer()).post(
        "/api/v1/decisions", json={"seed": 3}
    ).json()

    spans = {span.name: span for span in exporter.get_finished_spans()}
    plan = spans["aegisops.plan"].attributes or {}
    verify = spans["execute_tool verify"].attributes or {}
    assert plan["aegisops.decision_id"] == decision["decision_id"]
    assert verify["gen_ai.operation.name"] == "execute_tool"
    assert verify["gen_ai.tool.name"] == "verify"
    assert verify["aegisops.verify.verdict"] in {"pass", "blocked"}


def test_refused_self_approval_is_recorded_as_an_error_span(
    exporter: InMemorySpanExporter,
) -> None:
    exporter.clear()
    app = create_app(Settings(environment="test", database_url="sqlite://"), llm_client=_llm())
    alice = TestClient(app, headers=bearer("alice", "approver"))
    decision_id = alice.post("/api/v1/decisions", json={"seed": 3}).json()["decision_id"]

    response = alice.post(f"/api/v1/decisions/{decision_id}/disposition",
                          json={"action": "approve", "reason": "mine"})

    decide = next(s for s in exporter.get_finished_spans() if s.name == "aegisops.decide")
    assert response.status_code == 409
    assert (decide.attributes or {})["error.type"] == "HTTPException"


def test_a_malformed_traceparent_starts_a_new_trace(exporter: InMemorySpanExporter) -> None:
    exporter.clear()
    app = create_app(Settings(environment="test", database_url="sqlite://"), llm_client=_llm())

    decision = TestClient(app, headers=bearer()).post(
        "/api/v1/decisions", json={"seed": 3}, headers={"traceparent": "not-a-trace"}
    ).json()

    assert decision["traceparent"] is not None


def test_tracing_is_off_without_an_endpoint() -> None:
    assert configure_tracing(None, "aegisops-api") is False

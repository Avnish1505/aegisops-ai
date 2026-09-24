"""The OpenAI-compatible LLM client, driven by mocked HTTP (httpx2, which the openai SDK uses)."""

import json
import logging
from pathlib import Path

import httpx2
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import BaseModel, SecretStr

from aegisops.core.config import Settings
from aegisops.llm.cassette import CassetteTransport
from aegisops.llm.client import LLMClient, LLMError, LLMOutputError, Prompt

EXPORTER = InMemorySpanExporter()
if not isinstance(trace.get_tracer_provider(), TracerProvider):
    _provider = TracerProvider()
    _provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
    trace.set_tracer_provider(_provider)
else:  # another test module installed the provider first
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(EXPORTER))  # type: ignore[attr-defined]


class Answer(BaseModel):
    city: str
    count: int


PROMPT = Prompt(name="test", version="v1", system="Return JSON.", user="Where?")


def _completion(content: str, prompt_tokens: int = 120, completion_tokens: int = 30) -> dict:
    return {
        "id": "cmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": "nvidia/llama-3.1-nemotron-70b-instruct",
        "choices": [
            {"index": 0, "finish_reason": "stop",
             "message": {"role": "assistant", "content": content}}
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


class Server:
    def __init__(self, response: httpx2.Response) -> None:
        self.bodies: list[dict] = []
        self.headers: list[httpx2.Headers] = []
        self._response = response

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.bodies.append(json.loads(request.content))
        self.headers.append(request.headers)
        return self._response


def _client(server: Server, **settings: object) -> LLMClient:
    config = Settings(
        environment="test", llm_api_key=SecretStr("nvapi-test-key"), llm_max_retries=0,
        **settings,  # type: ignore[arg-type]
    )
    return LLMClient(config, http_client=httpx2.Client(transport=httpx2.MockTransport(server)))


def _ok(content: str = '{"city": "Lucknow", "count": 3}') -> Server:
    return Server(httpx2.Response(200, json=_completion(content)))


def test_default_model_is_70b_class_not_8b() -> None:
    model = Settings(_env_file=None).llm_model  # type: ignore[call-arg]

    assert "70b" in model and "8b" not in model


def test_nim_requests_use_guided_json_and_parse_into_the_schema() -> None:
    server = _ok()

    call = _client(server).complete_json(PROMPT, Answer)

    body = server.bodies[0]
    assert body["model"] == "nvidia/llama-3.1-nemotron-70b-instruct"
    assert body["nvext"]["guided_json"] == Answer.model_json_schema()
    assert "response_format" not in body
    assert body["temperature"] == 0.0
    assert call.value == Answer(city="Lucknow", count=3)
    assert server.headers[0]["authorization"] == "Bearer nvapi-test-key"


def test_other_providers_use_response_format_json_schema() -> None:
    server = _ok()

    _client(server, llm_base_url="https://api.example.test/v1").complete_json(PROMPT, Answer)

    body = server.bodies[0]
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == Answer.model_json_schema()
    assert "nvext" not in body


def test_each_call_logs_tokens_latency_and_cost(caplog: pytest.LogCaptureFixture) -> None:
    client = _client(_ok(), llm_price_in_usd_per_mtok=1.0, llm_price_out_usd_per_mtok=2.0)

    with caplog.at_level(logging.INFO, logger="aegisops.llm.client"):
        call = client.complete_json(PROMPT, Answer)

    assert (call.record.input_tokens, call.record.output_tokens) == (120, 30)
    assert call.record.cost_usd == pytest.approx((120 * 1.0 + 30 * 2.0) / 1_000_000)
    assert call.record.latency_s >= 0
    assert client.call_log.records == [call.record]
    assert "prompt=test@v1" in caplog.text and "tokens_in=120" in caplog.text


def test_fenced_json_is_accepted() -> None:
    call = _client(_ok('```json\n{"city": "Lucknow", "count": 1}\n```')).complete_json(
        PROMPT, Answer
    )

    assert call.value.count == 1


def test_output_that_breaks_the_schema_is_an_error_with_the_raw_text() -> None:
    client = _client(_ok('{"city": "Lucknow"}'))

    with pytest.raises(LLMOutputError) as caught:
        client.complete_json(PROMPT, Answer)

    assert caught.value.raw == '{"city": "Lucknow"}'
    assert client.call_log.records[-1].ok is False


def test_http_failure_is_an_llm_error() -> None:
    client = _client(Server(httpx2.Response(503, json={"error": "overloaded"})))

    with pytest.raises(LLMError):
        client.complete_json(PROMPT, Answer)


def test_cassettes_record_then_replay_without_a_key(tmp_path: Path) -> None:
    server = _ok()
    recording = LLMClient(
        Settings(environment="test", llm_api_key=SecretStr("nvapi-secret"), llm_max_retries=0),
        http_client=httpx2.Client(
            transport=CassetteTransport(tmp_path, "record", inner=httpx2.MockTransport(server))
        ),
    )
    recorded = recording.complete_json(PROMPT, Answer)

    replaying = LLMClient(
        Settings(environment="test", llm_cassette_mode="replay", llm_cassette_dir=tmp_path,
                 llm_max_retries=0)
    )
    replayed = replaying.complete_json(PROMPT, Answer)

    assert replayed.value == recorded.value
    assert len(server.bodies) == 1
    cassette = next(tmp_path.glob("*.json")).read_text()
    assert "nvapi-secret" not in cassette


def test_replay_mode_never_reaches_the_network(tmp_path: Path) -> None:
    client = LLMClient(
        Settings(environment="test", llm_cassette_mode="replay", llm_cassette_dir=tmp_path,
                 llm_max_retries=0)
    )

    with pytest.raises(LLMError, match="no cassette|Connection"):
        client.complete_json(PROMPT, Answer)


def test_calls_emit_genai_chat_spans() -> None:
    EXPORTER.clear()

    _client(_ok()).complete_json(PROMPT, Answer)

    span = next(s for s in EXPORTER.get_finished_spans() if s.name.startswith("chat "))
    attributes = dict(span.attributes or {})
    assert span.name == "chat nvidia/llama-3.1-nemotron-70b-instruct"
    assert attributes["gen_ai.operation.name"] == "chat"
    assert attributes["gen_ai.provider.name"] == "nvidia"
    assert attributes["gen_ai.usage.input_tokens"] == 120
    assert attributes["gen_ai.usage.output_tokens"] == 30
    assert attributes["aegisops.prompt.version"] == "v1"

"""Reader: grounding, deterministic severity, gazetteer geocoding. LLM replies are mocked."""

import json

import httpx2
import pytest
from pydantic import SecretStr

from aegisops.core.config import Settings
from aegisops.domain.models import Severity
from aegisops.intake.gazetteer import DEFAULT_GAZETTEER, Gazetteer
from aegisops.intake.grounding import number_stated, numbers_in, quote_in_report
from aegisops.intake.models import CountField, SignalField, TypeField
from aegisops.intake.reader import Reader, to_incident
from aegisops.intake.severity import severity_for
from aegisops.llm.client import LLMClient

GAZETTEER = Gazetteer.load(DEFAULT_GAZETTEER)


def _reader(reply: dict) -> Reader:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={
            "id": "c", "object": "chat.completion", "created": 1, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": json.dumps(reply)}}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 80, "total_tokens": 480},
        })

    client = LLMClient(
        Settings(environment="test", llm_api_key=SecretStr("k"), llm_max_retries=0),
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return Reader(client, GAZETTEER)


REPORT = ("Charbagh station ke peeche gali mein kamar tak pani, lagbhag 35 log chhat par "
          "fanse hain, ek budhe aadmi behosh hai. 2 boat bhejo jaldi.")


def _reply(**overrides: object) -> dict:
    reply = {
        "language": "hinglish",
        "incident_type": {"value": "flood", "quote": "kamar tak pani"},
        "location": {"value": "Charbagh station", "quote": "Charbagh station ke peeche"},
        "people_count": {"value": 35, "quote": "lagbhag 35 log"},
        "needs": [{"resource_type": "boat", "quantity": 2, "quote": "2 boat bhejo"}],
        "signals": [
            {"signal": "trapped", "quote": "chhat par fanse hain"},
            {"signal": "unconscious", "quote": "budhe aadmi behosh hai"},
        ],
    }
    reply.update(overrides)
    return reply


def test_grounded_reading_keeps_every_field_and_geocodes_from_osm() -> None:
    result = _reader(_reply()).read(REPORT)
    candidate = result.candidate

    assert candidate.dropped == []
    assert candidate.incident_type is not None and candidate.incident_type.value == "flood"
    assert candidate.people_count is not None and candidate.people_count.value == 35
    assert [(n.resource_type.value, n.quantity) for n in candidate.needs] == [("boat", 2)]
    assert candidate.geocode is not None and candidate.geocode.name == "Charbagh"
    assert candidate.geocode.osm.startswith("node/")
    assert (candidate.severity, candidate.severity_rule[:2]) == (Severity.CRITICAL, "R1")
    assert result.record.prompt_version == "reader-v1"


def test_fabricated_quotes_are_dropped_and_counted() -> None:
    reply = _reply(
        people_count={"value": 60, "quote": "60 log fanse hain"},
        location={"value": "Hazratganj", "quote": "Hazratganj crossing"},
        signals=[{"signal": "drowning", "quote": "bachcha doob raha hai"}],
    )

    candidate = _reader(reply).read(REPORT).candidate

    assert sorted(candidate.dropped) == ["location_text", "people_count", "signals.drowning"]
    assert candidate.people_count is None and candidate.geocode is None
    assert candidate.severity == Severity.MEDIUM  # a flood with no surviving life-threat signal


def test_a_count_must_be_stated_in_its_own_quote() -> None:
    reply = _reply(people_count={"value": 40, "quote": "lagbhag 35 log"},
                   needs=[{"resource_type": "boat", "quantity": 3, "quote": "2 boat bhejo"}])

    candidate = _reader(reply).read(REPORT).candidate

    assert set(candidate.dropped) == {"people_count", "needs.boat"}


def test_location_value_must_come_from_its_quote() -> None:
    reply = _reply(location={"value": "Hazratganj", "quote": "Charbagh station ke peeche"})

    assert "location_text" in _reader(reply).read(REPORT).candidate.dropped


def test_hindi_report_with_devanagari_digits() -> None:
    report = "हजरतगंज में पुरानी इमारत की छत गिरी, करीब १२ लोग मलबे में दबे हैं।"
    reply = {
        "language": "hi",
        "incident_type": {"value": "structural_collapse", "quote": "छत गिरी"},
        "location": {"value": "हजरतगंज", "quote": "हजरतगंज में"},
        "people_count": {"value": 12, "quote": "करीब १२ लोग"},
        "needs": [],
        "signals": [{"signal": "trapped", "quote": "मलबे में दबे हैं"}],
    }

    candidate = _reader(reply).read(report).candidate

    assert candidate.dropped == []
    assert candidate.geocode is not None and candidate.geocode.name == "Hazratganj"
    assert (candidate.severity, candidate.severity_rule[:2]) == (Severity.CRITICAL, "R2")
    incident = to_incident(candidate, "INC-read-1")
    assert incident is not None
    assert incident.resources_needed  # defaulted from the incident type
    assert "needs defaulted" in (incident.report or "")


def test_candidate_without_location_cannot_become_an_incident() -> None:
    candidate = _reader(_reply(location=None)).read(REPORT).candidate

    assert to_incident(candidate, "INC-x") is None


@pytest.mark.parametrize(
    ("quote", "report", "expected"),
    [
        ("Charbagh  Station", "near charbagh station now", True),
        ("Charbagh", "Aminabad mein pani", False),
        ("a", "a b c", False),
        ("“chhat par”", "log chhat par hain", True),
    ],
)
def test_quote_grounding(quote: str, report: str, expected: bool) -> None:
    assert quote_in_report(quote, report) is expected


@pytest.mark.parametrize(
    ("text", "numbers"),
    [("करीब ४५ लोग", {45}), ("lagbhag pachas log", {50}), ("about 35 residents", {35}),
     ("teen bachche", {3}), ("दो नाव", {2}), ("no number here", set())],
)
def test_numbers_in_any_script_or_word(text: str, numbers: set[int]) -> None:
    assert numbers_in(text) == numbers


def test_number_stated() -> None:
    assert number_stated(12, "करीब १२ लोग") and not number_stated(13, "करीब १२ लोग")


@pytest.mark.parametrize(
    ("kind", "people", "signals", "severity", "rule"),
    [
        ("flood", 3, ["drowning"], Severity.CRITICAL, "R1"),
        ("structural_collapse", 2, ["trapped"], Severity.CRITICAL, "R2"),
        ("flood", 60, [], Severity.CRITICAL, "R3"),
        ("medical", 1, ["injured"], Severity.HIGH, "R4"),
        ("fire", None, [], Severity.HIGH, "R5"),
        ("medical", 12, [], Severity.HIGH, "R6"),
        ("flood", None, [], Severity.MEDIUM, "R7"),
        (None, 4, [], Severity.MEDIUM, "R8"),
        (None, None, [], Severity.LOW, "R9"),
    ],
)
def test_severity_rules(kind, people, signals, severity, rule) -> None:  # type: ignore[no-untyped-def]
    got = severity_for(
        TypeField(value=kind, quote="x") if kind else None,
        CountField(value=people, quote="x") if people is not None else None,
        [SignalField(signal=s, quote="x") for s in signals],
    )

    assert (got[0], got[1][:2]) == (severity, rule)


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("Charbagh station ke peeche", "Charbagh"),
        ("Lucknow Charbagh railway station", "Charbagh Railway Station"),
        ("हजरतगंज में", "Hazratganj"),
        ("kaisarbagh bus adda", "Qaisarbagh"),
        ("Alambag ke paas", "Alambagh"),
        ("gomtinagar", "Gomti Nagar"),
    ],
)
def test_gazetteer_geocodes_lucknow_spellings(text: str, name: str) -> None:
    result = GAZETTEER.geocode(text)

    assert result is not None and result.name == name


def test_gazetteer_returns_none_for_unknown_places() -> None:
    assert GAZETTEER.geocode("xyzzy nowhere") is None


def test_read_endpoint_returns_grounded_candidate_and_preview() -> None:
    from auth_helpers import bearer
    from fastapi.testclient import TestClient

    from aegisops.api.app import create_app

    reader = _reader(_reply())
    app = create_app(Settings(environment="test", database_url="sqlite://"),
                     llm_client=reader._client)

    body = TestClient(app, headers=bearer()).post(
        "/api/v1/intake/read", json={"report": REPORT}
    ).json()

    assert body["candidate"]["severity"] == "critical"
    assert body["incident_preview"]["location"] == {"lat": 26.833497, "lon": 80.926414}
    assert body["llm"]["prompt_version"] == "reader-v1"


def test_read_endpoint_is_503_without_a_model() -> None:
    from auth_helpers import bearer
    from fastapi.testclient import TestClient

    from aegisops.api.app import create_app

    app = create_app(Settings(environment="test", database_url="sqlite://", llm_api_key=None))

    response = TestClient(app, headers=bearer()).post(
        "/api/v1/intake/read", json={"report": REPORT}
    )

    assert response.status_code == 503

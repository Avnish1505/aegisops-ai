"""Operator note -> one typed constraint, proposed for confirmation. LLM replies are mocked."""

import json

import httpx2
import pytest
from auth_helpers import bearer
from fastapi.testclient import TestClient
from pydantic import SecretStr

from aegisops.api.app import create_app
from aegisops.application.scenario_service import generate_scenario
from aegisops.core.config import Settings
from aegisops.domain.models import Location
from aegisops.intake.constraints import ConstraintTranslator
from aegisops.intake.gazetteer import DEFAULT_GAZETTEER, Gazetteer
from aegisops.llm.client import LLMClient
from aegisops.planning.constraints import ExcludeUnit, PriorityBoost, ReserveConstraint

GAZETTEER = Gazetteer.load(DEFAULT_GAZETTEER)
SCENARIO = generate_scenario(seed=3)
NOTE = "Gomti Nagar side ke liye ek boat rok ke rakho"


def _client(reply: dict) -> LLMClient:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={
            "id": "c", "object": "chat.completion", "created": 1, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": json.dumps(reply)}}],
            "usage": {"prompt_tokens": 300, "completion_tokens": 40, "total_tokens": 340},
        })

    return LLMClient(
        Settings(environment="test", llm_api_key=SecretStr("k"), llm_max_retries=0),
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )


def _draft(**fields: object) -> dict:
    draft = {"kind": "reserve", "resource_type": "boat", "count": 1, "place_text": "Gomti Nagar",
             "unit_ref": None, "incident_ref": None, "factor": None,
             "quote": "Gomti Nagar side ke liye ek boat rok ke rakho"}
    draft.update(fields)
    return draft


def _translate(note: str, **fields: object):  # type: ignore[no-untyped-def]
    return ConstraintTranslator(_client(_draft(**fields)), GAZETTEER).translate(note, SCENARIO)


def test_hinglish_reserve_note_becomes_a_zone_around_the_osm_place() -> None:
    proposal = _translate(NOTE).proposal

    assert proposal.status == "needs_confirmation"
    constraint = proposal.constraint
    assert isinstance(constraint, ReserveConstraint)
    assert (constraint.resource_type.value, constraint.count) == ("boat", 1)
    gomti_nagar = Location(lat=26.8528761, lon=80.9988505)
    assert constraint.zone.contains(gomti_nagar)
    assert constraint.zone.max_lat - constraint.zone.min_lat == pytest.approx(4 / 111.32, rel=1e-3)
    assert "Gomti Nagar" in proposal.explanation and "node/" in proposal.explanation


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({"quote": "Hazratganj mein do boat rakho"}, "quoted text is not in the note"),
        ({"count": 3}, "count 3 is not stated"),
        ({"place_text": "Atlantis"}, "no place named in the note"),
        ({"resource_type": None}, "no unit type stated"),
    ],
)
def test_unsupported_reserve_drafts_are_rejected(fields: dict, reason: str) -> None:
    proposal = _translate(NOTE, **fields).proposal

    assert proposal.status == "rejected" and proposal.constraint is None
    assert any(reason in r for r in proposal.reasons)


def test_place_named_in_the_note_but_unknown_to_the_gazetteer_is_rejected() -> None:
    note = "Xanadu colony ke liye ek boat rok ke rakho"
    proposal = _translate(note, place_text="Xanadu colony", quote=note).proposal

    assert proposal.status == "rejected"
    assert "not in the Lucknow gazetteer" in proposal.reasons[0]


def test_exclude_unit_needs_a_real_unit_id() -> None:
    unit = SCENARIO.resources[0].id
    note = f"{unit} ko mat bhejo, engine kharab hai"

    ok = _translate(note, kind="exclude_unit", resource_type=None, count=None, place_text=None,
                    unit_ref=unit, quote=f"{unit} ko mat bhejo").proposal
    ghost = _translate(note, kind="exclude_unit", unit_ref="RES-ghost",
                       quote=f"{unit} ko mat bhejo").proposal

    assert ok.constraint == ExcludeUnit(unit_id=unit)
    assert ghost.status == "rejected"


def test_priority_boost_defaults_to_2x_and_checks_a_stated_factor() -> None:
    incident = SCENARIO.incidents[0].id
    note = f"{incident} ko pehle dekho"

    default = _translate(note, kind="priority_boost", incident_ref=incident, factor=None,
                         quote=note).proposal
    unstated = _translate(note, kind="priority_boost", incident_ref=incident, factor=5,
                          quote=note).proposal

    assert default.constraint == PriorityBoost(incident_id=incident, factor=2.0)
    assert unstated.status == "rejected"


def test_translate_endpoint_proposes_without_planning() -> None:
    app = create_app(Settings(environment="test", database_url="sqlite://"),
                     llm_client=_client(_draft()))
    client = TestClient(app, headers=bearer())

    proposal = client.post("/api/v1/constraints/translate", json={"note": NOTE}).json()
    confirmed = client.post(
        "/api/v1/decisions",
        json={"scenario": SCENARIO.model_dump(mode="json"),
              "constraints": [proposal["constraint"]]},
    ).json()

    assert proposal["status"] == "needs_confirmation"
    assert proposal["constraint"]["kind"] == "reserve"
    assert confirmed["constraints"] == [proposal["constraint"]]

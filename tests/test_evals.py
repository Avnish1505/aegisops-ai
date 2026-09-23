"""The eval harness scores an oracle (a fake model that answers from the gold labels) perfectly.

This checks the scoring code, not a model: if an oracle does not score ~100%, the harness is wrong.
"""

import json
from pathlib import Path

import httpx2
import pytest
from pydantic import SecretStr

from aegisops.core.config import Settings
from aegisops.domain.models import Scenario
from aegisops.intake.constraints import ConstraintTranslator
from aegisops.intake.gazetteer import DEFAULT_GAZETTEER, Gazetteer
from aegisops.llm.client import LLMClient
from evals.metrics import bootstrap, mean, prf, quantile
from evals.run import (
    Reader,
    Reporter,
    load_jsonl,
    run_constraints,
    run_e2e,
    run_reader,
    score_e2e,
    score_reader,
)

DATA = Path(__file__).resolve().parents[1] / "evals" / "data"
REPORTS = [r for r in load_jsonl(DATA / "reports_v1.jsonl") if r["source"] == "synthetic_lucknow"]
BY_TEXT = {r["text"]: r for r in REPORTS}
NOTES = load_jsonl(DATA / "notes_v1.jsonl")
NOTE_BY_TEXT = {n["text"]: n for n in NOTES}
EXERCISE = Scenario.model_validate_json((DATA / "lucknow_exercise_v1.json").read_text())


def _between(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].rsplit(end, 1)[0].strip()


def _reader_answer(report: str) -> dict:
    gold = BY_TEXT[report]["gold"]
    anchor = report[:30]
    return {
        "language": BY_TEXT[report]["language"],
        "incident_type": {"value": gold["incident_type"], "quote": anchor}
        if gold["incident_type"] else None,
        "location": {"value": gold["location_text"], "quote": gold["location_text"]}
        if gold["location_text"] else None,
        "people_count": {"value": gold["people_count"], "quote": gold["people_text"]}
        if gold["people_count"] is not None else None,
        "needs": [{"resource_type": n["resource_type"], "quantity": n["quantity"],
                   "quote": gold["quantity_text"] if n["quantity"] > 1 else anchor}
                  for n in gold["needs"]],
        "signals": [{"signal": s, "quote": anchor} for s in gold["signals"]],
    }


def _note_answer(note: str) -> dict:
    gold = NOTE_BY_TEXT[note]["gold"]
    answer = {"kind": gold["kind"], "resource_type": None, "count": None, "place_text": None,
              "unit_ref": None, "incident_ref": None, "factor": None, "quote": note[:90]}
    if gold["kind"] == "reserve":
        place = next(s for s in (gold["place"]["name"],) if s)
        surface = next((w for w in _place_surfaces(note, place)), place)
        answer.update(resource_type=gold["resource_type"], count=gold["count"],
                      place_text=surface)
    elif gold["kind"] == "exclude_unit":
        answer["unit_ref"] = gold["unit_id"]
    else:
        answer["incident_ref"] = gold["incident_id"]
    return answer


GAZETTEER = Gazetteer.load(DEFAULT_GAZETTEER)


def _place_surfaces(note: str, name: str) -> list[str]:
    return [a for e in GAZETTEER.entries if e.name == name
            for a in (e.name, *e.aliases, *e.curated_aliases) if a in note]


def _oracle(request: httpx2.Request) -> httpx2.Response:
    body = json.loads(request.content)
    system, user = body["messages"][0]["content"], body["messages"][1]["content"]
    if system.startswith("You extract facts"):
        answer = _reader_answer(_between(user, "<<<", ">>>"))
    elif system.startswith("You translate one note"):
        answer = _note_answer(_between(user, "<<<", ">>>"))
    elif "situation report" in system:
        answer = {"situation_summary": "Response under way.", "objectives": ["Reach everyone."],
                  "actions": ["Units moving."], "resource_summary": ["Units assigned."],
                  "safety": ["Avoid live wires."]}
    else:
        answer = {"headline": "Exercise alert", "description": "Units are responding.",
                  "instruction": "Stay indoors."}
    return httpx2.Response(200, json={
        "id": "o", "object": "chat.completion", "created": 1, "model": "oracle",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": json.dumps(answer)}}],
        "usage": {"prompt_tokens": 500, "completion_tokens": 100, "total_tokens": 600},
    })


@pytest.fixture(scope="module")
def client() -> LLMClient:
    return LLMClient(
        Settings(environment="test", llm_api_key=SecretStr("k"), llm_max_retries=0),
        http_client=httpx2.Client(transport=httpx2.MockTransport(_oracle)),
    )


def test_oracle_reader_scores_perfectly(client: LLMClient) -> None:
    rows = REPORTS[:60]

    scored = score_reader(rows, run_reader(Reader(client, GAZETTEER), rows, workers=4))

    assert scored["failed_reads"] == 0 and scored["fields_dropped"] == 0
    for field in ("incident_type", "people_count", "needs", "signals"):
        assert scored["fields"][field]["f1"]["value"] == 1.0, field
    assert scored["fields"]["location"]["f1"]["value"] >= 0.95
    assert scored["severity_accuracy"]["value"] == 1.0
    assert scored["ungrounded_field_rate"]["value"] == 0.0


def test_oracle_constraint_translation_is_fully_correct(client: LLMClient) -> None:
    outputs = run_constraints(ConstraintTranslator(client, GAZETTEER), NOTES, EXERCISE, workers=4)

    wrong = [(o["id"], o["proposal"]) for o in outputs if not o["correct"]]
    assert wrong == []


def test_oracle_end_to_end_passes_every_trial(client: LLMClient) -> None:
    scenarios = load_jsonl(DATA / "e2e_v1.jsonl")[:3]
    reports = {r["id"]: r for r in REPORTS}
    units = [u.model_dump(mode="json") for u in EXERCISE.resources]

    outputs = run_e2e(Reader(client, GAZETTEER), Reporter(client), scenarios, reports, units,
                      trials=2, workers=2)
    scored = score_e2e(outputs, trials=2)

    assert scored["pass^2"]["value"] == 1.0
    assert scored["sitrep_numeric_match"]["value"] == 1.0
    assert scored["cost_per_decision_usd"]["value"] > 0


def test_bootstrap_is_seeded_and_brackets_the_point_estimate() -> None:
    values = [1.0] * 30 + [0.0] * 10

    first, second = bootstrap(values, mean), bootstrap(values, mean)

    assert first == second
    assert first.low is not None and first.high is not None
    assert first.low <= 0.75 <= first.high


def test_prf_and_quantile_basics() -> None:
    from collections import Counter

    assert prf([Counter(tp=3, fp=1, fn=1)]) == (0.75, 0.75, 0.75)
    assert quantile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5

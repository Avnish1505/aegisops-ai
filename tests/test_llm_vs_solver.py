"""The LLM-vs-solver harness: an oracle model that returns the CP-SAT plan scores as optimal and
feasible; a model that reuses a unit is infeasible; unparseable output counts as no plan."""

import json
from collections.abc import Callable

import httpx2
from pydantic import SecretStr

from aegisops.core.config import Settings
from aegisops.domain.models import Scenario
from aegisops.llm.client import LLMClient
from aegisops.planning.solver import solve
from aegisops.planning.travel import TravelTimeMatrix
from evals.llm_vs_solver import DATASET, constraints_of, run_experiment, score
from evals.run import load_jsonl

ROWS = load_jsonl(DATASET)[:6]


def _reply(content: str) -> httpx2.Response:
    return httpx2.Response(200, json={
        "id": "c", "object": "chat.completion", "created": 1, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 3000, "completion_tokens": 400, "total_tokens": 3400},
    })


def _solver_plan(request: httpx2.Request) -> dict[str, object]:
    payload = json.loads(json.loads(request.content)["messages"][1]["content"])
    scenario = Scenario.model_validate(payload["scenario"])
    row = next(r for r in ROWS if r["scenario"]["scenario_id"] == scenario.scenario_id)
    plan = solve(scenario, TravelTimeMatrix.model_validate(row["travel_times"]),
                 constraints_of(row))
    return {
        "scenario_id": scenario.scenario_id, "requires_human_approval": True,
        "assignments": [a.model_dump(mode="json") for a in plan.assignments],
        "unmet_requirements": [u.model_dump(mode="json") for u in plan.unmet_requirements],
        "decision_trace": ["oracle"],
    }


def _factory(handler: Callable[[httpx2.Request], httpx2.Response]) -> Callable[[], LLMClient]:
    settings = Settings(environment="test", llm_api_key=SecretStr("k"), llm_max_retries=0)
    return lambda: LLMClient(
        settings, http_client=httpx2.Client(transport=httpx2.MockTransport(handler))
    )


def test_dataset_is_100_recorded_osrm_scenarios() -> None:
    rows = load_jsonl(DATASET)

    assert len(rows) == 100
    assert {row["travel_times"]["provider"] for row in rows} == {"osrm-driving"}
    assert not any(row["travel_times"]["degraded"] for row in rows)


def test_oracle_llm_matches_the_solver() -> None:
    outputs = run_experiment(ROWS, _factory(lambda r: _reply(json.dumps(_solver_plan(r)))), 2)

    summary = score(outputs)

    assert summary["llm"]["feasible"]["value"] == 1.0
    assert summary["solver"]["feasible"]["value"] == 1.0
    assert summary["optimality_gap"]["n"] == len(ROWS)
    assert summary["optimality_gap"]["median"]["value"] == 0.0
    assert all(len(o["calls"]) == 1 for o in outputs)


def test_reusing_a_unit_is_infeasible() -> None:
    def duplicate(request: httpx2.Request) -> httpx2.Response:
        plan = _solver_plan(request)
        assignments = plan["assignments"]
        assert isinstance(assignments, list)
        if assignments:
            plan["assignments"] = [*assignments, dict(assignments[0], incident_id="INC-01")]
        return _reply(json.dumps(plan))

    summary = score(run_experiment(ROWS, _factory(duplicate), 2))

    assert summary["llm"]["feasible"]["value"] < 1.0
    assert summary["llm"]["failed_check_counts"].get("unit_not_duplicated", 0) >= 1
    assert summary["llm"]["findings_per_plan"]["value"] > summary["solver"]["findings_per_plan"][
        "value"]


def test_unparseable_output_counts_as_no_plan() -> None:
    outputs = run_experiment(ROWS[:2], _factory(lambda r: _reply("I cannot do that.")), 1)

    summary = score(outputs)

    assert summary["llm"]["produced_plan"]["value"] == 0.0
    assert summary["llm"]["feasible"]["value"] == 0.0
    assert all(len(o["calls"]) == 2 for o in outputs)  # one retry, then blocked

"""Experiment: LLM-direct allocation vs the CP-SAT solver on 100 Lucknow scenarios with OSRM times.

    docker compose up -d osrm                     # road graph from scripts/osrm_prepare.sh
    python -m evals.llm_vs_solver --build         # once: scenarios + recorded OSRM matrices
    python -m evals.llm_vs_solver                 # needs AEGISOPS_LLM_API_KEY

Scenarios draw incidents at gazetteer places inside urban Lucknow and units from the exercise's
45 real-facility units (evals/data/lucknow_exercise_v1.json), with a seeded mix of scarcity,
unavailable units, exclude_unit and priority_boost constraints. Road travel minutes come from
the OSRM table service and are recorded in the dataset, so a re-run needs no OSRM server and
both arms see identical numbers.

Both arms go through the same ``DecisionService`` and verifier. The LLM arm uses the shared
client and the ``alloc-v1`` prompt, which states the solver's objective and hard rules; it gets
no retrieval, so this compares allocation only. Metrics:

- feasibility: no failed hard check (units exist, available, used once, right type, not more
  than needed, constraints honoured), and the verifier's overall verdict;
- optimality gap: (LLM objective - CP-SAT objective) / CP-SAT objective, both scored by
  ``planning.objective.plan_objective`` on the recorded matrix, over plans both arms produced
  feasibly; objectives are dominated by the unmet penalty, so the weighted-travel part is
  reported separately;
- verifier findings per plan: failed checks per plan and which checks failed.

Outputs reports/llm_vs_solver.md and .json, and raw plans under reports/raw/llm_vs_solver_<date>/.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from aegisops.application.decision_service import DecisionOutcome, DecisionService
from aegisops.application.scenario_service import LUCKNOW_URBAN_BOUNDS, RESOURCE_REQUIREMENTS
from aegisops.core.config import Settings
from aegisops.domain.models import IncidentType, Scenario, Severity
from aegisops.infrastructure.llm_decision_engine import LLMDecisionEngine
from aegisops.intake.gazetteer import DEFAULT_GAZETTEER, Gazetteer
from aegisops.llm.client import LLMClient
from aegisops.planning.constraints import ExcludeUnit, PlanningConstraint, PriorityBoost
from aegisops.planning.objective import plan_objective
from aegisops.planning.osrm import OSRMProvider
from aegisops.planning.travel import TravelTimeMatrix
from evals.metrics import bootstrap, mean, quantile
from evals.run import DATA, ROOT, fmt, load_jsonl, pmap, record_dict, sha

SEED = 20260923
DATASET = DATA / "llm_vs_solver_v1.jsonl"
PROMPT_VERSION = "alloc-v1"
LLM_ENGINE = "llm_direct"
HARD_CHECKS = (
    "incident_exists", "unit_exists", "unit_available", "unit_not_duplicated",
    "capability_match", "quantity_within_requirement", "constraints_satisfied",
)
TYPE_WEIGHTS = {IncidentType.FLOOD: 45, IncidentType.MEDICAL: 30,
                IncidentType.STRUCTURAL_COLLAPSE: 15, IncidentType.FIRE: 10}
SEVERITY_MIX = {Severity.CRITICAL: 20, Severity.HIGH: 30, Severity.MEDIUM: 30, Severity.LOW: 20}


# --- Dataset --------------------------------------------------------------------------------
def build_scenarios(gazetteer: Gazetteer, units: Sequence[dict[str, Any]],
                    count: int = 100) -> list[dict[str, Any]]:
    """Seeded scenario specs (no travel times yet)."""
    rng = random.Random(SEED)
    min_lat, min_lon, max_lat, max_lon = LUCKNOW_URBAN_BOUNDS
    spots = sorted(
        (e for e in gazetteer.entries if e.kind in {"place", "landmark"}
         and min_lat <= e.lat <= max_lat and min_lon <= e.lon <= max_lon),
        key=lambda e: e.osm,
    )
    rows = []
    for number in range(1, count + 1):
        incidents = []
        for position, spot in enumerate(rng.sample(spots, rng.randint(3, 10)), start=1):
            kind = rng.choices(list(TYPE_WEIGHTS), weights=list(TYPE_WEIGHTS.values()))[0]
            needs = {k.value: v for k, v in RESOURCE_REQUIREMENTS[kind].items()}
            if rng.random() < 0.2:
                extra = rng.choice(sorted(needs))
                needs[extra] += 1
            incidents.append({
                "id": f"INC-{position:02d}", "type": kind.value,
                "severity": rng.choices(list(SEVERITY_MIX),
                                        weights=list(SEVERITY_MIX.values()))[0].value,
                "location": {"lat": spot.lat, "lon": spot.lon},
                "people_affected": rng.randint(1, 60), "reported_at_min": rng.randint(0, 60),
                "resources_needed": needs,
            })
        resources = [dict(unit, available=rng.random() >= 0.1)
                     for unit in rng.sample(list(units), rng.randint(8, 24))]
        constraints: list[dict[str, Any]] = []
        roll = rng.random()
        available = [unit["id"] for unit in resources if unit["available"]]
        if roll < 0.15 and available:
            constraints.append({"kind": "exclude_unit", "unit_id": rng.choice(available)})
        elif roll < 0.30:
            constraints.append({"kind": "priority_boost", "factor": 2.0,
                                "incident_id": rng.choice(incidents)["id"]})
        rows.append({
            "id": f"LVS-{number:03d}",
            "scenario": {"scenario_id": f"SCEN-LVS-{number:03d}", "incidents": incidents,
                         "resources": resources},
            "constraints": constraints,
        })
    return rows


def record_matrices(rows: list[dict[str, Any]], osrm_url: str) -> list[dict[str, Any]]:
    provider = OSRMProvider(osrm_url, timeout_s=30.0)
    for row in rows:
        matrix = provider.matrix(Scenario.model_validate(row["scenario"]))
        if matrix.degraded:
            sys.exit(f"OSRM at {osrm_url} is unavailable: {matrix.degraded_reason}")
        row["travel_times"] = matrix.model_dump(mode="json")
    return rows


# --- Experiment -----------------------------------------------------------------------------
class RecordedTravelTimes:
    """Serves the matrix recorded from OSRM at build time."""

    def __init__(self, matrix: TravelTimeMatrix) -> None:
        self._matrix = matrix
        self.name = matrix.provider

    def matrix(self, scenario: Scenario) -> TravelTimeMatrix:
        return self._matrix


class NoRetrieval:
    def retrieve(self, query: str) -> list[str]:
        return []


def constraints_of(row: dict[str, Any]) -> list[PlanningConstraint]:
    built: list[PlanningConstraint] = []
    for item in row["constraints"]:
        if item["kind"] == "exclude_unit":
            built.append(ExcludeUnit.model_validate(item))
        else:
            built.append(PriorityBoost.model_validate(item))
    return built


def arm_summary(outcome: DecisionOutcome, scenario: Scenario,
                constraints: Sequence[PlanningConstraint]) -> dict[str, Any]:
    result, report = outcome.result, outcome.verification
    failed = [check.id for check in report.failed()]
    objective = plan_objective(result.assignments, result.unmet_requirements, scenario,
                               outcome.travel_times, constraints)
    produced = not any(f.code == "NIM_DECISION_UNAVAILABLE" for f in result.safety_findings)
    return {
        "produced_plan": produced,
        "feasible": produced and not set(failed) & set(HARD_CHECKS),
        "verdict": report.verdict.value,
        "safety_gate_blocked": report.safety_gate_blocked,
        "failed_checks": failed,
        "objective": objective.total,
        "unmet_penalty": objective.unmet_penalty,
        "weighted_travel": objective.weighted_travel,
        "coverage": result.coverage,
        "assignments": [a.model_dump(mode="json") for a in result.assignments],
        "unmet": [u.model_dump(mode="json") for u in result.unmet_requirements],
    }


def run_experiment(rows: Sequence[dict[str, Any]], new_client: Callable[[], LLMClient],
                   workers: int) -> list[dict[str, Any]]:
    """``new_client`` builds one client per scenario, so each row's call log is its own."""

    def one(row: dict[str, Any]) -> dict[str, Any]:
        scenario = Scenario.model_validate(row["scenario"])
        constraints = constraints_of(row)
        matrix = TravelTimeMatrix.model_validate(row["travel_times"])
        llm = new_client()
        engine = LLMDecisionEngine(NoRetrieval(), llm=llm, prompt_version=PROMPT_VERSION)
        service = DecisionService({LLM_ENGINE: engine}, RecordedTravelTimes(matrix))
        solver = service.decide(scenario, "solver", constraints)
        model = service.decide(scenario, LLM_ENGINE, constraints)
        calls = [record_dict(r) for r in llm.call_log.records]
        return {
            "id": row["id"], "incidents": len(scenario.incidents),
            "units": len(scenario.resources), "constraints": row["constraints"],
            "solve_status": solver.reference.status.value,
            "solver": arm_summary(solver, scenario, constraints),
            "llm": arm_summary(model, scenario, constraints),
            "calls": calls,
        }

    return pmap(one, rows, workers)


def _rate(outputs: Sequence[dict[str, Any]], arm: str, key: str) -> dict[str, Any]:
    return bootstrap([1.0 if o[arm][key] else 0.0 for o in outputs], mean).as_dict()


def _median(values: Sequence[float]) -> float | None:
    return quantile(values, 0.5)


def score(outputs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    both = [o for o in outputs if o["llm"]["feasible"] and o["solver"]["feasible"]]
    gaps = [(o["llm"]["objective"] - o["solver"]["objective"]) / o["solver"]["objective"]
            for o in both if o["solver"]["objective"] > 0]
    travel_gaps = [
        (o["llm"]["weighted_travel"] - o["solver"]["weighted_travel"])
        / o["solver"]["weighted_travel"]
        for o in both
        if o["solver"]["weighted_travel"] > 0 and o["llm"]["unmet_penalty"]
        == o["solver"]["unmet_penalty"]
    ]
    summary: dict[str, Any] = {"scenarios": len(outputs)}
    for arm in ("solver", "llm"):
        summary[arm] = {
            "produced_plan": _rate(outputs, arm, "produced_plan"),
            "feasible": _rate(outputs, arm, "feasible"),
            "verdict_pass": bootstrap(
                [1.0 if o[arm]["verdict"] == "pass" else 0.0 for o in outputs], mean
            ).as_dict(),
            "findings_per_plan": bootstrap(
                [float(len(o[arm]["failed_checks"])) for o in outputs], mean
            ).as_dict(),
            "failed_check_counts": dict(Counter(
                check for o in outputs for check in o[arm]["failed_checks"]
            ).most_common()),
            "coverage": bootstrap([o[arm]["coverage"] for o in outputs], mean).as_dict(),
        }
    summary["optimality_gap"] = {
        "n": len(gaps),
        "median": bootstrap(gaps, _median).as_dict(),
        "mean": bootstrap(gaps, mean).as_dict(),
        "within_1pct": bootstrap([1.0 if g <= 0.01 else 0.0 for g in gaps], mean).as_dict(),
        "travel_only_median": bootstrap(travel_gaps, _median).as_dict(),
        "travel_only_n": len(travel_gaps),
    }
    return summary


def markdown(results: dict[str, Any]) -> str:
    meta, s = results["meta"], results["summary"]
    gap = s["optimality_gap"]
    lines = [
        f"# LLM-direct allocation vs CP-SAT ({meta['date']})",
        "",
        f"{s['scenarios']} Lucknow scenarios (`{DATASET.relative_to(ROOT)}`, SHA-256 "
        f"`{meta['dataset_sha256']}`), road travel minutes recorded from OSRM "
        f"(`{meta['travel_provider']}`). LLM arm: `{meta['model']}`, prompt `{PROMPT_VERSION}`, "
        "temperature 0, no retrieval. Both arms pass through the same `DecisionService` and "
        "verifier. 95% bootstrap CIs (2000 rounds, seed 20260923).",
        "",
        "| Metric | CP-SAT | LLM-direct |",
        "|---|---|---|",
    ]
    for label, key, percent in (
        ("Produced a plan", "produced_plan", True),
        ("Feasible (no failed hard check)", "feasible", True),
        ("Verdict pass (a critical shortage blocks either arm)", "verdict_pass", True),
        ("Coverage (mean)", "coverage", True),
        ("Verifier findings per plan (mean)", "findings_per_plan", False),
    ):
        lines.append(f"| {label} | {fmt(s['solver'][key], percent, 2 if not percent else 1)} | "
                     f"{fmt(s['llm'][key], percent, 2 if not percent else 1)} |")
    lines += [
        "",
        f"Optimality gap over the {gap['n']} scenarios where both plans are feasible: median "
        f"{fmt(gap['median'])}, mean {fmt(gap['mean'])}; within 1% of optimal: "
        f"{fmt(gap['within_1pct'])}. Travel-only gap (scenarios where both leave the same "
        f"demand unmet, n={gap['travel_only_n']}): median {fmt(gap['travel_only_median'])}.",
        "",
        "Failed checks, LLM-direct: "
        + (", ".join(f"`{k}` {v}" for k, v in s["llm"]["failed_check_counts"].items()) or "none")
        + ".",
        "Failed checks, CP-SAT: "
        + (", ".join(f"`{k}` {v}" for k, v in s["solver"]["failed_check_counts"].items())
           or "none") + ".",
        "",
        f"LLM calls: {meta['calls']}, estimated cost ${meta['total_cost_usd']:.4f} at "
        f"${meta['price_in']}/${meta['price_out']} per million input/output tokens; latency "
        f"p50 {meta['latency_p50_s']:.2f} s, p95 {meta['latency_p95_s']:.2f} s.",
        "",
        "Raw plans and per-plan verifier findings: "
        f"`reports/raw/llm_vs_solver_{meta['date']}/plans.jsonl`.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Build the dataset (needs OSRM).")
    parser.add_argument("--osrm-url", default="http://127.0.0.1:5001")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--date", default=datetime.now(UTC).strftime("%Y-%m-%d"))
    args = parser.parse_args()

    if args.build:
        exercise = json.loads((DATA / "lucknow_exercise_v1.json").read_text())
        rows = record_matrices(
            build_scenarios(Gazetteer.load(DEFAULT_GAZETTEER), exercise["resources"]),
            args.osrm_url,
        )
        DATASET.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        print(f"wrote {len(rows)} scenarios with OSRM matrices to {DATASET}")
        return

    settings = Settings(llm_max_retries=5)
    llm = LLMClient(settings)
    if not llm.available:
        sys.exit("No LLM key: set AEGISOPS_LLM_API_KEY (see ENVIRONMENT.md).")
    rows = load_jsonl(DATASET)[: args.limit]
    outputs = run_experiment(rows, lambda: LLMClient(settings), args.workers)
    raw = ROOT / "reports" / "raw" / f"llm_vs_solver_{args.date}"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "plans.jsonl").write_text(
        "".join(json.dumps(o) + "\n" for o in outputs), encoding="utf-8")
    calls = [c for o in outputs for c in o["calls"]]
    latencies = [c["latency_s"] for c in calls]
    results = {
        "meta": {
            "date": args.date, "model": llm.model, "base_url": settings.llm_base_url,
            "prompt_version": PROMPT_VERSION, "dataset_sha256": sha(DATASET),
            "travel_provider": rows[0]["travel_times"]["provider"] if rows else None,
            "calls": len(calls), "total_cost_usd": sum(c["cost_usd"] for c in calls),
            "price_in": settings.llm_price_in_usd_per_mtok,
            "price_out": settings.llm_price_out_usd_per_mtok,
            "latency_p50_s": quantile(latencies, 0.5) or 0.0,
            "latency_p95_s": quantile(latencies, 0.95) or 0.0, "limit": args.limit,
        },
        "summary": score(outputs),
    }
    out = ROOT / "reports" / "llm_vs_solver"
    out.with_suffix(".json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    out.with_suffix(".md").write_text(markdown(results), encoding="utf-8")
    print(f"wrote {out}.md and .json; raw plans in {raw}")


if __name__ == "__main__":
    main()

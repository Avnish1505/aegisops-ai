"""Re-run the deterministic steps on a stored decision record.

``reverify`` rebuilds the plan exactly as stored, re-solves the stored scenario on the stored
travel matrix and constraints for the reference optimum, and runs the verifier again; the result
is compared check by check with the verification stored at decision time. ``baseline`` solves the
same inputs without the operator's constraints, so a reviewer can see what the constraints cost.

Both read only the stored record (no OSRM, no LLM), so the answer depends on nothing that could
have changed since the decision was made.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import TypeAdapter

from aegisops.domain.models import DecisionResult, Evidence, Scenario
from aegisops.planning.constraints import PlanningConstraint
from aegisops.planning.objective import plan_objective
from aegisops.planning.solver import solve
from aegisops.planning.travel import TravelTimeMatrix
from aegisops.verification.models import TextDraft, VerificationPolicy
from aegisops.verification.verifier import verify

CONSTRAINTS = TypeAdapter(list[PlanningConstraint])
# Engines that must cite retrieved evidence (DecisionService.CITING_ENGINES, by result name).
CITING_ENGINE_NAMES = frozenset({"nvidia_nim_v1"})
SOLVER_TIME_LIMIT_S = 10.0


def stored_plan(record: Mapping[str, Any]) -> DecisionResult:
    return DecisionResult.model_validate({
        "scenario_id": record["scenario_id"],
        "engine": record["engine"],
        "status": record["status"],
        "requires_human_approval": record["requires_human_approval"],
        "assignments": record.get("assignments") or [],
        "unmet_requirements": record.get("unmet_requirements") or [],
        "safety_findings": record.get("safety_findings") or [],
        "coverage": record["coverage"],
        "decision_trace": record.get("decision_trace") or [],
        "evidence": record.get("evidence") or [],
    })


def _inputs(
    record: Mapping[str, Any],
) -> tuple[Scenario, TravelTimeMatrix, list[PlanningConstraint]]:
    return (
        Scenario.model_validate(record["scenario"]),
        TravelTimeMatrix.model_validate(record["travel_times"]),
        CONSTRAINTS.validate_python(record.get("constraints") or []),
    )


def reverify(record: Mapping[str, Any]) -> dict[str, Any]:
    scenario, matrix, constraints = _inputs(record)
    plan = stored_plan(record)
    reference = solve(scenario, matrix, constraints, time_limit_s=SOLVER_TIME_LIMIT_S)
    report = verify(
        plan,
        scenario,
        reference_plan=reference,
        travel_times=matrix,
        constraints=constraints,
        evidence=[Evidence.model_validate(e) for e in record.get("evidence") or []],
        text_drafts=[TextDraft.model_validate(d) for d in record.get("drafts") or []],
        policy=VerificationPolicy(require_citations=record["engine"] in CITING_ENGINE_NAMES),
    )
    recomputed = report.model_dump(mode="json")
    stored = record.get("verification") or {}
    stored_checks = {c["id"]: c["passed"] for c in stored.get("checks", [])}
    fresh_checks = {c["id"]: c["passed"] for c in recomputed["checks"]}
    differing = sorted(
        check_id for check_id in stored_checks.keys() | fresh_checks.keys()
        if stored_checks.get(check_id) != fresh_checks.get(check_id)
    )
    return {
        "decision_id": record["decision_id"],
        "matches": recomputed == stored,
        "same_verdict": recomputed["verdict"] == stored.get("verdict"),
        "differing_checks": differing,
        "stored": stored,
        "recomputed": recomputed,
        "scenario_sha256": scenario.sha256(),
        "scenario_sha256_matches": scenario.sha256() == record.get("scenario_sha256"),
    }


def _pairs(assignments: Sequence[Mapping[str, Any]]) -> Counter[tuple[str, str]]:
    return Counter((str(a["incident_id"]), str(a["resource_id"])) for a in assignments)


def _listed(pairs: Counter[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"incident_id": i, "resource_id": r} for (i, r) in sorted(pairs.elements())]


def baseline(record: Mapping[str, Any]) -> dict[str, Any]:
    scenario, matrix, constraints = _inputs(record)
    unconstrained = solve(scenario, matrix, (), time_limit_s=SOLVER_TIME_LIMIT_S)
    plan = stored_plan(record)
    plan_pairs = _pairs(record.get("assignments") or [])
    base_assignments = [a.model_dump(mode="json") for a in unconstrained.assignments]
    base_pairs = _pairs(base_assignments)
    base_objective = plan_objective(
        unconstrained.assignments, unconstrained.unmet_requirements, scenario, matrix, ()
    )
    plan_objective_value = plan_objective(
        plan.assignments, plan.unmet_requirements, scenario, matrix, ()
    )
    return {
        "decision_id": record["decision_id"],
        "constraints": len(constraints),
        "status": unconstrained.status.value,
        "assignments": base_assignments,
        "unmet_requirements": [u.model_dump(mode="json") for u in unconstrained.unmet_requirements],
        # Both scored without constraint weights, so the numbers are comparable.
        "objective": base_objective.total,
        "plan_objective": plan_objective_value.total,
        "only_in_plan": _listed(plan_pairs - base_pairs),
        "only_in_baseline": _listed(base_pairs - plan_pairs),
        "same_as_plan": plan_pairs == base_pairs,
    }

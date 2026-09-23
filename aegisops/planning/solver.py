"""CP-SAT assignment of available units to incident requirements.

Hard constraints: a unit serves at most one incident, only available units are used, a unit is
only assigned to an incident that needs its type, and no requirement receives more units than it
asked for. Operator constraints (``ReserveConstraint``, ``ExcludeUnit``) are also hard; each is
guarded by an assumption literal so an infeasible model reports which constraints conflict.
Coverage is soft: the objective (``planning.objective``) penalises every unmet unit.

The search runs single-threaded with a fixed seed so a stored scenario replays to the same plan.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from enum import StrEnum

from ortools.sat.python import cp_model
from pydantic import BaseModel, ConfigDict

from aegisops.domain.models import (
    Assignment,
    DecisionResult,
    DecisionStatus,
    Scenario,
    UnmetRequirement,
)
from aegisops.domain.policy import evaluate_safety_gates
from aegisops.planning.constraints import (
    ExcludeUnit,
    PlanningConstraint,
    PriorityBoost,
    ReserveConstraint,
)
from aegisops.planning.objective import (
    UNMET_PENALTY_MINUTES,
    incident_weight,
    plan_coverage,
    plan_objective,
)
from aegisops.planning.travel import EuclideanProvider, TravelTimeMatrix, TravelTimeProvider

# CP-SAT needs integer coefficients: weights and minutes are scaled to hundredths.
SCALE = 100


class SolveStatus(StrEnum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"
    INVALID_INPUT = "invalid_input"


class InfeasibilityExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflicting_constraints: list[PlanningConstraint]
    message: str


class SolveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SolveStatus
    assignments: list[Assignment]
    unmet_requirements: list[UnmetRequirement]
    objective: float | None
    infeasibility: InfeasibilityExplanation | None = None
    wall_time_s: float

    @property
    def has_plan(self) -> bool:
        return self.status in {SolveStatus.OPTIMAL, SolveStatus.FEASIBLE}


def solve(
    scenario: Scenario,
    travel_times: TravelTimeMatrix,
    constraints: Sequence[PlanningConstraint] = (),
    *,
    time_limit_s: float = 10.0,
) -> SolveResult:
    """Return the minimum-objective plan, or why none exists."""
    started = time.perf_counter()
    problems, bad_constraints = _input_problems(scenario, travel_times, constraints)
    if problems:
        return SolveResult(
            status=SolveStatus.INVALID_INPUT,
            assignments=[],
            unmet_requirements=[],
            objective=None,
            infeasibility=InfeasibilityExplanation(
                conflicting_constraints=bad_constraints, message="; ".join(problems)
            ),
            wall_time_s=time.perf_counter() - started,
        )

    model = cp_model.CpModel()
    candidates: dict[tuple[str, str], cp_model.IntVar] = {}
    for resource in scenario.resources:
        if not resource.available:
            continue
        for incident in scenario.incidents:
            if resource.type in incident.resources_needed:
                candidates[(resource.id, incident.id)] = model.new_bool_var(
                    f"x[{resource.id},{incident.id}]"
                )

    by_resource: dict[str, list[cp_model.IntVar]] = {}
    for (resource_id, _), variable in candidates.items():
        by_resource.setdefault(resource_id, []).append(variable)
    for variables in by_resource.values():
        model.add_at_most_one(variables)

    resource_types = {resource.id: resource.type for resource in scenario.resources}
    objective_terms: list[cp_model.LinearExprT] = []
    for incident in scenario.incidents:
        weight = round(incident_weight(incident, constraints) * SCALE)
        for resource_type, quantity in incident.resources_needed.items():
            assigned = [
                variable
                for (resource_id, incident_id), variable in candidates.items()
                if incident_id == incident.id and resource_types[resource_id] == resource_type
            ]
            model.add(sum(assigned) <= quantity)
            penalty = weight * round(UNMET_PENALTY_MINUTES * SCALE)
            objective_terms.append(penalty * (quantity - sum(assigned)))
        for (resource_id, incident_id), variable in candidates.items():
            if incident_id == incident.id:
                # _input_problems has already rejected matrices with missing pairs.
                minutes = travel_times.minutes[resource_id][incident_id]
                objective_terms.append(weight * round(minutes * SCALE) * variable)

    guards = _add_operator_constraints(model, scenario, candidates, constraints)
    model.minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    elapsed = time.perf_counter() - started

    if status == cp_model.INFEASIBLE:
        core = set(solver.sufficient_assumptions_for_infeasibility())
        conflicting = [
            constraint for constraint, guard in guards if guard.index in core
        ] or [constraint for constraint, _ in guards]
        return SolveResult(
            status=SolveStatus.INFEASIBLE,
            assignments=[],
            unmet_requirements=[],
            objective=None,
            infeasibility=InfeasibilityExplanation(
                conflicting_constraints=conflicting,
                message=_describe_conflict(conflicting, scenario),
            ),
            wall_time_s=elapsed,
        )
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolveResult(
            status=SolveStatus.TIMEOUT,
            assignments=[],
            unmet_requirements=[],
            objective=None,
            wall_time_s=elapsed,
        )

    assignments = [
        Assignment(
            incident_id=incident_id,
            resource_id=resource_id,
            resource_type=resource_types[resource_id],
            travel_minutes=round(travel_times.get(resource_id, incident_id) or 0.0, 2),
        )
        for (resource_id, incident_id), variable in sorted(candidates.items(), key=_pair_order)
        if solver.value(variable)
    ]
    unmet = _unmet(scenario, assignments)
    return SolveResult(
        status=SolveStatus.OPTIMAL if status == cp_model.OPTIMAL else SolveStatus.FEASIBLE,
        assignments=assignments,
        unmet_requirements=unmet,
        objective=plan_objective(assignments, unmet, scenario, travel_times, constraints).total,
        wall_time_s=elapsed,
    )


class SolverDecisionEngine:
    """DecisionEngine adapter around ``solve``."""

    name = "cp_sat_v1"

    def __init__(
        self, travel_provider: TravelTimeProvider | None = None, *, time_limit_s: float = 10.0
    ) -> None:
        self._travel_provider = travel_provider or EuclideanProvider()
        self._time_limit_s = time_limit_s

    def recommend(
        self,
        scenario: Scenario,
        travel_times: TravelTimeMatrix | None = None,
        constraints: Sequence[PlanningConstraint] = (),
    ) -> DecisionResult:
        matrix = travel_times or self._travel_provider.matrix(scenario)
        return self.result_from_solve(
            scenario, solve(scenario, matrix, constraints, time_limit_s=self._time_limit_s)
        )

    def result_from_solve(self, scenario: Scenario, result: SolveResult) -> DecisionResult:
        trace = [f"CP-SAT status {result.status.value} in {result.wall_time_s:.3f}s."]
        if not result.has_plan:
            reason = (
                result.infeasibility.message
                if result.infeasibility is not None
                else "The solver found no plan within its time limit."
            )
            trace.append(reason)
            findings, _ = evaluate_safety_gates([], scenario)
            return DecisionResult(
                scenario_id=scenario.scenario_id,
                engine=self.name,
                status=DecisionStatus.BLOCKED,
                assignments=[],
                unmet_requirements=[],
                safety_findings=findings,
                coverage=0.0,
                decision_trace=trace,
            )
        trace.append(f"Objective {result.objective:.2f} (weighted unmet penalty + travel).")
        findings, blocked = evaluate_safety_gates(result.unmet_requirements, scenario)
        trace.append("Applied deterministic safety gates; no dispatch was executed.")
        return DecisionResult(
            scenario_id=scenario.scenario_id,
            engine=self.name,
            status=DecisionStatus.BLOCKED if blocked else DecisionStatus.REQUIRES_HUMAN_APPROVAL,
            assignments=result.assignments,
            unmet_requirements=result.unmet_requirements,
            safety_findings=findings,
            coverage=plan_coverage(result.assignments, scenario),
            decision_trace=trace,
        )


def _pair_order(item: tuple[tuple[str, str], object]) -> tuple[str, str]:
    (resource_id, incident_id), _ = item
    return (incident_id, resource_id)


def _unmet(scenario: Scenario, assignments: list[Assignment]) -> list[UnmetRequirement]:
    counts: dict[tuple[str, object], int] = {}
    for assignment in assignments:
        key = (assignment.incident_id, assignment.resource_type)
        counts[key] = counts.get(key, 0) + 1
    return [
        UnmetRequirement(
            incident_id=incident.id,
            resource_type=resource_type,
            quantity=quantity - counts.get((incident.id, resource_type), 0),
            severity=incident.severity,
        )
        for incident in scenario.incidents
        for resource_type, quantity in incident.resources_needed.items()
        if quantity > counts.get((incident.id, resource_type), 0)
    ]


def _input_problems(
    scenario: Scenario, travel_times: TravelTimeMatrix, constraints: Sequence[PlanningConstraint]
) -> tuple[list[str], list[PlanningConstraint]]:
    resource_ids = {resource.id for resource in scenario.resources}
    incident_ids = {incident.id for incident in scenario.incidents}
    problems: list[str] = []
    bad: list[PlanningConstraint] = []
    for constraint in constraints:
        if isinstance(constraint, ExcludeUnit) and constraint.unit_id not in resource_ids:
            problems.append(f"ExcludeUnit names unknown unit {constraint.unit_id}")
            bad.append(constraint)
        if isinstance(constraint, PriorityBoost) and constraint.incident_id not in incident_ids:
            problems.append(f"PriorityBoost names unknown incident {constraint.incident_id}")
            bad.append(constraint)
    missing = [
        f"{resource.id}->{incident.id}"
        for resource in scenario.resources
        for incident in scenario.incidents
        if travel_times.get(resource.id, incident.id) is None
    ]
    if missing:
        problems.append(f"travel-time matrix is missing {len(missing)} pairs, e.g. {missing[0]}")
    return problems, bad


def _add_operator_constraints(
    model: cp_model.CpModel,
    scenario: Scenario,
    candidates: dict[tuple[str, str], cp_model.IntVar],
    constraints: Sequence[PlanningConstraint],
) -> list[tuple[PlanningConstraint, cp_model.IntVar]]:
    guards: list[tuple[PlanningConstraint, cp_model.IntVar]] = []
    exclusion_guards: dict[str, list[cp_model.IntVar]] = {}
    for index, constraint in enumerate(constraints):
        if isinstance(constraint, ExcludeUnit):
            guard = model.new_bool_var(f"guard[{index}]")
            for (resource_id, _), variable in candidates.items():
                if resource_id == constraint.unit_id:
                    model.add(variable == 0).only_enforce_if(guard)
            exclusion_guards.setdefault(constraint.unit_id, []).append(guard)
            guards.append((constraint, guard))

    for index, constraint in enumerate(constraints):
        if not isinstance(constraint, ReserveConstraint):
            continue
        guard = model.new_bool_var(f"guard[{index}]")
        counted: list[cp_model.IntVar] = []
        for resource in constraint.pool(scenario.resources, excluded_ids=set()):
            # A unit counts towards the reserve only if it stays idle and is not excluded.
            reserved = model.new_bool_var(f"reserved[{index},{resource.id}]")
            for (resource_id, _), variable in candidates.items():
                if resource_id == resource.id:
                    model.add(reserved + variable <= 1)
            for exclusion in exclusion_guards.get(resource.id, []):
                model.add(reserved + exclusion <= 1)
            counted.append(reserved)
        model.add(sum(counted) >= constraint.count).only_enforce_if(guard)
        guards.append((constraint, guard))

    if guards:
        model.add_assumptions([guard for _, guard in guards])
    return guards


def _describe_conflict(conflicting: list[PlanningConstraint], scenario: Scenario) -> str:
    excluded = {item.unit_id for item in conflicting if isinstance(item, ExcludeUnit)}
    parts: list[str] = []
    for constraint in conflicting:
        if isinstance(constraint, ReserveConstraint):
            pool = constraint.pool(scenario.resources, excluded_ids=excluded)
            parts.append(
                f"reserve of {constraint.count} {constraint.resource_type.value} in zone "
                f"{constraint.zone.id} but only {len(pool)} available, non-excluded units there"
            )
        elif isinstance(constraint, ExcludeUnit):
            parts.append(f"unit {constraint.unit_id} excluded")
    return "No plan satisfies: " + "; ".join(parts) + "."

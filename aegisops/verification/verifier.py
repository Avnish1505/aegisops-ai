"""Deterministic verification of a proposed plan. Pure: no I/O, no clock, no randomness.

Travel times arrive as a precomputed matrix, so a road-network provider can be swapped in
without the verifier ever making a network call. Any failed critical check blocks the plan; so
does the existing safety gate when a critical incident honestly declares unmet demand.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from aegisops.domain.models import (
    DecisionResult,
    Evidence,
    Incident,
    Resource,
    ResourceType,
    Scenario,
    Severity,
)
from aegisops.domain.policy import evaluate_safety_gates
from aegisops.planning.constraints import (
    ExcludeUnit,
    PlanningConstraint,
    ReserveConstraint,
    excluded_unit_ids,
)
from aegisops.planning.objective import plan_objective
from aegisops.planning.solver import SolveResult, SolveStatus
from aegisops.planning.travel import TravelTimeMatrix
from aegisops.verification.injection import looks_like_instruction
from aegisops.verification.models import (
    CheckResult,
    CheckSeverity,
    TextDraft,
    Verdict,
    VerificationPolicy,
    VerificationReport,
)
from aegisops.verification.numbers import number_mismatches

CRITICAL = CheckSeverity.CRITICAL
HIGH = CheckSeverity.HIGH
WARNING = CheckSeverity.WARNING


@dataclass(frozen=True, slots=True)
class _Context:
    plan: DecisionResult
    scenario: Scenario
    reference: SolveResult
    travel_times: TravelTimeMatrix
    constraints: Sequence[PlanningConstraint]
    evidence: Sequence[Evidence]
    drafts: Sequence[TextDraft]
    policy: VerificationPolicy
    resources: dict[str, Resource]
    incidents: dict[str, Incident]


def verify(
    plan: DecisionResult,
    scenario: Scenario,
    *,
    reference_plan: SolveResult,
    travel_times: TravelTimeMatrix,
    constraints: Sequence[PlanningConstraint] = (),
    evidence: Sequence[Evidence] = (),
    text_drafts: Sequence[TextDraft] = (),
    policy: VerificationPolicy | None = None,
) -> VerificationReport:
    context = _Context(
        plan=plan,
        scenario=scenario,
        reference=reference_plan,
        travel_times=travel_times,
        constraints=constraints,
        evidence=evidence,
        drafts=text_drafts,
        policy=policy or VerificationPolicy(),
        resources={resource.id: resource for resource in scenario.resources},
        incidents={incident.id: incident for incident in scenario.incidents},
    )
    checks = [check(context) for check in CHECKS]
    blocking = [c.id for c in checks if not c.passed and c.severity == CheckSeverity.CRITICAL]
    _, gate_blocked = evaluate_safety_gates(
        [item for item in plan.unmet_requirements if item.incident_id in context.incidents],
        scenario,
    )
    return VerificationReport(
        verdict=Verdict.BLOCKED if blocking or gate_blocked else Verdict.PASS,
        checks=checks,
        blocking_check_ids=blocking,
        safety_gate_blocked=gate_blocked,
    )


def _result(
    check_id: str, severity: CheckSeverity, offending: list[str], ok: str, failed: str
) -> CheckResult:
    unique = list(dict.fromkeys(offending))
    return CheckResult(
        id=check_id,
        passed=not unique,
        severity=severity,
        message=ok if not unique else f"{failed}: {', '.join(unique)}",
        offending_ids=unique,
    )


def _incident_exists(ctx: _Context) -> CheckResult:
    bad = [a.incident_id for a in ctx.plan.assignments if a.incident_id not in ctx.incidents]
    return _result(
        "incident_exists", CRITICAL, bad, "Every assignment targets a scenario incident.",
        "Assignments target incidents not in the scenario",
    )


def _unit_exists(ctx: _Context) -> CheckResult:
    bad = [a.resource_id for a in ctx.plan.assignments if a.resource_id not in ctx.resources]
    return _result(
        "unit_exists", CRITICAL, bad, "Every assigned unit exists in the scenario.",
        "Units not in the scenario",
    )


def _unit_available(ctx: _Context) -> CheckResult:
    bad = [
        a.resource_id
        for a in ctx.plan.assignments
        if a.resource_id in ctx.resources and not ctx.resources[a.resource_id].available
    ]
    return _result(
        "unit_available", CRITICAL, bad, "Every assigned unit is available.",
        "Unavailable units assigned",
    )


def _unit_not_duplicated(ctx: _Context) -> CheckResult:
    seen: set[str] = set()
    bad: list[str] = []
    for assignment in ctx.plan.assignments:
        if assignment.resource_id in seen:
            bad.append(assignment.resource_id)
        seen.add(assignment.resource_id)
    return _result(
        "unit_not_duplicated", CRITICAL, bad, "No unit is assigned twice.",
        "Units assigned more than once",
    )


def _capability_match(ctx: _Context) -> CheckResult:
    bad: list[str] = []
    for assignment in ctx.plan.assignments:
        resource = ctx.resources.get(assignment.resource_id)
        incident = ctx.incidents.get(assignment.incident_id)
        if resource is None or incident is None:
            continue
        if (
            assignment.resource_type != resource.type
            or resource.type not in incident.resources_needed
        ):
            bad.append(assignment.resource_id)
    return _result(
        "capability_match", CRITICAL, bad,
        "Every unit's type is one its incident requires, and is reported truthfully.",
        "Units whose type the incident does not need, or is misreported",
    )


def _assigned_counts(ctx: _Context) -> dict[tuple[str, ResourceType], int]:
    counts: dict[tuple[str, ResourceType], int] = {}
    for assignment in ctx.plan.assignments:
        resource = ctx.resources.get(assignment.resource_id)
        if resource is not None and assignment.incident_id in ctx.incidents:
            key = (assignment.incident_id, resource.type)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _quantity_within_requirement(ctx: _Context) -> CheckResult:
    bad = [
        incident_id
        for (incident_id, resource_type), count in _assigned_counts(ctx).items()
        if count > ctx.incidents[incident_id].resources_needed.get(resource_type, 0)
    ]
    return _result(
        "quantity_within_requirement", CRITICAL, bad,
        "No requirement receives more units than it asked for.",
        "Incidents given more units than required",
    )


def _travel_time_matches(ctx: _Context) -> CheckResult:
    bad: list[str] = []
    for assignment in ctx.plan.assignments:
        verified = ctx.travel_times.get(assignment.resource_id, assignment.incident_id)
        if verified is None:
            continue
        if abs(assignment.travel_minutes - verified) > ctx.policy.travel_tolerance(verified):
            bad.append(assignment.resource_id)
    return _result(
        "travel_time_matches", CRITICAL, bad,
        f"Every travel time matches the {ctx.travel_times.provider} recomputation.",
        f"Travel times differ from {ctx.travel_times.provider} beyond tolerance",
    )


def _requirements_unaccounted(ctx: _Context, critical: bool) -> list[str]:
    assigned = _assigned_counts(ctx)
    declared: dict[tuple[str, ResourceType], int] = {}
    for item in ctx.plan.unmet_requirements:
        key = (item.incident_id, item.resource_type)
        declared[key] = declared.get(key, 0) + item.quantity
    bad: list[str] = []
    for incident in ctx.scenario.incidents:
        if (incident.severity == Severity.CRITICAL) != critical:
            continue
        for resource_type, quantity in incident.resources_needed.items():
            key = (incident.id, resource_type)
            if min(assigned.get(key, 0), quantity) + declared.get(key, 0) != quantity:
                bad.append(incident.id)
    return bad


def _critical_incidents_accounted(ctx: _Context) -> CheckResult:
    return _result(
        "critical_incidents_accounted", CRITICAL, _requirements_unaccounted(ctx, critical=True),
        "Every critical requirement is covered or explicitly declared unmet (and so blocked).",
        "Critical incidents neither covered nor declared unmet",
    )


def _unmet_declared_accurately(ctx: _Context) -> CheckResult:
    return _result(
        "unmet_declared_accurately", HIGH, _requirements_unaccounted(ctx, critical=False),
        "Declared unmet demand matches the plan for non-critical incidents.",
        "Non-critical incidents with misreported unmet demand",
    )


def _objective_within_tolerance(ctx: _Context) -> CheckResult:
    reference = ctx.reference
    if not reference.has_plan or reference.objective is None:
        return CheckResult(
            id="objective_within_tolerance", passed=True, severity=HIGH,
            message=f"No reference optimum to compare against ({reference.status.value}).",
        )
    plan = plan_objective(
        ctx.plan.assignments, ctx.plan.unmet_requirements, ctx.scenario, ctx.travel_times,
        ctx.constraints,
    )
    best = plan_objective(
        reference.assignments, reference.unmet_requirements, ctx.scenario, ctx.travel_times,
        ctx.constraints,
    )
    limit = best.total * (1 + ctx.policy.objective_tolerance) + ctx.policy.objective_abs_slack
    worse_coverage = plan.unmet_penalty > best.unmet_penalty + ctx.policy.objective_abs_slack
    passed = not worse_coverage and plan.total <= limit
    return CheckResult(
        id="objective_within_tolerance",
        passed=passed,
        severity=HIGH,
        message=(
            f"Objective {plan.total:.1f} vs optimum {best.total:.1f} "
            f"(limit {limit:.1f}{'; covers less demand' if worse_coverage else ''})."
        ),
        offending_ids=[] if passed else [ctx.plan.engine],
    )


def _constraints_feasible(ctx: _Context) -> CheckResult:
    status = ctx.reference.status
    infeasible = status in {SolveStatus.INFEASIBLE, SolveStatus.INVALID_INPUT}
    message = (
        ctx.reference.infeasibility.message
        if infeasible and ctx.reference.infeasibility is not None
        else f"Operator constraints are satisfiable ({status.value})."
    )
    return CheckResult(
        id="constraints_feasible", passed=not infeasible, severity=CRITICAL, message=message,
        offending_ids=["constraints"] if infeasible else [],
    )


def _constraints_satisfied(ctx: _Context) -> CheckResult:
    assigned_units = {a.resource_id for a in ctx.plan.assignments}
    excluded = excluded_unit_ids(ctx.constraints)
    bad: list[str] = []
    for constraint in ctx.constraints:
        if isinstance(constraint, ExcludeUnit) and constraint.unit_id in assigned_units:
            bad.append(constraint.unit_id)
        if isinstance(constraint, ReserveConstraint):
            idle = [
                unit
                for unit in constraint.pool(ctx.scenario.resources, excluded)
                if unit.id not in assigned_units
            ]
            if len(idle) < constraint.count:
                bad.append(f"reserve:{constraint.zone.id}:{constraint.resource_type.value}")
    return _result(
        "constraints_satisfied", CRITICAL, bad, "Every operator constraint holds.",
        "Operator constraints violated",
    )


def _citations_retrieved(ctx: _Context) -> CheckResult:
    retrieved = {item.id for item in ctx.evidence}
    bad = [
        citation.evidence_id
        for assignment in ctx.plan.assignments
        for citation in assignment.citations
        if citation.evidence_id not in retrieved
    ]
    return _result(
        "citations_retrieved", CRITICAL, bad, "Every citation names evidence that was retrieved.",
        "Citations of evidence that was never retrieved",
    )


def _citation_quotes_present(ctx: _Context) -> CheckResult:
    texts = {item.id: _normalise(item.description) for item in ctx.evidence}
    bad: list[str] = []
    for assignment in ctx.plan.assignments:
        for citation in assignment.citations:
            text = texts.get(citation.evidence_id)
            quote = _normalise(citation.quote)
            if text is not None and (not quote or quote not in text):
                bad.append(citation.evidence_id)
    return _result(
        "citation_quotes_present", CRITICAL, bad,
        "Every quoted span appears verbatim in its cited evidence.",
        "Quotes not found in the cited evidence",
    )


def _assignments_cited(ctx: _Context) -> CheckResult:
    if not ctx.policy.require_citations:
        return CheckResult(
            id="assignments_cited", passed=True, severity=HIGH,
            message="This engine is not required to cite evidence.",
        )
    bad = [f"{a.incident_id}/{a.resource_id}" for a in ctx.plan.assignments if not a.citations]
    return _result(
        "assignments_cited", HIGH, bad, "Every assignment cites retrieved evidence.",
        "Assignments with no citation",
    )


def _draft_numbers_match_state(ctx: _Context) -> CheckResult:
    problems: list[str] = []
    for draft in ctx.drafts:
        for mismatch in number_mismatches(draft.text, ctx.plan, ctx.scenario, ctx.travel_times):
            problems.append(f"{draft.id} {mismatch.describe()}")
    return _result(
        "draft_numbers_match_state", CRITICAL, problems,
        f"Every number in {len(ctx.drafts)} draft(s) matches the plan.",
        "Draft numbers that do not match the plan",
    )


def _human_approval_required(ctx: _Context) -> CheckResult:
    bad = [] if ctx.plan.requires_human_approval else [ctx.plan.engine]
    return _result(
        "human_approval_required", CRITICAL, bad, "The plan requires human approval.",
        "The proposal removed the human-approval requirement",
    )


def _travel_times_not_degraded(ctx: _Context) -> CheckResult:
    matrix = ctx.travel_times
    return CheckResult(
        id="travel_times_not_degraded",
        passed=not matrix.degraded,
        severity=HIGH,
        message=(
            f"Travel times came from {matrix.provider} as configured."
            if not matrix.degraded
            else f"Degraded travel times: {matrix.degraded_reason or 'fallback estimates used'}."
        ),
        offending_ids=[matrix.provider] if matrix.degraded else [],
    )


def _no_instruction_injection(ctx: _Context) -> CheckResult:
    bad = [
        incident.id
        for incident in ctx.scenario.incidents
        if incident.report and looks_like_instruction(incident.report)
    ]
    bad += [draft.id for draft in ctx.drafts if looks_like_instruction(draft.text)]
    return _result(
        "no_instruction_injection", WARNING, bad,
        "No instruction-like text in reports or drafts.",
        "Instruction-like text (treated as data, never followed)",
    )


def _normalise(text: str) -> str:
    return " ".join(text.split()).casefold()


CHECKS: tuple[Callable[[_Context], CheckResult], ...] = (
    _incident_exists,
    _unit_exists,
    _unit_available,
    _unit_not_duplicated,
    _capability_match,
    _quantity_within_requirement,
    _travel_time_matches,
    _travel_times_not_degraded,
    _critical_incidents_accounted,
    _unmet_declared_accurately,
    _objective_within_tolerance,
    _constraints_feasible,
    _constraints_satisfied,
    _citations_retrieved,
    _citation_quotes_present,
    _assignments_cited,
    _draft_numbers_match_state,
    _human_approval_required,
    _no_instruction_injection,
)

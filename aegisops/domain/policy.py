"""Deterministic prioritisation and safety rules used as an evaluation baseline."""

from __future__ import annotations

from math import hypot

from aegisops.domain.models import (
    Assignment,
    Incident,
    SafetyFinding,
    Scenario,
    Severity,
    UnmetRequirement,
)

SEVERITY_WEIGHTS: dict[Severity, float] = {
    Severity.LOW: 1.0,
    Severity.MEDIUM: 3.0,
    Severity.HIGH: 7.0,
    Severity.CRITICAL: 15.0,
}


def priority_score(incident: Incident) -> float:
    """Rank known inputs; this is a transparent policy, not a risk prediction."""
    staleness_factor = min(incident.reported_at_min, 120) / 120
    return (
        SEVERITY_WEIGHTS[incident.severity] * (1 + incident.people_affected / 10) + staleness_factor
    )


def travel_minutes(source: tuple[float, float], target: tuple[float, float], speed: float) -> float:
    """Return Euclidean travel time in synthetic grid minutes."""
    return hypot(source[0] - target[0], source[1] - target[1]) / speed


def evaluate_safety_gates(
    unmet: list[UnmetRequirement], scenario: Scenario
) -> tuple[list[SafetyFinding], bool]:
    """Evaluate unmet requirements against deterministic safety gates."""
    severity_by_id = {incident.id: incident.severity for incident in scenario.incidents}
    findings: list[SafetyFinding] = []
    blocked = False
    for requirement in unmet:
        severity = severity_by_id[requirement.incident_id]
        if severity == Severity.CRITICAL:
            findings.append(
                SafetyFinding(
                    code="CRITICAL_UNMET_REQUIREMENT",
                    severity="critical",
                    incident_id=requirement.incident_id,
                    message=(
                        "A critical incident has an unmet required capability; "
                        "human escalation is mandatory."
                    ),
                )
            )
            blocked = True
        elif severity == Severity.HIGH:
            findings.append(
                SafetyFinding(
                    code="HIGH_PRIORITY_UNMET_REQUIREMENT",
                    severity="high",
                    incident_id=requirement.incident_id,
                    message=(
                        "A high-severity incident has unmet demand and requires human review."
                    ),
                )
            )
    if not findings:
        findings.append(
            SafetyFinding(
                code="HUMAN_APPROVAL_REQUIRED",
                severity="information",
                message=(
                    "Recommendation is advisory only; an authorised operator must "
                    "approve any dispatch."
                ),
            )
        )
    return findings, blocked


def validate_llm_recommendation(
    assignments: list[Assignment], requires_human_approval: bool, scenario: Scenario
) -> tuple[list[Assignment], list[UnmetRequirement], list[SafetyFinding], bool]:
    """Accept only policy-compliant LLM assignments and recompute safety state."""
    incidents = {incident.id: incident for incident in scenario.incidents}
    resources = {resource.id: resource for resource in scenario.resources}
    fulfilled: dict[tuple[str, object], int] = {}
    accepted: list[Assignment] = []
    findings: list[SafetyFinding] = []
    seen_resource_ids: set[str] = set()

    for assignment in assignments:
        incident = incidents.get(assignment.incident_id)
        resource = resources.get(assignment.resource_id)
        if resource is None:
            findings.append(
                SafetyFinding(
                    code="LLM_INVALID_RESOURCE_ID",
                    severity="critical",
                    incident_id=assignment.incident_id if incident else None,
                    message="LLM proposed a resource that is not in the scenario.",
                )
            )
            continue
        if resource.id in seen_resource_ids:
            findings.append(
                SafetyFinding(
                    code="LLM_DUPLICATE_RESOURCE_ASSIGNMENT",
                    severity="critical",
                    incident_id=assignment.incident_id if incident else None,
                    message="LLM proposed the same resource more than once.",
                )
            )
            continue
        seen_resource_ids.add(resource.id)
        if incident is None:
            findings.append(
                SafetyFinding(
                    code="LLM_INVALID_INCIDENT_ID",
                    severity="critical",
                    message="LLM proposed an incident that is not in the scenario.",
                )
            )
            continue
        if not resource.available:
            findings.append(
                SafetyFinding(
                    code="LLM_UNAVAILABLE_RESOURCE",
                    severity="critical",
                    incident_id=incident.id,
                    message="LLM proposed a resource that is unavailable in the scenario.",
                )
            )
            continue
        requirement_key = (incident.id, resource.type)
        required_quantity = incident.resources_needed.get(resource.type)
        if assignment.resource_type != resource.type or required_quantity is None:
            findings.append(
                SafetyFinding(
                    code="LLM_RESOURCE_TYPE_VIOLATION",
                    severity="critical",
                    incident_id=incident.id,
                    message="LLM proposed a resource type not required by the incident.",
                )
            )
            continue
        if fulfilled.get(requirement_key, 0) >= required_quantity:
            findings.append(
                SafetyFinding(
                    code="LLM_EXCESS_RESOURCE_ASSIGNMENT",
                    severity="critical",
                    incident_id=incident.id,
                    message="LLM proposed more resources than the incident requires.",
                )
            )
            continue
        accepted.append(assignment)
        fulfilled[requirement_key] = fulfilled.get(requirement_key, 0) + 1

    unmet = [
        UnmetRequirement(
            incident_id=incident.id,
            resource_type=resource_type,
            quantity=quantity - fulfilled.get((incident.id, resource_type), 0),
            severity=incident.severity,
        )
        for incident in scenario.incidents
        for resource_type, quantity in incident.resources_needed.items()
        if quantity > fulfilled.get((incident.id, resource_type), 0)
    ]
    safety_findings, blocked = evaluate_safety_gates(unmet, scenario)
    if not requires_human_approval:
        findings.append(
            SafetyFinding(
                code="LLM_HUMAN_APPROVAL_VIOLATION",
                severity="critical",
                message="LLM output attempted to remove the required human approval gate.",
            )
        )
    return accepted, unmet, findings + safety_findings, blocked or bool(findings)

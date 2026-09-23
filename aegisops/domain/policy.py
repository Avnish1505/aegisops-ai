"""Deterministic prioritisation and safety rules used as an evaluation baseline."""

from __future__ import annotations

from math import hypot

from aegisops.domain.models import (
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

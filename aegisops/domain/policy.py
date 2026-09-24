"""Deterministic prioritisation and safety rules used as an evaluation baseline."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from aegisops.domain.models import (
    Incident,
    Location,
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


EARTH_RADIUS_KM = 6_371.0088
# Roads are longer than the straight line between two points; 1.4 is a typical urban
# circuity. Only the degraded straight-line fallback uses it: road ETAs come from OSRM.
ROAD_CIRCUITY = 1.4


def haversine_km(source: Location, target: Location) -> float:
    """Great-circle distance between two WGS84 points."""
    lat1, lat2 = radians(source.lat), radians(target.lat)
    d_lat, d_lon = lat2 - lat1, radians(target.lon - source.lon)
    a = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def travel_minutes(source: Location, target: Location, speed_kmh: float) -> float:
    """Straight-line estimate: great-circle distance x ROAD_CIRCUITY at ``speed_kmh``."""
    return haversine_km(source, target) * ROAD_CIRCUITY / speed_kmh * 60


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

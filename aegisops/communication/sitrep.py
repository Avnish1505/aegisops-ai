"""Deterministic situation report for a plan.

Every number sits immediately after the keyword that names it (``ETA 16.4 min``,
``coverage 78%``), which is the grammar ``verification.numbers`` reads back. An LLM drafting step
must follow the same grammar or its numbers are reported as unattributed.
"""

from __future__ import annotations

from aegisops.domain.models import DecisionResult, Scenario, Severity
from aegisops.planning.objective import plan_coverage
from aegisops.planning.travel import TravelTimeMatrix
from aegisops.verification.models import TextDraft


def render_sitrep(
    plan: DecisionResult, scenario: Scenario, travel_times: TravelTimeMatrix
) -> TextDraft:
    critical = sum(incident.severity == Severity.CRITICAL for incident in scenario.incidents)
    available = sum(resource.available for resource in scenario.resources)
    unmet_units = sum(item.quantity for item in plan.unmet_requirements)
    coverage = round(plan_coverage(plan.assignments, scenario) * 100)
    lines = [
        f"SITREP {scenario.scenario_id}",
        f"Incidents {len(scenario.incidents)}; critical {critical}.",
        f"Units available {available}; assigned {len(plan.assignments)}.",
        f"Unmet units {unmet_units}; coverage {coverage}%.",
    ]
    for incident in scenario.incidents:
        clauses = [
            f"{item.resource_id} {item.resource_type.value} ETA "
            f"{_minutes(travel_times, item.resource_id, incident.id, item.travel_minutes)} min"
            for item in plan.assignments
            if item.incident_id == incident.id
        ]
        clauses += [
            f"unmet {item.quantity} {item.resource_type.value}"
            for item in plan.unmet_requirements
            if item.incident_id == incident.id
        ]
        if clauses:
            lines.append(
                f"{incident.id} {incident.severity.value} {incident.type.value}: "
                + "; ".join(clauses)
                + "."
            )
    return TextDraft(id=f"sitrep-{scenario.scenario_id}", kind="sitrep", text="\n".join(lines))


def _minutes(
    travel_times: TravelTimeMatrix, resource_id: str, incident_id: str, claimed: float
) -> str:
    verified = travel_times.get(resource_id, incident_id)
    return f"{verified if verified is not None else claimed:.1f}"

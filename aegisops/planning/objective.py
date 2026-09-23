"""The single definition of plan quality, shared by the solver and the verifier.

objective = sum over unmet units of (incident weight x UNMET_PENALTY_MINUTES)
          + sum over assignments of (incident weight x travel minutes)

The penalty makes covering a requirement always worth more than any realistic drive, so the
solver never leaves demand unmet to save travel time.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aegisops.domain.models import Assignment, Incident, ResourceType, Scenario, UnmetRequirement
from aegisops.domain.policy import SEVERITY_WEIGHTS
from aegisops.planning.constraints import PlanningConstraint, PriorityBoost
from aegisops.planning.travel import TravelTimeMatrix

UNMET_PENALTY_MINUTES = 10_000.0


@dataclass(frozen=True, slots=True)
class ObjectiveBreakdown:
    unmet_penalty: float
    weighted_travel: float

    @property
    def total(self) -> float:
        return self.unmet_penalty + self.weighted_travel


def incident_weight(incident: Incident, constraints: Sequence[PlanningConstraint]) -> float:
    """Severity weight, multiplied by any priority boosts for this incident."""
    weight = SEVERITY_WEIGHTS[incident.severity]
    for constraint in constraints:
        if isinstance(constraint, PriorityBoost) and constraint.incident_id == incident.id:
            weight *= constraint.factor
    return weight


def plan_objective(
    assignments: Sequence[Assignment],
    unmet: Sequence[UnmetRequirement],
    scenario: Scenario,
    travel_times: TravelTimeMatrix,
    constraints: Sequence[PlanningConstraint],
) -> ObjectiveBreakdown:
    """Score a plan; travel comes from the matrix, never from the plan's own claims."""
    incidents = {incident.id: incident for incident in scenario.incidents}
    unmet_penalty = sum(
        incident_weight(incidents[item.incident_id], constraints)
        * item.quantity
        * UNMET_PENALTY_MINUTES
        for item in unmet
        if item.incident_id in incidents
    )
    weighted_travel = 0.0
    for assignment in assignments:
        incident = incidents.get(assignment.incident_id)
        if incident is None:
            continue
        minutes = travel_times.get(assignment.resource_id, assignment.incident_id)
        weighted_travel += incident_weight(incident, constraints) * (
            minutes if minutes is not None else assignment.travel_minutes
        )
    return ObjectiveBreakdown(unmet_penalty=unmet_penalty, weighted_travel=weighted_travel)


def plan_coverage(assignments: Sequence[Assignment], scenario: Scenario) -> float:
    """Share of required units met by assignments of a real, matching unit (capped per need)."""
    resources = {resource.id: resource for resource in scenario.resources}
    assigned: dict[tuple[str, ResourceType], int] = {}
    for assignment in assignments:
        resource = resources.get(assignment.resource_id)
        if resource is not None:
            key = (assignment.incident_id, resource.type)
            assigned[key] = assigned.get(key, 0) + 1
    required = 0
    met = 0
    for incident in scenario.incidents:
        for resource_type, quantity in incident.resources_needed.items():
            required += quantity
            met += min(quantity, assigned.get((incident.id, resource_type), 0))
    return round(met / required, 2) if required else 1.0

"""Safe, deterministic allocation baseline for Phase 1 evaluation."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from aegisops.domain.models import (
    Assignment,
    DecisionResult,
    DecisionStatus,
    Incident,
    Resource,
    ResourceType,
    Scenario,
    UnmetRequirement,
)
from aegisops.domain.policy import evaluate_safety_gates, priority_score, travel_minutes
from aegisops.planning.constraints import PlanningConstraint, excluded_unit_ids
from aegisops.planning.travel import StraightLineProvider, TravelTimeMatrix


class RuleBasedDecisionEngine:
    """Greedy nearest-qualified allocation with explicit unmet demand and safety gating.

    This is intentionally a transparent baseline, not an autonomous dispatch system or
    an LLM substitute. Its stable results enable regression testing of later AI agents.
    """

    name = "rule_based_baseline_v1"

    def recommend(
        self,
        scenario: Scenario,
        travel_times: TravelTimeMatrix | None = None,
        constraints: Sequence[PlanningConstraint] = (),
    ) -> DecisionResult:
        """Greedy baseline. Honours ExcludeUnit; ignores reserves and priority boosts."""
        matrix = travel_times or StraightLineProvider().matrix(scenario)
        excluded = excluded_unit_ids(constraints)
        available = {
            resource.id: resource
            for resource in scenario.resources
            if resource.available and resource.id not in excluded
        }
        assignments: list[Assignment] = []
        unmet: list[UnmetRequirement] = []
        trace = ["Validated scenario schema and selected available qualified resources only."]

        ordered_incidents = sorted(
            scenario.incidents, key=lambda incident: (-priority_score(incident), incident.id)
        )
        for incident in ordered_incidents:
            trace.append(f"Assessed {incident.id} with priority {priority_score(incident):.2f}.")
            for resource_type, required_quantity in incident.resources_needed.items():
                candidates = self._rank_candidates(
                    available.values(), resource_type, incident, matrix
                )
                allocated = 0
                for resource in candidates[:required_quantity]:
                    duration = self._minutes(matrix, resource, incident)
                    assignments.append(
                        Assignment(
                            incident_id=incident.id,
                            resource_id=resource.id,
                            resource_type=resource.type,
                            travel_minutes=round(duration, 2),
                        )
                    )
                    del available[resource.id]
                    allocated += 1
                if allocated < required_quantity:
                    unmet.append(
                        UnmetRequirement(
                            incident_id=incident.id,
                            resource_type=resource_type,
                            quantity=required_quantity - allocated,
                            severity=incident.severity,
                        )
                    )

        findings, blocked = evaluate_safety_gates(unmet, scenario)
        trace.append("Applied deterministic safety gates; no dispatch was executed.")
        coverage = 1 - (
            sum(item.quantity for item in unmet)
            / max(1, len(assignments) + sum(item.quantity for item in unmet))
        )
        return DecisionResult(
            scenario_id=scenario.scenario_id,
            engine=self.name,
            status=DecisionStatus.BLOCKED if blocked else DecisionStatus.REQUIRES_HUMAN_APPROVAL,
            assignments=assignments,
            unmet_requirements=unmet,
            safety_findings=findings,
            coverage=round(max(0.0, min(1.0, coverage)), 2),
            decision_trace=trace,
        )

    @staticmethod
    def _minutes(matrix: TravelTimeMatrix, resource: Resource, incident: Incident) -> float:
        minutes = matrix.get(resource.id, incident.id)
        if minutes is None:
            return travel_minutes(resource.location, incident.location, resource.speed_kmh)
        return minutes

    @classmethod
    def _rank_candidates(
        cls,
        resources: Iterable[Resource],
        resource_type: ResourceType,
        incident: Incident,
        matrix: TravelTimeMatrix,
    ) -> list[Resource]:
        typed_resources = [resource for resource in resources if resource.type == resource_type]
        return sorted(
            typed_resources,
            key=lambda resource: (cls._minutes(matrix, resource, incident), resource.id),
        )

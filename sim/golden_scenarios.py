"""Reusable, hand-authored scenarios and expectations for engine evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from aegisops.domain.models import DecisionStatus, Scenario


@dataclass(frozen=True)
class EngineExpectation:
    """Stable expectations for an engine on one golden scenario."""

    status: DecisionStatus
    assignment_ids: tuple[str, ...]
    unmet_units: int
    required_finding_codes: tuple[str, ...]
    coverage: float


@dataclass(frozen=True)
class GoldenScenario:
    """A reproducible scenario with regression expectations for the baseline engine."""

    name: str
    description: str
    scenario: Scenario
    rule_based_expectation: EngineExpectation
    must_block: bool = False


def golden_scenarios() -> tuple[GoldenScenario, ...]:
    """Return the canonical evaluation suite without sharing mutable scenario state."""
    return (
        GoldenScenario(
            name="fully_covered_medical",
            description="An available ambulance completely satisfies a low-severity incident.",
            scenario=Scenario.model_validate(
                {
                    "scenario_id": "GOLDEN-covered-medical",
                    "incidents": [
                        {
                            "id": "INC-medical",
                            "type": "medical",
                            "severity": "low",
                            "location": [0, 0],
                            "people_affected": 1,
                            "reported_at_min": 0,
                            "resources_needed": {"ambulance": 1},
                        }
                    ],
                    "resources": [
                        {
                            "id": "RES-ambulance",
                            "type": "ambulance",
                            "location": [0, 0],
                            "available": True,
                        }
                    ],
                }
            ),
            rule_based_expectation=EngineExpectation(
                status=DecisionStatus.REQUIRES_HUMAN_APPROVAL,
                assignment_ids=("RES-ambulance",),
                unmet_units=0,
                required_finding_codes=("HUMAN_APPROVAL_REQUIRED",),
                coverage=1.0,
            ),
        ),
        GoldenScenario(
            name="critical_capability_gap",
            description="A missing critical ambulance capability must block the recommendation.",
            scenario=Scenario.model_validate(
                {
                    "scenario_id": "GOLDEN-critical-gap",
                    "incidents": [
                        {
                            "id": "INC-critical",
                            "type": "medical",
                            "severity": "critical",
                            "location": [0, 0],
                            "people_affected": 10,
                            "reported_at_min": 0,
                            "resources_needed": {"ambulance": 1},
                        }
                    ],
                    "resources": [],
                }
            ),
            rule_based_expectation=EngineExpectation(
                status=DecisionStatus.BLOCKED,
                assignment_ids=(),
                unmet_units=1,
                required_finding_codes=("CRITICAL_UNMET_REQUIREMENT",),
                coverage=0.0,
            ),
            must_block=True,
        ),
        GoldenScenario(
            name="unavailable_resource_excluded",
            description="An unavailable ambulance cannot be allocated to a high-severity incident.",
            scenario=Scenario.model_validate(
                {
                    "scenario_id": "GOLDEN-unavailable-resource",
                    "incidents": [
                        {
                            "id": "INC-high",
                            "type": "medical",
                            "severity": "high",
                            "location": [0, 0],
                            "people_affected": 5,
                            "reported_at_min": 0,
                            "resources_needed": {"ambulance": 1},
                        }
                    ],
                    "resources": [
                        {
                            "id": "RES-unavailable",
                            "type": "ambulance",
                            "location": [0, 0],
                            "available": False,
                        }
                    ],
                }
            ),
            rule_based_expectation=EngineExpectation(
                status=DecisionStatus.REQUIRES_HUMAN_APPROVAL,
                assignment_ids=(),
                unmet_units=1,
                required_finding_codes=("HIGH_PRIORITY_UNMET_REQUIREMENT",),
                coverage=0.0,
            ),
        ),
        GoldenScenario(
            name="priority_resource_contention",
            description="One ambulance is allocated to the higher-priority incident only.",
            scenario=Scenario.model_validate(
                {
                    "scenario_id": "GOLDEN-priority-contention",
                    "incidents": [
                        {
                            "id": "INC-high",
                            "type": "medical",
                            "severity": "high",
                            "location": [0, 0],
                            "people_affected": 5,
                            "reported_at_min": 0,
                            "resources_needed": {"ambulance": 1},
                        },
                        {
                            "id": "INC-low",
                            "type": "medical",
                            "severity": "low",
                            "location": [1, 1],
                            "people_affected": 1,
                            "reported_at_min": 0,
                            "resources_needed": {"ambulance": 1},
                        },
                    ],
                    "resources": [
                        {
                            "id": "RES-ambulance",
                            "type": "ambulance",
                            "location": [0, 0],
                            "available": True,
                        }
                    ],
                }
            ),
            rule_based_expectation=EngineExpectation(
                status=DecisionStatus.REQUIRES_HUMAN_APPROVAL,
                assignment_ids=("RES-ambulance",),
                unmet_units=1,
                required_finding_codes=(),
                coverage=0.5,
            ),
        ),
    )


__all__ = ["EngineExpectation", "GoldenScenario", "golden_scenarios"]

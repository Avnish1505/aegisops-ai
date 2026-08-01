from aegisops.domain.models import Scenario
from aegisops.infrastructure.rule_based_engine import RuleBasedDecisionEngine


def test_engine_blocks_critical_unmet_capability() -> None:
    scenario = Scenario.model_validate(
        {
            "scenario_id": "SCEN-critical",
            "incidents": [
                {
                    "id": "INC-1",
                    "type": "medical",
                    "severity": "critical",
                    "location": [0, 0],
                    "people_affected": 10,
                    "reported_at_min": 1,
                    "resources_needed": {"ambulance": 1},
                }
            ],
            "resources": [],
        }
    )

    result = RuleBasedDecisionEngine().recommend(scenario)

    assert result.status.value == "blocked"
    assert result.requires_human_approval is True
    assert result.assignments == []
    assert result.safety_findings[0].code == "CRITICAL_UNMET_REQUIREMENT"


def test_engine_does_not_allocate_unavailable_or_duplicate_resources() -> None:
    scenario = Scenario.model_validate(
        {
            "scenario_id": "SCEN-availability",
            "incidents": [
                {
                    "id": "INC-1",
                    "type": "medical",
                    "severity": "high",
                    "location": [0, 0],
                    "people_affected": 5,
                    "reported_at_min": 2,
                    "resources_needed": {"ambulance": 1},
                },
                {
                    "id": "INC-2",
                    "type": "medical",
                    "severity": "low",
                    "location": [1, 1],
                    "people_affected": 1,
                    "reported_at_min": 2,
                    "resources_needed": {"ambulance": 1},
                },
            ],
            "resources": [
                {
                    "id": "RES-available",
                    "type": "ambulance",
                    "location": [0, 0],
                    "available": True,
                },
                {
                    "id": "RES-unavailable",
                    "type": "ambulance",
                    "location": [1, 1],
                    "available": False,
                },
            ],
        }
    )

    result = RuleBasedDecisionEngine().recommend(scenario)
    assigned_ids = [assignment.resource_id for assignment in result.assignments]

    assert assigned_ids == ["RES-available"]
    assert len(assigned_ids) == len(set(assigned_ids))
    assert result.unmet_requirements[0].incident_id == "INC-2"

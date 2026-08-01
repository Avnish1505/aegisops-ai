"""Compatibility exports for the Phase 1 reproducible scenario factory.

New code should import from :mod:`aegisops.application.scenario_service`.
"""

from aegisops.application.scenario_service import RESOURCE_REQUIREMENTS, generate_scenario
from aegisops.domain.models import (
    Incident,
    IncidentType,
    Resource,
    ResourceType,
    Scenario,
    Severity,
)

__all__ = [
    "Incident",
    "IncidentType",
    "RESOURCE_REQUIREMENTS",
    "Resource",
    "ResourceType",
    "Scenario",
    "Severity",
    "generate_scenario",
]


if __name__ == "__main__":
    import json

    print(json.dumps(generate_scenario(seed=42).model_dump(mode="json"), indent=2))

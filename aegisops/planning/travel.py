"""Travel-time matrices and the providers that produce them."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from aegisops.domain.models import Scenario
from aegisops.domain.policy import travel_minutes


class TravelTimeMatrix(BaseModel):
    """Minutes from each resource to each incident, plus where the numbers came from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    minutes: dict[str, dict[str, float]]
    degraded: bool = False

    def get(self, resource_id: str, incident_id: str) -> float | None:
        return self.minutes.get(resource_id, {}).get(incident_id)


class TravelTimeProvider(Protocol):
    """Produce a matrix covering every resource and incident in a scenario."""

    name: str

    def matrix(self, scenario: Scenario) -> TravelTimeMatrix: ...


class EuclideanProvider:
    """Straight-line distance divided by each unit's speed; no road network."""

    name = "euclidean-v1"

    def matrix(self, scenario: Scenario) -> TravelTimeMatrix:
        return TravelTimeMatrix(
            provider=self.name,
            minutes={
                resource.id: {
                    incident.id: travel_minutes(
                        resource.location, incident.location, resource.eta_speed
                    )
                    for incident in scenario.incidents
                }
                for resource in scenario.resources
            },
        )

"""Reproducible synthetic scenario factory for development and evaluation."""

from __future__ import annotations

import random
import uuid

from aegisops.domain.models import (
    Incident,
    IncidentType,
    Location,
    Resource,
    ResourceType,
    Scenario,
    Severity,
)

RESOURCE_REQUIREMENTS: dict[IncidentType, dict[ResourceType, int]] = {
    IncidentType.MEDICAL: {ResourceType.AMBULANCE: 1},
    IncidentType.FIRE: {ResourceType.FIRE_UNIT: 2, ResourceType.AMBULANCE: 1},
    IncidentType.STRUCTURAL_COLLAPSE: {ResourceType.RESCUE_TEAM: 2, ResourceType.AMBULANCE: 2},
    IncidentType.FLOOD: {ResourceType.BOAT: 1, ResourceType.RESCUE_TEAM: 1},
    IncidentType.HAZMAT: {ResourceType.HAZMAT_UNIT: 1, ResourceType.FIRE_UNIT: 1},
}

# Synthetic points fall inside urban Lucknow (WGS84). They are random, not real addresses.
LUCKNOW_URBAN_BOUNDS = (26.78, 80.87, 26.93, 81.05)  # min_lat, min_lon, max_lat, max_lon
TYPICAL_SPEED_KMH: dict[ResourceType, float] = {
    ResourceType.AMBULANCE: 30.0,
    ResourceType.FIRE_UNIT: 25.0,
    ResourceType.RESCUE_TEAM: 25.0,
    ResourceType.HAZMAT_UNIT: 25.0,
    ResourceType.BOAT: 20.0,  # towed on a trailer by road
}


def _point(generator: random.Random) -> Location:
    min_lat, min_lon, max_lat, max_lon = LUCKNOW_URBAN_BOUNDS
    return Location(
        lat=round(generator.uniform(min_lat, max_lat), 5),
        lon=round(generator.uniform(min_lon, max_lon), 5),
    )


def generate_scenario(seed: int | None = None, num_incidents: int = 6) -> Scenario:
    """Generate bounded synthetic data; the same seed returns the same scenario exactly."""
    generator = random.Random(seed)
    scenario_key = f"seed:{seed}" if seed is not None else str(uuid.uuid4())

    def stable_id(kind: str, index: int) -> str:
        return f"{kind}-{uuid.uuid5(uuid.NAMESPACE_URL, f'{scenario_key}:{kind}:{index}').hex[:8]}"

    incidents: list[Incident] = []
    incident_types = list(IncidentType)
    severities = list(Severity)
    for index in range(num_incidents):
        incident_type = generator.choice(incident_types)
        severity = generator.choices(severities, weights=[3, 4, 2, 1], k=1)[0]
        incidents.append(
            Incident(
                id=stable_id("INC", index),
                type=incident_type,
                severity=severity,
                location=_point(generator),
                people_affected=generator.randint(1, 40),
                reported_at_min=generator.randint(0, 60),
                resources_needed=RESOURCE_REQUIREMENTS[incident_type],
            )
        )

    resources: list[Resource] = []
    resource_types = [ResourceType.AMBULANCE] * 4 + [ResourceType.FIRE_UNIT] * 3
    resource_types += [ResourceType.RESCUE_TEAM] * 2 + [ResourceType.HAZMAT_UNIT]
    resource_types += [ResourceType.BOAT] * 2
    for index, resource_type in enumerate(resource_types):
        resources.append(
            Resource(
                id=stable_id("RES", index),
                type=resource_type,
                location=_point(generator),
                speed_kmh=TYPICAL_SPEED_KMH[resource_type],
            )
        )

    return Scenario(scenario_id=stable_id("SCEN", 0), incidents=incidents, resources=resources)

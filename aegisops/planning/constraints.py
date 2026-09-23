"""Typed operator constraints the solver must honour and the verifier re-checks."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegisops.domain.models import Location, Resource, ResourceType

Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


class ConstraintModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Zone(ConstraintModel):
    """A WGS84 latitude/longitude box; bounds are inclusive. Does not cross the antimeridian."""

    id: Identifier
    min_lat: Annotated[float, Field(ge=-90, le=90)]
    min_lon: Annotated[float, Field(ge=-180, le=180)]
    max_lat: Annotated[float, Field(ge=-90, le=90)]
    max_lon: Annotated[float, Field(ge=-180, le=180)]

    @model_validator(mode="after")
    def _bounds_are_ordered(self) -> Zone:
        if self.min_lat > self.max_lat or self.min_lon > self.max_lon:
            raise ValueError("zone minimum bounds must not exceed maximum bounds")
        return self

    def contains(self, location: Location) -> bool:
        return (
            self.min_lat <= location.lat <= self.max_lat
            and self.min_lon <= location.lon <= self.max_lon
        )


class ReserveConstraint(ConstraintModel):
    """Keep at least ``count`` available, non-excluded units of a type unassigned inside a zone."""

    kind: Literal["reserve"] = "reserve"
    resource_type: ResourceType
    count: Annotated[int, Field(ge=1, le=500)]
    zone: Zone

    def pool(self, resources: list[Resource], excluded_ids: set[str]) -> list[Resource]:
        """Units that can count towards this reserve."""
        return [
            resource
            for resource in resources
            if resource.available
            and resource.type == self.resource_type
            and resource.id not in excluded_ids
            and self.zone.contains(resource.location)
        ]


class ExcludeUnit(ConstraintModel):
    """Never assign this unit (for example: out of service or held back by command)."""

    kind: Literal["exclude_unit"] = "exclude_unit"
    unit_id: Identifier


class PriorityBoost(ConstraintModel):
    """Multiply one incident's weight in the objective; it adds no hard constraint."""

    kind: Literal["priority_boost"] = "priority_boost"
    incident_id: Identifier
    factor: Annotated[float, Field(gt=0, le=10)]


PlanningConstraint = Annotated[
    ReserveConstraint | ExcludeUnit | PriorityBoost, Field(discriminator="kind")
]


def excluded_unit_ids(constraints: Sequence[PlanningConstraint]) -> set[str]:
    return {item.unit_id for item in constraints if isinstance(item, ExcludeUnit)}

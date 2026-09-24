"""Route geometry for drawing assignments on the map (display only; ETAs come from the matrix).

``OSRMProvider.route`` asks OSRM's route service for a simplified GeoJSON line; anything else,
or an OSRM failure, gives a two-point straight line marked ``straight_line``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from aegisops.domain.models import Location


class RouteGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # [lon, lat] pairs (GeoJSON order), from origin to destination.
    coordinates: list[tuple[float, float]]
    geometry: str  # "road" | "straight_line"
    reason: str | None = None


def straight_line(origin: Location, destination: Location, reason: str | None) -> RouteGeometry:
    return RouteGeometry(
        coordinates=[(origin.lon, origin.lat), (destination.lon, destination.lat)],
        geometry="straight_line",
        reason=reason,
    )

"""The travel-time provider the configuration asks for."""

from __future__ import annotations

from aegisops.core.config import Settings
from aegisops.planning.osrm import OSRMProvider
from aegisops.planning.travel import StraightLineProvider, TravelTimeProvider


def default_travel_provider(settings: Settings) -> TravelTimeProvider:
    """OSRM when ``osrm_url`` is set (straight-line fallback on failure), else straight-line."""
    if settings.osrm_url:
        return OSRMProvider(settings.osrm_url, profile=settings.osrm_profile)
    return StraightLineProvider()

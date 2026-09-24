"""Place exercise units at real OSM facilities.

OpenStreetMap tells us where hospitals, fire stations and police stations are; it says nothing
about how many ambulances, boats or rescue teams each holds. The counts below are an EXERCISE
ASSUMPTION, kept explicit and deterministic so every run stations the same units at the same
places:

- one ambulance at each of the ``ambulance_hospitals`` hospitals nearest the city centre;
- ``fire_units_per_station`` fire units and one rescue team at every fire station;
- one rescue team at each of the ``rescue_police_stations`` police stations nearest the centre;
- one flood-rescue boat at each of the ``boat_police_stations`` police stations nearest the centre.

"Nearest" is great-circle distance from ``CITY_CENTRE`` (the OSM place node for Hazratganj);
ties break on OSM id.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aegisops.application.scenario_service import TYPICAL_SPEED_KMH
from aegisops.domain.models import Location, Resource, ResourceType
from aegisops.domain.policy import haversine_km
from aegisops.geodata.osm import Facility

CITY_CENTRE = Location(lat=26.854809, lon=80.9447594)  # OSM node: place=suburb, name=Hazratganj
TYPE_CODES = {
    ResourceType.AMBULANCE: "AMB",
    ResourceType.FIRE_UNIT: "FIRE",
    ResourceType.RESCUE_TEAM: "RESC",
    ResourceType.BOAT: "BOAT",
    ResourceType.HAZMAT_UNIT: "HAZ",
}


@dataclass(frozen=True, slots=True)
class UnitPlacementPolicy:
    ambulance_hospitals: int = 20
    fire_units_per_station: int = 2
    rescue_police_stations: int = 9
    boat_police_stations: int = 7


@dataclass(frozen=True, slots=True)
class PlacedUnit:
    resource: Resource
    facility: Facility


def _nearest(facilities: Sequence[Facility], kind: str, count: int) -> list[Facility]:
    candidates = [f for f in facilities if f.kind == kind]
    candidates.sort(
        key=lambda f: (haversine_km(CITY_CENTRE, Location(lat=f.lat, lon=f.lon)), f.osm_id)
    )
    return candidates[:count]


def _unit(facility: Facility, resource_type: ResourceType, number: int) -> PlacedUnit:
    unit_id = f"RES-{TYPE_CODES[resource_type]}-{facility.osm_type[0]}{facility.osm_id}-{number}"
    return PlacedUnit(
        Resource(
            id=unit_id,
            type=resource_type,
            location=Location(lat=round(facility.lat, 6), lon=round(facility.lon, 6)),
            speed_kmh=TYPICAL_SPEED_KMH[resource_type],
        ),
        facility,
    )


def place_units(
    facilities: Sequence[Facility], policy: UnitPlacementPolicy | None = None
) -> list[PlacedUnit]:
    rules = policy or UnitPlacementPolicy()
    units: list[PlacedUnit] = []
    for hospital in _nearest(facilities, "hospital", rules.ambulance_hospitals):
        units.append(_unit(hospital, ResourceType.AMBULANCE, 1))
    for station in _nearest(facilities, "fire_station", len(facilities)):
        units += [
            _unit(station, ResourceType.FIRE_UNIT, n + 1)
            for n in range(rules.fire_units_per_station)
        ]
        units.append(_unit(station, ResourceType.RESCUE_TEAM, 1))
    for police in _nearest(facilities, "police", rules.rescue_police_stations):
        units.append(_unit(police, ResourceType.RESCUE_TEAM, 1))
    for police in _nearest(facilities, "police", rules.boat_police_stations):
        units.append(_unit(police, ResourceType.BOAT, 1))
    return units

"""The Lucknow monsoon-flood exercise: 20 incidents across nine localities.

Incident positions start from the OpenStreetMap place node of each locality and move a fixed
number of metres north/east, so every run produces the same scenario. Incidents, reports and
casualty figures are FICTIONAL exercise injects; only the places and the stationed units come
from real data (OSM place nodes and facilities).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import cos, radians

from aegisops.domain.models import (
    Incident,
    IncidentType,
    Location,
    Resource,
    ResourceType,
    Scenario,
    Severity,
)
from aegisops.geodata.osm import Place

EXERCISE_ID = "EX-LKO-MONSOON-01"
EXERCISE_NAME = "Lucknow monsoon flood exercise"
EXERCISE_DESCRIPTION = (
    "Twenty fictional incidents after an extreme overnight downpour across nine Lucknow "
    "localities, planned against units stationed at OpenStreetMap hospitals, fire stations and "
    "police stations. Exercise data only."
)
LOCALITIES = (
    "Charbagh",
    "Hazratganj",
    "Aminabad",
    "Chowk",
    "Aliganj",
    "Gomti Nagar",
    "Indira Nagar",
    "Alambagh",
    "Kaiserbagh",
)
# Names the same locality carries in OpenStreetMap.
OSM_NAMES: dict[str, tuple[str, ...]] = {
    "Kaiserbagh": ("Kaiserbagh", "Qaisarbagh", "Kaisarbagh", "Qaiserbagh"),
}
PREFERRED_PLACE_TYPES = ("suburb", "quarter", "neighbourhood", "locality")

FLOOD = {ResourceType.BOAT: 1, ResourceType.RESCUE_TEAM: 1}
COLLAPSE = {ResourceType.RESCUE_TEAM: 2, ResourceType.AMBULANCE: 2}
MEDICAL = {ResourceType.AMBULANCE: 1}
FIRE = {ResourceType.FIRE_UNIT: 2, ResourceType.AMBULANCE: 1}


@dataclass(frozen=True, slots=True)
class Inject:
    locality: str
    north_m: int
    east_m: int
    type: IncidentType
    severity: Severity
    people: int
    reported_at_min: int
    needs: dict[ResourceType, int]
    report: str


INJECTS: tuple[Inject, ...] = (
    Inject("Charbagh", -180, 120, IncidentType.FLOOD, Severity.CRITICAL, 35, 5, FLOOD,
           "Chest-deep water in lanes behind the railway station; about 35 residents on "
           "rooftops, including an elderly man who needs oxygen."),
    Inject("Charbagh", 250, -90, IncidentType.MEDICAL, Severity.HIGH, 1, 12, MEDICAL,
           "Man electrocuted by a snapped overhead line in standing water; breathing, "
           "unconscious."),
    Inject("Charbagh", 60, 300, IncidentType.MEDICAL, Severity.MEDIUM, 3, 40, MEDICAL,
           "Three passengers injured when an auto-rickshaw overturned in a submerged pothole."),
    Inject("Hazratganj", 150, -200, IncidentType.STRUCTURAL_COLLAPSE, Severity.HIGH, 4, 18,
           COLLAPSE, "Old shopfront balcony collapsed onto the pavement; two people trapped."),
    Inject("Hazratganj", -220, 140, IncidentType.MEDICAL, Severity.LOW, 1, 55, MEDICAL,
           "Pedestrian slipped in floodwater near the market; suspected fractured ankle."),
    Inject("Aminabad", 90, 110, IncidentType.STRUCTURAL_COLLAPSE, Severity.CRITICAL, 7, 9,
           COLLAPSE, "Rear wall of a century-old building gave way after soaking; family of "
           "seven reported inside, voices heard."),
    Inject("Aminabad", -140, -160, IncidentType.FIRE, Severity.HIGH, 6, 22, FIRE,
           "Short circuit fire in a flooded electrical shop; smoke spreading to rooms above."),
    Inject("Chowk", 200, 60, IncidentType.FLOOD, Severity.CRITICAL, 60, 3, FLOOD,
           "Gomti overtopping near the old city ghats; about 60 people cut off in a mohalla."),
    Inject("Chowk", -120, 180, IncidentType.FLOOD, Severity.HIGH, 20, 15, FLOOD,
           "Ground floors flooded in a narrow lane; 20 residents asking to be moved out."),
    Inject("Chowk", 40, -250, IncidentType.MEDICAL, Severity.MEDIUM, 1, 35, MEDICAL,
           "Pregnant woman in labour; the lane is waterlogged and cars cannot enter."),
    Inject("Aliganj", 160, 90, IncidentType.FLOOD, Severity.MEDIUM, 12, 28, FLOOD,
           "Basement flats flooding in a housing block; 12 residents on the stairwell."),
    Inject("Aliganj", -100, -130, IncidentType.MEDICAL, Severity.HIGH, 1, 20, MEDICAL,
           "Child bitten by a snake that came in with floodwater; parents are on the roof."),
    Inject("Gomti Nagar", 300, 150, IncidentType.FLOOD, Severity.CRITICAL, 45, 6,
           {ResourceType.BOAT: 2, ResourceType.RESCUE_TEAM: 1},
           "Riverside colony inundated after the embankment seeped; 45 people, several "
           "children, waiting on first floors."),
    Inject("Gomti Nagar", -200, -100, IncidentType.FIRE, Severity.MEDIUM, 2, 45, FIRE,
           "Transformer fire beside a flooded road; two nearby houses evacuating."),
    Inject("Gomti Nagar", 80, -280, IncidentType.MEDICAL, Severity.LOW, 1, 60, MEDICAL,
           "Resident with high fever unable to reach a clinic through waterlogged streets."),
    Inject("Indira Nagar", 120, 200, IncidentType.FLOOD, Severity.HIGH, 25, 14, FLOOD,
           "Low-lying sector under knee-deep water rising slowly; 25 residents with livestock."),
    Inject("Indira Nagar", -160, -60, IncidentType.MEDICAL, Severity.MEDIUM, 2, 38, MEDICAL,
           "Two workers hurt clearing a blocked drain; one with a deep leg wound."),
    Inject("Alambagh", 140, -140, IncidentType.FLOOD, Severity.LOW, 8, 50, FLOOD,
           "Water entering a bus depot staff quarters; 8 people want to leave before dark."),
    Inject("Alambagh", -90, 220, IncidentType.MEDICAL, Severity.HIGH, 1, 16, MEDICAL,
           "Dialysis patient stranded at home; next session is due within hours."),
    Inject("Kaiserbagh", 70, 90, IncidentType.FLOOD, Severity.MEDIUM, 15, 25, FLOOD,
           "Bus stand underpass flooded; a stalled minibus with 15 passengers inside."),
)


def locate_localities(places: Sequence[Place]) -> dict[str, Location]:
    """Map each exercise locality to its OSM place node; fail loudly if one is missing."""
    found: dict[str, Location] = {}
    for locality in LOCALITIES:
        names = {name.casefold() for name in OSM_NAMES.get(locality, (locality,))}
        matches = [p for p in places if p.name.casefold() in names]
        if not matches:
            raise ValueError(f"no OSM place node named {sorted(names)} for {locality}")
        matches.sort(
            key=lambda p: (
                PREFERRED_PLACE_TYPES.index(p.place)
                if p.place in PREFERRED_PLACE_TYPES
                else len(PREFERRED_PLACE_TYPES),
                p.osm_id,
            )
        )
        found[locality] = Location(lat=matches[0].lat, lon=matches[0].lon)
    return found


def _offset(origin: Location, north_m: int, east_m: int) -> Location:
    metres_per_degree = 111_320.0
    return Location(
        lat=round(origin.lat + north_m / metres_per_degree, 6),
        lon=round(origin.lon + east_m / (metres_per_degree * cos(radians(origin.lat))), 6),
    )


def build_lucknow_exercise(places: Sequence[Place], units: Sequence[Resource]) -> Scenario:
    anchors = locate_localities(places)
    incidents = [
        Incident(
            id=f"INC-LKO-{index:02d}",
            type=inject.type,
            severity=inject.severity,
            location=_offset(anchors[inject.locality], inject.north_m, inject.east_m),
            people_affected=inject.people,
            reported_at_min=inject.reported_at_min,
            resources_needed=inject.needs,
            report=f"{inject.locality}: {inject.report}",
        )
        for index, inject in enumerate(INJECTS, start=1)
    ]
    return Scenario(
        scenario_id=EXERCISE_ID,
        incidents=incidents,
        resources=sorted(units, key=lambda unit: unit.id),
    )

"""Human-readable names for incidents and units, for display only.

Incidents are named after a gazetteer place their report mentions, if it lies within
``MENTION_RADIUS_KM``; otherwise the nearest OpenStreetMap place in the Lucknow gazetteer within
``PLACE_RADIUS_KM``, else the nearest landmark within ``LANDMARK_RADIUS_KM``,
else "near <place>" for anything closer than ``NEAR_RADIUS_KM``. Units stationed at an imported
OSM facility take the facility's name. Labels never feed planning or verification.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from aegisops.domain.models import Location, Scenario
from aegisops.domain.policy import haversine_km
from aegisops.intake.gazetteer import Gazetteer, GazetteerEntry

MENTION_RADIUS_KM = 2.0
PLACE_RADIUS_KM = 1.5
LANDMARK_RADIUS_KM = 0.4
NEAR_RADIUS_KM = 5.0
# RES-<TYPE>-<osm type initial><osm id>-<n>, as written by aegisops/geodata/units.py.
UNIT_ID = re.compile(r"^RES-[A-Z]+-([nwr])(\d+)-\d+$")


Nearest = tuple[GazetteerEntry, float]


def _nearest(entries: list[GazetteerEntry], location: Location) -> Nearest | None:
    best: Nearest | None = None
    for entry in entries:
        distance = haversine_km(location, Location(lat=entry.lat, lon=entry.lon))
        if best is None or distance < best[1] or (distance == best[1] and entry.osm < best[0].osm):
            best = (entry, distance)
    return best


class Labeller:
    def __init__(self, gazetteer: Gazetteer) -> None:
        self._gazetteer = gazetteer
        self._places = [e for e in gazetteer.entries if e.kind == "place"]
        self._landmarks = [e for e in gazetteer.entries if e.kind == "landmark"]

    def place(self, location: Location, report: str | None = None) -> str | None:
        if report:
            mentioned = self._gazetteer.geocode(report)
            if mentioned is not None and haversine_km(
                location, Location(lat=mentioned.lat, lon=mentioned.lon)
            ) <= MENTION_RADIUS_KM:
                return mentioned.name
        place = _nearest(self._places, location)
        if place is not None and place[1] <= PLACE_RADIUS_KM:
            return place[0].name
        landmark = _nearest(self._landmarks, location)
        if landmark is not None and landmark[1] <= LANDMARK_RADIUS_KM:
            return landmark[0].name
        if place is not None and place[1] <= NEAR_RADIUS_KM:
            return f"near {place[0].name}"
        return None

    def labels(
        self, scenario: Scenario, facility_names: Mapping[tuple[str, int], str]
    ) -> dict[str, dict[str, str | None]]:
        units: dict[str, str | None] = {}
        for resource in scenario.resources:
            match = UNIT_ID.match(resource.id)
            name = None
            if match is not None:
                osm_type = {"n": "node", "w": "way", "r": "relation"}[match.group(1)]
                name = facility_names.get((osm_type, int(match.group(2))))
            units[resource.id] = name or self.place(resource.location)
        return {
            "incidents": {i.id: self.place(i.location, i.report) for i in scenario.incidents},
            "units": units,
        }

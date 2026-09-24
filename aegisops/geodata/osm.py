"""Read facilities and named places from an OSM extract (.osm.pbf or .osm XML) with pyosmium.

Facilities are amenity=hospital (or healthcare=hospital), amenity=fire_station and
amenity=police, mapped as nodes, ways (centroid of the outline) or multipolygon relations
(centroid of the outer rings). Only those inside the district boundary relation are kept.
Reading a local file only: nothing here calls Overpass or any other network service.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import osmium

FacilityKind = Literal["hospital", "fire_station", "police"]
LUCKNOW_DISTRICT_RELATION = 1959018  # boundary=administrative, admin_level=5, name=Lucknow
PLACE_TYPES = frozenset({"city", "town", "suburb", "quarter", "neighbourhood", "locality"})
Ring = list[tuple[float, float]]  # (lat, lon) vertices


@dataclass(frozen=True, slots=True)
class Facility:
    osm_type: Literal["node", "way", "relation"]
    osm_id: int
    kind: FacilityKind
    name: str | None
    lat: float
    lon: float
    tags: dict[str, str]


@dataclass(frozen=True, slots=True)
class Place:
    osm_id: int
    name: str
    place: str
    lat: float
    lon: float


@dataclass(slots=True)
class OsmExtract:
    district_rings: list[Ring]
    facilities: list[Facility] = field(default_factory=list)
    outside_district: int = 0
    places: list[Place] = field(default_factory=list)


def facility_kind(tags: dict[str, str]) -> FacilityKind | None:
    amenity = tags.get("amenity")
    if amenity == "hospital" or tags.get("healthcare") == "hospital":
        return "hospital"
    if amenity == "fire_station":
        return "fire_station"
    if amenity == "police":
        return "police"
    return None


def inside(lat: float, lon: float, rings: Sequence[Ring]) -> bool:
    """Even-odd point-in-polygon over every ring (so inner rings act as holes)."""
    hit = False
    for ring in rings:
        for index in range(len(ring)):
            (lat1, lon1), (lat2, lon2) = ring[index], ring[index - 1]
            if (lat1 > lat) != (lat2 > lat) and lon < (lon2 - lon1) * (lat - lat1) / (
                lat2 - lat1
            ) + lon1:
                hit = not hit
    return hit


def _centroid(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


class _Reader(osmium.SimpleHandler):
    def __init__(self, district_relation: int) -> None:
        super().__init__()
        self.district_relation = district_relation
        self.district_rings: list[Ring] = []
        self.candidates: list[Facility] = []
        self.places: list[Place] = []

    def node(self, node: osmium.osm.Node) -> None:
        tags = {tag.k: tag.v for tag in node.tags}
        if not node.location.valid():
            return
        kind = facility_kind(tags)
        if kind is not None:
            self.candidates.append(
                Facility("node", node.id, kind, tags.get("name"), node.location.lat,
                         node.location.lon, tags)
            )
        if tags.get("place") in PLACE_TYPES and tags.get("name"):
            self.places.append(
                Place(node.id, tags["name"], tags["place"], node.location.lat, node.location.lon)
            )

    def way(self, way: osmium.osm.Way) -> None:
        tags = {tag.k: tag.v for tag in way.tags}
        kind = facility_kind(tags)
        if kind is None:
            return
        points = [(n.location.lat, n.location.lon) for n in way.nodes if n.location.valid()]
        if points:
            lat, lon = _centroid(points)
            self.candidates.append(Facility("way", way.id, kind, tags.get("name"), lat, lon, tags))

    def area(self, area: osmium.osm.Area) -> None:
        if area.from_way():
            return
        rings: list[Ring] = [
            [(n.lat, n.lon) for n in ring] for ring in area.outer_rings()
        ]
        if area.orig_id() == self.district_relation:
            for outer in area.outer_rings():
                self.district_rings.append([(n.lat, n.lon) for n in outer])
                for inner in area.inner_rings(outer):
                    self.district_rings.append([(n.lat, n.lon) for n in inner])
            return
        tags = {tag.k: tag.v for tag in area.tags}
        kind = facility_kind(tags)
        points = [point for ring in rings for point in ring]
        if kind is not None and points:
            lat, lon = _centroid(points)
            self.candidates.append(
                Facility("relation", area.orig_id(), kind, tags.get("name"), lat, lon, tags)
            )


def read_extract(path: Path, district_relation: int = LUCKNOW_DISTRICT_RELATION) -> OsmExtract:
    """Read facilities inside the district boundary, plus every named place node."""
    reader = _Reader(district_relation)
    reader.apply_file(str(path), locations=True)
    if not reader.district_rings:
        raise ValueError(
            f"district relation {district_relation} is missing or incomplete in {path}; "
            "re-clip with a larger bounding box"
        )
    extract = OsmExtract(district_rings=reader.district_rings, places=reader.places)
    seen: set[tuple[str, int]] = set()
    for facility in sorted(reader.candidates, key=lambda f: (f.osm_type, f.osm_id)):
        key = (facility.osm_type, facility.osm_id)
        if key in seen:
            continue
        seen.add(key)
        if inside(facility.lat, facility.lon, extract.district_rings):
            extract.facilities.append(facility)
        else:
            extract.outside_district += 1
    return extract

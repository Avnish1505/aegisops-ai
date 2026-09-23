"""Build the Lucknow gazetteer from a local OSM extract.

    python scripts/build_gazetteer.py data/osm/lucknow.osm.pbf evals/data/lucknow_gazetteer.json

Keeps named places, landmarks and roads inside the Lucknow district boundary. Road ways that share
a name are merged and placed at the centroid of all their nodes. Curated aliases
(aegisops/intake/gazetteer.py) are attached to the OSM place of the same name.
Data (c) OpenStreetMap contributors, ODbL 1.0.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import osmium

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegisops.geodata.osm import LUCKNOW_DISTRICT_RELATION, inside, read_extract  # noqa: E402
from aegisops.intake.gazetteer import (  # noqa: E402
    CURATED_ALIASES,
    Gazetteer,
    GazetteerEntry,
    aliases_from,
    classify,
)


class _Collector(osmium.SimpleHandler):
    def __init__(self, rings: list[list[tuple[float, float]]]) -> None:
        super().__init__()
        self.rings = rings
        self.entries: list[GazetteerEntry] = []
        self.roads: dict[str, list[tuple[float, float]]] = {}
        self.road_aliases: dict[str, tuple[str, ...]] = {}
        self.road_ids: dict[str, str] = {}

    def _add(self, tags: dict[str, str], lat: float, lon: float, osm: str) -> None:
        kind = classify(tags)
        if kind is None or kind == "road" or not inside(lat, lon, self.rings):
            return
        aliases = aliases_from(tags)
        self.entries.append(GazetteerEntry(aliases[0], aliases[1:], kind, round(lat, 6),
                                           round(lon, 6), osm))

    def node(self, node: osmium.osm.Node) -> None:
        tags = {tag.k: tag.v for tag in node.tags}
        if "name" in tags and node.location.valid():
            self._add(tags, node.location.lat, node.location.lon, f"node/{node.id}")

    def way(self, way: osmium.osm.Way) -> None:
        tags = {tag.k: tag.v for tag in way.tags}
        if "name" not in tags:
            return
        points = [(n.location.lat, n.location.lon) for n in way.nodes if n.location.valid()]
        points = [p for p in points if inside(p[0], p[1], self.rings)]
        if not points:
            return
        if classify(tags) == "road":
            name = tags["name"]
            self.roads.setdefault(name, []).extend(points)
            self.road_aliases[name] = aliases_from(tags)
            self.road_ids.setdefault(name, f"way/{way.id}")
            return
        lat = sum(p[0] for p in points) / len(points)
        lon = sum(p[1] for p in points) / len(points)
        self._add(tags, lat, lon, f"way/{way.id}")


def build(extract: Path, district_relation: int = LUCKNOW_DISTRICT_RELATION) -> Gazetteer:
    rings = read_extract(extract, district_relation).district_rings
    collector = _Collector(rings)
    collector.apply_file(str(extract), locations=True)
    entries = list(collector.entries)
    for name, points in sorted(collector.roads.items()):
        aliases = collector.road_aliases[name]
        entries.append(
            GazetteerEntry(
                aliases[0], aliases[1:], "road",
                round(sum(p[0] for p in points) / len(points), 6),
                round(sum(p[1] for p in points) / len(points), 6),
                collector.road_ids[name],
            )
        )
    curated: list[GazetteerEntry] = []
    for entry in entries:
        extra = CURATED_ALIASES.get(entry.name, ()) if entry.kind == "place" else ()
        curated.append(
            GazetteerEntry(entry.name, entry.aliases, entry.kind, entry.lat, entry.lon,
                           entry.osm, tuple(extra))
        )
    curated.sort(key=lambda e: (e.kind, e.name, e.osm))
    return Gazetteer(curated)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extract", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    gazetteer = build(args.extract)
    source_file = args.extract.parent / "SOURCE.txt"
    source = source_file.read_text().strip() if source_file.exists() else str(args.extract)
    gazetteer.dump(args.output, source)
    kinds: dict[str, int] = {}
    for entry in gazetteer.entries:
        kinds[entry.kind] = kinds.get(entry.kind, 0) + 1
    print(f"{len(gazetteer.entries)} entries: {kinds}")


if __name__ == "__main__":
    main()

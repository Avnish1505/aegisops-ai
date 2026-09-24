"""Import hospitals, fire stations and police stations inside Lucknow district from a local OSM
extract, and station exercise units at them.

    python scripts/import_facilities.py data/osm/lucknow.osm.pbf

Reads only the local file (prepared by scripts/osrm_prepare.sh); it never calls Overpass. Replaces
previously imported facilities and units, so re-running is safe. Unit counts per facility are an
exercise assumption documented in aegisops/geodata/units.py.
OSM data (c) OpenStreetMap contributors, ODbL 1.0.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegisops.core.config import Settings  # noqa: E402
from aegisops.geodata.osm import LUCKNOW_DISTRICT_RELATION, read_extract  # noqa: E402
from aegisops.geodata.units import place_units  # noqa: E402
from backend.db.models import Facility, Unit  # noqa: E402


def import_facilities(
    extract_path: Path, database_url: str, district_relation: int = LUCKNOW_DISTRICT_RELATION
) -> dict[str, int]:
    extract = read_extract(extract_path, district_relation)
    placed = place_units(extract.facilities)
    session_factory = sessionmaker(bind=create_engine(database_url))
    with session_factory.begin() as session:
        session.execute(delete(Unit))
        session.execute(delete(Facility))
        rows: dict[tuple[str, int], Facility] = {}
        for facility in extract.facilities:
            row = Facility(
                osm_type=facility.osm_type,
                osm_id=facility.osm_id,
                kind=facility.kind,
                name=facility.name,
                location=(facility.lat, facility.lon),
                tags=facility.tags,
            )
            session.add(row)
            rows[(facility.osm_type, facility.osm_id)] = row
        session.flush()
        for unit in placed:
            resource = unit.resource
            session.add(
                Unit(
                    id=resource.id,
                    type=resource.type.value,
                    facility_id=rows[(unit.facility.osm_type, unit.facility.osm_id)].id,
                    location=(resource.location.lat, resource.location.lon),
                    available=resource.available,
                    speed_kmh=resource.speed_kmh,
                )
            )
    counts = Counter(f"facilities.{f.kind}" for f in extract.facilities)
    counts.update(f"units.{u.resource.type.value}" for u in placed)
    counts["facilities_outside_district"] = extract.outside_district
    return dict(sorted(counts.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extract", type=Path, help="Local .osm.pbf or .osm file")
    parser.add_argument("--district-relation", type=int, default=LUCKNOW_DISTRICT_RELATION)
    parser.add_argument("--database-url", default=None, help="Defaults to AEGISOPS_DATABASE_URL")
    args = parser.parse_args()
    counts = import_facilities(
        args.extract, args.database_url or Settings().database_url, args.district_relation
    )
    for key, value in counts.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()

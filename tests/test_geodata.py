"""OSM facility import and unit placement, from a local fixture (never Overpass)."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from aegisops.geodata.osm import inside, read_extract
from aegisops.geodata.units import place_units
from backend.db.models import Facility, Unit
from scripts.import_facilities import import_facilities

FIXTURE = Path(__file__).parent / "fixtures" / "osm" / "lucknow_mini.osm"


def test_reads_only_facilities_inside_the_district() -> None:
    extract = read_extract(FIXTURE)

    names = {(f.kind, f.name) for f in extract.facilities}
    assert names == {
        ("hospital", "Inside Node Hospital"),
        ("hospital", "Healthcare Tag Hospital"),
        ("hospital", "Way Hospital"),
        ("fire_station", "Test Fire Station"),
        ("police", "Police A"),
        ("police", "Police B"),
    }
    assert extract.outside_district == 1


def test_way_facilities_are_placed_at_their_outline_centroid() -> None:
    way_hospital = next(f for f in read_extract(FIXTURE).facilities if f.name == "Way Hospital")

    assert way_hospital.osm_type == "way"
    assert way_hospital.lat == pytest.approx(26.861)
    assert way_hospital.lon == pytest.approx(80.931)


def test_named_places_are_read() -> None:
    places = {place.name for place in read_extract(FIXTURE).places}

    assert {"Charbagh", "Hazratganj", "Qaisarbagh", "Gomti Nagar"} <= places


def test_missing_district_relation_is_an_error() -> None:
    with pytest.raises(ValueError, match="district relation 42"):
        read_extract(FIXTURE, district_relation=42)


def test_point_in_polygon_respects_holes() -> None:
    outer = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
    hole = [(4.0, 4.0), (4.0, 6.0), (6.0, 6.0), (6.0, 4.0)]

    assert inside(2, 2, [outer, hole])
    assert not inside(5, 5, [outer, hole])
    assert not inside(11, 5, [outer, hole])


def test_units_are_placed_deterministically_by_the_documented_rules() -> None:
    facilities = read_extract(FIXTURE).facilities

    first = place_units(facilities)
    second = place_units(list(reversed(facilities)))

    assert [u.resource.id for u in first] == [u.resource.id for u in second]
    counts: dict[str, int] = {}
    for unit in first:
        counts[unit.resource.type.value] = counts.get(unit.resource.type.value, 0) + 1
    # 3 hospitals (< 20), 1 fire station (2 fire units + 1 rescue), 2 police (rescue, boat).
    assert counts == {"ambulance": 3, "fire_unit": 2, "rescue_team": 3, "boat": 2}
    fire = next(u for u in first if u.resource.type.value == "fire_unit")
    assert fire.facility.name == "Test Fire Station"
    assert (fire.resource.location.lat, fire.resource.location.lon) == (
        pytest.approx(26.831),
        pytest.approx(80.921),
    )


def test_import_script_writes_facilities_and_units_and_is_rerunnable(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'geo.db'}"
    config = Config(str(Path(__file__).parents[1] / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")

    first = import_facilities(FIXTURE, url)
    second = import_facilities(FIXTURE, url)

    assert first == second
    assert first["facilities.hospital"] == 3
    with Session(create_engine(url)) as session:
        assert session.scalar(select(func.count()).select_from(Facility)) == 6
        assert session.scalar(select(func.count()).select_from(Unit)) == 10
        way_hospital = session.scalar(select(Facility).where(Facility.name == "Way Hospital"))
        assert way_hospital is not None
        assert way_hospital.location == (pytest.approx(26.861), pytest.approx(80.931))

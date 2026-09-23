"""PostgreSQL + PostGIS integration. Runs only when AEGISOPS_TEST_POSTGRES_URL is set (CI sets it);
everything else in the suite uses SQLite."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.db.models import Incident

URL = os.environ.get("AEGISOPS_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(URL is None, reason="AEGISOPS_TEST_POSTGRES_URL not set")


@pytest.fixture()
def migrated() -> str:
    assert URL is not None
    with create_engine(URL).begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.execute(text("DROP TYPE IF EXISTS userrole"))
    config = Config(str(Path(__file__).parents[1] / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", URL.replace("%", "%%"))
    command.upgrade(config, "head")
    command.check(config)
    return URL


def test_migrations_run_down_and_up_again(migrated: str) -> None:
    config = Config(str(Path(__file__).parents[1] / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", migrated.replace("%", "%%"))

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)


def test_locations_are_postgis_geography_and_round_trip(migrated: str) -> None:
    engine = create_engine(migrated)
    with Session(engine) as session:
        for incident_id, location in (("INC-charbagh", (26.8320, 80.9219)),
                                      ("INC-hazratganj", (26.8505, 80.9470))):
            session.add(
                Incident(id=incident_id, type="flood", severity="high", location=location,
                         people_affected=1, reported_at_min=0)
            )
        session.commit()
        session.expunge_all()

        stored = session.get(Incident, "INC-charbagh")
        column_type = session.execute(
            text(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "WHERE attrelid = 'incidents'::regclass AND attname = 'location'"
            )
        ).scalar_one()
        metres = session.execute(
            text(
                "SELECT ST_Distance(a.location, b.location) FROM incidents a, incidents b "
                "WHERE a.id = 'INC-charbagh' AND b.id = 'INC-hazratganj'"
            )
        ).scalar_one()

    assert stored is not None and stored.location == (26.832, 80.9219)
    assert column_type == "geography(Point,4326)"
    assert 3_100 < metres < 3_350  # Charbagh to Hazratganj is about 3.2 km as the crow flies

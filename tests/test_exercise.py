"""The Lucknow exercise: built from OSM places and stationed units, saved, served, planned."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from auth_helpers import bearer
from fastapi.testclient import TestClient

from aegisops.api.app import create_app
from aegisops.core.config import Settings
from aegisops.domain.models import Location, Resource, ResourceType
from aegisops.domain.policy import haversine_km
from aegisops.geodata.exercise import (
    EXERCISE_ID,
    INJECTS,
    LOCALITIES,
    build_lucknow_exercise,
    locate_localities,
)
from aegisops.geodata.osm import Place, read_extract
from aegisops.verification.injection import looks_like_instruction
from scripts.import_facilities import import_facilities
from scripts.seed_lucknow_exercise import seed_exercise

FIXTURE = Path(__file__).parent / "fixtures" / "osm" / "lucknow_mini.osm"
UNITS = [
    Resource(id=f"RES-{t.value}-{n}", type=t, location=Location(lat=26.85, lon=80.95))
    for t in (ResourceType.AMBULANCE, ResourceType.BOAT, ResourceType.RESCUE_TEAM)
    for n in range(3)
]


def test_twenty_incidents_across_the_nine_localities() -> None:
    scenario = build_lucknow_exercise(read_extract(FIXTURE).places, UNITS)

    assert scenario.scenario_id == EXERCISE_ID
    assert len(scenario.incidents) == 20
    assert {inject.locality for inject in INJECTS} == set(LOCALITIES)
    needed = {t for incident in scenario.incidents for t in incident.resources_needed}
    assert {ResourceType.BOAT, ResourceType.RESCUE_TEAM, ResourceType.AMBULANCE} <= needed


def test_incidents_sit_within_half_a_kilometre_of_their_osm_locality() -> None:
    places = read_extract(FIXTURE).places
    anchors = locate_localities(places)

    scenario = build_lucknow_exercise(places, UNITS)

    for inject, incident in zip(INJECTS, scenario.incidents, strict=True):
        assert haversine_km(anchors[inject.locality], incident.location) < 0.5
        assert incident.report is not None and incident.report.startswith(inject.locality)


def test_kaiserbagh_resolves_to_its_osm_spelling() -> None:
    anchors = locate_localities(read_extract(FIXTURE).places)

    assert (anchors["Kaiserbagh"].lat, anchors["Kaiserbagh"].lon) == (26.8563927, 80.9284775)


def test_missing_locality_fails_loudly() -> None:
    places = [p for p in read_extract(FIXTURE).places if p.name != "Chowk"]

    with pytest.raises(ValueError, match="chowk"):
        locate_localities(places)


def test_exercise_is_deterministic_and_reports_are_not_flagged_as_injection() -> None:
    places: list[Place] = read_extract(FIXTURE).places

    first = build_lucknow_exercise(places, UNITS)
    second = build_lucknow_exercise(places, list(reversed(UNITS)))

    assert first.sha256() == second.sha256()
    assert not any(looks_like_instruction(i.report or "") for i in first.incidents)


def test_seeded_exercise_is_served_and_plannable(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'exercise.db'}"
    config = Config(str(Path(__file__).parents[1] / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    import_facilities(FIXTURE, url)

    scenario, decision_id = seed_exercise(FIXTURE, url, record=True, settings=Settings())
    seed_exercise(FIXTURE, url)  # re-running replaces the saved exercise
    client = TestClient(
        create_app(Settings(environment="test", database_url=url)), headers=bearer()
    )

    listed = client.get("/api/v1/exercises").json()
    served = client.get(f"/api/v1/exercises/{EXERCISE_ID}").json()
    planned = client.post("/api/v1/decisions", json={"scenario": served}).json()

    assert decision_id == 1
    assert [(e["id"], e["incidents"], e["resources"]) for e in listed] == [
        (EXERCISE_ID, 20, len(scenario.resources))
    ]
    assert served == scenario.model_dump(mode="json")
    assert planned["scenario_sha256"] == scenario.sha256()
    assert planned["verification"]["verdict"] in {"pass", "blocked"}
    assert client.get("/api/v1/exercises/EX-UNKNOWN").status_code == 404

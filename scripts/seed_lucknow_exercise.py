"""Build the Lucknow monsoon-flood exercise and save it for the console.

    python scripts/seed_lucknow_exercise.py data/osm/lucknow.osm.pbf [--record-decision]

Locality positions come from OSM place nodes in the local extract; units come from the `units`
table filled by scripts/import_facilities.py (run that first). Incidents and reports are
fictional exercise injects (aegisops/geodata/exercise.py). --record-decision also plans the
exercise once with the configured travel-time provider (OSRM when AEGISOPS_OSRM_URL is set)
and stores that verified decision. Re-running replaces the saved exercise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegisops.api.app import _default_travel_provider  # noqa: E402
from aegisops.application.decision_service import DecisionService  # noqa: E402
from aegisops.core.config import Settings  # noqa: E402
from aegisops.domain.models import Location, Resource, ResourceType, Scenario  # noqa: E402
from aegisops.geodata.exercise import (  # noqa: E402
    EXERCISE_DESCRIPTION,
    EXERCISE_ID,
    EXERCISE_NAME,
    build_lucknow_exercise,
)
from aegisops.geodata.osm import read_extract  # noqa: E402
from aegisops.infrastructure.decision_store import record_decision  # noqa: E402
from backend.db.models import Exercise, Unit  # noqa: E402


def seed_exercise(
    extract_path: Path, database_url: str, *, record: bool = False, settings: Settings | None = None
) -> tuple[Scenario, int | None]:
    session_factory = sessionmaker(bind=create_engine(database_url))
    with session_factory() as session:
        units = [
            Resource(
                id=unit.id,
                type=ResourceType(unit.type),
                location=Location(lat=unit.location[0], lon=unit.location[1]),
                available=unit.available,
                speed_kmh=unit.speed_kmh,
            )
            for unit in session.scalars(select(Unit).order_by(Unit.id))
        ]
    if not units:
        raise SystemExit("No units found: run scripts/import_facilities.py first.")
    scenario = build_lucknow_exercise(read_extract(extract_path).places, units)
    decision_id: int | None = None
    with session_factory.begin() as session:
        existing = session.get(Exercise, EXERCISE_ID)
        if existing is not None:
            session.delete(existing)
            session.flush()
        session.add(
            Exercise(
                id=EXERCISE_ID,
                name=EXERCISE_NAME,
                description=EXERCISE_DESCRIPTION,
                scenario=scenario.model_dump(mode="json"),
                scenario_sha256=scenario.sha256(),
            )
        )
        if record:
            provider = _default_travel_provider(settings or Settings())
            outcome = DecisionService({}, provider).decide(scenario)
            decision_id = record_decision(session, scenario, outcome, proposer="exercise-seed").id
    return scenario, decision_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extract", type=Path, help="Local .osm.pbf or .osm file")
    parser.add_argument("--record-decision", action="store_true")
    parser.add_argument("--database-url", default=None, help="Defaults to AEGISOPS_DATABASE_URL")
    args = parser.parse_args()
    scenario, decision_id = seed_exercise(
        args.extract, args.database_url or Settings().database_url, record=args.record_decision
    )
    print(
        f"exercise {scenario.scenario_id}: {len(scenario.incidents)} incidents, "
        f"{len(scenario.resources)} units"
    )
    if decision_id is not None:
        print(f"recorded decision {decision_id}")


if __name__ == "__main__":
    main()

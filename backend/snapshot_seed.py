"""Seed the Lucknow exercise from its committed snapshot (no OSM extract needed).

    python -m backend.snapshot_seed

Used by the end-to-end tests and wherever the OSM extract is not available. The snapshot
(evals/data/lucknow_exercise_v1.json) is the exercise built from OSM by
scripts/seed_lucknow_exercise.py. The seed plans it once with the configured travel-time
provider (OSRM when AEGISOPS_OSRM_URL is set, else straight-line).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from aegisops.application.decision_service import DecisionService
from aegisops.core.config import REPOSITORY_ROOT, Settings
from aegisops.domain.models import Scenario
from aegisops.geodata.exercise import EXERCISE_DESCRIPTION, EXERCISE_ID, EXERCISE_NAME
from aegisops.infrastructure.decision_store import record_decision
from aegisops.planning.providers import default_travel_provider
from backend.db.models import Decision, Exercise

SNAPSHOT = REPOSITORY_ROOT / "evals" / "data" / "lucknow_exercise_v1.json"
PROPOSER = "exercise-seed"


def seed_from_snapshot(settings: Settings | None = None) -> int | None:
    """Replace the saved exercise with the snapshot and record one plan for it; returns its id."""
    active = settings or Settings()
    scenario = Scenario.model_validate_json(SNAPSHOT.read_text(encoding="utf-8"))
    sessions = sessionmaker(bind=create_engine(active.database_url))
    with sessions.begin() as session:
        existing = session.get(Exercise, EXERCISE_ID)
        if existing is not None:
            session.delete(existing)
            session.flush()
        session.add(Exercise(
            id=EXERCISE_ID, name=EXERCISE_NAME, description=EXERCISE_DESCRIPTION,
            scenario=scenario.model_dump(mode="json"), scenario_sha256=scenario.sha256(),
            created_at=datetime.now(UTC).replace(tzinfo=None),
        ))
        if session.scalars(
            select(Decision).where(Decision.scenario_sha256 == scenario.sha256())
        ).first() is not None:
            return None
    outcome = DecisionService({}, default_travel_provider(active)).decide(scenario)
    with sessions.begin() as session:
        return record_decision(session, scenario, outcome, proposer=PROPOSER).id


if __name__ == "__main__":
    print(f"exercise {EXERCISE_ID} seeded from snapshot; recorded decision {seed_from_snapshot()}")

"""Record one demo decision (synthetic seed 42) so a fresh stack has a stored record to inspect.

Idempotent: does nothing when any decision already exists. Run after migrations:
``python -m backend.seed``.
"""

from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from aegisops.application.decision_service import DecisionService
from aegisops.application.scenario_service import generate_scenario
from aegisops.core.config import Settings
from aegisops.infrastructure.decision_store import record_decision
from aegisops.planning.travel import EuclideanProvider
from backend.db.models import Decision

DEMO_SEED = 42


def seed(database_url: str) -> int | None:
    """Insert the demo decision if the table is empty; return its id, or None if skipped."""
    session_factory = sessionmaker(bind=create_engine(database_url))
    with session_factory.begin() as session:
        if session.scalar(select(func.count()).select_from(Decision)):
            return None
        scenario = generate_scenario(seed=DEMO_SEED)
        outcome = DecisionService({}, EuclideanProvider()).decide(scenario)
        return record_decision(session, scenario, outcome, actor="seed").id


def main() -> None:
    decision_id = seed(Settings().database_url)
    if decision_id is None:
        print("seed: decisions already present; nothing to do")
    else:
        print(f"seed: recorded demo decision {decision_id} for synthetic seed {DEMO_SEED}")


if __name__ == "__main__":
    main()

"""Reset the public demo sandbox: clear what visitors changed and re-seed the exercise.

The demo (AEGISOPS_ENVIRONMENT=demo) lets two fixed identities triage, plan, approve and reject
inside the Lucknow exercise. Every reset deletes decisions, approvals, audit events and triage
reports, then seeds the exercise from its snapshot (one recorded plan) and the demo reports.
Facilities, units, feed alerts and feed polls are kept. The audit chain restarts at genesis on
each reset; that is the point of a sandbox, and the console says the demo resets.
"""

from __future__ import annotations

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from aegisops.core.config import Settings
from backend.db.models import Approval, Decision, Event, Exercise, IntakeReport, User
from backend.demo_intake import seed_demo_intake
from backend.snapshot_seed import seed_from_snapshot


def reset_demo(settings: Settings | None = None) -> int | None:
    """Wipe visitor state and re-seed; returns the id of the seeded plan."""
    active = settings or Settings()
    sessions = sessionmaker(bind=create_engine(active.database_url))
    with sessions.begin() as session:
        for model in (Approval, Decision, Event, IntakeReport, Exercise, User):
            session.execute(delete(model))
    decision_id = seed_from_snapshot(active)
    with sessions.begin() as session:
        seed_demo_intake(session)
    return decision_id


if __name__ == "__main__":
    print(f"demo reset; seeded plan {reset_demo()}")

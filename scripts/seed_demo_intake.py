"""Fill an empty triage queue with the fictional demo reports (see backend/demo_intake.py)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aegisops.core.config import Settings
from backend.demo_intake import seed_demo_intake

if __name__ == "__main__":
    sessions = sessionmaker(bind=create_engine(Settings().database_url))
    with sessions.begin() as session:
        print(f"demo intake reports added: {seed_demo_intake(session)}")

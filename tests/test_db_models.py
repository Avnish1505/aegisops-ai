"""Tests for database models."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.db.models import (
    Approval,
    AuditLog,
    Base,
    Decision,
    Evidence,
    Incident,
    Role,
    User,
    UserRole,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing with foreign keys enabled."""
    engine = create_engine("sqlite:///:memory:")
    # Enable foreign key constraints for SQLite
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_user_model(db_session):
    """Test User model creation."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashedpassword",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.hashed_password == "hashedpassword"
    assert user.is_active is True
    assert user.created_at is not None
    assert user.updated_at is not None


def test_role_model(db_session):
    """Test Role model creation."""
    role = Role(name=UserRole.ADMIN, description="Administrator role")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    assert role.id is not None
    assert role.name == UserRole.ADMIN
    assert role.description == "Administrator role"
    assert role.created_at is not None


def test_user_role_relationship(db_session):
    """Test many-to-many relationship between User and Role."""
    user = User(
        username="testuser2",
        email="test2@example.com",
        hashed_password="hashedpassword",
    )
    role = Role(name=UserRole.OPERATOR, description="Operator role")
    db_session.add_all([user, role])
    db_session.commit()

    user.roles.append(role)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(role)

    assert len(user.roles) == 1
    assert user.roles[0].name == UserRole.OPERATOR
    assert len(role.users) == 1
    assert role.users[0].username == "testuser2"


def test_incident_model(db_session):
    """Test Incident model creation."""
    incident = Incident(
        id="inc1",
        type="medical",
        severity="medium",
        location_x=10.0,
        location_y=20.0,
        people_affected=5,
        reported_at_min=0,
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    assert incident.id == "inc1"
    assert incident.type == "medical"
    assert incident.severity == "medium"
    assert incident.location_x == 10.0
    assert incident.location_y == 20.0
    assert incident.people_affected == 5
    assert incident.reported_at_min == 0
    assert incident.created_at is not None


def test_evidence_model(db_session):
    """Test Evidence model creation."""
    incident = Incident(
        id="inc1",
        type="medical",
        severity="medium",
        location_x=10.0,
        location_y=20.0,
        people_affected=5,
        reported_at_min=0,
    )
    db_session.add(incident)
    db_session.commit()

    evidence = Evidence(
        id="ev1",
        description="Witness report",
        source="Eyewitness",
        confidence=0.9,
        incident_id="inc1",
    )
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)

    assert evidence.id == "ev1"
    assert evidence.description == "Witness report"
    assert evidence.source == "Eyewitness"
    assert evidence.confidence == 0.9
    assert evidence.incident_id == "inc1"
    assert evidence.created_at is not None
    # Relationship
    assert evidence.incident is not None
    assert evidence.incident.id == "inc1"


def test_evidence_incident_foreign_key(db_session):
    """Test foreign key constraint between Evidence and Incident."""
    # Test that inserting evidence with non-existent incident_id raises integrity error
    evidence = Evidence(
        id="ev1",
        description="Witness report",
        source="Eyewitness",
        confidence=0.9,
        incident_id="nonexistent",
    )
    db_session.add(evidence)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # With a valid incident_id
    incident = Incident(
        id="inc1",
        type="medical",
        severity="medium",
        location_x=10.0,
        location_y=20.0,
        people_affected=5,
        reported_at_min=0,
    )
    db_session.add(incident)
    db_session.commit()

    evidence.incident_id = "inc1"
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)
    assert evidence.incident.id == "inc1"


def test_decision_model(db_session):
    """Test Decision model creation."""
    decision = Decision(
        scenario_id="sc1",
        engine="test_engine",
        status="requires_human_approval",
        requires_human_approval=True,
        advisory_confidence=0.8,
        decision_trace=[{"step": 1, "note": "initial"}],
    )
    db_session.add(decision)
    db_session.commit()
    db_session.refresh(decision)

    assert decision.id is not None
    assert decision.scenario_id == "sc1"
    assert decision.engine == "test_engine"
    assert decision.status == "requires_human_approval"
    assert decision.requires_human_approval is True
    assert decision.advisory_confidence == 0.8
    assert decision.decision_trace == [{"step": 1, "note": "initial"}]
    assert decision.created_at is not None


def test_approval_model(db_session):
    """Test Approval model creation."""
    user = User(
        username="approver",
        email="approver@example.com",
        hashed_password="hashedpassword",
    )
    decision = Decision(
        scenario_id="sc1",
        engine="test_engine",
        status="requires_human_approval",
        requires_human_approval=True,
        advisory_confidence=0.8,
        decision_trace=[],
    )
    db_session.add_all([user, decision])
    db_session.commit()

    approval = Approval(
        decision_id=decision.id,
        user_id=user.id,
        approved=True,
    )
    db_session.add(approval)
    db_session.commit()
    db_session.refresh(approval)

    assert approval.id is not None
    assert approval.decision_id == decision.id
    assert approval.user_id == user.id
    assert approval.approved is True
    assert approval.commented_at is not None
    # Relationships
    assert approval.decision.id == decision.id
    assert approval.user.id == user.id


def test_audit_log_model(db_session):
    """Test AuditLog model creation."""
    user = User(
        username="auditor",
        email="auditor@example.com",
        hashed_password="hashedpassword",
    )
    db_session.add(user)
    db_session.commit()

    audit_log = AuditLog(
        user_id=user.id,
        action="CREATE",
        table_name="incidents",
        record_id="inc1",
        change_data={"field": "value"},
    )
    db_session.add(audit_log)
    db_session.commit()
    db_session.refresh(audit_log)

    assert audit_log.id is not None
    assert audit_log.user_id == user.id
    assert audit_log.action == "CREATE"
    assert audit_log.table_name == "incidents"
    assert audit_log.record_id == "inc1"
    assert audit_log.change_data == {"field": "value"}
    assert audit_log.timestamp is not None
    # Relationship
    assert audit_log.user.id == user.id
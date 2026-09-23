"""Database models for persistence layer."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from aegisops.application.roles import UserRole
from backend.db.types import GeoPoint


class Base(DeclarativeBase):
    pass


# Association table for user-role many-to-many
user_role_table = Table(
    "user_role",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    roles: Mapped[list[Role]] = relationship(
        secondary=user_role_table, back_populates="users"
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[UserRole] = mapped_column(Enum(UserRole), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list[User]] = relationship(
        secondary=user_role_table, back_populates="roles"
    )


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    # (lat, lon) WGS84; PostGIS geography on PostgreSQL.
    location: Mapped[tuple[float, float]] = mapped_column(GeoPoint(), nullable=False)
    people_affected: Mapped[int] = mapped_column(nullable=False)
    reported_at_min: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_incident_type", "type"),
        Index("idx_incident_severity", "severity"),
        Index("idx_incident_location", "location", postgresql_using="gist"),
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime)
    incident_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("incidents.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    incident: Mapped[Incident | None] = relationship()

    # Indexes
    __table_args__ = (
        Index("idx_evidence_incident_id", "incident_id"),
        Index("idx_evidence_confidence", "confidence"),
    )


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), index=True)
    engine: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50))
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    coverage: Mapped[float] = mapped_column(nullable=False)
    decision_trace: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    # Full record needed to replay a decision. Nullable only for rows written before these
    # columns existed; the API always populates them.
    scenario: Mapped[dict[str, object] | None] = mapped_column(JSON)
    scenario_sha256: Mapped[str | None] = mapped_column(String(64))
    assignments: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    unmet_requirements: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    safety_findings: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    evidence: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    prompt_version: Mapped[str | None] = mapped_column(String(100))
    model_version: Mapped[str | None] = mapped_column(String(200))
    # Token subject of whoever requested the plan; that subject may never approve it.
    proposer_sub: Mapped[str | None] = mapped_column(String(255))
    # W3C traceparent of the plan step, so later steps (decide, communicate) join its trace.
    trace_parent: Mapped[str | None] = mapped_column(String(55))
    verification: Mapped[dict[str, object] | None] = mapped_column(JSON)
    drafts: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    constraints: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    travel_times: Mapped[dict[str, object] | None] = mapped_column(JSON)
    objective: Mapped[float | None] = mapped_column()
    reference_objective: Mapped[float | None] = mapped_column()
    solve_status: Mapped[str | None] = mapped_column(String(32))
    infeasibility: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    approvals: Mapped[list[Approval]] = relationship(
        back_populates="decision", order_by="Approval.id"
    )

    # Indexes
    __table_args__ = (
        Index("idx_decision_scenario_id", "scenario_id"),
        Index("idx_decision_status", "status"),
        Index("idx_decision_scenario_sha256", "scenario_sha256"),
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approved: Mapped[bool] = mapped_column(Boolean)
    commented_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    decision: Mapped[Decision] = relationship(back_populates="approvals")
    user: Mapped[User] = relationship()

    # Indexes
    __table_args__ = (
        Index("idx_approval_decision_id", "decision_id"),
        Index("idx_approval_user_id", "user_id"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    table_name: Mapped[str] = mapped_column(String(50), nullable=False)
    record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    change_data: Mapped[dict[str, object] | None] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped[User | None] = relationship()

    # Indexes
    __table_args__ = (
        Index("idx_audit_user_id", "user_id"),
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_table_record", "table_name", "record_id"),
    )


class Event(Base):
    """Append-only, hash-chained audit event (see aegisops/audit/event_log.py)."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    ts: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    __table_args__ = (Index("idx_event_type", "type"),)


class Facility(Base):
    """An emergency facility imported from OpenStreetMap (ODbL)."""

    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    osm_type: Mapped[str] = mapped_column(String(8), nullable=False)
    osm_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[tuple[float, float]] = mapped_column(GeoPoint(), nullable=False)
    tags: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("osm_type", "osm_id", name="uq_facility_osm"),
        Index("idx_facility_kind", "kind"),
        Index("idx_facility_location", "location", postgresql_using="gist"),
    )


class Unit(Base):
    """A response unit stationed at a facility (placement is an exercise assumption)."""

    __tablename__ = "units"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    location: Mapped[tuple[float, float]] = mapped_column(GeoPoint(), nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    speed_kmh: Mapped[float] = mapped_column(nullable=False)

    facility: Mapped[Facility] = relationship()


class Exercise(Base):
    """A saved scenario (e.g. the Lucknow monsoon exercise) the console can load."""

    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    scenario: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    scenario_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Alert(Base):
    """A hazard alert ingested from a public feed, stored with the payload exactly as fetched."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event: Mapped[str | None] = mapped_column(String(255))
    severity: Mapped[str | None] = mapped_column(String(32))
    headline: Mapped[str | None] = mapped_column(Text)
    area_desc: Mapped[str | None] = mapped_column(Text)
    location: Mapped[tuple[float, float] | None] = mapped_column(GeoPoint())
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False)
    parsed: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("source", "identifier", name="uq_alert_source_identifier"),
        Index("idx_alert_source_ref", "source", "source_ref"),
        Index("idx_alert_sent_at", "sent_at"),
    )

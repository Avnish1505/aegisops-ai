"""Database models for persistence layer."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
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
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


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
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
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
    location_x: Mapped[float] = mapped_column(nullable=False)
    location_y: Mapped[float] = mapped_column(nullable=False)
    people_affected: Mapped[int] = mapped_column(nullable=False)
    reported_at_min: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_incident_type", "type"),
        Index("idx_incident_severity", "severity"),
        Index("idx_incident_location", "location_x", "location_y"),
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
    advisory_confidence: Mapped[float] = mapped_column(nullable=False)
    decision_trace: Mapped[list[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_decision_scenario_id", "scenario_id"),
        Index("idx_decision_status", "status"),
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approved: Mapped[bool] = mapped_column(Boolean)
    commented_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    decision: Mapped[Decision] = relationship()
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
    change_data: Mapped[dict | None] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped[User | None] = relationship()

    # Indexes
    __table_args__ = (
        Index("idx_audit_user_id", "user_id"),
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_table_record", "table_name", "record_id"),
    )

"""Validated crisis-domain contracts shared by API and application layers."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IncidentType(StrEnum):
    MEDICAL = "medical"
    FIRE = "fire"
    STRUCTURAL_COLLAPSE = "structural_collapse"
    FLOOD = "flood"
    HAZMAT = "hazmat"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResourceType(StrEnum):
    AMBULANCE = "ambulance"
    FIRE_UNIT = "fire_unit"
    RESCUE_TEAM = "rescue_team"
    HAZMAT_UNIT = "hazmat_unit"


Coordinate = Annotated[tuple[float, float], Field(min_length=2, max_length=2)]


class DomainModel(BaseModel):
    """Reject unrecognised fields at the trust boundary."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Incident(DomainModel):
    id: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
    type: IncidentType
    severity: Severity
    location: Coordinate
    people_affected: Annotated[int, Field(ge=0, le=1_000_000)]
    reported_at_min: Annotated[int, Field(ge=0, le=1_000_000)]
    resources_needed: dict[ResourceType, Annotated[int, Field(ge=1, le=100)]]

    @field_validator("resources_needed")
    @classmethod
    def requirements_must_not_be_empty(
        cls, value: dict[ResourceType, int]
    ) -> dict[ResourceType, int]:
        if not value:
            raise ValueError("resources_needed must contain at least one requirement")
        return value


class Resource(DomainModel):
    id: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
    type: ResourceType
    location: Coordinate
    available: bool = True
    eta_speed: Annotated[float, Field(gt=0, le=1_000)] = 1.0


class Scenario(DomainModel):
    scenario_id: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
    incidents: Annotated[list[Incident], Field(min_length=1, max_length=100)]
    resources: Annotated[list[Resource], Field(max_length=500)]
    sim_start_min: Annotated[int, Field(ge=0, le=1_000_000)] = 0

    @field_validator("incidents", "resources")
    @classmethod
    def identifiers_must_be_unique(
        cls, value: list[Incident] | list[Resource]
    ) -> list[Incident] | list[Resource]:
        ids = [item.id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("entity IDs must be unique within their collection")
        return value

    def to_dict(self) -> dict[str, object]:
        """Compatibility helper for prototype callers; prefer ``model_dump(mode='json')``."""
        return self.model_dump(mode="json")


class Assignment(DomainModel):
    incident_id: str
    resource_id: str
    resource_type: ResourceType
    travel_minutes: Annotated[float, Field(ge=0)]


class UnmetRequirement(DomainModel):
    incident_id: str
    resource_type: ResourceType
    quantity: Annotated[int, Field(ge=1)]
    severity: Severity


class SafetyFinding(DomainModel):
    code: str
    severity: str
    message: str
    incident_id: str | None = None


class Evidence(DomainModel):
    """Reusable evidence entity with source provenance and confidence metadata."""

    id: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
    description: Annotated[str, Field(min_length=1)]
    source: Annotated[str, Field(min_length=1)]
    confidence: Annotated[float, Field(ge=0, le=1)]
    timestamp: str | None = None
    incident_id: Annotated[
        str | None,
        Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    ] = None

    @field_validator("incident_id", mode="before")
    @classmethod
    def incident_id_must_not_be_empty_if_present(
        cls, value: str | None
    ) -> str | None:
        if value is not None and not value:
            raise ValueError("incident_id must not be empty if provided")
        return value


class DecisionStatus(StrEnum):
    REQUIRES_HUMAN_APPROVAL = "requires_human_approval"
    BLOCKED = "blocked"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DecisionResult(DomainModel):
    scenario_id: str
    engine: str
    status: DecisionStatus
    requires_human_approval: bool = True
    assignments: list[Assignment]
    unmet_requirements: list[UnmetRequirement]
    safety_findings: list[SafetyFinding]
    advisory_confidence: Annotated[float, Field(ge=0, le=1)]
    decision_trace: list[str]
    evidence_ids: list[str] = Field(default_factory=list)
    # Approval workflow fields
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    approver_id: str | None = None
    approved_at: str | None = None  # ISO 8601 timestamp
    rejection_reason: str | None = None

    @model_validator(mode="after")
    def _validate_approval_fields(self) -> DecisionResult:
        """Validate approval-related fields based on approval_status."""
        if self.approval_status == ApprovalStatus.APPROVED:
            if not self.approver_id:
                raise ValueError("approver_id must be set when approval_status is approved")
            if not self.approved_at:
                raise ValueError("approved_at must be set when approval_status is approved")
            # rejection_reason should be None when approved
            if self.rejection_reason is not None:
                raise ValueError("rejection_reason must be None when approval_status is approved")
        elif self.approval_status == ApprovalStatus.REJECTED:
            if not self.rejection_reason:
                raise ValueError("rejection_reason must be set when approval_status is rejected")
            # approver_id and approved_at should be set when rejected (who rejected and when)
            if not self.approver_id:
                raise ValueError("approver_id must be set when approval_status is rejected")
            if not self.approved_at:
                raise ValueError("approved_at must be set when approval_status is rejected")
        else:  # PENDING
            # When pending, approver_id, approved_at, and rejection_reason should be None
            if self.approver_id is not None:
                raise ValueError("approver_id must be None when approval_status is pending")
            if self.approved_at is not None:
                raise ValueError("approved_at must be None when approval_status is pending")
            if self.rejection_reason is not None:
                raise ValueError("rejection_reason must be None when approval_status is pending")
        return self

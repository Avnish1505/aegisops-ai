"""Request contracts for public HTTP endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from aegisops.application.roles import UserRole
from aegisops.domain.models import Scenario
from aegisops.planning.constraints import PlanningConstraint


class ScenarioDecisionRequest(BaseModel):
    """Accept an explicit validated scenario or request a generated seeded scenario."""

    model_config = ConfigDict(extra="forbid")

    scenario: Scenario | None = None
    seed: Annotated[int | None, Field(ge=0, le=2_147_483_647)] = None
    max_turns: Annotated[int, Field(ge=1, le=20)] = 4
    constraints: Annotated[list[PlanningConstraint], Field(max_length=100)] = Field(
        default_factory=list
    )


class DecisionDispositionRequest(BaseModel):
    """Record the authorised operator's disposition of a persisted decision."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "reject"]
    reason: Annotated[str, Field(min_length=1, max_length=1_000)]


class ErrorResponse(BaseModel):
    """Stable safe error envelope for clients."""

    detail: str
    request_id: str | None = None


class DevTokenRequest(BaseModel):
    """Development-only identity for the console's proposer/approver demo."""

    model_config = ConfigDict(extra="forbid")

    sub: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.@-]+$")]
    role: UserRole


class ReadReportRequest(BaseModel):
    """One free-text field report (English, Hindi or Hinglish)."""

    model_config = ConfigDict(extra="forbid")

    report: Annotated[str, Field(min_length=3, max_length=4_000)]


class TranslateNoteRequest(BaseModel):
    """An operator's constraint note, with the scenario it refers to (for unit/incident ids)."""

    model_config = ConfigDict(extra="forbid")

    note: Annotated[str, Field(min_length=3, max_length=1_000)]
    scenario: Scenario | None = None

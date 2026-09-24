"""Request contracts for public HTTP endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegisops.application.dispositions import reason_problem
from aegisops.application.roles import UserRole
from aegisops.domain.models import Scenario
from aegisops.planning.constraints import PlanningConstraint


class ConstraintSource(BaseModel):
    """Where a confirmed constraint came from: the operator's note and the quote it rests on."""

    model_config = ConfigDict(extra="forbid")

    note: Annotated[str, Field(min_length=1, max_length=1_000)]
    quote: Annotated[str | None, Field(max_length=500)] = None


class ScenarioDecisionRequest(BaseModel):
    """Accept an explicit validated scenario or request a generated seeded scenario."""

    model_config = ConfigDict(extra="forbid")

    scenario: Scenario | None = None
    seed: Annotated[int | None, Field(ge=0, le=2_147_483_647)] = None
    max_turns: Annotated[int, Field(ge=1, le=20)] = 4
    constraints: Annotated[list[PlanningConstraint], Field(max_length=100)] = Field(
        default_factory=list
    )
    # One entry per constraint (None for constraints typed directly); stored for review only.
    constraint_sources: Annotated[list[ConstraintSource | None], Field(max_length=100)] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def _sources_match_constraints(self) -> ScenarioDecisionRequest:
        if self.constraint_sources and len(self.constraint_sources) != len(self.constraints):
            raise ValueError("constraint_sources needs one entry per constraint")
        return self


class DecisionDispositionRequest(BaseModel):
    """Record the authorised operator's disposition of a persisted decision."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "reject"]
    reason_code: Annotated[str, Field(min_length=1, max_length=64)]
    reason: Annotated[str | None, Field(max_length=1_000)] = None

    @model_validator(mode="after")
    def _reason_code_fits_action(self) -> DecisionDispositionRequest:
        problem = reason_problem(self.action, self.reason_code, self.reason)
        if problem:
            raise ValueError(problem)
        return self


class ErrorResponse(BaseModel):
    """Stable safe error envelope for clients."""

    detail: str
    request_id: str | None = None
    # Validation problems: field location and message only; submitted values are never echoed.
    errors: list[dict[str, object]] | None = None


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

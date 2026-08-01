"""Request contracts for public HTTP endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from aegisops.domain.models import Scenario


class ScenarioDecisionRequest(BaseModel):
    """Accept an explicit validated scenario or request a generated seeded scenario."""

    model_config = ConfigDict(extra="forbid")

    scenario: Scenario | None = None
    seed: Annotated[int | None, Field(ge=0, le=2_147_483_647)] = None
    max_turns: Annotated[int, Field(ge=1, le=20)] = 4


class DecisionDispositionRequest(BaseModel):
    """Record the authorised operator's disposition of a persisted decision."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "reject"]
    reason: Annotated[str, Field(min_length=1, max_length=1_000)]


class ErrorResponse(BaseModel):
    """Stable safe error envelope for clients."""

    detail: str
    request_id: str | None = None

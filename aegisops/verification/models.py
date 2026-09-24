"""Verification results."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CheckSeverity(StrEnum):
    CRITICAL = "critical"  # a failure blocks the plan
    HIGH = "high"  # shown to the operator; does not block
    WARNING = "warning"  # flag only


class Verdict(StrEnum):
    PASS = "pass"
    BLOCKED = "blocked"


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    passed: bool
    severity: CheckSeverity
    message: str
    offending_ids: list[str] = Field(default_factory=list)


class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    checks: list[CheckResult]
    blocking_check_ids: list[str]
    # True when the plan is honest but a critical incident has declared unmet demand.
    safety_gate_blocked: bool

    def failed(self) -> list[CheckResult]:
        return [check for check in self.checks if not check.passed]

    def check(self, check_id: str) -> CheckResult:
        return next(check for check in self.checks if check.id == check_id)


class TextDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: Literal["sitrep"]
    text: str


class VerificationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    objective_tolerance: float = 0.10
    objective_abs_slack: float = 1.0
    travel_abs_minutes: float = 1.0
    travel_rel: float = 0.05
    # Plans from engines that read evidence (the LLM) must cite it for every assignment.
    require_citations: bool = False

    def travel_tolerance(self, verified_minutes: float) -> float:
        return max(self.travel_abs_minutes, self.travel_rel * verified_minutes)

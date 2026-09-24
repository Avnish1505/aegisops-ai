"""Ports isolate decision-making implementations from transport concerns."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from aegisops.domain.models import DecisionResult, Evidence, Scenario
from aegisops.planning.constraints import PlanningConstraint
from aegisops.planning.travel import TravelTimeMatrix


class DecisionEngine(Protocol):
    """A pluggable recommendation engine; outputs may never dispatch resources directly."""

    name: str

    def recommend(
        self,
        scenario: Scenario,
        travel_times: TravelTimeMatrix | None = None,
        constraints: Sequence[PlanningConstraint] = (),
    ) -> DecisionResult:
        """Create an auditable proposal for verification and human review."""


class RetrievalPort(Protocol):
    """Retrieve the top three local knowledge snippets for a query."""

    def retrieve(self, query: str) -> list[str]:
        """Return relevant knowledge snippets without executing an action."""


class StructuredRetrievalPort(RetrievalPort, Protocol):
    """Optional provenance-aware retrieval extension for newer adapters."""

    def retrieve_evidence(self, query: str) -> list[Evidence]:
        """Return relevant snippets as structured, attributable evidence."""

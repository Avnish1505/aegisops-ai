"""Ports isolate decision-making implementations from transport concerns."""

from __future__ import annotations

from typing import Protocol

from aegisops.domain.models import DecisionResult, Evidence, Scenario


class DecisionEngine(Protocol):
    """A pluggable recommendation engine; outputs may never dispatch resources directly."""

    def recommend(self, scenario: Scenario) -> DecisionResult:
        """Create an auditable recommendation for human review."""


class RetrievalPort(Protocol):
    """Retrieve the top three local knowledge snippets for a query."""

    def retrieve(self, query: str) -> list[str]:
        """Return relevant knowledge snippets without executing an action."""


class StructuredRetrievalPort(RetrievalPort, Protocol):
    """Optional provenance-aware retrieval extension for newer adapters."""

    def retrieve_evidence(self, query: str) -> list[Evidence]:
        """Return relevant snippets as structured, attributable evidence."""

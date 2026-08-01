"""Role contracts reserved for the future constrained multi-agent adapter.

They are data, not executable agents: Phase 1 avoids importing an LLM SDK or allowing a model to
influence operational recommendations before guardrails and evaluations exist.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentRole:
    """A narrow future role with explicit non-authority over dispatch."""

    name: str
    responsibility: str
    prohibited_action: str


AGENT_ROLES: tuple[AgentRole, ...] = (
    AgentRole("perception", "Normalise and rank evidence", "Allocate or dispatch resources"),
    AgentRole("allocator", "Propose capability-aware options", "Execute a dispatch"),
    AgentRole(
        "communications", "Draft operator-reviewed communications", "Publish unapproved content"
    ),
    AgentRole("safety_auditor", "Identify policy and evidence gaps", "Override human authority"),
)

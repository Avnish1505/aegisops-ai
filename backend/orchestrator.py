"""Compatibility orchestration facade for the Phase 1 deterministic baseline.

The original direct AutoGen integration has been intentionally removed from the runtime path.
Phase 2 will add an LLM adapter behind the ``DecisionEngine`` port after structured-output,
retrieval, evaluation, and human-approval controls are designed and tested.
"""

from __future__ import annotations

from aegisops.domain.models import Scenario
from aegisops.infrastructure.rule_based_engine import RuleBasedDecisionEngine


async def run_pipeline(scenario: dict[str, object], max_turns: int = 4) -> dict[str, object]:
    """Return a validated advisory recommendation without provider calls or side effects.

    ``max_turns`` remains accepted to avoid breaking prototype clients; it has no effect until a
    future multi-agent adapter is introduced.
    """
    del max_turns
    validated_scenario = Scenario.model_validate(scenario)
    return RuleBasedDecisionEngine().recommend(validated_scenario).model_dump(mode="json")

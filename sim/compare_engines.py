"""Compare rule-based and NIM RAG decision outputs for one synthetic scenario."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aegisops.application.scenario_service import generate_scenario
from aegisops.infrastructure.llm_decision_engine import LLMDecisionEngine
from aegisops.infrastructure.retrieval_engine import RetrievalEngine
from aegisops.infrastructure.rule_based_engine import RuleBasedDecisionEngine


def main() -> None:
    """Generate a scenario and print both engine outputs as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="Synthetic scenario seed.")
    args = parser.parse_args()

    scenario = generate_scenario(seed=args.seed)
    knowledge_dir = Path(__file__).parents[1] / "knowledge"
    results = {
        "scenario_id": scenario.scenario_id,
        "rule_based": RuleBasedDecisionEngine().recommend(scenario).model_dump(mode="json"),
        "llm_rag": LLMDecisionEngine(RetrievalEngine(knowledge_dir))
        .recommend(scenario)
        .model_dump(mode="json"),
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

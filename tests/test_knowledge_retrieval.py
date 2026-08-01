from pathlib import Path

from aegisops.infrastructure.knowledge_retrieval import KnowledgeRetriever
from aegisops.infrastructure.retrieval_engine import RetrievalEngine


def test_retrieves_human_approval_guidance() -> None:
    knowledge_dir = Path(__file__).parents[1] / "knowledge"

    results = KnowledgeRetriever(knowledge_dir).search(
        "contact responders or execute operational actions", limit=1
    )

    assert results[0].path.name == "human-approval.md"
    assert "authorised human operator" in results[0].content


def test_retrieval_engine_returns_three_snippets() -> None:
    knowledge_dir = Path(__file__).parents[1] / "knowledge"

    snippets = RetrievalEngine(knowledge_dir).retrieve("critical unmet capability escalation")

    assert len(snippets) == 3
    assert all(snippet for snippet in snippets)


def test_retrieval_engine_returns_structured_evidence_with_stable_ids() -> None:
    knowledge_dir = Path(__file__).parents[1] / "knowledge"
    engine = RetrievalEngine(knowledge_dir)

    evidence = engine.retrieve_evidence("critical unmet capability escalation")

    assert len(evidence) == 3
    assert all(item.id.startswith("knowledge-") for item in evidence)
    assert len({item.id for item in evidence}) == len(evidence)
    assert all(item.description and item.source.endswith(".md") for item in evidence)
    assert engine.retrieve("critical unmet capability escalation") == [
        item.description for item in evidence
    ]

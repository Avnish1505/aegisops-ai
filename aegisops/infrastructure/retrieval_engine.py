"""Retrieval engine for returning local knowledge snippets."""

from __future__ import annotations

from pathlib import Path

from aegisops.domain.models import Evidence
from aegisops.infrastructure.knowledge_retrieval import KnowledgeRetriever


class RetrievalEngine:
    """Return the three most relevant snippets from the local knowledge corpus."""

    def __init__(self, knowledge_dir: Path) -> None:
        self._retriever = KnowledgeRetriever(knowledge_dir)

    def retrieve(self, query: str) -> list[str]:
        """Return the top three knowledge snippets for legacy callers."""
        return [evidence.description for evidence in self.retrieve_evidence(query)]

    def retrieve_evidence(self, query: str) -> list[Evidence]:
        """Return the top three snippets with stable IDs and source provenance."""
        return [
            Evidence(
                id=f"knowledge-{result.path.stem}",
                description=result.content,
                source=result.path.name,
                confidence=round(max(0.0, min(1.0, result.score)), 4),
            )
            for result in self._retriever.search(query, limit=3)
        ]

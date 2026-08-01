"""Retrieval engine for returning local knowledge snippets."""

from __future__ import annotations

from pathlib import Path

from aegisops.infrastructure.knowledge_retrieval import KnowledgeRetriever


class RetrievalEngine:
    """Return the three most relevant snippets from the local knowledge corpus."""

    def __init__(self, knowledge_dir: Path) -> None:
        self._retriever = KnowledgeRetriever(knowledge_dir)

    def retrieve(self, query: str) -> list[str]:
        """Return the top three knowledge snippets for a query."""
        return [result.content for result in self._retriever.search(query, limit=3)]

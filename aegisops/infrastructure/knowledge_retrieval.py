"""Local, deterministic retrieval over the AegisOps knowledge corpus."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import blake2b
from pathlib import Path

import faiss
import numpy as np

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
EMBEDDING_DIMENSION = 256


@dataclass(frozen=True)
class RetrievalResult:
    """A knowledge document returned by local similarity search."""

    path: Path
    content: str
    score: float


class KnowledgeRetriever:
    """Load Markdown knowledge documents and search a local FAISS index."""

    def __init__(self, knowledge_dir: Path) -> None:
        self._paths = sorted(knowledge_dir.glob("*.md"))
        if not self._paths:
            raise ValueError("knowledge_dir must contain at least one Markdown file")
        self._documents = [path.read_text(encoding="utf-8") for path in self._paths]
        embeddings = np.vstack([self._embed(document) for document in self._documents])
        self._index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
        self._index.add(embeddings)

    def search(self, query: str, limit: int = 3) -> list[RetrievalResult]:
        """Return the most similar documents for a non-empty query."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if limit < 1:
            raise ValueError("limit must be at least 1")

        scores, indices = self._index.search(
            self._embed(query)[None, :], min(limit, len(self._paths))
        )
        return [
            RetrievalResult(
                path=self._paths[index], content=self._documents[index], score=float(score)
            )
            for score, index in zip(scores[0], indices[0], strict=True)
        ]

    @staticmethod
    def _embed(text: str) -> np.ndarray:
        vector = np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)
        for token in TOKEN_PATTERN.findall(text.lower()):
            digest = blake2b(token.encode(), digest_size=8).digest()
            position = int.from_bytes(digest, "big") % EMBEDDING_DIMENSION
            vector[position] += 1.0
        norm = np.linalg.norm(vector)
        if norm:
            vector /= norm
        return vector

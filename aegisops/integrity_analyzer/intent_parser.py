"""Parse a natural-language intent string into capability keywords.

This is a standalone stage: it takes the free-text description of what a piece
of code is *supposed* to do (an "intent") and reduces it to a normalized list
of keywords a later stage can compare against what the code actually does.
Nothing here inspects source code or an AST; it only processes text, and it
uses only the Python standard library.
"""

from __future__ import annotations

import re

MIN_KEYWORD_LENGTH = 3

# A small set of common English stopwords. Deliberately not exhaustive: this
# is a simple filter, not a linguistic stopword corpus.
STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "nor",
        "for",
        "yet",
        "so",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "am",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "from",
        "with",
        "into",
        "onto",
        "over",
        "under",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "as",
        "if",
        "then",
        "than",
        "when",
        "while",
        "which",
        "who",
        "whom",
        "whose",
        "there",
        "here",
        "not",
        "no",
        "can",
        "could",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "must",
        "have",
        "has",
        "had",
        "does",
        "did",
        "do",
        "we",
        "you",
        "your",
        "our",
        "their",
        "they",
        "them",
    }
)

_WORD_PATTERN = re.compile(r"[a-z0-9]+")


def parse_intent(intent: str) -> list[str]:
    """Reduce a natural-language intent string to a list of capability keywords.

    The text is normalized (lowercased, punctuation stripped), split into
    words, filtered against a small stopword list, and trimmed to words
    longer than :data:`MIN_KEYWORD_LENGTH` characters. Order is preserved and
    duplicate keywords are removed.
    """
    if not intent or not intent.strip():
        raise ValueError("intent must be a non-empty string")

    keywords: list[str] = []
    seen: set[str] = set()
    for word in _WORD_PATTERN.findall(intent.lower()):
        if len(word) <= MIN_KEYWORD_LENGTH:
            continue
        if word in STOPWORDS:
            continue
        if word in seen:
            continue
        seen.add(word)
        keywords.append(word)

    return keywords

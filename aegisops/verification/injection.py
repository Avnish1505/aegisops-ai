"""Detect instruction-like text in untrusted reports. Flag only: it never changes a plan."""

from __future__ import annotations

import re

PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(ignore|disregard|forget)\b.{0,30}\b(previous|prior|above|earlier|all)\b.{0,20}"
        r"\b(instructions?|rules?|prompts?|polic(y|ies))\b",
        r"\b(system|developer)\s+prompt\b",
        r"\byou\s+are\s+now\b",
        r"\b(act|behave)\s+as\s+(an?\s+)?(ai|assistant|system|administrator|admin)\b",
        r"\b(approve|dispatch|authori[sz]e)\b.{0,40}\bwithout\b.{0,20}"
        r"\b(review|approval|verification|checks?)\b",
        r"\b(bypass|override|disable|skip)\b.{0,20}\b(safety|approval|verification|verifier|"
        r"gates?|checks?)\b",
        r"\bdo\s+not\s+(require|ask\s+for|wait\s+for)\b.{0,20}\bapproval\b",
        r"<\|im_(start|end)\|>|\[/?INST\]|###\s*(instruction|system)",
    )
)


def looks_like_instruction(text: str) -> bool:
    return any(pattern.search(text) for pattern in PATTERNS)

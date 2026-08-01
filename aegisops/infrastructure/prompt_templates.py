"""Versioned prompt templates for reproducible NIM evaluation and A/B testing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    """An immutable, versioned system prompt."""

    version: str
    system_message: str


DEFAULT_PROMPT_VERSION = "nim-v1"

# The v1 text is intentionally identical to the pre-template system prompt.
PROMPT_TEMPLATES: dict[str, PromptTemplate] = {
    DEFAULT_PROMPT_VERSION: PromptTemplate(
        version=DEFAULT_PROMPT_VERSION,
        system_message=(
            "Return JSON only. The JSON must validate as an AegisOps "
            "DecisionResult. It must require human approval and must never "
            "describe dispatch execution. Reference only supplied evidence IDs "
            "in DecisionResult.evidence_ids and Assignment.evidence_ids."
        ),
    )
}


def get_prompt_template(version: str = DEFAULT_PROMPT_VERSION) -> PromptTemplate:
    """Return a registered prompt template or reject an unknown experiment arm."""
    try:
        return PROMPT_TEMPLATES[version]
    except KeyError as error:
        raise ValueError(f"Unknown prompt version: {version}") from error

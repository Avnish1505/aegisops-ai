import pytest

from aegisops.infrastructure.prompt_templates import (
    DEFAULT_PROMPT_VERSION,
    get_prompt_template,
)


def test_default_prompt_template_preserves_existing_prompt_text() -> None:
    assert get_prompt_template(DEFAULT_PROMPT_VERSION).system_message == (
        "Return JSON only. The JSON must validate as an AegisOps "
        "DecisionResult. It must require human approval and must never "
        "describe dispatch execution. Reference only supplied evidence IDs "
        "in DecisionResult.evidence_ids and Assignment.evidence_ids."
    )


def test_unknown_prompt_template_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown prompt version"):
        get_prompt_template("unknown")

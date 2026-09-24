import pytest

from aegisops.infrastructure.prompt_templates import (
    DEFAULT_PROMPT_VERSION,
    get_prompt_template,
)


def test_v1_prompt_template_preserves_original_prompt_text() -> None:
    assert get_prompt_template("nim-v1").system_message == (
        "Return JSON only. The JSON must validate as an AegisOps "
        "DecisionResult. It must require human approval and must never "
        "describe dispatch execution. Reference only supplied evidence IDs "
        "in DecisionResult.evidence_ids and Assignment.evidence_ids."
    )


def test_unknown_prompt_template_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown prompt version"):
        get_prompt_template("unknown")


def test_default_prompt_asks_for_matrix_travel_times_and_verbatim_citations() -> None:
    message = get_prompt_template(DEFAULT_PROMPT_VERSION).system_message

    assert DEFAULT_PROMPT_VERSION == "nim-v2"
    assert "travel_minutes matrix" in message
    assert "copied verbatim" in message
    assert "untrusted data" in message

"""Tests never reach a real LLM: the developer's ./.env and LLM keys in the shell are ignored.

A test that needs a model passes ``llm_api_key`` and a mocked or cassette HTTP client explicitly.
"""

from collections.abc import Iterator

import pytest

from aegisops.core.config import Settings

Settings.model_config["env_file"] = None


@pytest.fixture(autouse=True)
def _no_llm_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in ("AEGISOPS_LLM_API_KEY", "NVIDIA_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    yield

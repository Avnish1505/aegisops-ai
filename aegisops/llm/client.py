"""One OpenAI-compatible chat client with schema-constrained JSON output.

Constrained decoding: NVIDIA NIM gets ``extra_body={"nvext": {"guided_json": schema}}``; other
OpenAI-compatible servers get ``response_format={"type": "json_schema", ...}``. Either way the
reply is validated against the Pydantic schema before anyone sees it.

Every call is logged with model, prompt name and version, tokens in/out, latency and an estimated
cost, and recorded in a ``CallLog`` so evals can total cost per decision. A GenAI ``chat`` span is
emitted for tracing (``aegisops.telemetry``).
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Generic, TypeVar

import httpx2  # the openai SDK is built on httpx2 (same API as httpx)
from openai import APIError, OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam
from pydantic import BaseModel, ValidationError

from aegisops.core.config import Settings
from aegisops.llm.cassette import CassetteMiss, CassetteTransport
from aegisops.telemetry import chat_span

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


@dataclass(frozen=True, slots=True)
class Prompt:
    name: str
    version: str
    system: str
    user: str


@dataclass(frozen=True, slots=True)
class CallRecord:
    prompt_name: str
    prompt_version: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    cost_usd: float
    ok: bool


@dataclass(frozen=True, slots=True)
class LLMCall(Generic[T]):
    value: T
    raw: str
    record: CallRecord


class LLMError(RuntimeError):
    """The model could not be reached or answered with an HTTP error."""


class LLMOutputError(ValueError):
    """The model answered, but not with JSON matching the schema."""

    def __init__(self, message: str, raw: str) -> None:
        super().__init__(message)
        self.raw = raw


@dataclass
class CallLog:
    """In-process list of calls, for totals in evals and per-decision cost."""

    records: list[CallRecord] = field(default_factory=list)

    @property
    def cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.records)

    @property
    def tokens(self) -> tuple[int, int]:
        return (
            sum(r.input_tokens for r in self.records),
            sum(r.output_tokens for r in self.records),
        )


class LLMClient:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx2.Client | None = None,
        call_log: CallLog | None = None,
    ) -> None:
        self._settings = settings
        self.model = settings.llm_model
        self.call_log = call_log if call_log is not None else CallLog()
        if http_client is None and settings.llm_cassette_mode != "off":
            if settings.llm_cassette_dir is None:
                raise ValueError("llm_cassette_mode needs llm_cassette_dir")
            http_client = httpx2.Client(
                transport=CassetteTransport(settings.llm_cassette_dir, settings.llm_cassette_mode),
                timeout=settings.llm_timeout_s,
            )
        key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
        # Replaying cassettes needs no key; the placeholder never leaves this process.
        self._openai = OpenAI(
            api_key=key or "replay-only-no-key",
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            http_client=http_client,
        )
        self.available = bool(key) or settings.llm_cassette_mode == "replay"

    @property
    def provider(self) -> str:
        if self._settings.llm_provider != "auto":
            return self._settings.llm_provider
        return "nvidia" if "nvidia.com" in self._settings.llm_base_url else "openai"

    def _create(
        self,
        messages: list[ChatCompletionMessageParam],
        schema: type[BaseModel],
        temperature: float,
        max_tokens: int,
    ) -> ChatCompletion:
        json_schema = schema.model_json_schema()
        if self.provider == "nvidia":
            return self._openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={"nvext": {"guided_json": json_schema}},
            )
        return self._openai.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": json_schema, "strict": True},
            },
        )

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self._settings.llm_price_in_usd_per_mtok
            + output_tokens * self._settings.llm_price_out_usd_per_mtok
        ) / 1_000_000

    def complete_json(
        self,
        prompt: Prompt,
        schema: type[T],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMCall[T]:
        with chat_span(
            provider=self.provider,
            model=self.model,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
            temperature=temperature,
            max_tokens=max_tokens,
        ) as span:
            started = time.perf_counter()
            try:
                response = self._create(
                    [
                        {"role": "system", "content": prompt.system},
                        {"role": "user", "content": prompt.user},
                    ],
                    schema,
                    temperature,
                    max_tokens,
                )
            except (APIError, httpx2.HTTPError, CassetteMiss) as error:
                self._log(prompt, 0, 0, time.perf_counter() - started, ok=False)
                raise LLMError(f"{type(error).__name__}: {error}") from error
            latency = time.perf_counter() - started
            usage = response.usage
            tokens_in = usage.prompt_tokens if usage else 0
            tokens_out = usage.completion_tokens if usage else 0
            raw = (response.choices[0].message.content or "") if response.choices else ""
            span.record_response(response.model or self.model, tokens_in, tokens_out)
            try:
                value = schema.model_validate_json(_strip_fence(raw))
            except (ValidationError, json.JSONDecodeError) as error:
                record = self._log(prompt, tokens_in, tokens_out, latency, ok=False)
                span.record_error("invalid_output")
                raise LLMOutputError(f"output does not match {schema.__name__}", raw) from error
            record = self._log(prompt, tokens_in, tokens_out, latency, ok=True)
            return LLMCall(value=value, raw=raw, record=record)

    def _log(
        self, prompt: Prompt, tokens_in: int, tokens_out: int, latency: float, *, ok: bool
    ) -> CallRecord:
        record = CallRecord(
            prompt_name=prompt.name,
            prompt_version=prompt.version,
            model=self.model,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            latency_s=latency,
            cost_usd=self.cost(tokens_in, tokens_out),
            ok=ok,
        )
        self.call_log.records.append(record)
        logger.info(
            "llm_call model=%s prompt=%s@%s tokens_in=%d tokens_out=%d latency_s=%.3f "
            "cost_usd=%.6f ok=%s",
            record.model, record.prompt_name, record.prompt_version, tokens_in, tokens_out,
            latency, record.cost_usd, ok,
        )
        return record


def _strip_fence(text: str) -> str:
    text = text.strip()
    match = _FENCE.match(text)
    return match.group(1) if match else text

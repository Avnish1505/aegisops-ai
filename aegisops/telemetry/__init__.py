"""OpenTelemetry spans following the GenAI semantic conventions.

LLM calls become ``chat {model}`` spans and deterministic steps (solver, OSRM, verifier) become
``execute_tool {name}`` spans, both with ``gen_ai.*`` attributes. The matching OpenInference
attributes are set too, because Arize Phoenix renders those. With no exporter configured the
OpenTelemetry API is a no-op, so this costs nothing in tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

tracer = trace.get_tracer("aegisops")


class ChatSpan:
    def __init__(self, span: Span) -> None:
        self._span = span

    def record_response(self, model: str, input_tokens: int, output_tokens: int) -> None:
        self._span.set_attributes(
            {
                "gen_ai.response.model": model,
                "gen_ai.usage.input_tokens": input_tokens,
                "gen_ai.usage.output_tokens": output_tokens,
                "llm.token_count.prompt": input_tokens,
                "llm.token_count.completion": output_tokens,
                "llm.token_count.total": input_tokens + output_tokens,
            }
        )

    def record_error(self, error_type: str) -> None:
        self._span.set_attribute("error.type", error_type)
        self._span.set_status(Status(StatusCode.ERROR, error_type))


@contextmanager
def chat_span(
    *,
    provider: str,
    model: str,
    prompt_name: str,
    prompt_version: str,
    temperature: float,
    max_tokens: int,
) -> Iterator[ChatSpan]:
    with tracer.start_as_current_span(f"chat {model}", kind=trace.SpanKind.CLIENT) as span:
        span.set_attributes(
            {
                "gen_ai.operation.name": "chat",
                "gen_ai.provider.name": provider,
                "gen_ai.request.model": model,
                "gen_ai.request.temperature": temperature,
                "gen_ai.request.max_tokens": max_tokens,
                "aegisops.prompt.name": prompt_name,
                "aegisops.prompt.version": prompt_version,
                "openinference.span.kind": "LLM",
                "llm.model_name": model,
                "llm.provider": provider,
            }
        )
        try:
            yield ChatSpan(span)
        except Exception as error:
            span.set_attribute("error.type", type(error).__name__)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            raise


@contextmanager
def tool_span(name: str, **attributes: Any) -> Iterator[Span]:
    """A deterministic step (solve, travel matrix, verify) as a GenAI execute_tool span."""
    with tracer.start_as_current_span(f"execute_tool {name}") as span:
        span.set_attributes(
            {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": name,
                "gen_ai.tool.type": "function",
                "openinference.span.kind": "TOOL",
                "tool.name": name,
                **{f"aegisops.{key}": value for key, value in attributes.items()},
            }
        )
        yield span

"""OpenTelemetry spans following the GenAI semantic conventions.

LLM calls become ``chat {model}`` spans and deterministic steps (solver, OSRM, verifier) become
``execute_tool {name}`` spans, both with ``gen_ai.*`` attributes. The matching OpenInference
attributes are set too, because Arize Phoenix renders those. With no exporter configured the
OpenTelemetry API is a no-op, so this costs nothing in tests.

One decision is one trace. Its steps happen in separate HTTP requests (read a report, plan and
verify, approve or reject, draft messages), so each step span takes an explicit W3C
``traceparent``: the client passes the one returned by ``/intake/read`` when it requests a plan,
and the plan's traceparent is stored on the decision so the disposition and drafts join it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

tracer = trace.get_tracer("aegisops")
_propagator = TraceContextTextMapPropagator()
_configured = False


def configure_tracing(endpoint: str | None, service_name: str) -> bool:
    """Export spans over OTLP/HTTP to ``{endpoint}/v1/traces``. Idempotent; False when off.

    The global tracer provider can only be set once per process, so the first configured call
    wins and later ones (another ``create_app`` in the same process) are no-ops.
    """
    global _configured
    if not endpoint:
        return False
    if _configured:
        return True
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces"))
    )
    trace.set_tracer_provider(provider)
    _configured = True
    return True


def current_traceparent() -> str | None:
    """The W3C traceparent of the active span, or None when nothing is being recorded."""
    carrier: dict[str, str] = {}
    _propagator.inject(carrier)
    return carrier.get("traceparent")


@contextmanager
def step_span(step: str, *, traceparent: str | None = None, **attributes: Any) -> Iterator[Span]:
    """One pipeline step (read, plan, decide, communicate) of a decision's trace.

    ``traceparent`` continues a trace started in an earlier request; without one (or with an
    invalid one) the step starts a new trace.
    """
    parent = _propagator.extract({"traceparent": traceparent}) if traceparent else None
    with tracer.start_as_current_span(f"aegisops.{step}", context=parent) as span:
        span.set_attributes(
            {
                "aegisops.step": step,
                "openinference.span.kind": "CHAIN",
                **{f"aegisops.{key}": value for key, value in attributes.items()},
            }
        )
        try:
            yield span
        except Exception as error:
            span.set_attribute("error.type", type(error).__name__)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            raise


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

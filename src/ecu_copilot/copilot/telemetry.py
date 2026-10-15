"""OpenTelemetry setup. One tracer provider for the process; the Anthropic SDK emits its own
spans (anthropic.messages.create, tool runner) into it, our tools add child spans, and the
API handler wraps everything in one root span per question. Exported over OTLP/HTTP to
Jaeger when OTEL_EXPORTER_OTLP_ENDPOINT is set; otherwise spans stay in-process (no-op export).
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .. import config

_provider: TracerProvider | None = None


def setup_tracing() -> TracerProvider:
    global _provider
    if _provider is not None:
        return _provider
    provider = TracerProvider(resource=Resource.create({"service.name": config.OTEL_SERVICE_NAME}))
    if config.OTEL_ENDPOINT:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{config.OTEL_ENDPOINT}/v1/traces")))
    trace.set_tracer_provider(provider)
    _provider = provider
    return provider


def current_trace_id() -> str | None:
    ctx = trace.get_current_span().get_span_context()
    return f"{ctx.trace_id:032x}" if ctx.is_valid else None

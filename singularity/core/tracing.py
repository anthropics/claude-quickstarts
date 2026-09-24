"""
Singularity — OpenTelemetry distributed tracing (Fáze 13).

Setup: call setup_tracing() once at startup (lifespan).
Usage: get_tracer() returns the configured tracer; wrap node calls with
       tracer.start_as_current_span("node.plan").

In dev/test mode (otlp_endpoint="") an InMemorySpanExporter captures
all finished spans so they can be served via GET /traces.
In prod set otlp_endpoint to a Jaeger/Tempo/Collector gRPC address.
"""
from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_provider: TracerProvider | None = None
_memory_exporter: InMemorySpanExporter | None = None

SERVICE_NAME = "singularity"


def setup_tracing(otlp_endpoint: str = "", service_name: str = SERVICE_NAME) -> None:
    """Initialise global TracerProvider.  Call once at application startup."""
    global _provider, _memory_exporter

    resource = Resource.create({"service.name": service_name})
    _provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            _provider.add_span_processor(BatchSpanProcessor(exporter))
        except ImportError:
            pass  # opentelemetry-exporter-otlp-proto-grpc not installed — skip silently
    else:
        _memory_exporter = InMemorySpanExporter()
        _provider.add_span_processor(SimpleSpanProcessor(_memory_exporter))

    trace.set_tracer_provider(_provider)


def get_tracer(name: str = SERVICE_NAME) -> trace.Tracer:
    return trace.get_tracer(name)


def get_finished_spans(limit: int = 100) -> list[dict]:
    """Return last `limit` finished spans as JSON-serialisable dicts (in-memory mode only)."""
    if _memory_exporter is None:
        return []
    spans = _memory_exporter.get_finished_spans()
    result = []
    for span in spans[-limit:]:
        ctx = span.get_span_context()
        result.append({
            "name": span.name,
            "trace_id": format(ctx.trace_id, "032x"),
            "span_id": format(ctx.span_id, "016x"),
            "start_time_ns": span.start_time,
            "end_time_ns": span.end_time,
            "duration_ms": round((span.end_time - span.start_time) / 1_000_000, 3)
            if span.end_time and span.start_time else None,
            "status": span.status.status_code.name,
            "attributes": dict(span.attributes or {}),
        })
    return result


def clear_spans() -> None:
    """Flush in-memory exporter (useful in tests)."""
    if _memory_exporter is not None:
        _memory_exporter.clear()

"""OpenTelemetry tracing setup for distributed tracing with Jaeger."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def setup_tracing(service_name: str = "facebook-clone", jaeger_endpoint: str = "") -> None:
    """Configure OpenTelemetry with OTLP exporter (Jaeger/Grafana Tempo)."""
    if not jaeger_endpoint:
        logger.info("Tracing disabled — OTEL_EXPORTER_OTLP_ENDPOINT not set")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=jaeger_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Auto-instrument FastAPI and SQLAlchemy
        FastAPIInstrumentor().instrument()
        SQLAlchemyInstrumentor().instrument(enable_commenter=True)

        logger.info("OpenTelemetry tracing enabled → %s", jaeger_endpoint)
    except ImportError:
        logger.warning(
            "OpenTelemetry packages not installed — tracing disabled. "
            "Install: opentelemetry-distro opentelemetry-exporter-otlp"
        )

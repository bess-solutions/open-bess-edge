"""
src/interfaces/otel_setup.py
=============================
OpenTelemetry bootstrap for BESSAI Edge Gateway.

Configures the global ``TracerProvider`` and ``MeterProvider`` with:
* OTLP/gRPC export to the configured collector endpoint.
* Resource attributes (service name, version, site ID) for correlation.
* Batch processors / readers for production throughput.

Call ``configure_otel()`` once at application startup, before creating
any tracer or meter.

Usage
-----
::

    from src.interfaces.otel_setup import configure_otel, get_tracer, get_meter

    configure_otel()

    tracer = get_tracer()
    meter  = get_meter()
    counter = meter.create_counter("bess.publish.count")
"""

from __future__ import annotations

import structlog
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.core.config import settings

log: structlog.BoundLogger = structlog.get_logger(__name__)

# Internal state — set once by configure_otel()
_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None

_INSTRUMENTATION_SCOPE = "bessai.edge"


def _build_resource() -> Resource:
    """Create an OTel Resource from application settings."""
    cfg = settings
    return Resource.create(
        {
            "service.name": cfg.OTEL_SERVICE_NAME,
            "service.version": "0.2.0",
            "deployment.environment": "production",
            "bessai.site_id": cfg.SITE_ID,
        }
    )


def configure_otel(
    otlp_endpoint: str | None = None,
    metric_export_interval_ms: int = 30_000,
) -> None:
    """
    Initialise the global OpenTelemetry providers.

    This function is idempotent — calling it more than once is a no-op
    after the first successful initialisation.

    Parameters
    ----------
    otlp_endpoint:
        Override the OTLP collector endpoint.  Defaults to
        ``OTEL_EXPORTER_OTLP_ENDPOINT`` from the environment.
    metric_export_interval_ms:
        Milliseconds between metric exports (default 30 s).
    """
    global _tracer_provider, _meter_provider

    if _tracer_provider is not None:
        log.debug("otel.already_configured")
        return

    endpoint = otlp_endpoint or _resolve_endpoint()
    resource = _build_resource()

    # ------------------------------------------------------------------ Traces
    span_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    _tracer_provider = TracerProvider(resource=resource)
    _tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(_tracer_provider)

    # ------------------------------------------------------------------ Metrics
    metric_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
    reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=metric_export_interval_ms,
    )
    _meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(_meter_provider)

    log.info(
        "otel.configured",
        endpoint=endpoint,
        service=settings.OTEL_SERVICE_NAME,
        site=settings.SITE_ID,
    )


def shutdown_otel() -> None:
    """Flush and shut down all OTel providers gracefully."""
    global _tracer_provider, _meter_provider
    if _tracer_provider:
        _tracer_provider.shutdown()
        _tracer_provider = None
    if _meter_provider:
        _meter_provider.shutdown()
        _meter_provider = None
    log.info("otel.shutdown")


def get_tracer(name: str = _INSTRUMENTATION_SCOPE) -> trace.Tracer:
    """Return a named tracer from the global provider."""
    return trace.get_tracer(name)


def get_meter(name: str = _INSTRUMENTATION_SCOPE) -> metrics.Meter:
    """Return a named meter from the global provider."""
    return metrics.get_meter(name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_endpoint() -> str:
    """Read the OTLP endpoint from settings (env var or .env file)."""
    return settings.OTEL_EXPORTER_OTLP_ENDPOINT

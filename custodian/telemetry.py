"""OpenTelemetry wiring.

The Fortified Enterprise Fleet track names observability "using OpenTelemetry
standards" as a required component. ADK already emits OTel spans, so the work
here is exporting them to Cloud Trace, where the demo's final beat shows the
parallel fan-out as spans.

Falls back to a local no-export provider when no project is configured, so the
fleet still runs offline without special-casing telemetry at call sites.
"""

from __future__ import annotations

import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)

_configured = False


def configure(service_name: str) -> trace.Tracer:
    """Install a tracer provider exporting to Cloud Trace when available.

    Args:
        service_name: Identifies this process in traces, e.g. "discovery.cloudsql".

    Returns:
        A tracer for the calling module.
    """
    global _configured
    if _configured:
        return trace.get_tracer(service_name)

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service_name,
                "service.namespace": "custodian",
            }
        )
    )

    if project:
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

            provider.add_span_processor(
                BatchSpanProcessor(CloudTraceSpanExporter(project_id=project))
            )
        except Exception:
            # Never let telemetry setup take the fleet down with it.
            logger.exception("Cloud Trace export unavailable; tracing locally only")
    else:
        logger.info("GOOGLE_CLOUD_PROJECT unset; traces stay local")

    trace.set_tracer_provider(provider)
    _configured = True
    return trace.get_tracer(service_name)

"""OpenTelemetry metrics configuration for application monitoring.

This module provides unified metrics setup that:
1. Sends metrics to OpenTelemetry Collector via OTLP
2. Auto-instruments FastAPI with request/response metrics
3. Provides custom metric creation capabilities
4. Supports Prometheus exemplars for trace correlation
"""

import os
from typing import Optional


def configure_otel_metrics(service_name: str, otel_endpoint: Optional[str] = None):
    """Configure OpenTelemetry metrics with FastAPI auto-instrumentation.
    
    Args:
        service_name: Name of the service (e.g., 'dreamfarm-agent')
        otel_endpoint: OTLP endpoint URL (if None, reads from OTEL_EXPORTER_OTLP_ENDPOINT)
    
    Returns:
        Tuple of (meter_provider, meter) for custom metrics
    """
    # Get OTLP endpoint from env or parameter
    endpoint = otel_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    
    if not endpoint:
        print("[INFO] OpenTelemetry metrics disabled (no OTLP endpoint)")
        return None, None
    
    try:
        from opentelemetry import metrics
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        
        # Create resource with service name
        resource = Resource(attributes={SERVICE_NAME: service_name})
        
        # Create OTLP metric exporter
        otlp_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
        
        # Create periodic exporting metric reader (export every 60 seconds)
        metric_reader = PeriodicExportingMetricReader(
            exporter=otlp_exporter,
            export_interval_millis=60000  # 60 seconds
        )
        
        # Create meter provider
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader]
        )
        
        # Set as global meter provider
        metrics.set_meter_provider(meter_provider)
        
        # Get meter for custom metrics
        meter = metrics.get_meter(service_name)
        
        print(f"[OK] OpenTelemetry metrics configured: service={service_name} endpoint={endpoint}")
        return meter_provider, meter
        
    except Exception as e:
        print(f"[WARNING] Failed to configure OpenTelemetry metrics: {e}")
        return None, None


def instrument_fastapi_metrics(app, meter_provider, meter):
    """Add FastAPI metrics instrumentation for HTTP request monitoring.
    
    Args:
        app: FastAPI application instance
        meter_provider: OpenTelemetry meter provider
        meter: OpenTelemetry meter for custom metrics
    """
    if not meter_provider or not meter:
        print("[INFO] FastAPI metrics instrumentation skipped (metrics not configured)")
        return
    
    try:
        # Import FastAPI instrumentation
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        
        # Instrument FastAPI app for metrics
        # This adds default HTTP server metrics:
        # - http.server.duration (histogram of request duration)
        # - http.server.request.size (histogram of request sizes)
        # - http.server.response.size (histogram of response sizes)
        # - http.server.active_requests (gauge of concurrent requests)
        FastAPIInstrumentor.instrument_app(
            app,
            meter_provider=meter_provider,
            excluded_urls="/health"  # Don't track health checks
        )
        
        print("[OK] FastAPI metrics instrumented")
        
    except Exception as e:
        print(f"[WARNING] Failed to instrument FastAPI metrics: {e}")


def create_custom_metrics(meter):
    """Create custom business metrics for the application.
    
    Args:
        meter: OpenTelemetry meter instance
    
    Returns:
        Dictionary of custom metric instruments
    """
    if not meter:
        return {}
    
    try:
        # Create custom metric instruments
        metrics_dict = {
            # Counter: Total number of LLM requests
            "llm_requests_total": meter.create_counter(
                name="llm.requests.total",
                description="Total number of LLM API requests",
                unit="1"
            ),
            
            # Histogram: LLM request duration
            "llm_request_duration": meter.create_histogram(
                name="llm.request.duration",
                description="Duration of LLM API requests",
                unit="ms"
            ),
            
            # Counter: Total tokens used
            "llm_tokens_total": meter.create_counter(
                name="llm.tokens.total",
                description="Total number of tokens consumed",
                unit="tokens"
            ),
            
            # Histogram: RAG search duration
            "rag_search_duration": meter.create_histogram(
                name="rag.search.duration",
                description="Duration of RAG search operations",
                unit="ms"
            ),
            
            # Counter: Cache hits
            "cache_hits_total": meter.create_counter(
                name="cache.hits.total",
                description="Total number of semantic cache hits",
                unit="1"
            ),
            
            # Counter: Cache misses
            "cache_misses_total": meter.create_counter(
                name="cache.misses.total",
                description="Total number of semantic cache misses",
                unit="1"
            ),
            
            # Histogram: Database query duration
            "db_query_duration": meter.create_histogram(
                name="db.query.duration",
                description="Duration of database queries",
                unit="ms"
            ),
        }
        
        print(f"[OK] Created {len(metrics_dict)} custom metric instruments")
        return metrics_dict
        
    except Exception as e:
        print(f"[WARNING] Failed to create custom metrics: {e}")
        return {}

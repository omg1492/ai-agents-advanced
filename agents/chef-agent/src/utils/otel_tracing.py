"""OpenTelemetry tracing configuration and initialization.

Provides centralized configuration for distributed tracing with support for:
- Custom span processor for business dimensions propagation
- Multiple instrumentation providers (OpenInference, standard OpenTelemetry)
- Auto-instrumentation for common libraries (OpenAI, PostgreSQL, SQLAlchemy)

Usage:
    from utils.otel_tracing import configure_otel_tracing

    # Initialize tracing early in main.py (before importing instrumented libraries)
    otel_enabled = configure_otel_tracing()
    
    # Service automatically gets:
    # - Distributed tracing with OTLP export
    # - Business dimensions propagation (user_id, is_vip, agent_type, experiment, thread_id)
    # - Auto-instrumentation for FastAPI, OpenAI, PostgreSQL, SQLAlchemy
"""

import os
from typing import Optional


class BaggageSpanProcessor:
    """Custom span processor that automatically copies baggage values to span attributes.
    
    This ensures that user/session context set via Baggage API is available as
    queryable attributes on all spans (including child spans from auto-instrumented
    frameworks/libraries). Baggage propagates across service boundaries via W3C headers.
    
    Key differences from ContextAttributeSpanProcessor:
    - Uses OpenTelemetry Baggage API (propagates across services)
    - Compatible with W3C Baggage propagation headers
    - Allows querying traces by business dimensions in Grafana Tempo
    
    Baggage keys to propagate (using Langfuse conventions):
    - user.id: User identifier for tracking user-specific traces (Langfuse semantic convention)
    - is_vip: VIP status for filtering premium user interactions
    - agent_type: Agent service identifier (dreamfarm, chef, etc.)
    - experiment: Experiment identifier for A/B testing
    - thread_id: Conversation thread identifier
    - session.id: Session identifier for grouping related interactions (Langfuse semantic convention)
    """
    
    # Define which baggage keys to copy to span attributes
    # Using Langfuse semantic conventions for user.id and session.id
    BAGGAGE_KEYS = [
        "user.id",
        "is_vip",
        "agent_type",
        "experiment",
        "thread_id",
        "session.id",
    ]
    
    def on_start(self, span: "Span", parent_context=None):
        """Called when span starts - copy baggage to span attributes.
        
        Args:
            span: The span being started
            parent_context: Optional parent context to inherit baggage from
        """
        from opentelemetry import baggage, context as otel_context
        
        ctx = parent_context or otel_context.get_current()
        
        # Copy each baggage item to span attributes
        for key in self.BAGGAGE_KEYS:
            value = baggage.get_baggage(key, ctx)
            if value is not None:
                span.set_attribute(key, value)
    
    def on_end(self, span):
        """Called when span ends."""
        pass
    
    def shutdown(self):
        """Called on shutdown."""
        pass
    
    def force_flush(self, timeout_millis: int = 30000):
        """Called on force flush."""
        return True


def configure_otel_tracing(
    service_name: Optional[str] = None,
    otlp_endpoint: Optional[str] = None,
    instrument_openai: bool = True,
    instrument_psycopg2: bool = False,
    instrument_sqlalchemy: bool = False,
) -> bool:
    """Configure OpenTelemetry distributed tracing with auto-instrumentation.
    
    Initializes OpenTelemetry tracing with:
    - TracerProvider with service name resource
    - Custom span processor for business dimensions propagation
    - OTLP gRPC exporter with batch processing
    - Optional auto-instrumentation for OpenAI, PostgreSQL, SQLAlchemy
    
    Environment Variables:
        OTEL_EXPORTER_OTLP_ENDPOINT: OTel Collector endpoint (required to enable)
        OTEL_SERVICE_NAME: Service name for traces (default: from service_name arg)
        OTEL_INSTRUMENTATION_PROVIDER: OpenAI instrumentation provider
            - "opentelemetry": Standard GenAI conventions (Langfuse-compatible)
            - "openinference": Custom conventions (Responses API streaming support)
    
    Args:
        service_name: Service name for resource attributes (default: from env or "unknown-service")
        otlp_endpoint: OTel Collector endpoint (default: from env or None)
        instrument_openai: Whether to auto-instrument OpenAI SDK (default: True)
        instrument_psycopg2: Whether to auto-instrument psycopg2 (default: False)
        instrument_sqlalchemy: Whether to auto-instrument SQLAlchemy (default: False)
    
    Returns:
        bool: True if tracing was successfully initialized, False otherwise
    
    Example:
        # In main.py, before importing FastAPI or other instrumented libraries
        from dotenv import load_dotenv
        load_dotenv()
        
        from utils.otel_tracing import configure_otel_tracing
        
        # Initialize tracing with OpenAI and PostgreSQL instrumentation
        otel_enabled = configure_otel_tracing(
            service_name="dreamfarm-agent",
            instrument_openai=True,
            instrument_psycopg2=True,
            instrument_sqlalchemy=True
        )
        
        # NOW import FastAPI and other libraries
        from fastapi import FastAPI
        app = FastAPI()
    """
    # Check if tracing is enabled via environment variable
    otlp_endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not otlp_endpoint:
        print("[INFO] OpenTelemetry tracing disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")
        return False
    
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        
        # Get service name from argument, env, or default
        service_name = service_name or os.getenv("OTEL_SERVICE_NAME", "unknown-service")
        
        # Create resource with service name
        resource = Resource(attributes={SERVICE_NAME: service_name})
        
        # Configure tracer provider
        provider = TracerProvider(resource=resource)
        
        # Add custom span processor to propagate baggage to span attributes
        provider.add_span_processor(BaggageSpanProcessor())
        
        # Add OTLP exporter with batch processor
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        
        # Set as global tracer provider
        trace.set_tracer_provider(provider)
        
        print(f"[OK] OpenTelemetry tracing initialized: service={service_name} endpoint={otlp_endpoint}")
        
        # Auto-instrument libraries based on flags
        if instrument_openai:
            _instrument_openai(provider)
        
        if instrument_psycopg2:
            _instrument_psycopg2()
        
        if instrument_sqlalchemy:
            _instrument_sqlalchemy()
        
        return True
        
    except Exception as e:
        print(f"[WARNING] OpenTelemetry tracing initialization failed: {e}")
        return False


def _instrument_openai(provider):
    """Instrument OpenAI SDK with chosen provider.
    
    Supports two instrumentation providers:
    - opentelemetry: Standard GenAI semantic conventions (Langfuse-compatible)
    - openinference: Custom conventions with Responses API streaming support
    
    Args:
        provider: TracerProvider instance to use for instrumentation
    """
    otel_provider = os.getenv("OTEL_INSTRUMENTATION_PROVIDER", "opentelemetry").lower()
    
    try:
        if otel_provider == "openinference":
            from openinference.instrumentation.openai import OpenAIInstrumentor
            OpenAIInstrumentor().instrument(tracer_provider=provider)
            print("[OK] OpenAI instrumented with OpenInference (Responses API streaming supported)")
        else:
            from opentelemetry.instrumentation.openai import OpenAIInstrumentor
            OpenAIInstrumentor().instrument(tracer_provider=provider)
            print("[OK] OpenAI instrumented with standard OpenTelemetry (GenAI conventions)")
        
        print(f"[INFO] OTEL_INSTRUMENTATION_PROVIDER={otel_provider}")
    except Exception as e:
        print(f"[WARNING] OpenAI instrumentation failed: {e}")


def _instrument_psycopg2():
    """Instrument psycopg2 for PostgreSQL query tracing."""
    try:
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
        Psycopg2Instrumentor().instrument()
        print("[OK] PostgreSQL (psycopg2) instrumented for database tracing")
    except Exception as e:
        print(f"[WARNING] psycopg2 instrumentation failed: {e}")


def _instrument_sqlalchemy():
    """Instrument SQLAlchemy for ORM operation tracing."""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument()
        print("[OK] SQLAlchemy instrumented for ORM tracing")
    except Exception as e:
        print(f"[WARNING] SQLAlchemy instrumentation failed: {e}")

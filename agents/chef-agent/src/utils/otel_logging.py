"""OpenTelemetry logging configuration for structured logging with trace correlation.

This module provides a unified logging setup that:
1. Sends logs to OpenTelemetry Collector via OTLP
2. Correlates logs with traces automatically
3. Uses structured JSON format for better queryability
4. Falls back to console logging if OTLP is unavailable
"""

import logging
import os
from typing import Optional


def configure_otel_logging(service_name: Optional[str] = None, otel_endpoint: Optional[str] = None) -> logging.Logger:
    """Configure OpenTelemetry logging with structured output and trace correlation.
    
    Configures the ROOT logger so all loggers in the application inherit OTLP handler.
    
    Args:
        service_name: Name of the service (if None, reads from OTEL_SERVICE_NAME env var)
        otel_endpoint: OTLP endpoint URL (if None, reads from OTEL_EXPORTER_OTLP_ENDPOINT)
    
    Returns:
        Root logger instance
    """
    # Get service name and OTLP endpoint from env if not provided
    service_name = service_name or os.getenv("OTEL_SERVICE_NAME", "unknown-service")
    endpoint = otel_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    
    # Configure ROOT logger (so all child loggers inherit handlers)
    logger = logging.getLogger()  # Root logger
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Add trace context filter FIRST (before formatters try to use the fields)
    _add_trace_context_filter(logger)
    
    # Always add console handler with structured format
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logger.level)
    
    # Structured format: timestamp service level message trace_id span_id
    console_format = logging.Formatter(
        '{"timestamp":"%(asctime)s","service":"%(name)s","level":"%(levelname)s",'
        '"message":"%(message)s","trace_id":"%(otelTraceID)s","span_id":"%(otelSpanID)s",'
        '"filename":"%(filename)s","lineno":%(lineno)d}',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # If OTLP endpoint is configured, add OTLP log handler
    if endpoint:
        try:
            from opentelemetry._logs import set_logger_provider
            from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
            from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
            from opentelemetry.sdk.resources import Resource, SERVICE_NAME
            
            # Create resource with service name
            resource = Resource(attributes={SERVICE_NAME: service_name})
            
            # Create logger provider
            logger_provider = LoggerProvider(resource=resource)
            
            # Add OTLP exporter with batch processor
            otlp_exporter = OTLPLogExporter(endpoint=endpoint, insecure=True)
            logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_exporter))
            
            # Set as global logger provider
            set_logger_provider(logger_provider)
            
            # Add OpenTelemetry logging handler
            otel_handler = LoggingHandler(level=logger.level, logger_provider=logger_provider)
            logger.addHandler(otel_handler)
            
            logger.info(f"OpenTelemetry logging configured: service={service_name} endpoint={endpoint}")
        except Exception as e:
            logger.warning(f"Failed to configure OpenTelemetry logging: {e}. Using console logging only.")
    else:
        logger.info("OpenTelemetry logging disabled (no OTLP endpoint). Using console logging only.")
    
    return logger


def _add_trace_context_filter(logger: logging.Logger):
    """Internal helper to add trace context to ALL log records globally.
    
    Uses setLogRecordFactory to ensure ALL log records (including from third-party libraries)
    have the trace context fields, preventing KeyError in formatters.
    
    Args:
        logger: Logger instance (not used, but kept for API compatibility)
    """
    from opentelemetry import trace
    
    # Get the original factory
    old_factory = logging.getLogRecordFactory()
    
    def record_factory(*args, **kwargs):
        """Custom LogRecord factory that adds trace context fields."""
        record = old_factory(*args, **kwargs)
        
        # Always initialize these fields to prevent KeyError
        record.otelTraceID = ""
        record.otelSpanID = ""
        
        # Try to populate from current span
        try:
            span = trace.get_current_span()
            if span:
                ctx = span.get_span_context()
                if ctx.is_valid:
                    record.otelTraceID = format(ctx.trace_id, '032x')
                    record.otelSpanID = format(ctx.span_id, '016x')
        except Exception:
            # Silently ignore - fields already initialized to empty strings
            pass
        
        return record
    
    # Install the custom factory globally
    logging.setLogRecordFactory(record_factory)


def add_trace_context_to_logs():
    """Add a logging filter that injects trace context into log records.
    
    This is now a no-op since the filter is added during configure_otel_logging().
    Kept for backward compatibility with existing code that calls this function.
    
    Note: The filter is automatically added when configure_otel_logging() is called,
    so you don't need to call this function separately.
    """
    pass  # Filter already added during configure_otel_logging()


def get_uvicorn_log_config() -> dict:
    """Get uvicorn logging configuration that uses the OTLP-configured root logger.
    
    This ensures uvicorn logs propagate to root logger (which has OTLP handler and filter).
    
    Returns:
        Dictionary compatible with uvicorn's log_config parameter
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {},
        "handlers": {},
        "loggers": {
            # All uvicorn loggers propagate to root logger (no handlers, just propagate)
            "uvicorn": {"level": log_level, "propagate": True, "handlers": []},
            "uvicorn.error": {"level": log_level, "propagate": True, "handlers": []},
            "uvicorn.access": {"level": log_level, "propagate": True, "handlers": []},
        },
    }

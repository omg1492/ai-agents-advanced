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


def configure_otel_logging(service_name: str, otel_endpoint: Optional[str] = None) -> logging.Logger:
    """Configure OpenTelemetry logging with structured output and trace correlation.
    
    Args:
        service_name: Name of the service (e.g., 'dreamfarm-agent')
        otel_endpoint: OTLP endpoint URL (if None, reads from OTEL_EXPORTER_OTLP_ENDPOINT)
    
    Returns:
        Configured logger instance
    """
    # Get OTLP endpoint from env or parameter
    endpoint = otel_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    
    # Create logger
    logger = logging.getLogger(service_name)
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
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


def add_trace_context_to_logs():
    """Add a logging filter that injects trace context into log records.
    
    This allows log records to include trace_id and span_id for correlation.
    Should be called after OpenTelemetry trace provider is initialized.
    """
    from opentelemetry import trace
    
    class TraceContextFilter(logging.Filter):
        """Logging filter that adds trace context to log records."""
        
        def filter(self, record):
            """Add trace_id and span_id to log record."""
            span = trace.get_current_span()
            if span:
                ctx = span.get_span_context()
                if ctx.is_valid:
                    # Format trace_id and span_id as hex strings
                    record.otelTraceID = format(ctx.trace_id, '032x')
                    record.otelSpanID = format(ctx.span_id, '016x')
                else:
                    record.otelTraceID = ""
                    record.otelSpanID = ""
            else:
                record.otelTraceID = ""
                record.otelSpanID = ""
            return True
    
    # Add filter to root logger
    logging.root.addFilter(TraceContextFilter())

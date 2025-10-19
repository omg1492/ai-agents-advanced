"""Chef Agent - FastAPI application using Responses API.

Specialized culinary services agent that connects to the remote Chef Services
MCP server for handling queries about chefs, catering, availability, and pricing.
"""

import os
import logging
from contextlib import asynccontextmanager

# Load environment variables FIRST (before any other imports that might use them)
from dotenv import load_dotenv
load_dotenv()

# Initialize OpenTelemetry tracing BEFORE importing any LLM libraries or services
# This is critical for auto-instrumentation to work properly
otel_enabled = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip() != ""
if otel_enabled:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry import context as otel_context
        from opentelemetry.sdk.trace import ReadableSpan
        
        # Custom span processor to propagate context attributes to all child spans
        class ContextAttributeSpanProcessor(SpanProcessor):
            """Propagates context values to span attributes for all instrumentation layers."""
            
            def on_start(self, span: "Span", parent_context=None):
                """Called when span starts - add context attributes."""
                ctx = parent_context or otel_context.get_current()
                
                # Propagate custom dimensions from context
                user_id = otel_context.get_value("user_id", ctx)
                if user_id:
                    span.set_attribute("user_id", user_id)
                
                is_vip = otel_context.get_value("is_vip", ctx)
                if is_vip is not None:
                    span.set_attribute("is_vip", is_vip)
                
                agent_type = otel_context.get_value("agent_type", ctx)
                if agent_type:
                    span.set_attribute("agent_type", agent_type)
                
                experiment = otel_context.get_value("experiment", ctx)
                if experiment:
                    span.set_attribute("experiment", experiment)
            
            def on_end(self, span: ReadableSpan):
                """Called when span ends."""
                pass
            
            def shutdown(self):
                """Called on shutdown."""
                pass
            
            def force_flush(self, timeout_millis: int = 30000):
                """Called on force flush."""
                pass
        
        service_name = os.getenv("OTEL_SERVICE_NAME", "chef-agent")
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        
        # Create resource with service name
        resource = Resource(attributes={
            SERVICE_NAME: service_name
        })
        
        # Configure tracer provider
        provider = TracerProvider(resource=resource)
        
        # Add custom span processor to propagate context attributes
        provider.add_span_processor(ContextAttributeSpanProcessor())
        
        # Add OTLP exporter with batch processor
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        
        # Set as global tracer provider
        trace.set_tracer_provider(provider)
        
        # Instrument OpenAI SDK BEFORE importing it
        # Choose between OpenInference and standard OTel via environment variable
        otel_provider = os.getenv("OTEL_INSTRUMENTATION_PROVIDER", "opentelemetry").lower()
        
        if otel_provider == "openinference":
            from openinference.instrumentation.openai import OpenAIInstrumentor
            OpenAIInstrumentor().instrument(tracer_provider=provider)
            print("[OK] OpenAI instrumented with OpenInference (Responses API streaming supported)")
        else:
            from opentelemetry.instrumentation.openai import OpenAIInstrumentor
            OpenAIInstrumentor().instrument(tracer_provider=provider)
            print("[OK] OpenAI instrumented with standard OpenTelemetry (GenAI conventions)")
        
        print(f"[INFO] OTEL_INSTRUMENTATION_PROVIDER={otel_provider}")
        print(f"[OK] OpenTelemetry initialized: service={service_name} endpoint={otlp_endpoint}")
    except Exception as e:
        print(f"[WARNING] OpenTelemetry initialization failed: {e}")
        otel_enabled = False
else:
    print("[INFO] OpenTelemetry disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")

# NOW import FastAPI and other libraries AFTER OpenTelemetry initialization
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from src.models import QueryRequest, QueryResponse, HealthResponse
from src.services import ConfigService, OpenAIService

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global services
config_service: ConfigService = None
openai_service: OpenAIService = None


# System prompt for Chef Agent (English)
SYSTEM_PROMPT = """You are a specialized culinary services backend agent for Dream Farm marketplace.

**YOUR ROLE:**
You are NOT directly serving end users. You are a backend specialist assisting the main DreamFarm Agent.
The DreamFarm Agent handles user interaction and delegates culinary-related queries to you for expert processing.

**YOUR RESPONSIBILITIES:**
Process culinary service requests and provide detailed, actionable information about:
- Private chefs for events and occasions
- Catering services for gatherings
- Meal preparation and delivery
- Chef consulting and menu planning

**YOUR TOOLS:**
You have access to specialized MCP tools for:
- Searching for chefs by specialty, cuisine type, and event requirements
- Searching for catering services by type, guest count, and preferences
- Checking availability of chefs and services for specific dates
- Calculating detailed pricing quotes based on requirements
- Placing orders for confirmed bookings

**GUIDELINES:**
1. Process each request independently (stateless operation)
2. Extract all relevant parameters from the delegated query (dates, guest count, preferences, etc.)
3. Use appropriate tools to fetch accurate, up-to-date information
4. If critical information is missing, specify what additional details are needed
5. Provide complete, structured responses with:
   - Chef/service options with full details
   - Availability status with specific dates
   - Detailed pricing breakdowns (base price, complexity multipliers, additional services)
   - Booking confirmation details when orders are placed
6. Be concise but comprehensive - the DreamFarm Agent will present your response to the user

**WORKFLOW PATTERNS:**
- Search queries: Use search tools and return all matching results with key details
- Availability checks: Check specific dates and return yes/no with details
- Pricing requests: Calculate quotes with full breakdown (base + complexity + extras)
- Booking requests: Validate all required fields (contact info, date, guest count) then place order

**OUTPUT FORMAT:**
Return information in natural language that the DreamFarm Agent can relay to the user.
Be direct and factual. Avoid conversational fluff - focus on delivering the requested culinary service information efficiently.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global config_service, openai_service

    # Startup
    logger.info("Starting Chef Agent...")
    try:
        # Load and validate configuration
        config_service = ConfigService()
        cfg = config_service.config
        
        # Apply log level from config
        logger.setLevel(getattr(logging, cfg.log_level.upper(), logging.INFO))
        
        logger.info(
            "Config loaded: environment=%s, openai.base_url=%s, openai.model=%s, mcp_url=%s",
            cfg.environment,
            cfg.openai.base_url,
            cfg.openai.model_name,
            cfg.chef_services_mcp.mcp_url,
        )
        
        # Initialize OpenAI service with MCP tools
        openai_service = OpenAIService(
            config=config_service.get_openai_config(),
            app_config=cfg,
        )
        
        logger.info("Chef Agent initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Chef Agent: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Chef Agent...")


# Create FastAPI application
app = FastAPI(
    title="Chef Agent",
    description="AI-powered culinary services assistant using remote Chef Services MCP",
    version="0.1.0",
    lifespan=lifespan
)

# Instrument FastAPI with OpenTelemetry (after app creation)
if otel_enabled:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        # Exclude health check endpoint from tracing (reduces noise)
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/health"
        )
        print("[OK] FastAPI instrumented with OpenTelemetry (excluding /health)")
    except Exception as e:
        print(f"[WARNING] FastAPI instrumentation failed: {e}")

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# OpenTelemetry business dimensions middleware
@app.middleware("http")
async def add_business_dimensions(request: Request, call_next):
    """Add business context attributes to OpenTelemetry spans and propagate via context."""
    if otel_enabled:
        from opentelemetry import trace as otel_trace
        from opentelemetry import context as otel_context
        
        span = otel_trace.get_current_span()
        if span and span.is_recording():
            # Set static agent_type dimension (chef for this service)
            span.set_attribute("agent_type", "chef")
            
            # Set experiment dimension
            experiment = os.getenv("OTEL_EXPERIMENT", "production")
            span.set_attribute("experiment", experiment)
            
            # Note: Chef Agent is typically called by DreamFarm Agent, so user context
            # may be propagated via trace context headers (W3C Trace Context)
            # We could extract user_id/is_vip from custom headers if DreamFarm sends them,
            # but for now we'll use defaults since this is a backend service
            user_id = "backend-service"
            is_vip = False
            
            span.set_attribute("user_id", user_id)
            span.set_attribute("is_vip", is_vip)
            
            # Propagate custom dimensions via OpenTelemetry context
            ctx = otel_context.get_current()
            ctx = otel_context.set_value("user_id", user_id, ctx)
            ctx = otel_context.set_value("is_vip", is_vip, ctx)
            ctx = otel_context.set_value("agent_type", "chef", ctx)
            ctx = otel_context.set_value("experiment", experiment, ctx)
            
            # Execute request with propagated context
            token_ctx = otel_context.attach(ctx)
            try:
                response = await call_next(request)
                return response
            finally:
                otel_context.detach(token_ctx)
        else:
            response = await call_next(request)
            return response
    else:
        response = await call_next(request)
        return response


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint.
    
    Returns:
        Health status
    """
    return HealthResponse(status="ok")


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Process a culinary services query.
    
    Stateless endpoint that processes each query independently using the
    Responses API with MCP tool integration.
    
    Args:
        request: Query request containing user's message
        
    Returns:
        Query response with agent's answer and response ID
        
    Raises:
        HTTPException: If query processing fails
    """
    try:
        logger.info("=" * 80)
        logger.info("🔵 CHEF AGENT: Received query from DreamFarm Agent")
        logger.info("Query (first 100 chars): %s", request.message[:100])
        logger.info("Query length: %d characters", len(request.message))
        
        # Generate response using OpenAI service with MCP tools
        response_text, response_id = await openai_service.generate_response(
            user_text=request.message,
            system_prompt=SYSTEM_PROMPT,
            previous_response_id=None,  # Stateless for simplicity
        )
        
        logger.info("✅ CHEF AGENT: Query processed successfully")
        logger.info("Response ID: %s", response_id)
        logger.info("Response length: %d characters", len(response_text))
        logger.info("Response preview (first 150 chars): %s", response_text[:150])
        logger.info("=" * 80)
        
        return QueryResponse(
            response=response_text,
            response_id=response_id,
        )
        
    except Exception as e:
        logger.error("❌ CHEF AGENT: Query processing failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")


def main():
    """Main entry point for the application."""
    import uvicorn
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

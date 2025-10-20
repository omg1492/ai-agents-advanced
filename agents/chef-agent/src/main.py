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

# Initialize OpenTelemetry BEFORE importing any LLM libraries or services
service_name = os.getenv("OTEL_SERVICE_NAME", "chef-agent")
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
otel_enabled = otlp_endpoint != ""

if otel_enabled:
    try:
        # 1. Configure tracing (TracerProvider + auto-instrumentation for OpenAI)
        from src.utils.otel_tracing import configure_otel_tracing
        configure_otel_tracing(
            service_name=service_name,
            otlp_endpoint=otlp_endpoint,
            instrument_openai=True,
            instrument_psycopg2=False,
            instrument_sqlalchemy=False
        )
        print(f"[OK] OpenTelemetry tracing initialized: service={service_name}")
        
        # 2. Configure logging (structured JSON logs with trace correlation)
        from src.utils.otel_logging import configure_otel_logging, add_trace_context_to_logs
        logger_otel = configure_otel_logging()  # Configures ROOT logger
        add_trace_context_to_logs()
        print("[OK] OpenTelemetry logging initialized (root logger with OTLP)")
        
        # 3. Configure metrics (application metrics + FastAPI instrumentation)
        from src.utils.otel_metrics import configure_otel_metrics, create_custom_metrics
        meter_provider, meter = configure_otel_metrics()
        metrics = create_custom_metrics(meter)
        print("[OK] OpenTelemetry metrics initialized")
        
    except Exception as e:
        print(f"[WARNING] OpenTelemetry initialization failed: {e}")
        otel_enabled = False
        logger_otel = None
        meter_provider = None
        meter = None
        metrics = None
else:
    print("[INFO] OpenTelemetry disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")
    logger_otel = None
    meter_provider = None
    meter = None
    metrics = None

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

# Instrument FastAPI with custom metrics
if metrics:
    try:
        from src.utils.otel_metrics import instrument_fastapi_metrics
        instrument_fastapi_metrics(app, meter)
        print("[OK] FastAPI instrumented with custom metrics")
    except Exception as e:
        print(f"[WARNING] FastAPI metrics instrumentation failed: {e}")

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
    
    # Get uvicorn logging config that uses OTLP-enabled root logger
    if otel_enabled:
        from src.utils.otel_logging import get_uvicorn_log_config
        log_config = get_uvicorn_log_config()
        uvicorn.run(app, host="0.0.0.0", port=port, log_config=log_config)
    else:
        uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

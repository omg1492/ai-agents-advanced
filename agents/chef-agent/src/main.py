"""Chef Agent - FastAPI application using Responses API.

Specialized culinary services agent that connects to the remote Chef Services
MCP server for handling queries about chefs, catering, availability, and pricing.
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from src.models import QueryRequest, QueryResponse, HealthResponse
from src.services import ConfigService, OpenAIService


# Load environment variables
load_dotenv()

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

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

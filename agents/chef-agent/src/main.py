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
SYSTEM_PROMPT = """You are a specialized culinary services assistant for Dream Farm marketplace.

Your role is to help users find and book professional culinary services including:
- Private chefs for events and occasions
- Catering services for gatherings
- Meal preparation and delivery
- Chef consulting and menu planning

You have access to tools that allow you to:
- Search for chefs by specialty, cuisine type, and event requirements
- Search for catering services by type, guest count, and preferences
- Check availability of chefs and services for specific dates
- Calculate detailed pricing quotes based on requirements
- Place orders for confirmed bookings

Guidelines:
1. Be professional, friendly, and detail-oriented
2. Ask clarifying questions to understand the user's needs (event type, guest count, date, preferences)
3. Use the search tools to find appropriate chefs or services
4. Always check availability before suggesting booking
5. Provide detailed pricing breakdowns when discussing costs
6. Confirm all details before placing an order
7. Explain menu complexity options (simple, moderate, complex) and additional services available

When users express interest in booking:
1. Gather requirements: date, guest count, cuisine preferences, event type
2. Search for suitable chefs/services
3. Check availability for the desired date
4. Calculate pricing with options
5. Confirm details and place order with complete contact information

Be proactive in using the available tools to provide accurate, up-to-date information about chefs and services.
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
        logger.info("Processing query: %s", request.message[:100])
        
        # Generate response using OpenAI service with MCP tools
        response_text, response_id = await openai_service.generate_response(
            user_text=request.message,
            system_prompt=SYSTEM_PROMPT,
            previous_response_id=None,  # Stateless for simplicity
        )
        
        logger.info(
            "Query processed successfully: response_id=%s text_length=%d",
            response_id,
            len(response_text),
        )
        
        return QueryResponse(
            response=response_text,
            response_id=response_id,
        )
        
    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")


def main():
    """Main entry point for the application."""
    import uvicorn
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

"""DreamFarm Agent - FastAPI application for Dream Farm marketplace AI assistant."""

import os
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from src.models.health import HealthResponse
from src.models.thread import (
    CreateThreadRequest, CreateThreadResponse,
    SendMessageRequest, SendMessageResponse,
    GetMessagesResponse
)
from src.services.openai_service import OpenAIService
from src.services.thread_service import ThreadService


# Load environment variables
load_dotenv()

# Configure logging level from environment (default to INFO)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global services
openai_service: OpenAIService = None
thread_service: ThreadService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global openai_service, thread_service
    
    # Startup
    logger.info("Starting DreamFarm Agent...")
    try:
        openai_service = OpenAIService()
        thread_service = ThreadService(openai_service)
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down DreamFarm Agent...")


# Create FastAPI application
app = FastAPI(
    title="DreamFarm Agent",
    description="AI-powered assistant for Dream Farm marketplace",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
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
        Health status and timestamp
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.post("/threads", response_model=CreateThreadResponse)
async def create_thread(request: CreateThreadRequest):
    """Create a new conversation thread.
    
    Args:
        request: Thread creation request with optional title
        
    Returns:
        Created thread details
    """
    try:
        return thread_service.create_thread(request.title)
    except Exception as e:
        logger.error(f"Failed to create thread: {e}")
        raise HTTPException(status_code=500, detail="Failed to create thread")


@app.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    """Get thread information by ID.
    
    Args:
        thread_id: ID of the thread to retrieve
        
    Returns:
        Thread information
        
    Raises:
        HTTPException: If thread not found
    """
    thread = thread_service.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@app.post("/threads/{thread_id}/messages", response_model=SendMessageResponse)
async def send_message(thread_id: str, request: SendMessageRequest):
    """Send a message in a conversation thread.
    
    Args:
        thread_id: ID of the thread
        request: Message content to send
        
    Returns:
        Response containing user message and AI response
        
    Raises:
        HTTPException: If thread not found or processing fails
    """
    try:
        return await thread_service.send_message(thread_id, request.message)
    except ValueError as e:
        logger.warning(f"Invalid request: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail="Failed to process message")


@app.get("/threads/{thread_id}/messages", response_model=GetMessagesResponse)
async def get_messages(thread_id: str, limit: int = 50, offset: int = 0):
    """Get conversation history for a thread.
    
    Args:
        thread_id: ID of the thread
        limit: Maximum number of messages to return (default: 50)
        offset: Number of messages to skip (default: 0)
        
    Returns:
        Messages and total count
        
    Raises:
        HTTPException: If thread not found
    """
    try:
        return thread_service.get_messages(thread_id, limit, offset)
    except ValueError as e:
        logger.warning(f"Invalid request: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve messages")


def main():
    """Main entry point for the application."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()

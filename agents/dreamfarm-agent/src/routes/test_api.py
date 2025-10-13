"""Simple test API endpoint for security testing with PyRIT.

This endpoint provides a non-streaming, authentication-optional interface
specifically designed for automated security testing tools like PyRIT.

Unlike the production /chat endpoint which uses:
- SSE streaming responses
- JWT authentication
- Thread/session management
- Complex response format

This endpoint provides:
- Simple request/response (no streaming)
- Optional API key authentication (X-Test-API-Key header)
- Stateless operation (no threads)
- Plain JSON response
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
import logging
import os

from src.services.openai_service import OpenAIService
from src.services.config_service import ConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test", tags=["testing"])


class TestChatRequest(BaseModel):
    """Simple test chat request."""
    message: str


class TestChatResponse(BaseModel):
    """Simple test chat response."""
    response: str


def verify_test_api_key(x_test_api_key: str = Header(None)):
    """Verify test API key if configured.
    
    If TEST_API_KEY is set in environment, requests must provide matching
    X-Test-API-Key header. If not set, all requests are allowed (dev mode).
    """
    required_key = os.getenv("TEST_API_KEY")
    
    # If no key configured, allow all requests (dev/testing mode)
    if not required_key:
        return True
    
    # If key configured but not provided or doesn't match, reject
    if not x_test_api_key or x_test_api_key != required_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-Test-API-Key header"
        )
    
    return True


@router.post("/chat", response_model=TestChatResponse)
async def test_chat(
    request: TestChatRequest,
    _: bool = Depends(verify_test_api_key)
):
    """Simple non-streaming chat endpoint for security testing.
    
    This endpoint:
    - Accepts a single message
    - Returns a simple text response (no streaming)
    - Does not maintain conversation history/threads
    - Uses minimal features (no tools, no memory, no RAG)
    - Optional API key authentication via X-Test-API-Key header
    
    This is intentionally simplified to make automated security testing
    (e.g., PyRIT, red teaming) straightforward without dealing with
    streaming, authentication, or state management complexity.
    
    Security note: This endpoint is designed to be tested with harmful
    prompts to validate safety guardrails. The simplified interface
    ensures test tools can properly validate refusal responses.
    """
    try:
        # Create OpenAI service with minimal config
        config_service = ConfigService()
        app_config = config_service.get_app_config()
        openai_service = OpenAIService(config=app_config.openai)
        
        # Get simple response (no tools, no memory, no streaming)
        response = await openai_service.chat(
            user_message=request.message,
            conversation_history=[],  # No history
            user_id=None,  # No user tracking
            thread_id=None,  # No thread management
            enable_tools=False,  # No tool calling
            model=app_config.openai.model,
        )
        
        # Extract just the text response
        response_text = response.get("response", "")
        
        logger.info(
            "Test API chat completed",
            extra={
                "prompt_length": len(request.message),
                "response_length": len(response_text),
            }
        )
        
        return TestChatResponse(response=response_text)
    
    except Exception as e:
        logger.error(f"Test API chat failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chat processing failed: {str(e)}"
        )


@router.get("/health")
async def test_health():
    """Health check for test API."""
    return {"status": "healthy", "endpoint": "test"}

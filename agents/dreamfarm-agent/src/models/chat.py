"""Chat models for simple conversation using Responses API.

Defines request/response models for the /chat endpoint.
"""
from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    """Request model for chat interaction.

    Attributes:
        message: The user's input message
        previous_response_id: Optional previous response ID to continue server-side state
    """
    message: str
    previous_response_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response model for chat interaction.

    Attributes:
        response_id: The ID of the response created by the API
        message: Assistant's generated message
        timestamp: ISO 8601 timestamp when the response was generated
    """
    response_id: str
    message: str
    timestamp: str

"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for chef query endpoint.
    
    Attributes:
        message: User's query about culinary services
    """
    message: str = Field(..., description="User's query message")


class QueryResponse(BaseModel):
    """Response model for chef query endpoint.
    
    Attributes:
        response: Agent's response text
        response_id: OpenAI response ID for state continuity
    """
    response: str = Field(..., description="Agent's response message")
    response_id: str = Field(..., description="OpenAI Responses API response ID")

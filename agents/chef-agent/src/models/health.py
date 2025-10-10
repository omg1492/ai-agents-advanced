"""Pydantic models for health check endpoint."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response model.
    
    Attributes:
        status: Health status indicator (always 'ok' when service is running)
    """
    status: str = Field(default="ok", description="Service health status")

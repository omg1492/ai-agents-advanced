"""Health check models."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response model.
    
    Attributes:
        status: Current health status of the service
        timestamp: ISO 8601 timestamp of the health check
    """
    status: str
    timestamp: str

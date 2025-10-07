"""File upload models for code interpreter file attachments."""

from pydantic import BaseModel, Field


class FileUploadResponse(BaseModel):
    """Response model for file upload endpoint.
    
    Contains the Azure OpenAI file ID that can be attached to messages
    for code interpreter processing.
    """
    file_id: str = Field(..., description="Azure OpenAI file ID")
    filename: str = Field(..., description="Original filename")
    size_bytes: int = Field(..., description="File size in bytes")
    purpose: str = Field(default="assistants", description="File purpose (assistants for code interpreter)")
    status: str = Field(default="uploaded", description="Upload status")


class FileUploadError(BaseModel):
    """Error response for file upload failures."""
    error: str = Field(..., description="Error message")
    detail: str | None = Field(None, description="Additional error details")

"""
Data models for complaint handling workflow.

Defines Pydantic models for complaint input, classification, decision outputs,
and workflow results. Structured outputs enforce deterministic schema validation.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TerminalStatus(str, Enum):
    """Terminal states for complaint workflow."""
    NEEDS_MORE_INFO = "NEEDS_MORE_INFO"  # Missing required fields
    COMPLETED = "COMPLETED"  # Resolved (valid/not_valid)
    PENDING_REVIEW = "PENDING_REVIEW"  # Escalated to human


class Action(str, Enum):
    """Decision actions from LLM analysis."""
    VALID = "VALID"
    NOT_VALID = "NOT_VALID"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class ComplaintIn(BaseModel):
    """
    Input complaint with simplified structure.
    
    Only contains the raw message text and user_id.
    Order details, product info, dates will be extracted from the message by LLM in later steps.
    """
    message: str = Field(description="The raw complaint/message text from the user")
    user_id: str = Field(description="User identifier")


class ComplaintClassification(BaseModel):
    """LLM classification result using structured output."""
    is_complaint: bool = Field(description="True if input is a complaint")
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence 0-1")


class ComplaintExtraction(BaseModel):
    """Extracted information from complaint message using structured output."""
    products_involved: Optional[list[str]] = Field(
        default=None,
        description="List of products mentioned in the complaint, None if not specified"
    )
    order_date: Optional[str] = Field(
        default=None,
        description="Order date mentioned in the complaint (YYYY-MM-DD format), None if not specified"
    )
    order_id: Optional[str] = Field(
        default=None,
        description="Order ID/number mentioned in the complaint, None if not specified"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Main reason/issue described in the complaint, None if unclear"
    )
    evidence_provided: Optional[str] = Field(
        default=None,
        description="Description of any evidence mentioned (photos, receipts, etc.), None if not mentioned"
    )


class OrderRecord(BaseModel):
    """Mock order data structure."""
    order_id: str
    user_id: str
    items: list[str]
    date: str
    amount: float = 0.0


class UserProfile(BaseModel):
    """Mock user profile data from user management system."""
    user_id: str = Field(description="User identifier")
    segment: str = Field(description="Customer segment: premium, regular, occasional")
    loyalty_level: str = Field(description="Loyalty tier: platinum, gold, silver, bronze")
    city: str = Field(description="User's city")
    country: str = Field(description="User's country")
    user_score: float = Field(
        ge=0.0, le=100.0,
        description="Internal user quality score (0-100). High score = good customer (many orders, pays on time, positive reviews). Low score = problematic (frequent complaints, late payments, bad reviews)"
    )
    total_orders: int = Field(ge=0, description="Total number of orders placed")
    complaint_count: int = Field(ge=0, description="Number of complaints filed")


class DecisionOutput(BaseModel):
    """LLM decision on complaint validity."""
    action: Action = Field(description="Action: VALID, NOT_VALID, or HUMAN_REVIEW")
    reason: str = Field(description="Explanation for decision")


class UserMessage(BaseModel):
    """Generated user-facing message."""
    text: str = Field(description="Message content")
    tone: str = Field(default="professional", description="Message tone")


class ReviewPacket(BaseModel):
    """Human review packet for escalated complaints."""
    summary: str = Field(description="Brief case summary")
    details: dict = Field(default_factory=dict, description="Full context")


class WorkflowResult(BaseModel):
    """Final workflow output."""
    complaint_id: str
    terminal_status: TerminalStatus
    action: Optional[Action] = None
    reason: Optional[str] = None
    user_message: Optional[str] = None
    review_packet_id: Optional[str] = None

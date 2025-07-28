"""Thread and message models for conversation management."""

from typing import List, Literal, Optional
from pydantic import BaseModel


class Thread(BaseModel):
    """Thread model representing a conversation.
    
    Attributes:
        thread_id: Unique identifier for the thread
        title: Optional title for the thread
        created_at: ISO 8601 timestamp when thread was created
        updated_at: ISO 8601 timestamp when thread was last updated
        message_count: Number of messages in the thread
    """
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class CreateThreadRequest(BaseModel):
    """Request model for creating a new thread.
    
    Attributes:
        title: Optional title for the thread
    """
    title: Optional[str] = None


class CreateThreadResponse(BaseModel):
    """Response model for thread creation.
    
    Attributes:
        thread_id: Unique identifier for the created thread
        title: Title of the created thread
        created_at: ISO 8601 timestamp when thread was created
        updated_at: ISO 8601 timestamp when thread was last updated
    """
    thread_id: str
    title: str
    created_at: str
    updated_at: str


class Message(BaseModel):
    """Message model representing a single message in a conversation.
    
    Attributes:
        message_id: Unique identifier for the message
        thread_id: ID of the thread this message belongs to
        role: Role of the message sender (user or assistant)
        content: Content of the message
        timestamp: ISO 8601 timestamp when message was created
    """
    message_id: str
    thread_id: str
    role: Literal["user", "assistant"]
    content: str
    timestamp: str


class SendMessageRequest(BaseModel):
    """Request model for sending a message.
    
    Attributes:
        message: Content of the message to send
    """
    message: str


class SendMessageResponse(BaseModel):
    """Response model for sending a message.
    
    Attributes:
        message_id: Unique identifier for the user message
        thread_id: ID of the thread
        user_message: Content of the user's message
        assistant_response: Content of the assistant's response
        timestamp: ISO 8601 timestamp when the interaction occurred
    """
    message_id: str
    thread_id: str
    user_message: str
    assistant_response: str
    timestamp: str


class GetMessagesResponse(BaseModel):
    """Response model for retrieving messages.
    
    Attributes:
        thread_id: ID of the thread
        messages: List of messages in the thread
        total_count: Total number of messages in the thread
    """
    thread_id: str
    messages: List[Message]
    total_count: int

"""Thread service for managing conversation threads and messages."""

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.models.thread import Thread, Message, CreateThreadResponse, SendMessageResponse, GetMessagesResponse
from src.services.openai_service import OpenAIService


logger = logging.getLogger(__name__)


class ThreadService:
    """Service for managing conversation threads and messages.
    
    Provides in-memory storage for Lesson 1. Future lessons will replace
    with database persistence.
    """
    
    def __init__(self, openai_service: OpenAIService):
        """Initialize the thread service.
        
        Args:
            openai_service: OpenAI service instance for generating responses
        """
        self.openai_service = openai_service
        self.threads: Dict[str, Thread] = {}
        self.messages: Dict[str, List[Message]] = {}
        logger.info("Initialized ThreadService with in-memory storage")
    
    def create_thread(self, title: Optional[str] = None) -> CreateThreadResponse:
        """Create a new conversation thread.
        
        Args:
            title: Optional title for the thread
            
        Returns:
            Response containing thread details
        """
        thread_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()
        
        if not title:
            title = f"Dream Farm Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        thread = Thread(
            thread_id=thread_id,
            title=title,
            created_at=current_time,
            updated_at=current_time,
            message_count=0
        )
        
        self.threads[thread_id] = thread
        self.messages[thread_id] = []
        
        logger.info(f"Created thread {thread_id} with title: {title}")
        
        return CreateThreadResponse(
            thread_id=thread_id,
            title=title,
            created_at=current_time,
            updated_at=current_time
        )
    
    def get_thread(self, thread_id: str) -> Optional[Thread]:
        """Get thread information by ID.
        
        Args:
            thread_id: ID of the thread to retrieve
            
        Returns:
            Thread object if found, None otherwise
        """
        return self.threads.get(thread_id)
    
    async def send_message(self, thread_id: str, user_message: str) -> SendMessageResponse:
        """Send a message in a thread and generate AI response.
        
        Args:
            thread_id: ID of the thread
            user_message: Content of the user's message
            
        Returns:
            Response containing both user message and AI response
            
        Raises:
            ValueError: If thread doesn't exist
        """
        thread = self.threads.get(thread_id)
        if not thread:
            raise ValueError(f"Thread {thread_id} not found")
        
        current_time = datetime.now(timezone.utc).isoformat()
        message_id = str(uuid.uuid4())
        
        # Add user message to conversation history
        user_msg = Message(
            message_id=message_id,
            thread_id=thread_id,
            role="user",
            content=user_message,
            timestamp=current_time
        )
        
        # Prepare conversation history for AI
        thread_messages = self.messages[thread_id]
        conversation_messages = [
            {"role": msg.role, "content": msg.content} 
            for msg in thread_messages
        ]
        conversation_messages.append({"role": "user", "content": user_message})
        
        # Generate AI response with Dream Farm context
        system_prompt = """You are a helpful AI assistant for Dream Farm, a virtual farmers' marketplace that connects local farmers with customers. 

Your role is to help customers:
- Find fresh, local produce and farm products
- Learn about seasonal availability
- Connect with local farmers
- Understand sustainable farming practices
- Get cooking suggestions for farm-fresh ingredients

Be friendly, knowledgeable about farming and fresh produce, and always focus on connecting people with local, sustainable food sources. If asked about topics unrelated to farming, food, or the marketplace, politely redirect the conversation back to how you can help with farm-related needs."""
        
        try:
            assistant_response = await self.openai_service.generate_response(
                messages=conversation_messages,
                system_prompt=system_prompt
            )
        except Exception as e:
            logger.error(f"Failed to generate AI response: {e}")
            assistant_response = "I apologize, but I'm having trouble connecting to our AI service right now. Please try again in a moment."
        
        # Add assistant response to conversation history
        assistant_msg = Message(
            message_id=str(uuid.uuid4()),
            thread_id=thread_id,
            role="assistant",
            content=assistant_response,
            timestamp=current_time
        )
        
        # Store both messages
        self.messages[thread_id].extend([user_msg, assistant_msg])
        
        # Update thread
        thread.message_count = len(self.messages[thread_id])
        thread.updated_at = current_time
        
        logger.info(f"Processed message in thread {thread_id}, total messages: {thread.message_count}")
        
        return SendMessageResponse(
            message_id=message_id,
            thread_id=thread_id,
            user_message=user_message,
            assistant_response=assistant_response,
            timestamp=current_time
        )
    
    def get_messages(self, thread_id: str, limit: int = 50, offset: int = 0) -> GetMessagesResponse:
        """Get messages from a thread with pagination.
        
        Args:
            thread_id: ID of the thread
            limit: Maximum number of messages to return
            offset: Number of messages to skip
            
        Returns:
            Response containing messages and total count
            
        Raises:
            ValueError: If thread doesn't exist
        """
        if thread_id not in self.threads:
            raise ValueError(f"Thread {thread_id} not found")
        
        thread_messages = self.messages[thread_id]
        total_count = len(thread_messages)
        
        # Apply pagination
        paginated_messages = thread_messages[offset:offset + limit]
        
        return GetMessagesResponse(
            thread_id=thread_id,
            messages=paginated_messages,
            total_count=total_count
        )

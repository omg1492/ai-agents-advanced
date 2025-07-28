"""Unit tests for DreamFarm Agent ThreadService."""

import pytest
from unittest.mock import Mock, AsyncMock

from src.services.thread_service import ThreadService
from src.services.openai_service import OpenAIService


@pytest.mark.unit
class TestThreadService:
    """Test cases for ThreadService functionality."""
    
    @pytest.fixture
    def mock_openai_service(self):
        """Create a mock OpenAI service."""
        service = Mock(spec=OpenAIService)
        service.generate_response = AsyncMock(return_value="Hello! I'm here to help you with Dream Farm marketplace.")
        return service
    
    @pytest.fixture
    def thread_service(self, mock_openai_service):
        """Create a ThreadService instance with mocked dependencies."""
        return ThreadService(mock_openai_service)
    
    def test_create_thread(self, thread_service):
        """Test thread creation."""
        response = thread_service.create_thread("Test Thread")
        
        assert response.title == "Test Thread"
        assert response.thread_id is not None
        assert len(response.thread_id) > 0
        assert response.created_at is not None
        assert response.updated_at is not None
    
    def test_create_thread_default_title(self, thread_service):
        """Test thread creation with default title."""
        response = thread_service.create_thread()
        
        assert "Dream Farm Chat" in response.title
        assert response.thread_id is not None
    
    def test_get_thread(self, thread_service):
        """Test thread retrieval."""
        # Create a thread first
        create_response = thread_service.create_thread("Test Thread")
        thread_id = create_response.thread_id
        
        # Retrieve the thread
        thread = thread_service.get_thread(thread_id)
        
        assert thread is not None
        assert thread.thread_id == thread_id
        assert thread.title == "Test Thread"
        assert thread.message_count == 0
    
    def test_get_nonexistent_thread(self, thread_service):
        """Test retrieving a non-existent thread."""
        thread = thread_service.get_thread("nonexistent-id")
        assert thread is None
    
    @pytest.mark.asyncio
    async def test_send_message(self, thread_service, mock_openai_service):
        """Test sending a message."""
        # Create a thread first
        create_response = thread_service.create_thread("Test Thread")
        thread_id = create_response.thread_id
        
        # Send a message
        response = await thread_service.send_message(thread_id, "Hello, can you help me find fresh vegetables?")
        
        assert response.thread_id == thread_id
        assert response.user_message == "Hello, can you help me find fresh vegetables?"
        assert response.assistant_response == "Hello! I'm here to help you with Dream Farm marketplace."
        assert response.message_id is not None
        assert response.timestamp is not None
        
        # Verify OpenAI service was called
        mock_openai_service.generate_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message_to_nonexistent_thread(self, thread_service):
        """Test sending a message to a non-existent thread."""
        with pytest.raises(ValueError, match="Thread .* not found"):
            await thread_service.send_message("nonexistent-id", "Hello")
    
    def test_get_messages(self, thread_service):
        """Test retrieving messages."""
        # Create a thread first
        create_response = thread_service.create_thread("Test Thread")
        thread_id = create_response.thread_id
        
        # Initially should have no messages
        response = thread_service.get_messages(thread_id)
        
        assert response.thread_id == thread_id
        assert len(response.messages) == 0
        assert response.total_count == 0
    
    def test_get_messages_from_nonexistent_thread(self, thread_service):
        """Test retrieving messages from a non-existent thread."""
        with pytest.raises(ValueError, match="Thread .* not found"):
            thread_service.get_messages("nonexistent-id")

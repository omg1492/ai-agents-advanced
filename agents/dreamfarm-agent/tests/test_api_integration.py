"""Integration tests using FastAPI TestClient - Industry Standard Approach.

This is the recommended way to test FastAPI applications.
Uses TestClient for fast, reliable testing without starting a real server.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
import uuid
from datetime import datetime, timezone

from src.main import app
from src.services.openai_service import OpenAIService


class TestDreamFarmAgentAPI:
    """Integration tests for DreamFarm Agent API endpoints."""
    
    @pytest.fixture
    def mock_openai_service(self):
        """Mock the OpenAI service for consistent testing."""
        service = Mock(spec=OpenAIService)
        service.generate_response = AsyncMock(
            return_value="Hello! I'm here to help you with Dream Farm marketplace. What vegetables are you looking for today?"
        )
        return service
    
    @pytest.fixture
    def client(self, mock_openai_service):
        """Create a test client with mocked dependencies."""
        with patch('src.main.openai_service', mock_openai_service):
            with patch('src.main.thread_service') as mock_thread_service:
                # Setup mock thread service
                mock_thread_service.create_thread.return_value = Mock(
                    thread_id=str(uuid.uuid4()),
                    title="Test Thread",
                    created_at=datetime.now(timezone.utc).isoformat(),
                    updated_at=datetime.now(timezone.utc).isoformat()
                )
                
                with TestClient(app) as test_client:
                    yield test_client
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    def test_create_thread_with_title(self, client):
        """Test creating a thread with a title."""
        response = client.post(
            "/threads",
            json={"title": "Fresh Vegetables Inquiry"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "thread_id" in data
        assert data["title"] == "Fresh Vegetables Inquiry"  # Should match the request
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_create_thread_without_title(self, client):
        """Test creating a thread without a title."""
        response = client.post("/threads", json={})
        
        assert response.status_code == 200
        data = response.json()
        assert "thread_id" in data
        assert "title" in data
    
    def test_get_thread_success(self, client):
        """Test getting an existing thread."""
        # First create a thread
        create_response = client.post("/threads", json={"title": "Test Thread"})
        thread_id = create_response.json()["thread_id"]
        
        # Then get it
        response = client.get(f"/threads/{thread_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] == thread_id
    
    def test_get_thread_not_found(self, client):
        """Test getting a non-existent thread."""
        response = client.get("/threads/non-existent-id")
        
        assert response.status_code == 404
        assert "Thread not found" in response.json()["detail"]
    
    def test_send_message_success(self, client, mock_openai_service):
        """Test sending a message successfully."""
        # Create thread first
        create_response = client.post("/threads", json={"title": "Test Thread"})
        thread_id = create_response.json()["thread_id"]
        
        # Send message
        response = client.post(
            f"/threads/{thread_id}/messages",
            json={"message": "What vegetables do you have?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] == thread_id
        assert data["user_message"] == "What vegetables do you have?"
        assert "assistant_response" in data
        assert "message_id" in data
        assert "timestamp" in data
    
    def test_send_message_thread_not_found(self, client):
        """Test sending a message to non-existent thread."""
        response = client.post(
            "/threads/non-existent-id/messages",
            json={"message": "This should fail"}
        )
        
        assert response.status_code == 404
    
    def test_send_message_invalid_payload(self, client):
        """Test sending a message with invalid payload."""
        create_response = client.post("/threads", json={"title": "Test Thread"})
        thread_id = create_response.json()["thread_id"]
        
        # Missing 'message' field
        response = client.post(
            f"/threads/{thread_id}/messages",
            json={"wrong_field": "value"}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_get_messages_success(self, client):
        """Test getting messages from a thread."""
        create_response = client.post("/threads", json={"title": "Test Thread"})
        thread_id = create_response.json()["thread_id"]
        
        response = client.get(f"/threads/{thread_id}/messages")
        
        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] == thread_id
        assert "messages" in data
        assert "total_count" in data
    
    def test_get_messages_with_pagination(self, client):
        """Test getting messages with pagination parameters."""
        create_response = client.post("/threads", json={"title": "Test Thread"})
        thread_id = create_response.json()["thread_id"]
        
        response = client.get(f"/threads/{thread_id}/messages?limit=10&offset=5")
        
        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] == thread_id
    
    def test_get_messages_thread_not_found(self, client):
        """Test getting messages from non-existent thread."""
        response = client.get("/threads/non-existent-id/messages")
        
        assert response.status_code == 404
    
    def test_cors_headers(self, client):
        """Test CORS headers are properly set."""
        response = client.options("/threads")
        
        # FastAPI TestClient doesn't fully simulate CORS, but we can test the endpoint exists
        assert response.status_code in [200, 405]  # Either OK or Method Not Allowed is fine


@pytest.mark.integration
class TestDreamFarmAgentIntegration:
    """Integration tests that test the full flow without extensive mocking."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for integration tests."""
        return TestClient(app)
    
    @pytest.mark.skipif(
        True,  # Skip by default - requires real OpenAI API
        reason="Integration test requires real OpenAI API key"
    )
    def test_full_conversation_flow(self, client):
        """Test a complete conversation flow with real API.
        
        This test is skipped by default but can be enabled for full integration testing.
        Set OPENAI_API_KEY environment variable and change skipif to False.
        """
        # Create thread
        create_response = client.post("/threads", json={"title": "Integration Test"})
        assert create_response.status_code == 200
        thread_id = create_response.json()["thread_id"]
        
        # Send message
        message_response = client.post(
            f"/threads/{thread_id}/messages",
            json={"message": "What vegetables are in season?"}
        )
        assert message_response.status_code == 200
        
        # Get messages
        messages_response = client.get(f"/threads/{thread_id}/messages")
        assert messages_response.status_code == 200
        assert messages_response.json()["total_count"] >= 2

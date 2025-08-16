"""Unit-level API tests for the /chat flow using FastAPI TestClient with mocks.

These are fast and isolated; they patch OpenAIService so no external calls are made.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

from src.main import app
from src.services.openai_service import OpenAIService


pytestmark = pytest.mark.unit


class TestDreamFarmAgentAPI:
    """Integration tests for DreamFarm Agent API endpoints."""

    @pytest.fixture
    def mock_openai_service(self):
        """Mock the OpenAI service for consistent testing."""
        service = Mock(spec=OpenAIService)
        # Return tuple (text, response_id)
        service.generate_response = AsyncMock(return_value=(
            "Hello! I'm DreamFarm. How can I help you today?",
            "resp_123",
        ))
        return service

    @pytest.fixture
    def client(self, mock_openai_service):
        """Create a test client with mocked dependencies."""
        # Patch the OpenAIService constructor used in app startup to return our mock
        with patch('src.main.OpenAIService', return_value=mock_openai_service):
            with TestClient(app) as test_client:
                yield test_client

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_chat_basic(self, client):
        """Test basic /chat request-response."""
        response = client.post("/chat", json={"message": "Hi"})
        assert response.status_code == 200
        data = response.json()
        assert data["message"].startswith("Hello!")
        assert data["response_id"]
        assert "timestamp" in data

    def test_chat_with_previous_response_id(self, client):
        """Test /chat with server-side state continuation."""
        response = client.post("/chat", json={"message": "Continue", "previous_response_id": "resp_123"})
        assert response.status_code == 200
        data = response.json()
        assert data["response_id"] == "resp_123"

    def test_chat_invalid_payload(self, client):
        """Test /chat validation errors."""
        response = client.post("/chat", json={"wrong": "field"})
        assert response.status_code == 422

    def test_cors_preflight(self, client):
        """Test CORS preflight basic behavior."""
        response = client.options("/chat")
        assert response.status_code in [200, 405]

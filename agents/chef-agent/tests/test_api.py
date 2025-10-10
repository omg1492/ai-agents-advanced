"""Unit tests for FastAPI endpoints.

Tests health check and query endpoints with mocked services.
"""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from src.main import app


@pytest.fixture
async def client():
    """Fixture providing async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestHealthEndpoint:
    """Test suite for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Test health check returns OK status."""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestQueryEndpoint:
    """Test suite for /query endpoint."""

    @pytest.mark.asyncio
    async def test_query_success(self):
        """Test successful query processing."""
        # Mock the global openai_service
        with patch("src.main.openai_service") as mock_service:
            mock_service.generate_response = AsyncMock(
                return_value=("I found 3 Italian chefs available.", "resp_test123")
            )
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/query",
                    json={"message": "Find me an Italian chef"}
                )
            
            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "I found 3 Italian chefs available."
            assert data["response_id"] == "resp_test123"
            
            # Verify service was called correctly
            mock_service.generate_response.assert_called_once()
            call_args = mock_service.generate_response.call_args
            assert call_args.kwargs["user_text"] == "Find me an Italian chef"
            assert "culinary services assistant" in call_args.kwargs["system_prompt"]

    @pytest.mark.asyncio
    async def test_query_empty_message(self):
        """Test query with empty message."""
        with patch("src.main.openai_service") as mock_service:
            mock_service.generate_response = AsyncMock(
                return_value=("Please provide more details about what you're looking for.", "resp_empty")
            )
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/query",
                    json={"message": ""}
                )
            
            # Empty message should be accepted and processed
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_query_missing_message(self):
        """Test query without message field."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/query",
                json={}
            )
        
        # Should return validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_query_invalid_json(self):
        """Test query with invalid JSON."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/query",
                content="not valid json",
                headers={"Content-Type": "application/json"}
            )
        
        # Should return validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_query_service_error(self):
        """Test query handling when service raises exception."""
        with patch("src.main.openai_service") as mock_service:
            mock_service.generate_response = AsyncMock(
                side_effect=Exception("API connection failed")
            )
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/query",
                    json={"message": "Test query"}
                )
            
            # Should return 500 error
            assert response.status_code == 500
            data = response.json()
            assert "Failed to process query" in data["detail"]

    @pytest.mark.asyncio
    async def test_query_long_message(self):
        """Test query with very long message."""
        with patch("src.main.openai_service") as mock_service:
            mock_service.generate_response = AsyncMock(
                return_value=("Response to long query", "resp_long")
            )
            
            long_message = "x" * 10000  # 10k character message
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/query",
                    json={"message": long_message}
                )
            
            # Should process successfully
            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "Response to long query"

    @pytest.mark.asyncio
    async def test_query_special_characters(self):
        """Test query with special characters and unicode."""
        with patch("src.main.openai_service") as mock_service:
            mock_service.generate_response = AsyncMock(
                return_value=("Handled special characters", "resp_special")
            )
            
            special_message = "Find chef with 🍕 pizza & pasta expertise (rating: 4.5★)"
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/query",
                    json={"message": special_message}
                )
            
            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "Handled special characters"


class TestCORS:
    """Test CORS configuration."""

    @pytest.mark.asyncio
    async def test_cors_headers_present(self):
        """Test that CORS headers are properly set."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.options(
                "/query",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "POST",
                }
            )
        
        # Should include CORS headers
        assert "access-control-allow-origin" in response.headers

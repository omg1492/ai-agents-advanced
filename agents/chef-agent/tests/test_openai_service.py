"""Unit tests for OpenAIService.

Tests OpenAI service initialization, tool registration, and response generation
with mocked dependencies.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.config_service import OpenAIConfig, AppConfig, ChefServicesMCPConfig
from src.services.openai_service import OpenAIService


@pytest.fixture
def openai_config():
    """Fixture providing OpenAI configuration."""
    return OpenAIConfig(
        api_key="test-api-key",
        model_name="gpt-5",
        base_url="https://test.openai.azure.com/openai/v1/",
        api_version="preview",
    )


@pytest.fixture
def app_config():
    """Fixture providing application configuration."""
    return AppConfig(
        environment="test",
        log_level="INFO",
        cors_origins=["*"],
        port=8002,
        openai=OpenAIConfig(
            api_key="test-key",
            model_name="gpt-5",
        ),
        chef_services_mcp=ChefServicesMCPConfig(
            mcp_url="https://test-mcp.example.com/mcp",
            mcp_api_key="test-mcp-key",
        ),
        reasoning_effort="low",
    )


class TestOpenAIService:
    """Test suite for OpenAIService."""

    def test_init_success(self, openai_config, app_config):
        """Test successful service initialization."""
        with patch("src.services.openai_service.AsyncOpenAI") as mock_openai:
            service = OpenAIService(config=openai_config, app_config=app_config)
            
            assert service.model_name == "gpt-5"
            assert service._config == openai_config
            assert service._app_config == app_config
            
            # Verify AsyncOpenAI was called with correct params
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args.kwargs
            assert call_kwargs["api_key"] == "test-api-key"
            assert call_kwargs["base_url"] == "https://test.openai.azure.com/openai/v1/"

    def test_get_tools_returns_mcp_config(self, openai_config, app_config):
        """Test that get_tools returns MCP server configuration."""
        with patch("src.services.openai_service.AsyncOpenAI"):
            service = OpenAIService(config=openai_config, app_config=app_config)
            tools = service.get_tools()
            
            assert len(tools) == 1
            assert tools[0]["type"] == "mcp"
            assert tools[0]["server_label"] == "chef_services"
            assert tools[0]["server_url"] == "https://test-mcp.example.com/mcp"
            assert tools[0]["require_approval"] == "never"
            assert tools[0]["headers"]["Authorization"] == "Bearer test-mcp-key"

    @pytest.mark.asyncio
    async def test_generate_response_success(self, openai_config, app_config):
        """Test successful response generation with mocked API call."""
        with patch("src.services.openai_service.AsyncOpenAI") as mock_openai_class:
            # Mock the client and response
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            
            # Mock the response object
            mock_response = MagicMock()
            mock_response.id = "resp_test123"
            
            # Mock output items with message content
            mock_content = MagicMock()
            mock_content.text = "I found 3 Italian chefs available for your event."
            
            mock_message = MagicMock()
            mock_message.type = "message"
            mock_message.content = [mock_content]
            
            mock_response.output = [mock_message]
            
            # Mock the responses.create method
            mock_client.responses.create = AsyncMock(return_value=mock_response)
            
            # Create service and generate response
            service = OpenAIService(config=openai_config, app_config=app_config)
            text, response_id = await service.generate_response(
                user_text="Find me an Italian chef",
                system_prompt="You are a chef assistant",
                previous_response_id=None,
            )
            
            # Verify results
            assert text == "I found 3 Italian chefs available for your event."
            assert response_id == "resp_test123"
            
            # Verify API was called with correct parameters
            mock_client.responses.create.assert_called_once()
            call_kwargs = mock_client.responses.create.call_args.kwargs
            
            assert call_kwargs["model"] == "gpt-5"
            assert call_kwargs["instructions"] == "You are a chef assistant"
            assert call_kwargs["input"][0]["content"] == "Find me an Italian chef"
            assert call_kwargs["store"] is True
            assert len(call_kwargs["tools"]) == 1
            assert call_kwargs["tools"][0]["type"] == "mcp"
            assert call_kwargs["reasoning"]["effort"] == "low"

    @pytest.mark.asyncio
    async def test_generate_response_with_previous_id(self, openai_config, app_config):
        """Test response generation with previous_response_id for continuity."""
        with patch("src.services.openai_service.AsyncOpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            
            # Mock response
            mock_response = MagicMock()
            mock_response.id = "resp_test456"
            
            mock_content = MagicMock()
            mock_content.text = "Based on your previous request..."
            
            mock_message = MagicMock()
            mock_message.type = "message"
            mock_message.content = [mock_content]
            
            mock_response.output = [mock_message]
            
            mock_client.responses.create = AsyncMock(return_value=mock_response)
            
            # Create service and generate response with previous_response_id
            service = OpenAIService(config=openai_config, app_config=app_config)
            text, response_id = await service.generate_response(
                user_text="What about availability?",
                system_prompt="You are a chef assistant",
                previous_response_id="resp_test123",
            )
            
            # Verify previous_response_id was passed
            call_kwargs = mock_client.responses.create.call_args.kwargs
            assert call_kwargs["previous_response_id"] == "resp_test123"
            assert text == "Based on your previous request..."
            assert response_id == "resp_test456"

    @pytest.mark.asyncio
    async def test_generate_response_empty_output(self, openai_config, app_config):
        """Test handling of response with empty output."""
        with patch("src.services.openai_service.AsyncOpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            
            # Mock response with empty output
            mock_response = MagicMock()
            mock_response.id = "resp_empty"
            mock_response.output = []
            
            mock_client.responses.create = AsyncMock(return_value=mock_response)
            
            service = OpenAIService(config=openai_config, app_config=app_config)
            text, response_id = await service.generate_response(
                user_text="Test query",
                system_prompt="Test prompt",
            )
            
            # Empty output should return empty string
            assert text == ""
            assert response_id == "resp_empty"

    @pytest.mark.asyncio
    async def test_generate_response_multiple_content_blocks(self, openai_config, app_config):
        """Test response with multiple text content blocks."""
        with patch("src.services.openai_service.AsyncOpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            
            # Mock response with multiple content blocks
            mock_response = MagicMock()
            mock_response.id = "resp_multi"
            
            mock_content1 = MagicMock()
            mock_content1.text = "First part. "
            
            mock_content2 = MagicMock()
            mock_content2.text = "Second part."
            
            mock_message = MagicMock()
            mock_message.type = "message"
            mock_message.content = [mock_content1, mock_content2]
            
            mock_response.output = [mock_message]
            
            mock_client.responses.create = AsyncMock(return_value=mock_response)
            
            service = OpenAIService(config=openai_config, app_config=app_config)
            text, response_id = await service.generate_response(
                user_text="Test",
                system_prompt="Test",
            )
            
            # Should concatenate all text blocks
            assert text == "First part. Second part."
            assert response_id == "resp_multi"

"""Unit tests for VoiceService.

Tests voice tool filtering, configuration, and client initialization.
VoiceService creates its own realtime client (Azure or OpenAI) with preview API version.
"""
import pytest
import os
from src.services.voice_service import VoiceService
from src.services.config_service import AppConfig, OpenAIConfig
from unittest.mock import Mock, patch


pytestmark = pytest.mark.unit  # Mark all tests in this file as unit tests


@pytest.fixture
def mock_config():
    """Create a mock AppConfig with OpenAI configuration."""
    config = Mock(spec=AppConfig)
    config.openai = Mock(spec=OpenAIConfig)
    config.openai.api_key = "test-api-key"
    config.openai.base_url = None
    config.openai.model_name = "gpt-5"  # Text chat model (not used for voice)
    return config


@patch('openai.AsyncAzureOpenAI')
def test_voice_service_initialization_azure(mock_async_azure, mock_config):
    """VoiceService should build AsyncAzureOpenAI with 2025-04-01-preview api version."""
    mock_config.openai.base_url = "https://test.openai.azure.com/openai/v1/"

    service = VoiceService(config=mock_config)

    mock_async_azure.assert_called_once_with(
        api_key="test-api-key",
        azure_endpoint="https://test.openai.azure.com",
        api_version="2025-04-01-preview",
    )
    assert service.model_name == "gpt-realtime"


@patch('src.services.voice_service.AsyncOpenAI')
def test_voice_service_initialization_openai(mock_async_openai, mock_config):
    """Test VoiceService for OpenAI (no base_url)."""
    service = VoiceService(config=mock_config)
    
    # For OpenAI, no default_query needed
    mock_async_openai.assert_called_once_with(api_key="test-api-key")
    assert service.model_name == "gpt-realtime"


@patch('src.services.voice_service.AsyncOpenAI')
@patch.dict(os.environ, {'VOICE_MODEL': 'custom-realtime-deployment'})
def test_voice_service_uses_voice_model_env(mock_async_openai, mock_config):
    """Test VoiceService uses VOICE_MODEL env var if set."""
    service = VoiceService(config=mock_config)
    
    # Should use VOICE_MODEL from environment
    assert service.model_name == "custom-realtime-deployment"


@patch('src.services.voice_service.AsyncOpenAI')
def test_get_voice_tools_default_no_memory(mock_async_openai, mock_config):
    """Test tool filtering with no memory search available."""
    service = VoiceService(
        config=mock_config,
        memory_search_service=None
    )
    
    tools = service.get_voice_tools(enable_heavy_tools=False)
    assert tools == []


@patch('src.services.voice_service.AsyncOpenAI')
def test_get_voice_tools_with_memory_search(mock_async_openai, mock_config):
    """Test tool filtering includes memory_search when available."""
    mock_memory = Mock()
    mock_memory.enabled = True
    
    service = VoiceService(
        config=mock_config,
        memory_search_service=mock_memory
    )
    
    tools = service.get_voice_tools(enable_heavy_tools=False)
    assert len(tools) == 1
    assert tools[0]["name"] == "memory_search"
    assert tools[0]["type"] == "function"


@patch('src.services.voice_service.AsyncOpenAI')
def test_get_voice_tools_memory_disabled(mock_async_openai, mock_config):
    """Test tool filtering excludes memory_search when disabled."""
    mock_memory = Mock()
    mock_memory.enabled = False
    
    service = VoiceService(
        config=mock_config,
        memory_search_service=mock_memory
    )
    
    tools = service.get_voice_tools(enable_heavy_tools=False)
    assert tools == []


@patch('src.services.voice_service.AsyncOpenAI')
def test_get_voice_tools_heavy_enabled(mock_async_openai, mock_config):
    """Test that enable_heavy_tools flag is respected (currently no-op)."""
    mock_memory = Mock()
    mock_memory.enabled = True
    
    service = VoiceService(
        config=mock_config,
        memory_search_service=mock_memory
    )
    
    # Heavy tools currently doesn't add anything (reserved for future)
    tools_default = service.get_voice_tools(enable_heavy_tools=False)
    tools_heavy = service.get_voice_tools(enable_heavy_tools=True)
    
    # Should be same length (no heavy tools implemented yet)
    assert len(tools_default) == len(tools_heavy)
    assert len(tools_heavy) == 1  # Just memory_search

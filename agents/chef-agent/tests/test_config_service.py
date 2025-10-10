"""Unit tests for ConfigService.

Tests configuration loading, validation, and error handling.
"""

import pytest
import os
from unittest.mock import patch, MagicMock

from src.services.config_service import ConfigService, OpenAIConfig


class TestConfigService:
    """Test suite for ConfigService."""

    def test_load_config_success(self):
        """Test successful configuration loading with all required variables."""
        env_vars = {
            "OPENAI_API_KEY": "test-api-key",
            "OPENAI_MODEL": "gpt-5",
            "OPENAI_BASE_URL": "https://test.openai.azure.com/openai/v1/",
            "OPENAI_API_VERSION": "preview",
            "CHEF_SERVICES_MCP_URL": "https://test-mcp.example.com/mcp",
            "CHEF_SERVICES_MCP_API_KEY": "test-mcp-key",
            "CORS_ORIGINS": "http://localhost:3000,http://localhost:8080",
            "LOG_LEVEL": "DEBUG",
            "PORT": "8002",
            "REASONING_EFFORT": "medium",
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config_service = ConfigService()
            cfg = config_service.config
            
            # Verify OpenAI config
            assert cfg.openai.api_key == "test-api-key"
            assert cfg.openai.model_name == "gpt-5"
            assert cfg.openai.base_url == "https://test.openai.azure.com/openai/v1/"
            assert cfg.openai.api_version == "preview"
            
            # Verify MCP config
            assert cfg.chef_services_mcp.mcp_url == "https://test-mcp.example.com/mcp"
            assert cfg.chef_services_mcp.mcp_api_key == "test-mcp-key"
            
            # Verify server config
            assert cfg.cors_origins == ["http://localhost:3000", "http://localhost:8080"]
            assert cfg.log_level == "DEBUG"
            assert cfg.port == 8002
            assert cfg.reasoning_effort == "medium"

    def test_load_config_minimal(self):
        """Test configuration loading with only required variables."""
        env_vars = {
            "OPENAI_API_KEY": "test-key",
            "CHEF_SERVICES_MCP_URL": "https://mcp.example.com/mcp",
            "CHEF_SERVICES_MCP_API_KEY": "mcp-key",
            # Explicitly unset optional variables that might be in .env
            "OPENAI_BASE_URL": "",
            "OPENAI_API_VERSION": "",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            # Mock load_dotenv to prevent loading .env file
            with patch("src.services.config_service.load_dotenv"):
                config_service = ConfigService()
                cfg = config_service.config
                
                # Verify defaults
                assert cfg.openai.model_name == "gpt-5"
                # Note: base_url and api_version may be empty strings instead of None
                assert cfg.cors_origins == ["*"]
                assert cfg.log_level == "INFO"
                assert cfg.port == 8002
                assert cfg.reasoning_effort == "low"

    def test_missing_openai_api_key(self):
        """Test that missing OPENAI_API_KEY raises ValueError."""
        env_vars = {
            "OPENAI_API_KEY": "",  # Empty string to clear any existing value
            "CHEF_SERVICES_MCP_URL": "https://mcp.example.com/mcp",
            "CHEF_SERVICES_MCP_API_KEY": "mcp-key",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            with patch("src.services.config_service.load_dotenv"):
                with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                    ConfigService()

    def test_missing_mcp_url(self):
        """Test that missing CHEF_SERVICES_MCP_URL raises ValueError."""
        env_vars = {
            "OPENAI_API_KEY": "test-key",
            "CHEF_SERVICES_MCP_URL": "",  # Empty to clear
            "CHEF_SERVICES_MCP_API_KEY": "mcp-key",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            with patch("src.services.config_service.load_dotenv"):
                with pytest.raises(ValueError, match="CHEF_SERVICES_MCP_URL"):
                    ConfigService()

    def test_missing_mcp_api_key(self):
        """Test that missing CHEF_SERVICES_MCP_API_KEY raises ValueError."""
        env_vars = {
            "OPENAI_API_KEY": "test-key",
            "CHEF_SERVICES_MCP_URL": "https://mcp.example.com/mcp",
            "CHEF_SERVICES_MCP_API_KEY": "",  # Empty to clear
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            with patch("src.services.config_service.load_dotenv"):
                with pytest.raises(ValueError, match="CHEF_SERVICES_MCP_API_KEY"):
                    ConfigService()

    def test_invalid_log_level(self):
        """Test that invalid LOG_LEVEL raises ValueError."""
        env_vars = {
            "OPENAI_API_KEY": "test-key",
            "CHEF_SERVICES_MCP_URL": "https://mcp.example.com/mcp",
            "CHEF_SERVICES_MCP_API_KEY": "mcp-key",
            "LOG_LEVEL": "INVALID",
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="Invalid LOG_LEVEL"):
                ConfigService()

    def test_invalid_port(self):
        """Test that invalid PORT raises ValueError."""
        env_vars = {
            "OPENAI_API_KEY": "test-key",
            "CHEF_SERVICES_MCP_URL": "https://mcp.example.com/mcp",
            "CHEF_SERVICES_MCP_API_KEY": "mcp-key",
            "PORT": "99999",
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="Invalid PORT"):
                ConfigService()

    def test_invalid_reasoning_effort(self):
        """Test that invalid REASONING_EFFORT defaults to 'low' with warning."""
        env_vars = {
            "OPENAI_API_KEY": "test-key",
            "CHEF_SERVICES_MCP_URL": "https://mcp.example.com/mcp",
            "CHEF_SERVICES_MCP_API_KEY": "mcp-key",
            "REASONING_EFFORT": "ultra-high",
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config_service = ConfigService()
            # Should default to 'low' instead of raising error
            assert config_service.config.reasoning_effort == "low"

    def test_get_openai_config(self):
        """Test get_openai_config method returns OpenAI config."""
        env_vars = {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "gpt-4",
            "CHEF_SERVICES_MCP_URL": "https://mcp.example.com/mcp",
            "CHEF_SERVICES_MCP_API_KEY": "mcp-key",
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config_service = ConfigService()
            openai_config = config_service.get_openai_config()
            
            assert isinstance(openai_config, OpenAIConfig)
            assert openai_config.api_key == "test-key"
            assert openai_config.model_name == "gpt-4"

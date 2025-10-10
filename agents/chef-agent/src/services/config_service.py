"""Configuration service for managing Chef Agent settings.

Loads and validates environment variables following the same pattern
as the DreamFarm agent but simplified for Chef Agent's focused scope.
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass

from dotenv import load_dotenv


logger = logging.getLogger(__name__)


@dataclass
class OpenAIConfig:
    """OpenAI service configuration.

    Unified fields work for both OpenAI and Azure OpenAI. For Azure, set
    base_url to the resource '/openai/v1/' URL and api_version to 'preview'.
    """
    api_key: str
    model_name: str
    base_url: Optional[str] = None
    api_version: Optional[str] = None


@dataclass
class ChefServicesMCPConfig:
    """Configuration for the Chef Services MCP server.
    
    The Chef Agent connects to a remote MCP server that provides culinary
    service tools (chef search, service search, availability checking, etc.).
    """
    mcp_url: str
    mcp_api_key: str


@dataclass
class AppConfig:
    """Application configuration container."""
    environment: str
    log_level: str
    cors_origins: list[str]
    port: int
    openai: OpenAIConfig
    chef_services_mcp: ChefServicesMCPConfig
    reasoning_effort: str = "low"


class ConfigService:
    """Service for loading and validating application configuration."""

    def __init__(self):
        """Initialize config service and load environment variables."""
        load_dotenv()
        self.config = self._load_config()
        self._validate_config()

    def _load_config(self) -> AppConfig:
        """Load configuration from environment variables.
        
        Returns:
            Validated application configuration
            
        Raises:
            ValueError: If required environment variables are missing
        """
        # OpenAI configuration
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        model_name = os.getenv("OPENAI_MODEL", "gpt-5")
        base_url = os.getenv("OPENAI_BASE_URL")
        api_version = os.getenv("OPENAI_API_VERSION")
        
        openai_config = OpenAIConfig(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            api_version=api_version,
        )
        
        # Chef Services MCP configuration
        mcp_url = os.getenv("CHEF_SERVICES_MCP_URL")
        if not mcp_url:
            raise ValueError("CHEF_SERVICES_MCP_URL environment variable is required")
        
        mcp_api_key = os.getenv("CHEF_SERVICES_MCP_API_KEY")
        if not mcp_api_key:
            raise ValueError("CHEF_SERVICES_MCP_API_KEY environment variable is required")
        
        chef_services_mcp = ChefServicesMCPConfig(
            mcp_url=mcp_url,
            mcp_api_key=mcp_api_key,
        )
        
        # Server configuration
        cors_origins_str = os.getenv("CORS_ORIGINS", "*")
        cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]
        
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        port = int(os.getenv("PORT", "8002"))
        environment = os.getenv("ENVIRONMENT", "development")
        reasoning_effort = os.getenv("REASONING_EFFORT", "low")
        
        return AppConfig(
            environment=environment,
            log_level=log_level,
            cors_origins=cors_origins,
            port=port,
            openai=openai_config,
            chef_services_mcp=chef_services_mcp,
            reasoning_effort=reasoning_effort,
        )

    def _validate_config(self) -> None:
        """Validate loaded configuration.
        
        Raises:
            ValueError: If configuration is invalid
        """
        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.config.log_level not in valid_log_levels:
            raise ValueError(f"Invalid LOG_LEVEL: {self.config.log_level}. Must be one of {valid_log_levels}")
        
        # Validate port
        if not 1 <= self.config.port <= 65535:
            raise ValueError(f"Invalid PORT: {self.config.port}. Must be between 1 and 65535")
        
        # Validate reasoning effort
        valid_efforts = ["low", "medium", "high"]
        if self.config.reasoning_effort not in valid_efforts:
            logger.warning(
                f"Invalid REASONING_EFFORT: {self.config.reasoning_effort}. Defaulting to 'low'. "
                f"Valid values: {valid_efforts}"
            )
            self.config.reasoning_effort = "low"
        
        logger.info("Configuration validated successfully")

    def get_openai_config(self) -> OpenAIConfig:
        """Get OpenAI configuration.
        
        Returns:
            OpenAI configuration object
        """
        return self.config.openai

"""Configuration service for managing application settings."""

import os
import logging
from typing import Optional
from dataclasses import dataclass

from dotenv import load_dotenv


logger = logging.getLogger(__name__)


@dataclass
class OpenAIConfig:
    """OpenAI service configuration."""
    api_type: str
    api_key: str
    api_version: Optional[str] = None
    endpoint: Optional[str] = None
    model_name: Optional[str] = None


@dataclass
class AppConfig:
    """Application configuration."""
    environment: str
    cors_origins: list[str]
    log_level: str
    openai: OpenAIConfig


class ConfigService:
    """Service for loading and managing application configuration.
    
    Centralized configuration management with validation and fallbacks.
    """
    
    def __init__(self):
        """Initialize configuration by loading from environment."""
        load_dotenv()
        self._config = self._load_config()
        logger.info(f"Loaded configuration for environment: {self._config.environment}")
    
    def _load_config(self) -> AppConfig:
        """Load configuration from environment variables.
        
        Returns:
            Loaded application configuration
            
        Raises:
            ValueError: If required configuration is missing
        """
        # OpenAI configuration
        api_type = os.getenv("OPENAI_API_TYPE", "azure")
        
        if api_type == "azure":
            openai_config = OpenAIConfig(
                api_type=api_type,
                api_key=self._get_required_env("AZURE_OPENAI_API_KEY"),
                api_version=self._get_required_env("AZURE_OPENAI_API_VERSION"),
                endpoint=self._get_required_env("AZURE_OPENAI_ENDPOINT"),
                model_name=os.getenv("AZURE_OPENAI_MODEL_NAME", "gpt-4")
            )
        else:
            openai_config = OpenAIConfig(
                api_type=api_type,
                api_key=self._get_required_env("OPENAI_API_KEY"),
                model_name=os.getenv("OPENAI_MODEL_NAME", "gpt-4")
            )
        
        # Application configuration
        cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        cors_origins = [origin.strip() for origin in cors_origins]
        
        return AppConfig(
            environment=os.getenv("ENVIRONMENT", "development"),
            cors_origins=cors_origins,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            openai=openai_config
        )
    
    def _get_required_env(self, key: str) -> str:
        """Get required environment variable.
        
        Args:
            key: Environment variable key
            
        Returns:
            Environment variable value
            
        Raises:
            ValueError: If environment variable is not set
        """
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Required environment variable {key} is not set")
        return value
    
    @property
    def config(self) -> AppConfig:
        """Get application configuration.
        
        Returns:
            Application configuration
        """
        return self._config
    
    def get_openai_config(self) -> OpenAIConfig:
        """Get OpenAI configuration.
        
        Returns:
            OpenAI configuration
        """
        return self._config.openai
    
    def is_development(self) -> bool:
        """Check if running in development environment.
        
        Returns:
            True if development environment
        """
        return self._config.environment.lower() in ["development", "dev"]
    
    def is_production(self) -> bool:
        """Check if running in production environment.
        
        Returns:
            True if production environment
        """
        return self._config.environment.lower() in ["production", "prod"]

"""Configuration service for managing application settings."""

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
    model_name: Optional[str] = None
    base_url: Optional[str] = None
    api_version: Optional[str] = None


@dataclass
class DatabaseConfig:
    """Database configuration for PostgreSQL."""
    host: str
    port: int
    database: str
    user: str
    password: str


@dataclass
class RagConfig:
    """RAG feature configuration."""
    enabled: bool
    similarity_threshold: float
    max_results: int
    embedding_model: str = "text-embedding-3-large"


@dataclass
class AppConfig:
    """Application configuration."""
    environment: str
    cors_origins: list[str]
    log_level: str
    openai: OpenAIConfig
    db: DatabaseConfig
    rag: RagConfig


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
        # OpenAI configuration (unified)
        api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("AZURE_OPENAI_API_KEY")
            or os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY")
        )
        if not api_key:
            raise ValueError("Required environment variable OPENAI_API_KEY is not set")

        openai_config = OpenAIConfig(
            api_key=api_key,
            model_name=os.getenv("OPENAI_MODEL") or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5"),
            base_url=os.getenv("OPENAI_BASE_URL") or os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=(
                os.getenv("OPENAI_API_VERSION")
                or os.getenv("AZURE_OPENAI_API_VERSION")
                or os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION")
            ),
        )
        
        # Application configuration
        cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        cors_origins = [origin.strip() for origin in cors_origins]

        # Database configuration
        db_config = DatabaseConfig(
            host=os.getenv("PGHOST", ""),
            port=int(os.getenv("PGPORT", "5432")),
            database=os.getenv("PGDATABASE", ""),
            user=os.getenv("PGUSER", ""),
            password=os.getenv("PGPASSWORD", ""),
        )

        # RAG configuration
        rag_config = RagConfig(
            enabled=os.getenv("ENABLE_RAG", "false").lower() in ["true", "1", "yes", "on"],
            similarity_threshold=float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.7")),
            max_results=int(os.getenv("RAG_MAX_RESULTS", "3")),
            embedding_model=(
                os.getenv("OPENAI_EMBEDDING_MODEL")
                or os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME")
                or "text-embedding-3-large"
            ),
        )

        return AppConfig(
            environment=os.getenv("ENVIRONMENT", "development"),
            cors_origins=cors_origins,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            openai=openai_config,
            db=db_config,
            rag=rag_config,
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

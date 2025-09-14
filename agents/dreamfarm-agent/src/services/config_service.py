"""Configuration service for managing application settings.

Extended to include:
- Agentic search tool configuration (semantic + keyword function tools)
- Reasoning effort level for GPT‑5 models (REASONING_EFFORT env)
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
class SemanticCacheConfig:
    """Semantic first-turn cache configuration.

    The semantic cache stores (question, answer, embedding) pairs for common
    first user messages (greetings, capability questions, onboarding). Only
    the FIRST user turn in a thread is eligible for cache lookup; subsequent
    turns always go to the model.

    similarity_threshold should be intentionally high (e.g. ≥0.9) to avoid
    mismatching user intent and returning an imprecise canned answer.
    """
    enabled: bool
    similarity_threshold: float
    embedding_model: str = "text-embedding-3-large"

@dataclass
class FarmerToolsConfig:
    """Configuration for the Farmer Tools MCP server.

    The DreamFarm Agent connects to a remote MCP server exposed over HTTP
    and authenticates using a simple Bearer token header. These settings
    allow wiring that server into the OpenAI Responses API as a remote tool.
    """
    enabled: bool
    mcp_url: str | None
    mcp_api_key: str | None

@dataclass
class TavilyConfig:
    """Configuration for the Tavily MCP server.

    The DreamFarm Agent connects to Tavily's remote MCP server for web search
    capabilities. Tavily provides real-time web search, news search, and data
    extraction tools via their remote MCP endpoint.
    """
    enabled: bool
    api_key: str | None
    mcp_url: str = "https://mcp.tavily.com/mcp/"

@dataclass
class StockToolConfig:
    """Configuration for local Stock API custom tool.

    This tool is invoked locally by the agent (cannot be registered as a remote
    MCP server) and proxies requests to the stock REST API. The model may have
    product UUIDs provided in the user's message; when enabled the agent will
    fetch stock information and inject it into the system prompt.
    """
    enabled: bool
    api_url: str | None

@dataclass
class AuthConfig:
    """Keycloak authentication configuration.

    Stores the minimal parameters needed to validate JWTs issued for our
    frontend public client. Signature verification uses JWKS from the
    Keycloak realm. For now this is dev‑only and kept intentionally simple.
    """
    enabled: bool
    keycloak_url: str
    realm: str
    audience: str
    issuer: str
    jwks_url: str


@dataclass
class AppConfig:
    """Application configuration."""
    environment: str
    cors_origins: list[str]
    log_level: str
    # Reasoning effort for GPT‑5 models (minimal|medium|high|max) default minimal
    reasoning_effort: str
    openai: OpenAIConfig
    db: DatabaseConfig
    rag: RagConfig
    semantic_cache: SemanticCacheConfig | None
    farmer_tools: FarmerToolsConfig | None
    tavily: TavilyConfig | None
    stock_tool: StockToolConfig | None
    auth: AuthConfig | None
    agentic_search: Optional["AgenticSearchConfig"]  # forward ref
    graph_search: Optional["GraphSearchConfig"]  # forward ref
    memory_search: Optional["MemorySearchConfig"]  # forward ref


@dataclass
class AgenticSearchConfig:
    enabled: bool
    max_results: int


@dataclass
class GraphSearchConfig:
    """Configuration for graph traversal search tools (DFS/BFS).

    Currently only DFS (depth-first similarity style) is implemented. Feature
    is gated by GRAPH_SEARCH_ENABLED env var to allow incremental rollout.
    """
    enabled: bool
    graph_name: str
    dfs_max_results: int


@dataclass
class MemorySearchConfig:
    """Configuration for memory (conversation summary) semantic search tool.

    Enabled via MEMORY_SEARCH_ENABLED. Results limited by max_results and always
    strictly fenced by user_id in SQL (never exposed to other users).
    """
    enabled: bool
    max_results: int


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

        # Semantic cache configuration (first-turn accelerator)
        semantic_cache_enabled = os.getenv("SEMANTIC_CACHE_ENABLED", "true").lower() in ["true", "1", "yes", "on"]
        semantic_cache_threshold = float(os.getenv("SEMANTIC_CACHE_SIMILARITY_THRESHOLD", "0.93"))
        semantic_cache = SemanticCacheConfig(
            enabled=semantic_cache_enabled,
            similarity_threshold=semantic_cache_threshold,
            embedding_model=(
                os.getenv("SEMANTIC_CACHE_EMBEDDING_MODEL")
                or os.getenv("OPENAI_EMBEDDING_MODEL")
                or "text-embedding-3-large"
            ),
        ) if semantic_cache_enabled else None

        # Farmer Tools MCP configuration (remote MCP tool)
        farmer_tools_url = os.getenv("FARMER_TOOLS_MCP_URL") or os.getenv("MCP_URL")
        # Fallback to legacy MCP_API_KEY if present, but prefer namespaced env var
        farmer_tools_api_key = os.getenv("FARMER_TOOLS_MCP_API_KEY") or os.getenv("MCP_API_KEY")
        farmer_tools_enabled = (
            os.getenv("FARMER_TOOLS_ENABLED", "true").lower() in ["true", "1", "yes", "on"]
            and bool(farmer_tools_url)
            and bool(farmer_tools_api_key)
        )
        farmer_tools_config = (
            FarmerToolsConfig(
                enabled=farmer_tools_enabled,
                mcp_url=farmer_tools_url,
                mcp_api_key=farmer_tools_api_key,
            )
            if (farmer_tools_url or farmer_tools_api_key)
            else None
        )

        # Tavily MCP configuration (remote search tool)
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        tavily_enabled = (
            os.getenv("TAVILY_ENABLED", "true").lower() in ["true", "1", "yes", "on"]
            and bool(tavily_api_key)
        )
        tavily_config = (
            TavilyConfig(
                enabled=tavily_enabled,
                api_key=tavily_api_key,
            )
            if tavily_api_key
            else None
        )

        # Local Stock Tool configuration (custom function tool)
        stock_tool_url = os.getenv("STOCK_API_URL") or os.getenv("STOCK_TOOL_URL")
        stock_tool_enabled = (
            os.getenv("STOCK_TOOL_ENABLED", "true").lower() in ["true", "1", "yes", "on"]
            and bool(stock_tool_url)
        )
        stock_tool_config = (
            StockToolConfig(
                enabled=stock_tool_enabled,
                api_url=stock_tool_url,
            )
            if stock_tool_url
            else None
        )

        # Auth (Keycloak) configuration
        keycloak_url = os.getenv("KEYCLOAK_URL") or "http://localhost:8080"
        keycloak_realm = os.getenv("KEYCLOAK_REALM") or "dreamfarm"
        audience = os.getenv("KEYCLOAK_AUDIENCE") or os.getenv("KEYCLOAK_DEMO_CLIENT_ID") or "dreamfarm-frontend"
        auth_enabled = os.getenv("AUTH_ENABLED", "true").lower() in ["true", "1", "yes", "on"]
        issuer = f"{keycloak_url}/realms/{keycloak_realm}"
        jwks_url = f"{issuer}/protocol/openid-connect/certs"
        auth_config = AuthConfig(
            enabled=auth_enabled,
            keycloak_url=keycloak_url,
            realm=keycloak_realm,
            audience=audience,
            issuer=issuer,
            jwks_url=jwks_url,
        ) if auth_enabled else None

        # Agentic search (tool-based retrieval) configuration
        agentic_enabled = os.getenv("AGENTIC_SEARCH_ENABLED", "false").lower() in ["true", "1", "yes", "on"]
        agentic_cfg = AgenticSearchConfig(
            enabled=agentic_enabled,
            max_results=int(os.getenv("AGENTIC_SEARCH_MAX_RESULTS", "10")),
        ) if agentic_enabled else None

        # Graph search (DFS/BFS future) configuration
        graph_search_enabled = os.getenv("GRAPH_SEARCH_ENABLED", "false").lower() in ["true", "1", "yes", "on"]
        graph_search_cfg = GraphSearchConfig(
            enabled=graph_search_enabled,
            graph_name=os.getenv("AGE_GRAPH_NAME", "dreamfarm"),
            dfs_max_results=int(os.getenv("GRAPH_DFS_MAX_RESULTS", "10")),
        ) if graph_search_enabled else None

        # Memory search configuration (conversation summaries)
        memory_search_enabled = os.getenv("MEMORY_SEARCH_ENABLED", "true").lower() in ["true", "1", "yes", "on"]
        memory_search_cfg = MemorySearchConfig(
            enabled=memory_search_enabled,
            max_results=int(os.getenv("MEMORY_SEARCH_MAX_RESULTS", "5")),
        ) if memory_search_enabled else None

        return AppConfig(
            environment=os.getenv("ENVIRONMENT", "development"),
            cors_origins=cors_origins,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            reasoning_effort=os.getenv("REASONING_EFFORT", "minimal"),
            openai=openai_config,
            db=db_config,
            rag=rag_config,
            semantic_cache=semantic_cache,
            farmer_tools=farmer_tools_config,
            tavily=tavily_config,
            stock_tool=stock_tool_config,
            auth=auth_config,
            agentic_search=agentic_cfg,
            graph_search=graph_search_cfg,
            memory_search=memory_search_cfg,
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

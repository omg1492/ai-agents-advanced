"""OpenAI service for handling AI interactions via the Responses API.

This module provides a thin wrapper over the official OpenAI Python SDK's
Responses API and supports BOTH OpenAI and Azure OpenAI with a single client
configuration using the unified v1 API style:

- OpenAI (hosted by OpenAI): provide only ``OPENAI_API_KEY`` and optional
    ``OPENAI_MODEL``.
- Azure OpenAI: use the same client with ``OPENAI_API_KEY`` set to the Azure
    key, plus ``OPENAI_BASE_URL`` set to the Azure resource URL ending with
    ``/openai/v1/`` and ``OPENAI_API_VERSION`` (typically ``preview``).

For compatibility with older environment variables used in this repository,
this service will also honor the previous Azure-specific variables if the new
unified variables are not provided.

Additionally, when a GPT-5 family model is selected, minimal reasoning effort
is enabled automatically when supported.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.services.config_service import ConfigService, OpenAIConfig

from openai import AsyncOpenAI


logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI or Azure OpenAI via Responses API.

    The service supports:
    - OpenAI or Azure OpenAI backends using a single client
    - Server-side conversation state using `store=True` and `previous_response_id`
    - GPT-5 minimal reasoning effort when the configured model is gpt-5
    """

    def __init__(self, config: Optional[OpenAIConfig] = None):
        """Initialize the OpenAI service.

        Args:
            config: Optional OpenAI configuration (preferred). If not provided,
                configuration will be loaded via ConfigService.
        """
        cfg_service = ConfigService()
        self._config = config or cfg_service.get_openai_config()
        # Optional remote MCP server (Farmer Tools)
        self._farmer_tools = getattr(cfg_service.config, "farmer_tools", None)
        self.client = self._get_openai_client()
        self.model_name = self._get_model_name()
        logger.info(
            "Initialized OpenAI service with base_url=%s, model=%s",
            getattr(self.client, "base_url", None),
            self.model_name,
        )

    def get_tools(self) -> Optional[list[dict]]:
        """Return configured remote MCP tools for the Responses API.

        Currently exposes the Farmer Tools MCP server when enabled.
        """
        if self._farmer_tools and getattr(self._farmer_tools, "enabled", False):
            if self._farmer_tools.mcp_url and self._farmer_tools.mcp_api_key:
                tool = {
                    "type": "mcp",
                    "server_label": "farmer-tools",
                    "server_url": self._farmer_tools.mcp_url,
                    "require_approval": "never",
                    "headers": {
                        "Authorization": f"Bearer {self._farmer_tools.mcp_api_key}",
                    },
                }
                # Log minimal diagnostics to aid troubleshooting (mask key)
                try:
                    masked = self._farmer_tools.mcp_api_key[:4] + "***" if self._farmer_tools.mcp_api_key else ""
                    logger.info(
                        "Configured MCP tool: label=%s url=%s auth=%s",
                        tool.get("server_label"),
                        tool.get("server_url"),
                        f"Bearer {masked}",
                    )
                except Exception:
                    pass
                return [tool]
        return None

    def _get_openai_client(self) -> AsyncOpenAI:
        """Create a unified async OpenAI client for OpenAI or Azure OpenAI.

        Returns:
            AsyncOpenAI client instance

        Raises:
            ValueError: If required environment variables are missing
        """
        if not self._config:
            raise ValueError("OpenAIService requires OpenAIConfig to be provided")

        api_key = self._config.api_key
        base_url = self._config.base_url

        # API version for Azure next-gen v1 when base_url is set
        default_query = None
        if base_url:
            api_version = self._config.api_version or "preview"
            default_query = {"api-version": api_version}

        return AsyncOpenAI(api_key=api_key, base_url=base_url, default_query=default_query)

    def _get_model_name(self) -> str:
        """Resolve the model name (or Azure deployment name).

        For Azure, the SDK expects the deployment name in `model`.
        For OpenAI, the global model name is used.
        """
        if not self._config or not self._config.model_name:
            raise ValueError("OpenAI model name must be provided via OpenAIConfig.model_name")
        return self._config.model_name

    async def generate_response(
        self,
        user_text: str,
        *,
        system_prompt: Optional[str] = None,
        previous_response_id: Optional[str] = None,
    ) -> tuple[str, str]:
        """Generate a response using the Responses API.
        
        Args:
            user_text: The user message input text
            system_prompt: Optional system instructions/preamble
            previous_response_id: Optional previous response ID to continue server-side state

        Returns:
            Tuple of (assistant_text, response_id)

        Raises:
            Exception: If the API call fails
        """
        try:
            tools = self.get_tools()

            kwargs = {}
            if tools:
                kwargs["tools"] = tools
            response = await self.client.responses.create(
                model=self.model_name,
                instructions=system_prompt or None,
                input=user_text,
                store=True,
                previous_response_id=previous_response_id or None,
                reasoning = {"effort": "minimal"},
                **kwargs,
            )

            text = getattr(response, "output_text", None) or ""
            resp_id = getattr(response, "id", None) or ""
            return text, resp_id
        except Exception as e:  # pragma: no cover - pass through for API errors
            logger.exception("OpenAI Responses API call failed: %s", e)
            raise

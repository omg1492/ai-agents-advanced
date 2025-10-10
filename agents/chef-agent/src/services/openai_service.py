"""OpenAI service for handling AI interactions via the Responses API.

Thin wrapper over the official OpenAI Python SDK's Responses API, supporting
both OpenAI and Azure OpenAI with unified configuration. Registers the remote
Chef Services MCP server as a tool source for culinary service queries.
"""
from __future__ import annotations

import logging
from typing import Optional

from openai import AsyncOpenAI

from src.services.config_service import OpenAIConfig, AppConfig


logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI or Azure OpenAI via the Responses API.
    
    Registers the remote Chef Services MCP server to provide culinary service
    tools (chef search, availability, pricing, ordering, etc.).
    """

    def __init__(self, config: OpenAIConfig, app_config: AppConfig):
        """Initialize the OpenAI service.

        Args:
            config: OpenAI configuration (API key, model, base URL, etc.)
            app_config: Full application configuration including MCP settings
        """
        self._config = config
        self._app_config = app_config
        self.client = self._get_openai_client()
        self.model_name = config.model_name
        
        logger.info(
            "Initialized OpenAI service: base_url=%s model=%s mcp_url=%s",
            getattr(self.client, "base_url", None),
            self.model_name,
            app_config.chef_services_mcp.mcp_url,
        )

    def _get_openai_client(self) -> AsyncOpenAI:
        """Create and configure the AsyncOpenAI client.
        
        Returns:
            Configured AsyncOpenAI client instance
        """
        # Build client kwargs (unified for OpenAI and Azure OpenAI)
        client_kwargs = {
            "api_key": self._config.api_key,
        }
        
        # Add Azure-specific parameters if configured
        if self._config.base_url:
            client_kwargs["base_url"] = self._config.base_url
        
        if self._config.api_version:
            client_kwargs["default_headers"] = {"api-version": self._config.api_version}
        
        return AsyncOpenAI(**client_kwargs)

    def get_tools(self) -> list[dict]:
        """Return tool definitions for the Responses API.

        Registers the remote Chef Services MCP server using the 'mcp' tool type.
        The Responses API will automatically discover and expose all tools from
        the MCP server (search_chefs, search_services, check_availability, etc.).
        
        Returns:
            List of tool configuration dictionaries
        """
        tools = []
        
        # Register Chef Services MCP server
        mcp_config = self._app_config.chef_services_mcp
        tools.append({
            "type": "mcp",
            "server_label": "chef_services",
            "server_url": mcp_config.mcp_url,
            "require_approval": "never",
            "headers": {
                "Authorization": f"Bearer {mcp_config.mcp_api_key}"
            }
        })
        
        logger.info(
            "Registered MCP tools: chef_services (label=chef_services url=%s)",
            mcp_config.mcp_url,
        )
        
        return tools

    async def generate_response(
        self,
        user_text: str,
        system_prompt: str,
        previous_response_id: Optional[str] = None,
    ) -> tuple[str, str]:
        """Generate a response using the Responses API with stateful continuity.

        Args:
            user_text: User's input message
            system_prompt: System instructions for the agent
            previous_response_id: Optional response ID from previous turn for continuity

        Returns:
            Tuple of (response_text, response_id) where response_id can be used
            for the next turn to maintain conversation state
            
        Raises:
            Exception: If the API call fails
        """
        # Build input messages
        input_messages = [
            {"role": "user", "content": user_text}
        ]
        
        # Get tools (MCP server registration)
        tools = self.get_tools()
        
        # Build API call parameters
        api_params = {
            "model": self.model_name,
            "instructions": system_prompt,
            "input": input_messages,
            "store": True,  # Enable server-side state storage
            "tools": tools,
            "reasoning": {"effort": self._app_config.reasoning_effort},
        }
        
        # Add previous response ID for continuity if available
        if previous_response_id:
            api_params["previous_response_id"] = previous_response_id
        
        logger.debug(
            "Calling Responses API: model=%s tools_count=%d has_previous=%s",
            self.model_name,
            len(tools),
            bool(previous_response_id),
        )
        
        # Call the Responses API
        response = await self.client.responses.create(**api_params)
        
        # Extract response text from output
        response_text = ""
        if hasattr(response, "output") and response.output:
            for item in response.output:
                if hasattr(item, "type") and item.type == "message":
                    if hasattr(item, "content"):
                        for content_block in item.content:
                            if hasattr(content_block, "text"):
                                response_text += content_block.text
        
        # Get response ID for continuity
        response_id = getattr(response, "id", "")
        
        logger.info(
            "Generated response: response_id=%s text_length=%d",
            response_id,
            len(response_text),
        )
        
        return response_text, response_id

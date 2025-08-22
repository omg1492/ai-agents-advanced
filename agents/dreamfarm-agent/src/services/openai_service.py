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
import json
from typing import Optional, List, Any

from src.services.config_service import ConfigService, OpenAIConfig, AppConfig
from src.services.stock_service import StockService

from openai import AsyncOpenAI


logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI or Azure OpenAI via the Responses API.

    Adds lightweight function-calling support for a local custom tool (Stock API)
    that cannot be exposed as a remote MCP server. Remote MCP tools (Farmer Tools)
    are still supported concurrently.
    """

    def __init__(
        self,
        config: Optional[OpenAIConfig] = None,
        app_config: Optional[AppConfig] = None,
        stock_service: Optional[StockService] = None,
    ):
        """Initialize the OpenAI service.

        Args:
            config: Optional OpenAI configuration (preferred). If not provided,
                configuration will be loaded via ConfigService.
            app_config: Full application configuration. Only required when
                passing a pre-built stock_service; if omitted it will be loaded.
            stock_service: Optional existing ``StockService`` instance. When not
                provided and the stock tool is enabled in config, a new instance
                is created internally.
        """
        cfg_service = ConfigService()
        self._config = config or cfg_service.get_openai_config()
        self._app_config: AppConfig = app_config or cfg_service.config
        # Remote MCP server (Farmer Tools)
        self._farmer_tools = getattr(self._app_config, "farmer_tools", None)
        # Remote MCP server (Tavily Search)
        self._tavily = getattr(self._app_config, "tavily", None)
        # Local stock custom tool
        self._stock_service: StockService | None = stock_service
        if self._stock_service is None:
            try:
                self._stock_service = StockService(self._app_config)
            except Exception:  # pragma: no cover - defensive
                self._stock_service = None
        self.client = self._get_openai_client()
        self.model_name = self._get_model_name()
        logger.info(
            "Initialized OpenAI service with base_url=%s, model=%s, stock_tool_enabled=%s, tavily_enabled=%s",
            getattr(self.client, "base_url", None),
            self.model_name,
            bool(self._stock_service and self._stock_service.enabled),
            bool(self._tavily and self._tavily.enabled),
        )

    def get_tools(self) -> Optional[list[dict]]:
        """Return tool definitions for the Responses API.

        Includes (when enabled):
        - Remote MCP Farmer Tools server
        - Remote MCP Tavily Search server
        - Local function tool ``get_stock`` for the stock custom tool
        """
        tools: list[dict] = []

        # Remote MCP tool - Farmer Tools
        if self._farmer_tools and getattr(self._farmer_tools, "enabled", False):
            if self._farmer_tools.mcp_url and self._farmer_tools.mcp_api_key:
                try:
                    masked = (
                        self._farmer_tools.mcp_api_key[:4] + "***" if self._farmer_tools.mcp_api_key else ""
                    )
                    logger.info(
                        "Configured MCP tool: label=%s url=%s auth=%s",
                        "farmer-tools",
                        self._farmer_tools.mcp_url,
                        f"Bearer {masked}",
                    )
                except Exception:
                    pass
                tools.append(
                    {
                        "type": "mcp",
                        "server_label": "farmer-tools",
                        "server_url": self._farmer_tools.mcp_url,
                        "require_approval": "never",
                        "headers": {
                            "Authorization": f"Bearer {self._farmer_tools.mcp_api_key}",
                        },
                    }
                )

        # Remote MCP tool - Tavily Search
        if self._tavily and getattr(self._tavily, "enabled", False):
            if self._tavily.api_key:
                try:
                    masked = (
                        self._tavily.api_key[:4] + "***" if self._tavily.api_key else ""
                    )
                    # Construct the full URL with API key parameter
                    tavily_url = f"{self._tavily.mcp_url}?tavilyApiKey={self._tavily.api_key}"
                    logger.info(
                        "Configured MCP tool: label=%s url=%s",
                        "tavily",
                        f"{self._tavily.mcp_url}?tavilyApiKey={masked}",
                    )
                except Exception:
                    pass
                tools.append(
                    {
                        "type": "mcp",
                        "server_label": "tavily",
                        "server_url": tavily_url,
                        "require_approval": "never",
                    }
                )

        # Local function tool for stock
        if self._stock_service and self._stock_service.enabled:
            # NOTE: External API expects camelCase 'productIds'. We publish that key.
            # We still accept legacy 'product_ids' in parsing for backwards compatibility.
            tools.append(
                {
                    "type": "function",
                    "name": "get_stock",
                    "description": "Get current stock levels for up to 20 product UUIDs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "productIds": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "description": "Product UUID (36-char)"
                                },
                                "minItems": 1,
                                "maxItems": 20,
                                "description": "List of product UUIDs (max 20)"
                            }
                        },
                        "required": ["productIds"],
                    },
                }
            )

        return tools or None

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
        """Generate a response handling any synchronous function tool calls.

        Implements a simple tool-call loop for the local ``get_stock`` function
        tool. Remote MCP tools are handled entirely by the platform.
        """
        tools = self.get_tools()
        kwargs: dict[str, Any] = {}
        if tools:
            kwargs["tools"] = tools

        try:
            response = await self.client.responses.create(
                model=self.model_name,
                instructions=system_prompt or None,
                input=user_text,
                store=True,
                previous_response_id=previous_response_id or None,
                reasoning={"effort": "minimal"},
                **kwargs,
            )
        except Exception as e:  # pragma: no cover - network / auth errors
            logger.exception("Initial Responses API call failed: %s", e)
            raise

        # Function-call resolution loop (no fixed round limit). We rely on the
        # model to stop requesting calls; we still log if unusually many loops occur.
        loop_count = 0
        while True:
            fn_calls = self._extract_function_calls(response)
            if not fn_calls:
                break
            tool_outputs: list[dict[str, str]] = []
            for call in fn_calls:
                name = call.get("name")
                call_id = call.get("id")
                raw_args = call.get("arguments") or "{}"
                if name != "get_stock":
                    logger.info("Ignoring unsupported function call name=%s", name)
                    continue
                if not (self._stock_service and self._stock_service.enabled):
                    logger.info("Stock tool called but service disabled; returning empty list")
                    output_payload = {"items": []}
                else:
                    try:
                        parsed = json.loads(raw_args) if isinstance(raw_args, str) else {}
                    except Exception:
                        parsed = {}
                    # Accept both new camelCase and legacy snake_case
                    prod_ids = parsed.get("productIds") or parsed.get("product_ids") or []
                    if not isinstance(prod_ids, list):
                        prod_ids = []
                    prod_ids = [str(p) for p in prod_ids][:20]
                    items = []
                    if prod_ids:
                        try:
                            stock_items = await self._stock_service.get_stock(prod_ids)
                            for it in stock_items:
                                items.append({"product_id": it.product_id, "on_stock": it.on_stock})
                        except Exception as se:  # pragma: no cover - API failure
                            logger.warning("Stock tool execution failed: %s", se)
                    output_payload = {"items": items}
                if call_id:
                    tool_outputs.append(
                        {"tool_call_id": call_id, "output": json.dumps(output_payload)}
                    )
            if not tool_outputs:
                break  # nothing executable
            try:
                response = await self.client.responses.submit_tool_outputs(
                    response_id=getattr(response, "id", None),
                    tool_outputs=tool_outputs,
                )
            except Exception as e:  # pragma: no cover
                logger.exception("submit_tool_outputs failed: %s", e)
                break
            loop_count += 1
            if loop_count in (10, 25, 50):  # progressive diagnostics only
                logger.warning("High number of function call loops executed: %s", loop_count)

        text = getattr(response, "output_text", None) or ""
        resp_id = getattr(response, "id", None) or ""
        return text, resp_id

    # ------------------------ internal helpers ------------------------ #
    @staticmethod
    def _extract_function_calls(response: Any) -> List[dict]:
        """Extract function call items from a Responses API response object.

        Returns list of dicts with keys: id, name, arguments (string).
        """
        calls: List[dict] = []
        output_items = getattr(response, "output", None)
        if not output_items:
            return calls
        for item in output_items:
            try:
                if getattr(item, "type", None) == "function_call":
                    calls.append(
                        {
                            "id": getattr(item, "id", None),
                            "name": getattr(item, "name", None),
                            "arguments": getattr(item, "arguments", None),
                        }
                    )
            except Exception:  # pragma: no cover - defensive
                continue
        return calls

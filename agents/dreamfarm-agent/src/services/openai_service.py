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
from src.services.agentic_search import AgenticSearchService
from src.services.graph_search_service import GraphSearchService
from src.services.stock_service import StockService
from src.services.memory_search_service import MemorySearchService
from src.services.user_profile_service import UserProfileService
import os

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
        user_profile_service: Optional[UserProfileService] = None,
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
        # Memory search service (granular flag: MEMORY_SEARCH_ENABLED) – legacy MEMORY_FEATURES_ENABLED deprecated
        self._memory_search: MemorySearchService | None = None
        try:
            mem_enabled_flag = os.getenv("MEMORY_SEARCH_ENABLED", "false").lower() in ["true","1","yes","on"]
            if mem_enabled_flag and getattr(self._app_config, "memory_search", None) and self._app_config.memory_search.enabled:  # type: ignore[attr-defined]
                self._memory_search = MemorySearchService(self._app_config)
            else:
                logger.info("Memory search disabled; skipping memory_search tool init")
        except Exception as me:  # pragma: no cover
            logger.warning(f"Memory search init failed: {me}")
        # User profile service (write path for memory_write_profile tool) – may be injected externally (tests) or None
        self._user_profile_service: UserProfileService | None = user_profile_service
        self.client = self._get_openai_client()
        self.model_name = self._get_model_name()
        # Agentic search service (function tools) optional
        self._agentic_search: AgenticSearchService | None = None
        self._graph_search: GraphSearchService | None = None
        try:
            if getattr(self._app_config, "agentic_search", None) and self._app_config.agentic_search.enabled:  # type: ignore[attr-defined]
                self._agentic_search = AgenticSearchService(self._app_config)
        except Exception as ae:  # pragma: no cover
            logger.warning(f"Agentic search init failed: {ae}")
        try:
            if getattr(self._app_config, "graph_search", None) and self._app_config.graph_search.enabled:  # type: ignore[attr-defined]
                self._graph_search = GraphSearchService(self._app_config)
        except Exception as ge:  # pragma: no cover
            logger.warning(f"Graph search init failed: {ge}")
        logger.info(
            "Initialized OpenAI service base_url=%s model=%s stock_tool=%s tavily=%s agentic=%s graph=%s memory_search=%s",
            getattr(self.client, "base_url", None),
            self.model_name,
            bool(self._stock_service and self._stock_service.enabled),
            bool(self._tavily and self._tavily.enabled),
            bool(self._agentic_search and self._agentic_search.enabled),
            bool(self._graph_search and self._graph_search.enabled),
            bool(self._memory_search and self._memory_search.enabled),
        )

    def get_tools(self) -> Optional[list[dict]]:
        """Return tool definitions for the Responses API.

        Includes (when enabled):
        - Code Interpreter (built-in Azure OpenAI tool)
        - Remote MCP Farmer Tools server
        - Remote MCP Tavily Search server
        - Local function tool ``get_stock`` for the stock custom tool
        """
        tools: list[dict] = []

        # Code Interpreter tool (built-in Azure OpenAI capability)
        if getattr(self._app_config, "code_interpreter", None) and self._app_config.code_interpreter.enabled:  # type: ignore[attr-defined]
            container_type = getattr(self._app_config.code_interpreter, "container_type", "auto")
            tools.append(
                {
                    "type": "code_interpreter",
                    "container": {"type": container_type}
                }
            )
            logger.info("Code interpreter tool enabled (container_type=%s)", container_type)

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

        # Agentic search function tools
        if self._agentic_search and self._agentic_search.enabled:
            tools.append(
                {
                    "type": "function",
                    "name": "semantic_product_search",
                    "description": "Semantic vector search over products using HyDE style expanded description. Use when rich context or description of need is helpful.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "HyDE style expanded description of the user's need (the model writes this)."
                            },
                            "k": {
                                "type": "integer",
                                "minimum": 3,
                                "maximum": 10,
                                "description": "How many top products to retrieve (3-10)."
                            }
                        },
                        "required": ["text"],
                    },
                }
            )
            tools.append(
                {
                    "type": "function",
                    "name": "keyword_product_search",
                    "description": "Keyword / phrase full-text search over products. Use when concise specific terms are known (e.g. exact product or producer names).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 1,
                                "maxItems": 8,
                                "description": "Distinct short keywords or short noun phrases (no stop words)."
                            },
                            "k": {
                                "type": "integer",
                                "minimum": 3,
                                "maximum": 10,
                                "description": "How many top products to retrieve (3-10)."
                            }
                        },
                        "required": ["keywords"],
                    },
                }
            )
        # Graph DFS similarity tool
        if self._graph_search and self._graph_search.enabled:
            tools.append(
                {
                    "type": "function",
                    "name": "graph_dfs_similarity_search",
                    "description": "Depth-first similarity style structural traversal starting from a concrete product UUID (find structurally similar alternatives). Use only after a product has been identified.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "description": "UUID of a previously grounded product (must have appeared in prior tool output or RAG block)."
                            },
                            "k": {
                                "type": "integer",
                                "minimum": 3,
                                "maximum": 10,
                                "description": "How many similar products to retrieve (3-10)."
                            }
                        },
                        "required": ["product_id"],
                    },
                }
            )
            tools.append(
                {
                    "type": "function",
                    "name": "graph_bfs_taxonomy_search",
                    "description": "Breadth-style taxonomy expansion using semantic concepts (categories, cuisines, certifications, allergens) for ambiguous or high-level intent.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Abstract or high-level user intent text to ground into taxonomy concepts."
                            },
                            "k": {
                                "type": "integer",
                                "minimum": 3,
                                "maximum": 10,
                                "description": "How many representative products to retrieve (3-10)."
                            }
                        },
                        "required": ["query"],
                    },
                }
            )
        # Memory search tool
        if self._memory_search and self._memory_search.enabled:
            tools.append(
                {
                    "type": "function",
                    "name": "memory_search",
                    "description": "Search the user's own past conversation summaries via semantic similarity (HyDE style expanded query recommended). Returns prior summaries to ground personalization.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "HyDE style expanded query describing what past conversations to look for (user intent, preference topic, etc.)."
                            },
                            "k": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 8,
                                "description": "How many top memories to retrieve (1-8)."
                            }
                        },
                        "required": ["query"],
                    },
                }
            )
        # Memory write (profile patch) tool – only if user profiles enabled (environment flag handled in main for injection logic)
        prof_enabled_flag = os.getenv("USER_PROFILE_ENABLED", "false").lower() in ["true","1","yes","on"]
        if prof_enabled_flag:
            logger.info("Registering memory_write_profile tool (USER_PROFILE_ENABLED=%s)", prof_enabled_flag)
            tools.append(
                {
                    "type": "function",
                    "name": "memory_write_profile",
                    "description": "Patch the user's profile with new or corrected preference facts. Use ONLY when the user explicitly asks to remember something for next time or when a critical, durable preference/contradiction becomes clear.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patch": {
                                "type": "object",
                                "description": "Constrained patch object with optional keys: set (object), append (object of arrays), remove (array of field names). Do NOT send full profile.",
                                "properties": {
                                    "set": {"type": "object", "description": "New or updated fields (objects merged recursively)."},
                                    "append": {"type": "object", "description": "Arrays of primitive values to append uniquely."},
                                    "remove": {"type": "array", "items": {"type": "string"}, "description": "Top-level fields to remove."}
                                }
                            }
                        },
                        "required": ["patch"],
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
        user_is_vip: bool = False,
        user_id: Optional[str] = None,
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
                reasoning={"effort": getattr(self._app_config, 'reasoning_effort', 'minimal')},
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
            last_graph_products: List[dict] = []  # capture latest graph tool result for fallback
            for call in fn_calls:
                name = call.get("name")
                call_id = call.get("id")
                raw_args = call.get("arguments") or "{}"
                output_payload = None
                if name == "get_stock":
                    if not (self._stock_service and self._stock_service.enabled):
                        logger.info("Stock tool called but service disabled; returning empty list")
                        output_payload = {"items": []}
                    else:
                        try:
                            parsed = json.loads(raw_args) if isinstance(raw_args, str) else {}
                        except Exception:
                            parsed = {}
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
                elif name in {"semantic_product_search", "keyword_product_search"}:
                    if self._agentic_search and self._agentic_search.enabled:
                        try:
                            parsed = json.loads(raw_args) if isinstance(raw_args, str) else {}
                        except Exception:
                            parsed = {}
                        try:
                            output_json = await self._agentic_search.execute(name, parsed, user_is_vip=user_is_vip)
                            output_payload = json.loads(output_json)
                        except Exception as ae:  # pragma: no cover
                            logger.warning(f"Agentic search execution failed: {ae}")
                            output_payload = {"products": []}
                    else:
                        output_payload = {"products": []}
                elif name in {"graph_dfs_similarity_search", "graph_bfs_taxonomy_search"}:
                    if self._graph_search and self._graph_search.enabled:
                        try:
                            parsed = json.loads(raw_args) if isinstance(raw_args, str) else {}
                        except Exception:
                            parsed = {}
                        try:
                            output_json = await self._graph_search.execute(name, parsed, user_is_vip=user_is_vip)
                            output_payload = json.loads(output_json)
                            if isinstance(output_payload, dict) and "products" in output_payload:
                                prods = output_payload.get("products") or []
                                if isinstance(prods, list):
                                    last_graph_products = prods
                                logger.info(
                                    "Graph tool executed name=%s args=%s products=%d", name, parsed, len(last_graph_products)
                                )
                                if last_graph_products:
                                    logger.debug("Graph tool sample product_ids=%s", [p.get("product_id") for p in last_graph_products[:5]])
                        except Exception as ge:  # pragma: no cover
                            logger.warning(f"Graph search execution failed: {ge}")
                            output_payload = {"products": []}
                    else:
                        output_payload = {"products": []}
                elif name == "memory_search":
                    if self._memory_search and self._memory_search.enabled and user_id:
                        try:
                            parsed = json.loads(raw_args) if isinstance(raw_args, str) else {}
                        except Exception:
                            parsed = {}
                        try:
                            output_json = await self._memory_search.execute(parsed, user_id=user_id)
                            output_payload = json.loads(output_json)
                        except Exception as me:  # pragma: no cover
                            logger.warning(f"Memory search execution failed: {me}")
                            output_payload = {"memories": []}
                    else:
                        output_payload = {"memories": []}
                elif name == "memory_write_profile":
                    prof_enabled_flag = os.getenv("USER_PROFILE_ENABLED", "false").lower() in ["true","1","yes","on"]
                    logger.info("memory_write_profile tool called: user_id=%s prof_enabled=%s service_available=%s", user_id, prof_enabled_flag, bool(self._user_profile_service))
                    if user_id and prof_enabled_flag and self._user_profile_service:
                        try:
                            parsed = json.loads(raw_args) if isinstance(raw_args, str) else {}
                        except Exception:
                            parsed = {}
                        patch = parsed.get("patch") or {}
                        logger.info("memory_write_profile attempting patch user_id=%s patch=%s", user_id, patch)
                        try:
                            # Use verbose report
                            report = self._user_profile_service.apply_patch_with_report(user_id, patch)
                            try:
                                logger.info("memory_write_profile executed user_id=%s applied=%s updated=%s ignored=%s not_found=%s errors=%s", user_id, report.get("applied"), report.get("updated"), report.get("ignored"), report.get("not_found"), report.get("errors"))
                                # DF_META style structured line for UI parsing (if frontend listens)
                                logger.info("DF_META memory_write_profile report=%s", json.dumps({
                                    "user_id": user_id,
                                    "applied": report.get("applied"),
                                    "updated": report.get("updated"),
                                    "not_found": report.get("not_found"),
                                    "ignored": report.get("ignored"),
                                    "errors": report.get("errors"),
                                }, ensure_ascii=False))
                            except Exception:
                                pass
                            output_payload = report
                        except Exception as pe:  # pragma: no cover
                            logger.warning(f"Profile patch failed: {pe}")
                            output_payload = {"applied": False, "error": "patch_failed", "full_profile": self._user_profile_service.get_profile(user_id)}
                    else:
                        logger.warning("memory_write_profile disabled or missing requirements: user_id=%s prof_enabled=%s service=%s", user_id, prof_enabled_flag, bool(self._user_profile_service))
                        output_payload = {"applied": False, "error": "disabled"}
                else:
                    logger.info("Ignoring unsupported function call name=%s", name)
                    continue
                if call_id:
                    tool_outputs.append(
                        {"tool_call_id": call_id, "output": json.dumps(output_payload)}
                    )
            if not tool_outputs:
                break  # nothing executable
            try:
                logger.info("Submitting %d tool outputs to response_id=%s", len(tool_outputs), getattr(response, "id", None))
                for i, tool_out in enumerate(tool_outputs):
                    logger.info("Tool output %d: call_id=%s output_len=%d", i, tool_out.get("tool_call_id"), len(tool_out.get("output", "")))
                response = await self.client.responses.submit_tool_outputs(
                    response_id=getattr(response, "id", None),
                    tool_outputs=tool_outputs,
                )
                logger.info("submit_tool_outputs succeeded, new response_id=%s", getattr(response, "id", None))
            except Exception as e:  # pragma: no cover
                logger.exception("submit_tool_outputs failed: %s", e)
                break
            loop_count += 1
            if loop_count in (10, 25, 50):  # progressive diagnostics only
                logger.warning("High number of function call loops executed: %s", loop_count)

        text = getattr(response, "output_text", None) or ""
        # Fallback synthesis if model produced no natural language but we have graph products
        if not text and 'last_graph_products' in locals() and last_graph_products:
            lines = ["(Auto‑summary) Výsledky z grafového nástroje:"]
            for p in last_graph_products[:10]:
                lines.append(f"- {p.get('product_name')} ({p.get('producer_name')}) score={p.get('similarity_score')}")
            text = "\n".join(lines)
            logger.info("Synthesized fallback text from %d graph products", len(last_graph_products))
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

    # ------------------------ user profile helpers ------------------------ #
    async def _run_user_profile_patch(self, user_id: str, patch: dict) -> dict:
        """Run the user profile patch (async wrapper).

        The underlying service method is synchronous (DB write). We execute it in
        a thread via loop.run_in_executor if needed in future; for now direct call
        to keep simple (I/O bound small single statement).
        """
        if not self._user_profile_service:
            return {}
        # Service method is sync; call directly (SQLAlchemy engine uses threadpool internally).
        return self._user_profile_service.apply_patch(user_id, patch)

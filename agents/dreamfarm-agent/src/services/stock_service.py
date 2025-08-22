"""Stock service providing access to local stock REST API.

This is implemented as a *custom tool* executed inside the agent process
because the Stock API is a plain REST service that cannot be exposed to the
OpenAI Responses API as a remote MCP server. When enabled via configuration
the agent can proactively (or reactively) fetch stock levels for a list of
product UUIDs and include summarized results in prompts.

Environment / config variables (parsed in ConfigService):
    STOCK_TOOL_ENABLED (bool) - default true when url provided
    STOCK_API_URL / STOCK_TOOL_URL - base URL of stock API (e.g. http://localhost:8011)

Usage pattern in agent code:
    stock_service = StockService()
    if stock_service.enabled:
        items = await stock_service.get_stock([uuid1, uuid2])
        prompt_fragment = stock_service.format_stock_items(items)

The service is intentionally simple; retries/backoff can be added later.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Iterable, List, Optional
from uuid import UUID
import httpx

from src.services.config_service import ConfigService, AppConfig


logger = logging.getLogger(__name__)


@dataclass
class StockItem:
    """Single stock record returned from the Stock API."""
    product_id: str
    producer_id: Optional[str]
    on_stock: int
    updated_at: Optional[str]


class StockService:
    """Service proxying calls to the external (local) Stock API."""

    def __init__(self, config: Optional[AppConfig] = None, client: Optional[httpx.AsyncClient] = None):
        cfg_service = ConfigService()
        self._config = config or cfg_service.config
        self._tool_cfg = getattr(self._config, "stock_tool", None)
        self.enabled: bool = bool(self._tool_cfg and self._tool_cfg.enabled and self._tool_cfg.api_url)
        self._base_url: Optional[str] = getattr(self._tool_cfg, "api_url", None)
        self._client = client or httpx.AsyncClient(timeout=10.0)
        if self.enabled:
            logger.info("StockService enabled with base_url=%s", self._base_url)
        else:
            logger.info("StockService disabled (missing or disabled configuration)")

    async def get_stock(self, product_ids: Iterable[str | UUID]) -> List[StockItem]:
        """Fetch stock items for provided product UUIDs.

        Returns empty list when service disabled.
        Raises httpx.HTTPError for transport problems (surface to caller for now).
        """
        if not self.enabled:
            return []
        ids = [str(p) for p in product_ids]
        if not ids:
            return []
        url = f"{self._base_url.rstrip('/')}/stock"
        try:
            resp = await self._client.post(url, json={"productIds": ids})
            resp.raise_for_status()
        except Exception as e:  # noqa: BLE001
            logger.warning("Stock API request failed: %s", e)
            return []
        data = resp.json()
        raw_items = data.get("items", []) if isinstance(data, dict) else []
        items: List[StockItem] = []
        for r in raw_items:
            try:
                items.append(
                    StockItem(
                        product_id=str(r.get("productId")),
                        producer_id=r.get("producerId"),
                        on_stock=int(r.get("onStock", 0)),
                        updated_at=r.get("updatedAt"),
                    )
                )
            except Exception:  # noqa: BLE001
                continue
        return items

    def format_stock_items(self, items: List[StockItem]) -> str:
        """Return a concise human-readable summary for prompt injection."""
        if not items:
            return ""
        lines: list[str] = ["Current stock levels (product_id -> on_stock)"]
        for it in items[:50]:  # safety cap
            lines.append(f"{it.product_id}: {it.on_stock}")
        return "\n".join(lines)

    async def close(self):  # pragma: no cover - simple resource cleanup
        try:
            await self._client.aclose()
        except Exception:
            pass

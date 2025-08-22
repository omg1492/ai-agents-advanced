"""Integration test for Stock custom tool.

Requires a running local stock API (api_stock) reachable via STOCK_API_URL.
Skips automatically if configuration missing or tool disabled.
"""
import os
import uuid
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.config_service import ConfigService

pytestmark = pytest.mark.integration


def _has_stock_tool():
    cfg = ConfigService().config
    st = getattr(cfg, "stock_tool", None)
    return bool(st and st.enabled and st.api_url)


class TestStockToolIntegration:
    def setup_method(self):  # skip if not configured
        if not _has_stock_tool():
            pytest.skip("Stock tool not enabled/configured; set STOCK_API_URL and STOCK_TOOL_ENABLED=true")

    def test_stock_tool_available(self):
        # Use a random UUID that likely has no stock row; test shouldn't fail, just empty context
        random_pid = str(uuid.uuid4())
        with TestClient(app) as client:
            r = client.post("/chat", json={"message": f"Can you check stock for product {random_pid}?"})
            assert r.status_code == 200, r.text
            data = r.json()
            assert "message" in data
            # Not asserting on stock content presence because unknown DB state; just ensure call succeeds.
            assert isinstance(data["message"], str) and len(data["message"]) > 0

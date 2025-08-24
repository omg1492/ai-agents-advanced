"""Integration tests for SemanticCacheService with real DB + OpenAI embeddings.

Run with: pytest -m integration tests/test_semantic_cache_integration.py
Skips automatically if required env vars or table are missing.
"""
from __future__ import annotations

import os
import pytest
import psycopg2

from src.services.semantic_cache_service import SemanticCacheService

pytestmark = pytest.mark.integration


def _has_table(conn_params: dict) -> bool:
    try:
        with psycopg2.connect(**conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.semantic_cache');")
                val = cur.fetchone()[0]
                return val is not None
    except Exception:
        return False


class TestSemanticCacheIntegration:
    @classmethod
    def setup_class(cls):  # noqa: D401
        required_db = ['PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD']
        if any(not os.getenv(k) for k in required_db):
            pytest.skip("Semantic cache integration requires PostgreSQL env vars")
        if not os.getenv("OPENAI_API_KEY") and not os.getenv("AZURE_OPENAI_API_KEY"):
            pytest.skip("OpenAI/Azure API key required for embeddings")
        # Ensure semantic cache enabled
        os.environ['SEMANTIC_CACHE_ENABLED'] = 'true'
        # Check table existence
        params = {
            "host": os.getenv("PGHOST"),
            "port": int(os.getenv("PGPORT", 5432)),
            "database": os.getenv("PGDATABASE"),
            "user": os.getenv("PGUSER"),
            "password": os.getenv("PGPASSWORD"),
        }
        if not _has_table(params):
            pytest.skip("semantic_cache table missing; run import_qna pipeline first")

    def setup_method(self):
        self.service = SemanticCacheService()
        if not self.service.enabled:
            pytest.skip("Semantic cache disabled in config")

    @pytest.mark.requires_api
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_cache_hit_hello(self):
        hit = await self.service.lookup("Hello!")
        assert hit is not None, "Expected a cache hit for 'Hello!'"
        assert hit.answer
        assert hit.similarity >= self.service.threshold

    @pytest.mark.requires_api
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_cache_miss_random(self):
        miss = await self.service.lookup("jsdovnfjepsd")
        assert miss is None, "Random string should not hit semantic cache"

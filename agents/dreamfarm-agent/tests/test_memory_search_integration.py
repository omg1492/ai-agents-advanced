"""Integration test for MemorySearchService (read‑only, no data mutation).

Strategy:
 - Skip if `conversation_summaries` table absent OR empty.
 - Pick one existing user_id present in the table.
 - Collect that user's thread_ids and a sample of other users' thread_ids (if any).
 - Run memory_search with a stub embedding (deterministic vector) so the query
     executes but similarity ordering is not asserted (model independent).
 - Assert all returned memories belong ONLY to the picked user and never leak
     a thread_id belonging to a different user.

This keeps the integration test side‑effect free (no INSERT/DELETE) and still
validates strict user fencing.
"""
from __future__ import annotations

import os
import json
import pytest
from sqlalchemy import create_engine, text

from src.services.memory_search_service import MemorySearchService
from src.services.config_service import ConfigService


def _engine():
    url = (
        f"postgresql://{os.getenv('PGUSER','admin')}:{os.getenv('PGPASSWORD','Admin12345678')}@"
        f"{os.getenv('PGHOST','localhost')}:{os.getenv('PGPORT','5432')}/{os.getenv('PGDATABASE','aidb')}"
    )
    return create_engine(url, echo=False)


def _has_table() -> bool:
    try:
        with _engine().connect() as conn:
            row = conn.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name='conversation_summaries'" )).fetchone()
            return bool(row)
    except Exception:
        return False

@pytest.mark.integration
@pytest.mark.asyncio
async def test_memory_search_user_fencing(monkeypatch):
    if not _has_table():
        pytest.skip("conversation_summaries table not present")

    # Discover one existing user with at least one summary row
    with _engine().connect() as conn:
        row = conn.execute(text("SELECT user_id FROM conversation_summaries LIMIT 1")).fetchone()
        if not row:
            pytest.skip("conversation_summaries table empty – nothing to test")
        picked_user = row.user_id
        user_threads = {
            r.thread_id
            for r in conn.execute(
                text("SELECT thread_id FROM conversation_summaries WHERE user_id = :u"), {"u": picked_user}
            ).fetchall()
        }
        other_threads = {
            r.thread_id
            for r in conn.execute(
                text("SELECT thread_id FROM conversation_summaries WHERE user_id <> :u LIMIT 50"), {"u": picked_user}
            ).fetchall()
        }

    assert user_threads, "Expected at least one thread for picked user"

    # Instantiate service & stub embedding (deterministic 2000-d vector)
    cfg = ConfigService().config
    service = MemorySearchService(cfg)
    if not service.enabled:
        pytest.skip("Memory search disabled in configuration")

    async def _stub_embed(_q):  # constant vector keeps similarity math simple
        return [1.0] + [0.0] * 1999

    monkeypatch.setattr(service, "_embed", _stub_embed)

    # Run search with generic query; request more than max to test clamp
    out_json = await service.execute({"query": "test memory search", "k": 25}, user_id=picked_user)
    payload = json.loads(out_json)
    memories = payload.get("memories", [])

    # Assertions: all thread_ids belong to picked_user; none from other users
    returned_ids = {m["thread_id"] for m in memories}
    assert returned_ids.issubset(user_threads)
    if other_threads:
        assert not (returned_ids & other_threads)
    # Similarity scores should be within [0,1]
    # Cosine similarity may be in [-1,1] (we compute 1 - distance where distance = 1 - cos_sim)
    for m in memories:
        assert -1.0 <= m["similarity_score"] <= 1.0
    if service._cfg:  # type: ignore[attr-defined]
        assert len(memories) <= service._cfg.max_results  # type: ignore[attr-defined]

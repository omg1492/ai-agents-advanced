"""Unit-style tests for new ConversationStore thread listing & metadata helpers.

Requires a reachable Postgres with `conversations_raw` DDL applied. Marked unit to
stay consistent with prior convention (fast, direct DB access, no FastAPI).
"""
import os
import time
import pytest

from src.services.conversation_store import ConversationStore
from src.services.config_service import ConfigService

pytestmark = pytest.mark.unit


def _ensure_env(monkeypatch):
    monkeypatch.setenv("PGHOST", os.getenv("PGHOST", "localhost"))
    monkeypatch.setenv("PGPORT", os.getenv("PGPORT", "5432"))
    monkeypatch.setenv("PGDATABASE", os.getenv("PGDATABASE", "aidb"))
    monkeypatch.setenv("PGUSER", os.getenv("PGUSER", "admin"))
    monkeypatch.setenv("PGPASSWORD", os.getenv("PGPASSWORD", "Admin12345678"))


def test_create_list_metadata(monkeypatch):
    _ensure_env(monkeypatch)
    store = ConversationStore(ConfigService().config)
    user_id = "test-user"
    t1 = "thread-list-1"
    t2 = "thread-list-2"

    try:
        # Create two empty threads
        store.create_thread(t1, user_id, "Title One")
        store.create_thread(t2, user_id, "Title Two")

        meta1 = store.get_thread_metadata(t1, user_id)
        meta2 = store.get_thread_metadata(t2, user_id)
        assert meta1 is not None and meta2 is not None
        assert meta1["title"] == "Title One"
        assert meta2["title"] == "Title Two"
        assert meta1["message_count"] == 0

        # Append a message to thread2 so it becomes most recently updated
        store.upsert_message(t2, user_id, store.build_message("user", "Hi from t2"))

        lst = store.list_threads(user_id, limit=10, offset=0)
        assert len([r for r in lst if r["thread_id"] in (t1, t2)]) >= 2
        # thread2 should appear before thread1 due to updated_at ordering
        order = [r["thread_id"] for r in lst if r["thread_id"] in (t1, t2)]
        assert order[0] == t2
        # Now update thread1 and ensure it bubbles to front
        time.sleep(1)  # ensure distinct timestamp
        store.upsert_message(t1, user_id, store.build_message("assistant", "Reply t1"))
        lst2 = store.list_threads(user_id, limit=10, offset=0)
        order2 = [r["thread_id"] for r in lst2 if r["thread_id"] in (t1, t2)]
        assert order2[0] == t1
        # After both have 1 message, message_count reflects that
        latest_meta1 = store.get_thread_metadata(t1, user_id)
        latest_meta2 = store.get_thread_metadata(t2, user_id)
        assert latest_meta1["message_count"] == 1
        assert latest_meta2["message_count"] == 1
    finally:
        # Cleanup rows
        store.delete_conversation(t1, user_id)
        store.delete_conversation(t2, user_id)

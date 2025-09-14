"""Unit tests for ConversationStore independent of FastAPI endpoints."""
import os
import pytest

from src.services.conversation_store import ConversationStore
from src.services.config_service import ConfigService

pytestmark = pytest.mark.unit


def test_conversation_store_append(monkeypatch):
    # Ensure DB env vars exist (use test defaults)
    monkeypatch.setenv("PGHOST", os.getenv("PGHOST", "localhost"))
    monkeypatch.setenv("PGPORT", os.getenv("PGPORT", "5432"))
    monkeypatch.setenv("PGDATABASE", os.getenv("PGDATABASE", "aidb"))
    monkeypatch.setenv("PGUSER", os.getenv("PGUSER", "admin"))
    monkeypatch.setenv("PGPASSWORD", os.getenv("PGPASSWORD", "Admin12345678"))

    store = ConversationStore(ConfigService().config)
    thread_id = "unit-thread-1"
    user_id = "test-user"

    try:
        # Replace messages to start deterministic
        store.replace_messages(thread_id, user_id, [])
        assert store.fetch_messages(thread_id, user_id) == []

        m1 = store.build_message("user", "Hello")
        store.upsert_message(thread_id, user_id, m1)
        msgs = store.fetch_messages(thread_id, user_id)
        assert len(msgs) == 1 and msgs[0]["role"] == "user"

        m2 = store.build_message("assistant", "Hi there")
        store.upsert_message(thread_id, user_id, m2)
        msgs = store.fetch_messages(thread_id, user_id)
        assert len(msgs) == 2 and msgs[1]["role"] == "assistant"

        deleted = store.delete_conversation(thread_id, user_id)
        assert deleted == 1
        assert store.fetch_messages(thread_id, user_id) == []
    finally:
        # Defensive cleanup in case assertions failed
        try:
            store.delete_conversation(thread_id, user_id)
        except Exception:
            pass

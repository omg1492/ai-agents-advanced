"""Integration tests for the streaming /threads/{id}/messages/stream endpoint."""

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.config_service import ConfigService


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def ensure_llm_configuration():
    """Skip test suite when mandatory OpenAI configuration is missing."""
    try:
        ConfigService()
    except Exception as exc:  # pragma: no cover - skip path only
        pytest.skip(f"Skipping streaming integration test: {exc}")


@pytest.fixture
def client(ensure_llm_configuration):
    with TestClient(app) as test_client:
        yield test_client


def test_streaming_tokens_and_history(client):
    """Verify the streaming endpoint produces tokens and records history."""
    # Create a thread
    res = client.post("/threads", json={"title": "Streaming Test"})
    assert res.status_code == 200
    thread_id = res.json()["thread_id"]

    # Stream a response from the real LLM backend
    collected = ""
    with client.stream(
        "POST",
        f"/threads/{thread_id}/messages/stream",
        json={"message": "Hi"},
    ) as resp:
        assert resp.status_code == 200
        for chunk in resp.iter_text():
            collected += chunk

    assert collected.strip(), "Expected non-empty streamed assistant text"

    # Messages endpoint should include both user and assistant messages
    msgs = client.get(f"/threads/{thread_id}/messages")
    assert msgs.status_code == 200
    payload = msgs.json()
    assert payload["thread_id"] == thread_id

    roles = [m["role"] for m in payload["messages"]]
    assert "user" in roles and "assistant" in roles

    assistant_messages = [m for m in payload["messages"] if m["role"] == "assistant"]
    assert assistant_messages, "Assistant message should be persisted"
    assert assistant_messages[-1]["content"].strip(), "Assistant response stored"
    assert assistant_messages[-1]["content"].strip() == collected.strip()

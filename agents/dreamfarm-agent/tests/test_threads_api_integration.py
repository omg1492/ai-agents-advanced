"""Integration tests for the /threads session flow using the real LLM backend."""

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
        pytest.skip(f"Skipping threads integration test: {exc}")


@pytest.fixture
def client(ensure_llm_configuration):
    with TestClient(app) as test_client:
        yield test_client


def test_thread_flow_create_send_list(client):
    """Exercise the thread lifecycle end-to-end against the real LLM."""
    # Create a thread
    create_res = client.post("/threads", json={"title": "API Test Thread"})
    assert create_res.status_code == 200
    thread = create_res.json()
    assert thread["thread_id"]
    thread_id = thread["thread_id"]

    # Send a message in that thread
    send_res = client.post(f"/threads/{thread_id}/messages", json={"message": "Hello"})
    assert send_res.status_code == 200
    send_payload = send_res.json()
    assistant_response = send_payload["assistant_response"].strip()
    assert assistant_response, "Assistant response should not be empty"
    assert send_payload["message_id"], "Message ID should be returned"

    # Fetch messages (should have user + assistant)
    msgs_res = client.get(f"/threads/{thread_id}/messages?limit=10&offset=0")
    assert msgs_res.status_code == 200
    msgs = msgs_res.json()
    assert msgs["thread_id"] == thread_id
    assert msgs["total_count"] >= 2
    assert len(msgs["messages"]) >= 2
    roles = [m["role"] for m in msgs["messages"]]
    assert "user" in roles and "assistant" in roles

    # The latest assistant message should match the synchronous response
    assistant_messages = [m for m in msgs["messages"] if m["role"] == "assistant"]
    assert assistant_messages, "Assistant history missing"
    assert assistant_messages[-1]["content"].strip() == assistant_response

    # Get thread info and ensure message_count updated
    get_res = client.get(f"/threads/{thread_id}")
    assert get_res.status_code == 200
    thread_info = get_res.json()
    assert thread_info["message_count"] == msgs["total_count"]

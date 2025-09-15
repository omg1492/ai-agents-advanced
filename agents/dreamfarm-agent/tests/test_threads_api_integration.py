"""Unit-level API tests for lightweight /threads session flow using TestClient.

These tests mock OpenAIService (no real API calls). Flow: create thread ->
send message -> fetch messages -> fetch thread info.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

from src.main import app
from src.services.openai_service import OpenAIService

pytestmark = pytest.mark.unit


class TestThreadsAPI:
    @pytest.fixture
    def mock_openai_service(self):
        service = Mock(spec=OpenAIService)
        service.generate_response = AsyncMock(return_value=(
            "Hi! I'm DreamFarm. Nice to meet you.",
            "resp_abc123",
        ))
        return service

    @pytest.fixture
    def client(self, mock_openai_service, monkeypatch):
        # Disable semantic cache & RAG for deterministic responses
        monkeypatch.setenv("SEMANTIC_CACHE_ENABLED", "false")
        monkeypatch.setenv("ENABLE_RAG", "false")
        with patch('src.main.OpenAIService', return_value=mock_openai_service):
            with TestClient(app) as test_client:
                yield test_client

    def test_thread_flow_create_send_list(self, client):
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
        assert (
            send_payload["assistant_response"].startswith("Hi!")
            or send_payload["assistant_response"].startswith("Hi there!")
        )

        # Fetch messages (should have user + assistant)
        msgs_res = client.get(f"/threads/{thread_id}/messages?limit=10&offset=0")
        assert msgs_res.status_code == 200
        msgs = msgs_res.json()
        assert msgs["thread_id"] == thread_id
        assert msgs["total_count"] >= 2
        assert len(msgs["messages"]) >= 2
        roles = [m["role"] for m in msgs["messages"]]
        assert "user" in roles and "assistant" in roles

        # Get thread info and ensure message_count updated
        get_res = client.get(f"/threads/{thread_id}")
        assert get_res.status_code == 200
        thread_info = get_res.json()
        assert thread_info["message_count"] == msgs["total_count"]

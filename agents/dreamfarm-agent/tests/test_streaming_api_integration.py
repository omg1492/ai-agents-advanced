"""Unit-level API tests for the streaming /threads/{id}/messages/stream endpoint.

These tests avoid real OpenAI/Azure calls by patching the app's OpenAI service
with a fake streaming client that yields text deltas and a final response id.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import app


pytestmark = pytest.mark.unit


class FakeStream:
    def __init__(self, events, final_id: str = "resp_stream_test_1"):
        self._events = events
        self._final_id = final_id

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def __aiter__(self):
        async def gen():
            for e in self._events:
                yield e
        return gen()

    async def get_final_response(self):
        return SimpleNamespace(id=self._final_id)


class FakeResponsesAPI:
    def __init__(self, events):
        self._events = events

    def stream(self, **kwargs):  # accepts arbitrary params
        return FakeStream(self._events)


class FakeOpenAIClient:
    def __init__(self, events):
        self.responses = FakeResponsesAPI(events)


class FakeOpenAIService:
    def __init__(self, events):
        self.client = FakeOpenAIClient(events)
        self.model_name = "gpt-5"


class TestStreamingAPI:
    @pytest.fixture
    def events(self):
        # Simulate two text delta events
        return [
            SimpleNamespace(type="response.output_text.delta", delta="Hello "),
            SimpleNamespace(type="response.output_text.delta", delta="world!"),
        ]

    @pytest.fixture
    def client(self, events):
        # Patch OpenAIService used in app startup to our fake that streams events
        with patch("src.main.OpenAIService", return_value=FakeOpenAIService(events)):
            with TestClient(app) as test_client:
                yield test_client

    def test_streaming_tokens_and_history(self, client):
        # Create a thread
        res = client.post("/threads", json={"title": "Streaming Test"})
        assert res.status_code == 200
        thread_id = res.json()["thread_id"]

        # Stream a response
        collected = ""
        with client.stream("POST", f"/threads/{thread_id}/messages/stream", json={"message": "Hi"}) as resp:
            assert resp.status_code == 200
            for chunk in resp.iter_text():
                collected += chunk

        # Full text should be accumulated from deltas
        assert collected == "Hello world!"

        # Messages endpoint should include both user and assistant messages
        msgs = client.get(f"/threads/{thread_id}/messages")
        assert msgs.status_code == 200
        payload = msgs.json()
        assert payload["thread_id"] == thread_id
        roles = [m["role"] for m in payload["messages"]]
        assert "user" in roles and "assistant" in roles
        # Assistant message should match collected text
        assert any(m["role"] == "assistant" and m["content"] == collected for m in payload["messages"]) 

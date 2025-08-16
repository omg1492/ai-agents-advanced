"""Live integration test for /threads hitting the real OpenAI/Azure OpenAI service.

Runs when selected with `-m integration`. Skips at runtime if required env/infra
is not available. It will create a thread, send a message, and validate a non-empty
assistant response.
"""

import os
import pytest
from fastapi.testclient import TestClient

from src.main import app

# Mark as integration; selection is via `pytest -m integration`
pytestmark = pytest.mark.integration


class TestLiveThreadsAPI:
    def setup_method(self):
        # Basic sanity: require credentials (skip if missing)
        # If OPENAI_BASE_URL is set, assume Azure-style config (next-gen v1)
        if os.getenv("OPENAI_BASE_URL"):
            required = [
                "OPENAI_API_KEY",
                "OPENAI_API_VERSION",  # usually 'preview'
                "OPENAI_MODEL",        # Azure deployment name
            ]
        else:
            # OpenAI hosted
            required = ["OPENAI_API_KEY", "OPENAI_MODEL"]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            pytest.skip(f"Missing provider env vars: {missing}")

    def test_live_thread_flow(self):
        # Use TestClient as a context manager so FastAPI startup/shutdown (lifespan) runs
        with TestClient(app) as client:
            # Create thread
            r = client.post("/threads", json={"title": "Live API Test"})
            assert r.status_code == 200, r.text
            thread = r.json()
            thread_id = thread["thread_id"]

            # Send a message
            r = client.post(f"/threads/{thread_id}/messages", json={"message": "Say hello from DreamFarm."})
            assert r.status_code == 200, r.text
            payload = r.json()
            # Validate non-empty assistant response
            assert isinstance(payload.get("assistant_response"), str)
            assert len(payload["assistant_response"]) > 0

            # Fetch messages
            r = client.get(f"/threads/{thread_id}/messages")
            assert r.status_code == 200, r.text
            msgs = r.json()
            assert msgs["thread_id"] == thread_id
            assert msgs["total_count"] >= 2

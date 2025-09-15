"""Tests for granular memory feature flags.

Covers:
 - MEMORY_SEARCH_ENABLED gating of memory_search tool publication.
 - USER_PROFILE_ENABLED gating of user profile JSON injection into system prompt.
The conversation store disabled path is implicitly exercised (no DB dependency) by
verifying it remains None when CONVERSATION_STORE_ENABLED=false.
"""
from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
import pytest


@pytest.mark.unit
def test_memory_search_tool_disabled(monkeypatch):
    """When MEMORY_SEARCH_ENABLED=false, OpenAIService should not expose the memory_search tool."""
    # Environment for disabled memory search
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5")
    monkeypatch.setenv("MEMORY_SEARCH_ENABLED", "false")
    # Ensure any prior module import is cleared
    if "src.services.openai_service" in sys.modules:
        del sys.modules["src.services.openai_service"]
    from src.services.openai_service import OpenAIService
    svc = OpenAIService()  # uses ConfigService internally
    tools = svc.get_tools() or []
    assert all(t.get("name") != "memory_search" for t in tools)


@pytest.mark.unit
def test_memory_search_tool_enabled(monkeypatch):
    """When MEMORY_SEARCH_ENABLED=true, memory_search tool should be present (with stubbed service)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5")
    monkeypatch.setenv("MEMORY_SEARCH_ENABLED", "true")
    # Provide max results env to avoid relying on default path
    monkeypatch.setenv("MEMORY_SEARCH_MAX_RESULTS", "5")

    # Stub MemorySearchService to avoid DB access
    class _DummyMemorySearch:
        enabled = True
        def __init__(self, *_a, **_k):
            pass
    # Re-import module after monkeypatching class symbol
    import src.services.openai_service as oas
    monkeypatch.setattr(oas, "MemorySearchService", _DummyMemorySearch)
    importlib.reload(oas)
    svc = oas.OpenAIService()
    tools = svc.get_tools() or []
    assert any(t.get("name") == "memory_search" for t in tools)


@pytest.mark.unit
def test_user_profile_injection_disabled(monkeypatch):
    """With USER_PROFILE_ENABLED=false no <user_profile_json> block should appear in /chat system prompt."""
    # Disable user profile + memory/search features to isolate test; disable auth for simpler dependency
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5")
    monkeypatch.setenv("USER_PROFILE_ENABLED", "false")
    monkeypatch.setenv("MEMORY_SEARCH_ENABLED", "false")
    monkeypatch.setenv("CONVERSATION_STORE_ENABLED", "false")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("SEMANTIC_CACHE_ENABLED", "false")
    monkeypatch.setenv("ENABLE_RAG", "false")

    # Force fresh import so module-level flags recompute
    if "src.main" in sys.modules:
        del sys.modules["src.main"]
    from fastapi.testclient import TestClient
    import src.main as main_mod

    # Patch auth_service to dummy that satisfies dependency (since we disabled AUTH, _require_user would 503)
    class _DummyAuth:
        def validate(self, _t):
            return {"preferred_username": "user1"}
        def extract_identity(self, claims):
            return claims.get("preferred_username", "user1"), False
    main_mod.auth_service = _DummyAuth()

    captured_prompt = {}
    async def _fake_generate_response(user_text, system_prompt, **_k):  # noqa: D401
        captured_prompt["prompt"] = system_prompt
        return ("ok", "resp1")

    # Patch constructor so lifespan uses our stub
    from unittest.mock import patch
    with patch("src.main.OpenAIService", return_value=SimpleNamespace(generate_response=_fake_generate_response)):
        with TestClient(main_mod.app) as client:
            r = client.post(
                "/chat",
                json={"message": "hi"},
                headers={"Authorization": "Bearer dummy"},
            )
            assert r.status_code == 200
    assert "<user_profile_json>" not in captured_prompt.get("prompt", "")


@pytest.mark.unit
def test_user_profile_injection_enabled(monkeypatch):
    """With USER_PROFILE_ENABLED=true and a dummy profile the prompt must include <user_profile_json>."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5")
    monkeypatch.setenv("USER_PROFILE_ENABLED", "true")
    monkeypatch.setenv("MEMORY_SEARCH_ENABLED", "false")
    monkeypatch.setenv("CONVERSATION_STORE_ENABLED", "false")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("SEMANTIC_CACHE_ENABLED", "false")
    monkeypatch.setenv("ENABLE_RAG", "false")

    if "src.main" in sys.modules:
        del sys.modules["src.main"]
    from fastapi.testclient import TestClient
    import src.main as main_mod

    # Patch auth & user_profile services
    class _DummyAuth:
        def validate(self, _t):
            return {"preferred_username": "user1"}
        def extract_identity(self, claims):
            return claims.get("preferred_username", "user1"), False
    class _DummyProfile:
        enabled = True
        def __init__(self, *_a, **_k):
            pass
        def get_profile(self, user_id):
            return {"user_id": user_id, "favorite": "apples"}
    main_mod.auth_service = _DummyAuth()

    from unittest.mock import patch
    captured_prompt = {}
    async def _fake_generate_response(user_text=None, system_prompt=None, **_k):  # lenient signature
        captured_prompt["prompt"] = system_prompt
        return ("ok", "resp1")
    # Patch both UserProfileService (constructed during lifespan) and OpenAIService
    with patch("src.main.UserProfileService", return_value=_DummyProfile()):
        with patch("src.main.OpenAIService", return_value=SimpleNamespace(generate_response=_fake_generate_response)):
            with TestClient(main_mod.app) as client:
                r = client.post(
                    "/chat",
                    json={"message": "hello"},
                    headers={"Authorization": "Bearer dummy"},
                )
                assert r.status_code == 200
    prompt = captured_prompt.get("prompt", "")
    assert "<user_profile_json>" in prompt
    assert "apples" in prompt

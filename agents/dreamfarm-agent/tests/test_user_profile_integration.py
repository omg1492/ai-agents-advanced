"""Integration test ensuring real user profile (user1) is injected into system prompt.

Skips if `user_profiles` table or user1 row absent. Uses patched OpenAIService to
capture the rendered system prompt without making real API calls.
"""
from __future__ import annotations

import os
import pytest
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient
from unittest.mock import patch

import importlib


def _engine():
    url = (
        f"postgresql://{os.getenv('PGUSER','admin')}:{os.getenv('PGPASSWORD','Admin12345678')}@"
        f"{os.getenv('PGHOST','localhost')}:{os.getenv('PGPORT','5432')}/{os.getenv('PGDATABASE','aidb')}"
    )
    return create_engine(url, echo=False)


def _has_user1_profile() -> bool:
    try:
        with _engine().connect() as conn:
            row = conn.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name='user_profiles'")).fetchone()
            if not row:
                return False
            row2 = conn.execute(text("SELECT 1 FROM user_profiles WHERE user_id='user1'" )).fetchone()
            return bool(row2)
    except Exception:
        return False


@pytest.mark.integration
def test_user_profile_real_injection(monkeypatch):
    if not _has_user1_profile():
        pytest.skip("user1 profile not present")

    # Enable user profile feature only, disable others for isolation
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5")
    monkeypatch.setenv("USER_PROFILE_ENABLED", "true")
    monkeypatch.setenv("MEMORY_SEARCH_ENABLED", "false")
    monkeypatch.setenv("CONVERSATION_STORE_ENABLED", "false")
    monkeypatch.setenv("SEMANTIC_CACHE_ENABLED", "false")
    monkeypatch.setenv("ENABLE_RAG", "false")
    # Disable auth complexity; we'll patch auth manually
    monkeypatch.setenv("AUTH_ENABLED", "false")

    # Force fresh import of main after env prepared
    if "src.main" in importlib.sys.modules:
        del importlib.sys.modules["src.main"]
    import src.main as main_mod

    class _DummyAuth:
        def validate(self, _t):
            return {"preferred_username": "user1"}
        def extract_identity(self, claims):
            return claims.get("preferred_username", "user1"), False
    main_mod.auth_service = _DummyAuth()

    captured = {}
    class DummySvc:
        async def generate_response(self, user_text=None, system_prompt=None, **_k):
            captured["system_prompt"] = system_prompt
            return ("ok", "resp_test")

    with patch("src.main.OpenAIService", return_value=DummySvc()):
        from src.main import app as app_instance
        with TestClient(app_instance) as client:
            r = client.post("/chat", json={"message": "hello"}, headers={"Authorization": "Bearer x"})
            assert r.status_code == 200

    prompt = captured.get("system_prompt", "")
    assert "<user_profile_json>" in prompt
    # Basic sanity: user1 identifier appears
    assert "user1" in prompt

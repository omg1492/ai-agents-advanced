"""Unit tests for UserProfileService.apply_patch.

Covers:
- Creation when no existing profile
- Deep set merge
- Append uniqueness (primitive only)
- Remove fields
- Malformed patch resilience (ignored gracefully)
"""
from __future__ import annotations

import json
import pytest
from types import SimpleNamespace

from src.services.user_profile_service import UserProfileService
from src.services.config_service import AppConfig, DatabaseConfig, OpenAIConfig, RagConfig, CodeInterpreterConfig


class DummyConn:
    def __init__(self, select_row, executed):
        self._select_row = select_row
        self.executed = executed
    def execute(self, sql, params):  # noqa: D401 simplified
        s = str(sql).lower()
        self.executed.append((s, params))
        if "select" in s and "from user_profiles" in s:
            # Simulate fetchone structure
            return SimpleNamespace(fetchone=lambda: self._select_row)
        return SimpleNamespace(fetchone=lambda: None)
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False

class DummyEngine:
    def __init__(self, select_row=None):
        self._select_row = select_row
        self.executed = []
    def connect(self):
        return DummyConn(self._select_row, self.executed)
    def begin(self):  # context manager for upsert
        return DummyConn(self._select_row, self.executed)


def build_cfg():
    return AppConfig(
        environment="test",
        cors_origins=["http://localhost"],
        log_level="INFO",
        reasoning_effort="minimal",
        openai=OpenAIConfig(api_key="sk-test", model_name="gpt-5"),
        db=DatabaseConfig(host="localhost", port=5432, database="aidb", user="admin", password="pwd"),
        rag=RagConfig(enabled=False, similarity_threshold=0.5, max_results=3),
        semantic_cache=None,
        code_interpreter=CodeInterpreterConfig(enabled=False, container_type="auto"),
        farmer_tools=None,
        tavily=None,
        stock_tool=None,
        auth=None,
        agentic_search=None,
        graph_search=None,
        memory_search=None,
        visualization_mcp=None,
    )


@pytest.mark.unit
def test_profile_creation_set_and_append(monkeypatch):
    cfg = build_cfg()
    svc = UserProfileService(cfg)
    dummy = DummyEngine(select_row=None)
    monkeypatch.setattr(svc, "engine", dummy)
    out = svc.apply_patch("u1", {"set": {"diet": {"vegetarian": True}}, "append": {"dislikes": ["kozí sýr", "celer"]}})
    assert out["diet"]["vegetarian"] is True
    assert set(out["dislikes"]) == {"kozí sýr", "celer"}
    # Ensure an INSERT/UPSERT happened
    assert any("insert into user_profiles" in sql for sql, _ in dummy.executed)


@pytest.mark.unit
def test_deep_merge_and_no_duplicates(monkeypatch):
    cfg = build_cfg()
    existing = {"diet": {"vegetarian": False, "allergens": ["lepek"]}, "dislikes": ["kozí sýr"]}
    svc = UserProfileService(cfg)
    dummy = DummyEngine(select_row=[json.dumps(existing)])
    monkeypatch.setattr(svc, "engine", dummy)
    out = svc.apply_patch("u2", {"set": {"diet": {"vegetarian": True}}, "append": {"dislikes": ["kozí sýr", "koriandr"]}})
    assert out["diet"]["vegetarian"] is True  # overwritten
    assert out["diet"]["allergens"] == ["lepek"]  # preserved
    assert out["dislikes"] == ["kozí sýr", "koriandr"]  # no duplicate first item


@pytest.mark.unit
def test_remove_field(monkeypatch):
    cfg = build_cfg()
    existing = {"notes": "temp", "dislikes": ["a"], "diet": {}}
    svc = UserProfileService(cfg)
    dummy = DummyEngine(select_row=[json.dumps(existing)])
    monkeypatch.setattr(svc, "engine", dummy)
    out = svc.apply_patch("u3", {"remove": ["notes"]})
    assert "notes" not in out
    assert "dislikes" in out


@pytest.mark.unit
def test_malformed_patch_resilience(monkeypatch):
    cfg = build_cfg()
    existing = {"x": 1}
    svc = UserProfileService(cfg)
    dummy = DummyEngine(select_row=[json.dumps(existing)])
    monkeypatch.setattr(svc, "engine", dummy)
    # set is not dict, append has non-list, remove not list
    out = svc.apply_patch("u4", {"set": 123, "append": {"arr": "oops"}, "remove": "bad"})
    assert out["x"] == 1  # unchanged
    # arr should not be created because append invalid
    assert "arr" not in out

"""Integration tests for memory_write_profile tool loop.

Approach: We simulate a Responses API cycle by crafting a fake response object
that contains a function_call for memory_write_profile, then invoke
OpenAIService.generate_response which should detect the call, execute the patch
(via injected UserProfileService with dummy engine), and submit tool output.

We stub the OpenAI client methods (responses.create & responses.submit_tool_outputs)
so no network access occurs. The second call returns an object with no further
function calls but an assistant message acknowledging completion.
"""
from __future__ import annotations

import json
import types
import pytest

from src.services.openai_service import OpenAIService
from src.services.user_profile_service import UserProfileService
from src.services.config_service import AppConfig, DatabaseConfig, OpenAIConfig, RagConfig, CodeInterpreterConfig


class DummyUserProfileEngine:
    def __init__(self):
        # start empty profile storage per user
        self.storage = {}
        self.executed = []
    def connect(self):
        return self  # simplistic
    def begin(self):
        return self
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False
    def execute(self, sql, params):  # minimal pattern sniff
        s = str(sql).lower()
        self.executed.append((s, params))
        if "select" in s and "from user_profiles" in s:
            user_id = params.get("uid")
            prof = self.storage.get(user_id)
            if prof is None:
                return types.SimpleNamespace(fetchone=lambda: None)
            return types.SimpleNamespace(fetchone=lambda: [json.dumps(prof)])
        if "insert into user_profiles" in s:
            user_id = params.get("uid")
            prof_json = params.get("profile")
            self.storage[user_id] = json.loads(prof_json)
        return types.SimpleNamespace(fetchone=lambda: None)


class DummyResp:
    def __init__(self, function_calls=None, text="", rid="r1"):
        self._function_calls = function_calls or []
        self.output = [
            types.SimpleNamespace(
                type="function_call", id=fc["id"], name=fc["name"], arguments=fc["arguments"]
            ) for fc in self._function_calls
        ]
        if text:
            # mimic final text output attr
            self.output_text = text
        self.id = rid


@pytest.mark.integration
@pytest.mark.asyncio
async def test_memory_write_profile_single_patch(monkeypatch):
    # Build minimal config with USER_PROFILE_ENABLED=true via env
    monkeypatch.setenv("USER_PROFILE_ENABLED", "true")
    cfg = AppConfig(
        environment="test",
        cors_origins=["*"],
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
    )
    ups = UserProfileService(cfg)
    engine = DummyUserProfileEngine()
    monkeypatch.setattr(ups, "engine", engine)

    svc = OpenAIService(cfg.openai, app_config=cfg, user_profile_service=ups)

    # First call: model emits function_call
    fc = [{"id": "tc1", "name": "memory_write_profile", "arguments": json.dumps({"patch": {"set": {"diet": {"vegetarian": True}}, "append": {"dislikes": ["kozí sýr"]}}})}]

    create_calls = []
    submit_calls = []

    class DummyResponsesClient:
        async def create(self, **kwargs):  # noqa: D401
            create_calls.append(kwargs)
            return DummyResp(function_calls=fc)
        async def submit_tool_outputs(self, response_id, tool_outputs):  # noqa: D401
            submit_calls.append((response_id, tool_outputs))
            # Return final assistant response with normal text
            return DummyResp(function_calls=[], text="Uloženo.", rid="r2")

    # Inject dummy client
    svc.client.responses = DummyResponsesClient()

    text, resp_id = await svc.generate_response("Pamatuj si moje preference.", user_id="u100")
    assert text == "Uloženo."  # final response text
    assert resp_id == "r2"
    # Verify profile stored
    stored = engine.storage.get("u100")
    assert stored["diet"]["vegetarian"] is True
    assert stored["dislikes"] == ["kozí sýr"]
    # Ensure tool outputs were submitted
    assert len(submit_calls) == 1
    # Tool output payload structure
    tool_output_payload = json.loads(submit_calls[0][1][0]["output"])
    assert tool_output_payload["applied"] is True
    assert "diet" in tool_output_payload["current"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_memory_write_profile_patch_diagnostics(monkeypatch):
    monkeypatch.setenv("USER_PROFILE_ENABLED", "true")
    cfg = AppConfig(
        environment="test",
        cors_origins=["*"],
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
    )
    ups = UserProfileService(cfg)
    engine = DummyUserProfileEngine()
    # Seed profile to test remove not_found
    engine.storage["u200"] = {"diet": {"vegetarian": True}, "dislikes": ["celer"]}
    monkeypatch.setattr(ups, "engine", engine)
    svc = OpenAIService(cfg.openai, app_config=cfg, user_profile_service=ups)

    # Patch attempts to remove non-existent field and append invalid value type
    patch_obj = {"patch": {"remove": ["missing_field"], "append": {"dislikes": ["celer", {"x":1}]}}}
    fc = [{"id": "tc2", "name": "memory_write_profile", "arguments": json.dumps(patch_obj)}]

    create_calls = []
    submit_calls = []

    class DummyResponsesClient2:
        async def create(self, **kwargs):
            create_calls.append(kwargs)
            return DummyResp(function_calls=fc)
        async def submit_tool_outputs(self, response_id, tool_outputs):
            submit_calls.append((response_id, tool_outputs))
            return DummyResp(function_calls=[], text="OK", rid="r3")

    svc.client.responses = DummyResponsesClient2()
    text, rid = await svc.generate_response("diagnostics", user_id="u200")
    assert text == "OK"
    tool_payload = json.loads(submit_calls[0][1][0]["output"])
    assert "not_found" in tool_payload and tool_payload["not_found"] == ["missing_field"]
    assert tool_payload["ignored"]["append"]  # contains reason for invalid value
    # full_profile should be present because of not_found/ignored
    assert "full_profile" in tool_payload


@pytest.mark.integration
@pytest.mark.asyncio
async def test_memory_write_profile_tool_not_present_when_disabled(monkeypatch):
    monkeypatch.delenv("USER_PROFILE_ENABLED", raising=False)
    monkeypatch.setenv("USER_PROFILE_ENABLED", "false")
    cfg = AppConfig(
        environment="test",
        cors_origins=["*"],
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
    )
    svc = OpenAIService(cfg.openai, app_config=cfg)
    tools = svc.get_tools() or []
    assert not any(t.get("name") == "memory_write_profile" for t in tools)

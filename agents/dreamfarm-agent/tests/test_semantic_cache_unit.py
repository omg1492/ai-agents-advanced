"""Unit tests for SemanticCacheService with mocked dependencies.

These tests avoid real network / DB by patching the OpenAI client and SQLAlchemy engine.
"""
from __future__ import annotations

import types
import pytest

from src.services.semantic_cache_service import SemanticCacheService, SemanticCacheHit
from src.services.config_service import AppConfig, DatabaseConfig, OpenAIConfig, RagConfig, SemanticCacheConfig, CodeInterpreterConfig


def build_config():
    return AppConfig(
        environment="test",
        cors_origins=["http://localhost:3000"],
        log_level="INFO",
        reasoning_effort="minimal",
        openai=OpenAIConfig(api_key="sk-test", model_name="gpt-5"),
        db=DatabaseConfig(host="localhost", port=5432, database="aidb", user="admin", password="pwd"),
        rag=RagConfig(enabled=False, similarity_threshold=0.5, max_results=3),
        semantic_cache=SemanticCacheConfig(enabled=True, similarity_threshold=0.9),
        code_interpreter=CodeInterpreterConfig(enabled=False, container_type="auto"),
        farmer_tools=None,
        tavily=None,
        stock_tool=None,
        auth=None,
        agentic_search=None,
        graph_search=None,
        memory_search=None,
    )


class DummyRow:
    def __init__(self, question, answer, sim):
        self.question = question
        self.answer = answer
        self.sim = sim


class DummyResult:
    def __init__(self, row):
        self._row = row
    def fetchone(self):
        return self._row


class DummyConn:
    def __init__(self, row):
        self._row = row
    def execute(self, *_, **__):
        return DummyResult(self._row)
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False


class DummyEngine:
    def __init__(self, row):
        self._row = row
    def connect(self):
        return DummyConn(self._row)


class DummyEmbeddingClient:
    class DataObj:
        def __init__(self, emb):
            self.embedding = emb
    class Resp:
        def __init__(self, emb):
            self.data = [DummyEmbeddingClient.DataObj(emb)]
    def __init__(self, emb):
        self._emb = emb
    def create(self, **_):
        return DummyEmbeddingClient.Resp(self._emb)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_semantic_cache_hit(monkeypatch):
    cfg = build_config()
    service = SemanticCacheService(cfg)
    # Patch engine and openai client
    monkeypatch.setattr(service, "engine", DummyEngine(DummyRow("Hello!", "Hi there!", 0.95)))
    dummy_client = types.SimpleNamespace(embeddings=DummyEmbeddingClient([0.1] * 2000))
    monkeypatch.setattr(service, "openai_client", dummy_client)
    hit = await service.lookup("Hello!")
    assert isinstance(hit, SemanticCacheHit)
    assert hit.answer.startswith("Hi")
    assert hit.similarity >= 0.9


@pytest.mark.unit
@pytest.mark.asyncio
async def test_semantic_cache_miss(monkeypatch):
    cfg = build_config()
    service = SemanticCacheService(cfg)
    # similarity below threshold
    monkeypatch.setattr(service, "engine", DummyEngine(None))
    dummy_client = types.SimpleNamespace(embeddings=DummyEmbeddingClient([0.2] * 2000))
    monkeypatch.setattr(service, "openai_client", dummy_client)
    miss = await service.lookup("random")
    assert miss is None

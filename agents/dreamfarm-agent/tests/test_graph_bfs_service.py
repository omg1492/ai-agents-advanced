import pytest

from src.services.graph_search_service import GraphSearchService
from src.services.config_service import ConfigService


def test_bfs_disabled_returns_empty(monkeypatch):
    monkeypatch.setenv("GRAPH_SEARCH_ENABLED", "false")
    svc = GraphSearchService(ConfigService().config)
    assert svc.enabled is False
    out = svc.bfs_taxonomy("some query", 5, user_is_vip=False)
    assert out == []

@pytest.mark.unit
def test_bfs_embedding_failure(monkeypatch):
    monkeypatch.setenv("GRAPH_SEARCH_ENABLED", "true")
    # Force embed to return empty (simulate failure)
    svc = GraphSearchService(ConfigService().config)
    svc._embed_query = lambda q: []  # type: ignore
    res = svc.bfs_taxonomy("abstract italian spicy snacks", 5, user_is_vip=False)
    assert res == []

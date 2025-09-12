import os
import pytest

from src.services.config_service import ConfigService
from src.services.graph_search_service import GraphSearchService


def ensure_graph_enabled():
    os.environ.setdefault("GRAPH_SEARCH_ENABLED", "true")
    os.environ.setdefault("AGE_GRAPH_NAME", "dreamfarm")


@pytest.mark.unit
def test_graph_service_init_disabled(monkeypatch):
    monkeypatch.setenv("GRAPH_SEARCH_ENABLED", "false")
    cfg = ConfigService().config
    svc = GraphSearchService(cfg)
    assert svc.enabled is False


@pytest.mark.unit
def test_graph_service_init_enabled(monkeypatch):
    ensure_graph_enabled()
    cfg = ConfigService().config
    svc = GraphSearchService(cfg)
    assert svc.enabled is True
    assert svc.graph_name == os.getenv("AGE_GRAPH_NAME", "dreamfarm")


@pytest.mark.unit
@pytest.mark.skipif(os.getenv("GRAPH_SEARCH_ENABLED", "false").lower() not in ("true", "1", "yes"), reason="Graph search disabled")
def test_dfs_similarity_empty(monkeypatch):
    # Use a random UUID unlikely to exist; expect empty list not exception
    ensure_graph_enabled()
    cfg = ConfigService().config
    svc = GraphSearchService(cfg)
    results = svc.dfs_similarity("00000000-0000-0000-0000-000000000000", 5, user_is_vip=False)
    assert isinstance(results, list)
    # Either empty or list of dicts
    for r in results:
        assert set(r.keys()) == {"product_id", "producer_name", "product_name", "product_description", "similarity_score"}
        assert 0 <= r["similarity_score"] <= 1

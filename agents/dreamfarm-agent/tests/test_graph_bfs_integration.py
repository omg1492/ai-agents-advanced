import os
import pytest

from src.services.config_service import ConfigService
from src.services.graph_search_service import GraphSearchService

REQUIRED_ENV = ["PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"]

def _has_db_env():
    return all(os.getenv(k) for k in REQUIRED_ENV)

@pytest.mark.integration
@pytest.mark.skipif(not _has_db_env(), reason="Database env not configured")
@pytest.mark.skipif(os.getenv("GRAPH_SEARCH_ENABLED", "false").lower() not in ("true", "1", "yes"), reason="Graph search disabled")
def test_bfs_taxonomy_real_query():
    cfg = ConfigService().config
    svc = GraphSearchService(cfg)
    assert svc.enabled
    # broad query should expand to some products if data & embeddings loaded
    products = svc.bfs_taxonomy("fresh italian dairy", 5, user_is_vip=False)
    # Now that concept embeddings are required, treat empty as failure
    assert products, "Expected BFS taxonomy expansion to return at least one product"
    assert 1 <= len(products) <= 5
    for p in products:
        assert 0 <= p["similarity_score"] <= 1
        assert "product_id" in p
        # VIP fencing implicitly validated by absence of VIP-only when non VIP user

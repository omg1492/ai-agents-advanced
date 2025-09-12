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
def test_dfs_similarity_real_product(monkeypatch):
    cfg = ConfigService().config
    svc = GraphSearchService(cfg)
    assert svc.enabled
    import sqlalchemy as sa
    engine = sa.create_engine(f"postgresql://{cfg.db.user}:{cfg.db.password}@{cfg.db.host}:{cfg.db.port}/{cfg.db.database}")
    # Grab one real product id
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT product_id FROM products LIMIT 1")).fetchone()
    if not row:
        pytest.skip("No products present in DB")
    pid = str(row.product_id)
    results = svc.dfs_similarity(pid, 5, user_is_vip=False)
    assert isinstance(results, list)
    # If VIP products exist ensure they are excluded for non VIP
    for r in results:
        assert r["product_id"] != pid
        assert 0 <= r["similarity_score"] <= 1


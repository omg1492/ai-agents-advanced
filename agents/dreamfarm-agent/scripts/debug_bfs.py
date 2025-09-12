"""Debug script for BFS taxonomy selection.
Run with: uv run python scripts/debug_bfs.py "fresh italian dairy"
"""
import os, sys, sqlalchemy as sa
from src.services.config_service import ConfigService
from src.services.graph_search_service import GraphSearchService

query = " ".join(sys.argv[1:]) or "fresh italian dairy"
cfg = ConfigService().config
svc = GraphSearchService(cfg)
print("Graph enabled:", svc.enabled)
print("Query:", query)

engine = svc.engine
with engine.connect() as conn:
    cnt = conn.execute(sa.text('SELECT count(*) FROM concept_embeddings')).scalar()
    print('concept_embeddings count:', cnt)

concepts = svc._select_semantic_concepts(query, top_n=8)
print("Selected concepts (type,id,score):", concepts)

products = svc.bfs_taxonomy(query, 5, user_is_vip=False)
print("BFS products:")
for p in products:
    print(p)

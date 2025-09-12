from src.services.config_service import ConfigService
from src.services.graph_search_service import GraphSearchService

cfg = ConfigService().config
svc = GraphSearchService(cfg)

print('Testing BFS taxonomy search...')
try:
    # Test with a query that should find some vegetable categories
    results = svc.bfs_taxonomy("fresh vegetables", k=5, user_is_vip=False)
    print(f'✅ BFS taxonomy search works! Got {len(results)} results')
    for i, result in enumerate(results):
        print(f'  {i+1}. {result.get("product_name", "N/A")} - {result.get("producer_name", "N/A")}')
except Exception as e:
    print(f'❌ BFS taxonomy search failed: {e}')
    import traceback
    traceback.print_exc()

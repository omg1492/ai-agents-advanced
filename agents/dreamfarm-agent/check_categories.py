from src.services.config_service import ConfigService
from src.services.graph_search_service import GraphSearchService
from sqlalchemy import text

cfg = ConfigService().config
svc = GraphSearchService(cfg)

print('Checking categories in database...')
with svc.engine.begin() as conn:
    query = """SELECT name, name_en, code 
               FROM ag_catalog.cypher('dreamfarm', $$
                   MATCH (c:Category) 
                   RETURN c.name, c.name_en, c.code 
                   LIMIT 10
               $$) AS (name ag_catalog.agtype, name_en ag_catalog.agtype, code ag_catalog.agtype)"""
    result = conn.execute(text(query)).fetchall()
    print('Categories in database:')
    for row in result:
        print(f'  {row}')

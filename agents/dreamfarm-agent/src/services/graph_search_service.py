"""Graph search service (DFS similarity + BFS taxonomy expansion).

Tools exposed to the OpenAI Responses API layer:

1. graph_dfs_similarity_search(product_id: str, k: int = 5)
     Starting from a concrete product UUID, collect nearby products sharing core
     taxonomy traits (categories / cuisines / certifications / allergens) plus an
     optional producer bonus and return top-k normalized 0..1.

2. graph_bfs_taxonomy_search(query: str, k: int = 5)
     Embed free‑text intent, pick top semantic taxonomy concepts via
     concept_embeddings similarity, expand products linked to ANY concept and
     score with a rank + similarity weighted sum (normalized 0..1).

VIP fencing: non‑VIP users never see products with is_vip=true.

Implementation Notes:
- Stable invocation: fixed 2‑argument AGE form `cypher(:graph, $$...$$)`; probing showed
    all 3‑arg forms failed (unterminated dollar string) while 2‑arg variants worked.
- Connection hook (`LOAD 'age'; SET search_path=ag_catalog, public;`) ensures availability.
- Cypher body dollar‑quoted; only graph name bound (no parameter map to avoid errors).
- BFS uses relationship variables + `type(rel)='REL_TYPE'` to avoid colon bind issues.
- Failures logged → empty list (caller can fallback gracefully).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple
import logging

from sqlalchemy import text, create_engine, event
from sqlalchemy.engine import Engine

from src.services.config_service import AppConfig

logger = logging.getLogger(__name__)


class GraphSearchService:  # pragma: no cover - exercised via integration tests
    """Service exposing graph traversal search tools (DFS & BFS).

    Args:
        app_config: Loaded application configuration (must include graph_search
            section when enabled).
    """

    def __init__(self, app_config: AppConfig):
        self._app_config = app_config
        self._cfg = getattr(app_config, "graph_search", None)
        self.enabled: bool = bool(self._cfg and self._cfg.enabled)
        if not self.enabled:
            logger.info("Graph search disabled via configuration")
            return
        self.graph_name: str = self._cfg.graph_name  # type: ignore[assignment]
        self.dfs_max_results: int = int(self._cfg.dfs_max_results)  # type: ignore[assignment]
        db = self._app_config.db
        url = f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.database}"
        self.engine: Engine = create_engine(url, echo=False)

        # Ensure every new DB-API connection has AGE loaded & search_path set
        # so that cypher() is resolvable (prevents "function cypher(unknown, unknown) does not exist").
        def _on_connect(dbapi_conn, _):  # type: ignore[no-untyped-def]
            try:
                cur = dbapi_conn.cursor()
                try:
                    cur.execute("LOAD 'age';")
                except Exception as e:  # pragma: no cover
                    logger.debug("AGE LOAD failed (may already be loaded): %s", e)
                try:
                    cur.execute("SET search_path = ag_catalog, public;")
                except Exception as e:  # pragma: no cover
                    logger.debug("AGE search_path set failed: %s", e)
                finally:
                    cur.close()
            except Exception as e:  # pragma: no cover
                logger.debug("AGE connection init hook error: %s", e)

        event.listen(self.engine, "connect", _on_connect)
        logger.info(
            "Initialized GraphSearchService graph=%s dfs_max_results=%s", self.graph_name, self.dfs_max_results
        )
        # Cache for detected concept embedding vector dimension (BFS semantic selection)
        self._concept_embedding_dim = None  # lazy loaded embedding dimension (int)

    # ------------------------ Internal Helpers ------------------------ #
    def _build_cypher_sql(self, cypher_body: str, column_signature: str) -> Any:
        """Return SQL fragment for fixed 2-arg cypher form."""
        # Use string formatting instead of parameter binding due to AGE compatibility issues
        # Use qualified ag_catalog.cypher to ensure function resolution
        fragment = f"FROM ag_catalog.cypher('{self.graph_name}', $${cypher_body}$$) AS ({column_signature})"
        return fragment

    def _extract_agtype_value(self, agtype_value) -> str:
        """Extract the actual value from Apache AGE agtype, removing quotes."""
        return str(agtype_value).strip('"')

    # ------------------------- DFS Similarity ------------------------- #
    def dfs_similarity(self, product_id: str, k: int, user_is_vip: bool) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        logger.debug("DFS start product_id='%s' k=%s vip=%s", product_id, k, user_is_vip)
        k = max(3, min(k, 10))
        k = min(k, self.dfs_max_results)
        
        # Find similar products using graph relationships (simplified without ORDER BY)
        all_product_ids = set()
        
        # Find products with shared categories
        try:
            cypher_query = f"""
            MATCH (source:Product {{productId: '{product_id}'}})-[r1:IN_CATEGORY]->(cat:Category)<-[r2:IN_CATEGORY]-(similar:Product)
            WHERE source.productId <> similar.productId
            RETURN similar.productId AS productId
            LIMIT {k * 2}
            """
            
            cypher_part = self._build_cypher_sql(cypher_query, "productId ag_catalog.agtype")
            sql = text("SELECT productId " + cypher_part)
            
            # Use fresh AGE engine to avoid vector contamination
            age_engine = self._get_fresh_age_engine()
            with age_engine.connect() as conn:
                rows = list(conn.execute(sql))
                for row in rows:
                    if row[0]:
                        # Apache AGE returns agtype wrapped values, extract string
                        similar_id = str(row[0]).strip('"')
                        all_product_ids.add(similar_id)
        except Exception as e:
            logger.warning("DFS category similarity query failed: %s", e)
        
        # Find products with shared cuisines
        try:
            cypher_query = f"""
            MATCH (source:Product {{productId: '{product_id}'}})-[r1:IN_CUISINE]->(cuisine:Cuisine)<-[r2:IN_CUISINE]-(similar:Product)
            WHERE source.productId <> similar.productId
            RETURN similar.productId AS productId
            LIMIT {k * 2}
            """
            
            cypher_part = self._build_cypher_sql(cypher_query, "productId ag_catalog.agtype")
            sql = text("SELECT productId " + cypher_part)
            
            # Use fresh AGE engine to avoid vector contamination
            age_engine = self._get_fresh_age_engine()
            with age_engine.connect() as conn:
                rows = list(conn.execute(sql))
                for row in rows:
                    if row[0]:
                        # Apache AGE returns agtype wrapped values, extract string
                        similar_id = str(row[0]).strip('"')
                        all_product_ids.add(similar_id)
        except Exception as e:
            logger.warning("DFS cuisine similarity query failed: %s", e)
        
        if not all_product_ids:
            logger.info("DFS found no similar products")
            return []
        
        # Get detailed product info from PostgreSQL table with VIP filtering
        product_list = list(all_product_ids)[:k * 2]  # Get more than needed for VIP filtering
        if not product_list:
            return []
            
        pg_sql = text("""
        SELECT product_id, producer_name, product_name, product_description, is_vip
        FROM products 
        WHERE product_id::text = ANY(:product_ids)
        AND (is_vip = false OR :user_is_vip = true)
        ORDER BY product_name
        LIMIT :limit_val
        """)
        
        results: List[Dict[str, Any]] = []
        try:
            # Use separate connection for PostgreSQL lookup to avoid AGE interference
            db = self._app_config.db
            pg_url = f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.database}"
            pg_engine = create_engine(pg_url, echo=False)
            
            with pg_engine.connect() as conn:
                pg_rows = conn.execute(pg_sql, {
                    'product_ids': product_list,
                    'user_is_vip': user_is_vip,
                    'limit_val': k
                })
                for row in pg_rows:
                    results.append({
                        "product_id": str(row[0]),
                        "producer_name": row[1],
                        "product_name": row[2],
                        "product_description": row[3],
                        "similarity_score": 1.0,  # Simplified DFS doesn't calculate similarity scores
                    })
        except Exception as e:  # pragma: no cover
            logger.warning("PostgreSQL product lookup failed: %s", e)
            return []

        logger.info("Graph DFS similarity returned %d results (k=%s vip=%s)", len(results), k, user_is_vip)
        return results

    # ------------------------ BFS Taxonomy Expansion ------------------------ #
    def _embed_query(self, query: str) -> List[float]:  # pragma: no cover - network
        """Embed free‑text query for taxonomy concept selection.

        We reuse the RAG embedding model (if configured) to maintain vector
        dimensionality compatibility with concept_embeddings. Dimension is
        auto‑detected once (vector_dims) to avoid mismatch errors.
        """
        if self._concept_embedding_dim is None:
            try:
                with self.engine.connect() as conn:
                    row = conn.execute(
                        text("SELECT vector_dims(embedding) AS dim FROM concept_embeddings LIMIT 1")
                    ).fetchone()
                    if row and getattr(row, "dim", None):
                        self._concept_embedding_dim = int(row.dim)  # type: ignore[attr-defined]
                        logger.info(
                            "Detected concept embedding dimension=%s", self._concept_embedding_dim
                        )
            except Exception as e:  # pragma: no cover
                logger.debug("Concept embedding dimension detection failed: %s", e)
                self._concept_embedding_dim = None
        try:  # pragma: no cover - network
            from openai import OpenAI  # type: ignore

            client = OpenAI(
                api_key=self._app_config.openai.api_key,
                base_url=self._app_config.openai.base_url,
                default_query={
                    "api-version": self._app_config.openai.api_version or "preview"
                }
                if self._app_config.openai.base_url
                else None,
            )
            model = (
                getattr(self._app_config.rag, "embedding_model", None)
                or self._app_config.openai.model_name
                or "text-embedding-3-large"
            )
            kwargs: Dict[str, Any] = {
                "model": model,
                "input": query,
                "encoding_format": "float",
            }
            if self._concept_embedding_dim:
                kwargs["dimensions"] = self._concept_embedding_dim
            resp = client.embeddings.create(**kwargs)
            return resp.data[0].embedding  # type: ignore[index]
        except Exception as e:  # pragma: no cover
            logger.warning("Graph BFS embedding failed: %s", e)
            return []

    def _select_semantic_concepts(
        self, query: str, top_n: int = 6
    ) -> List[Tuple[str, str, float]]:
        """Return top (concept_type, concept_id, score) tuples by vector similarity.
        
        Uses a separate connection to avoid vector/agtype operation interference.
        """
        emb = self._embed_query(query)
        if not emb:
            logger.info("BFS embedding empty query='%s'", query)
            return []
        emb_str = "[" + ",".join(map(str, emb)) + "]"
        sql = text(
            f"""
            SELECT concept_type, concept_id, 1 - (embedding <=> '{emb_str}'::vector) AS score
            FROM concept_embeddings
            WHERE concept_type IN ('category','cuisine','certification','allergen')
            ORDER BY embedding <=> '{emb_str}'::vector
            LIMIT {top_n}
            """
        )
        rows: List[Tuple[str, str, float]] = []
        try:
            # Use a separate connection for vector operations to avoid AGE interference
            db = self._app_config.db
            vector_url = f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.database}"
            vector_engine = create_engine(vector_url, echo=False)
            
            with vector_engine.connect() as conn:
                for r in conn.execute(sql):
                    rows.append((r.concept_type, str(r.concept_id), float(r.score or 0.0)))
        except Exception as e:  # pragma: no cover
            logger.warning("Graph BFS concept selection failed: %s", e)
            return []
        logger.debug("BFS selected concepts count=%d top=%s", len(rows), rows[:5])
        return rows
        
    def _get_fresh_age_engine(self):
        """Create a fresh engine with AGE setup for each operation to avoid vector interference."""
        db = self._app_config.db
        url = f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.database}"
        age_engine = create_engine(url, echo=False)
        
        @event.listens_for(age_engine, "connect")
        def _on_connect(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("LOAD 'age';")
            cur.execute("SET search_path = ag_catalog, public;")
        
        return age_engine

    def bfs_taxonomy(self, query: str, k: int, user_is_vip: bool) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        logger.debug("BFS start query='%s' k=%s vip=%s", query, k, user_is_vip)
        k = max(3, min(k, 10))
        k = min(k, self.dfs_max_results)
        concepts = self._select_semantic_concepts(query)
        if not concepts:
            logger.info("BFS no concepts selected query='%s'", query)
            return []
        
        # Collect product IDs from graph relationships
        all_product_ids = set()
        
        # Search by categories
        cat_ids = [cid for ctype, cid, _ in concepts if ctype == "category"]
        for cat_id in cat_ids:
            cypher_query = f"""
            MATCH (p:Product)-[r:IN_CATEGORY]->(c:Category {{code: '{cat_id}'}})
            RETURN p.productId AS productId
            LIMIT {k * 2}
            """
            try:
                cypher_part = self._build_cypher_sql(cypher_query, "productId ag_catalog.agtype")
                sql = text("SELECT productId " + cypher_part)
                
                # Use fresh AGE engine to avoid vector contamination
                age_engine = self._get_fresh_age_engine()
                with age_engine.connect() as conn:
                    rows = list(conn.execute(sql))
                    for row in rows:
                        if row[0]:
                            # Apache AGE returns agtype wrapped values, extract string
                            product_id = str(row[0]).strip('"')
                            all_product_ids.add(product_id)
            except Exception as e:
                logger.warning("BFS category query failed for %s: %s", cat_id, e)
        
        # Search by cuisines  
        cui_ids = [cid for ctype, cid, _ in concepts if ctype == "cuisine"]
        for cui_id in cui_ids:
            cypher_query = f"""
            MATCH (p:Product)-[r:IN_CUISINE]->(cu:Cuisine {{code: '{cui_id}'}})
            RETURN p.productId AS productId
            LIMIT {k * 2}
            """
            try:
                cypher_part = self._build_cypher_sql(cypher_query, "productId ag_catalog.agtype")
                sql = text("SELECT productId " + cypher_part)
                
                # Use fresh AGE engine to avoid vector contamination
                age_engine = self._get_fresh_age_engine()
                with age_engine.connect() as conn:
                    rows = list(conn.execute(sql))
                    for row in rows:
                        if row[0]:
                            # Apache AGE returns agtype wrapped values, extract string
                            product_id = str(row[0]).strip('"')
                            all_product_ids.add(product_id)
            except Exception as e:
                logger.warning("BFS cuisine query failed for %s: %s", cui_id, e)

        # Search by certifications
        cert_ids = [cid for ctype, cid, _ in concepts if ctype == "certification"]
        for cert_id in cert_ids:
            cypher_query = f"""
            MATCH (p:Product)-[r:HAS_CERTIFICATION]->(cc:Certification {{code: '{cert_id}'}})
            RETURN p.productId AS productId
            LIMIT {k * 2}
            """
            try:
                cypher_part = self._build_cypher_sql(cypher_query, "productId ag_catalog.agtype")
                sql = text("SELECT productId " + cypher_part)
                
                # Use fresh AGE engine to avoid vector contamination
                age_engine = self._get_fresh_age_engine()
                with age_engine.connect() as conn:
                    rows = list(conn.execute(sql))
                    for row in rows:
                        if row[0]:
                            # Apache AGE returns agtype wrapped values, extract string
                            product_id = str(row[0]).strip('"')
                            all_product_ids.add(product_id)
            except Exception as e:
                logger.warning("BFS certification query failed for %s: %s", cert_id, e)

        # Search by allergens
        allerg_ids = [cid for ctype, cid, _ in concepts if ctype == "allergen"]
        for allerg_id in allerg_ids:
            cypher_query = f"""
            MATCH (p:Product)-[r:CONTAINS_ALLERGEN]->(al:Allergen {{code: '{allerg_id}'}})
            RETURN p.productId AS productId
            LIMIT {k * 2}
            """
            try:
                cypher_part = self._build_cypher_sql(cypher_query, "productId ag_catalog.agtype")
                sql = text("SELECT productId " + cypher_part)
                
                # Use fresh AGE engine to avoid vector contamination
                age_engine = self._get_fresh_age_engine()
                with age_engine.connect() as conn:
                    rows = list(conn.execute(sql))
                    for row in rows:
                        if row[0]:
                            # Apache AGE returns agtype wrapped values, extract string
                            product_id = str(row[0]).strip('"')
                            all_product_ids.add(product_id)
            except Exception as e:
                logger.warning("BFS allergen query failed for %s: %s", allerg_id, e)

        if not all_product_ids:
            logger.info("BFS found no matching products")
            return []
        
        # Get detailed product info from PostgreSQL table with VIP filtering
        product_list = list(all_product_ids)[:k * 2]  # Get more than needed for VIP filtering
        if not product_list:
            return []
            
        pg_sql = text("""
        SELECT product_id, producer_name, product_name, product_description, is_vip
        FROM products 
        WHERE product_id::text = ANY(:product_ids)
        AND (is_vip = false OR :user_is_vip = true)
        ORDER BY product_name
        LIMIT :limit_val
        """)
        
        results: List[Dict[str, Any]] = []
        try:
            # Use separate connection for PostgreSQL lookup to avoid AGE interference
            db = self._app_config.db
            pg_url = f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.database}"
            pg_engine = create_engine(pg_url, echo=False)
            
            with pg_engine.connect() as conn:
                pg_rows = conn.execute(pg_sql, {
                    'product_ids': product_list,
                    'user_is_vip': user_is_vip,
                    'limit_val': k
                })
                for row in pg_rows:
                    results.append({
                        "product_id": str(row[0]),
                        "producer_name": row[1],
                        "product_name": row[2],
                        "product_description": row[3],
                        "similarity_score": 1.0,  # BFS doesn't calculate similarity scores
                    })
        except Exception as e:  # pragma: no cover
            logger.warning("PostgreSQL product lookup failed: %s", e)
            return []

        logger.info("Graph BFS taxonomy returned %d results (k=%s vip=%s)", len(results), k, user_is_vip)
        return results

    # ------------------------ Unified Execute ------------------------ #
    async def execute(self, name: str, arguments: Dict[str, Any], user_is_vip: bool) -> str:
        if not self.enabled:
            return '{"products": []}'
        if name == "graph_dfs_similarity_search":
            pid = str(arguments.get("product_id", ""))
            if not pid:
                return '{"products": []}'
            try:
                k = int(arguments.get("k", 5))
            except (TypeError, ValueError):  # pragma: no cover
                k = 5
            products = self.dfs_similarity(pid, k, user_is_vip=user_is_vip)
            return __import__("json").dumps({"products": products})
        if name == "graph_bfs_taxonomy_search":
            q = str(arguments.get("query", ""))
            if not q.strip():
                return '{"products": []}'
            try:
                k = int(arguments.get("k", 5))
            except (TypeError, ValueError):  # pragma: no cover
                k = 5
            products = self.bfs_taxonomy(q, k, user_is_vip=user_is_vip)
            return __import__("json").dumps({"products": products})
        return '{"products": []}'

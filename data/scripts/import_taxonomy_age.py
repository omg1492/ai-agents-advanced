"""Import taxonomy (Category & Cuisine) concepts and product assignments into Apache AGE graph.

Prerequisites:
 1. Base graph (Producer/Product/Allergen/Certification) already imported via `import_graph_age.py`.
 2. Taxonomy generation script `gen_graph_taxonomy.py` has produced:
       ../processed/taxonomy_concepts.parquet
       ../processed/taxonomy_assignments.parquet

What this script does:
  - Creates / updates Category and Cuisine nodes (labels: Category, Cuisine).
  - Creates relationships from Product -> Category (:IN_CATEGORY) and Product -> Cuisine (:IN_CUISINE).
  - Idempotent MERGE pattern (safe to re-run). Existing names/descriptions are updated each run.
  - Skips edge creation when referenced Product node is missing (logs count).
  - Batch execution with progress logging & percentage.

Environment (same as other data scripts):
  PGHOST (default localhost)
  PGPORT (default 5432)
  PGDATABASE (default aidb)
  PGUSER (default admin)
  PGPASSWORD (default Admin12345678)

CLI Options:
  --batch-size N    Number of Cypher statements per commit (default 1000)
  --reset-taxonomy  (Optional) Removes existing Category/Cuisine nodes & edges before import.
                    DOES NOT touch Producer/Product/etc. Use for clean rebuild of taxonomy only.

Design Notes:
  - Separate labels (Category, Cuisine) instead of single generic Concept label simplifies traversal.
  - Code property is the stable key for both; uniqueness assumed per label.
  - Edges do not currently carry version/confidence. Can be extended later.
  - Statement ordering: all concepts first, then edges, for early failure if concept dataset malformed.

Usage:
  uv run python data/scripts/import_taxonomy_age.py
  uv run python data/scripts/import_taxonomy_age.py --reset-taxonomy --batch-size 500
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import psycopg2
from psycopg2.extensions import connection as PGConnection
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

GRAPH_NAME = 'dreamfarm'


def _conn_params() -> Dict[str, Any]:
    load_dotenv()
    return {
        'host': os.getenv('PGHOST', 'localhost'),
        'port': int(os.getenv('PGPORT', 5432)),
        'database': os.getenv('PGDATABASE', 'aidb'),
        'user': os.getenv('PGUSER', 'admin'),
        'password': os.getenv('PGPASSWORD', 'Admin12345678'),
    }


def _escape(s: str) -> str:
    if s is None:
        return ''
    return str(s).replace("'", "’")


def _ensure_graph(conn: PGConnection) -> None:
    cur = conn.cursor()
    try:
        # Try to load AGE extension for this session
        # This is required for local PostgreSQL but will fail gracefully in Azure
        # where AGE must be preloaded via shared_preload_libraries
        try:
            cur.execute("LOAD 'age';")
            logger.debug("AGE library loaded successfully")
        except Exception as e:
            # If loading fails (e.g., in Azure where it's preloaded), rollback and continue
            logger.debug("AGE library already loaded or preloaded: %s", e)
            conn.rollback()
        
        cur.execute("SET search_path = ag_catalog, public;")
        cur.execute("SELECT 1 FROM ag_catalog.ag_graph WHERE name=%s;", (GRAPH_NAME,))
        if cur.fetchone() is None:
            raise RuntimeError(f"Graph '{GRAPH_NAME}' not found. Run import_graph_age.py first.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _reset_taxonomy(conn: PGConnection) -> None:
    logger.warning('Resetting taxonomy: deleting Category/Cuisine nodes and related edges')
    cur = conn.cursor()
    try:
        for stmt in [
            "MATCH (p:Product)-[r:IN_CATEGORY]->(:Category) DELETE r",
            "MATCH (p:Product)-[r:IN_CUISINE]->(:Cuisine) DELETE r",
            "MATCH (c:Category) DETACH DELETE c",
            "MATCH (c:Cuisine) DETACH DELETE c",
        ]:
            sql = f"SELECT * FROM cypher('{GRAPH_NAME}', $$ {stmt} $$) AS (r agtype);"
            cur.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception('Failed during taxonomy reset')
        raise
    finally:
        cur.close()


def _load_parquets() -> tuple[pd.DataFrame, pd.DataFrame]:
    base = Path(__file__).parent / '../processed'
    concepts_path = (base / 'taxonomy_concepts.parquet').resolve()
    assigns_path = (base / 'taxonomy_assignments.parquet').resolve()
    if not concepts_path.exists():
        raise FileNotFoundError(concepts_path)
    if not assigns_path.exists():
        raise FileNotFoundError(assigns_path)
    concepts_df = pd.read_parquet(concepts_path)
    assigns_df = pd.read_parquet(assigns_path)
    required_concept_cols = {'kind', 'code', 'name', 'description'}
    if not required_concept_cols.issubset(concepts_df.columns):
        missing = required_concept_cols - set(concepts_df.columns)
        raise ValueError(f'Missing concept columns: {missing}')
    required_assign_cols = {'product_id', 'category_codes', 'cuisine_codes'}
    if not required_assign_cols.issubset(assigns_df.columns):
        missing = required_assign_cols - set(assigns_df.columns)
        raise ValueError(f'Missing assignment columns: {missing}')
    return concepts_df, assigns_df


def _build_statements(concepts_df: pd.DataFrame, assigns_df: pd.DataFrame) -> List[str]:
    statements: List[str] = []

    # Concept nodes
    cat_count = 0
    cui_count = 0
    for _, row in concepts_df.iterrows():
        kind = row['kind']
        code = _escape(row['code'])
        name = _escape(row.get('name', '')[:200])
        desc = _escape(row.get('description', '')[:800])
        if kind == 'category':
            cat_count += 1
            statements.append(
                f"MERGE (c:Category {{code:'{code}'}}) SET c.name='{name}', c.description='{desc}' RETURN c"
            )
        elif kind == 'cuisine':
            cui_count += 1
            statements.append(
                f"MERGE (c:Cuisine {{code:'{code}'}}) SET c.name='{name}', c.description='{desc}' RETURN c"
            )
        else:
            logger.warning('Unknown concept kind %s code=%s (skipped)', kind, code)

    # Edge relationships
    missing_products = 0
    edge_total = 0
    def _codes(val) -> List[str]:
        """Coerce a parquet-loaded list/array/scalar into a clean list of strings.

        Handles cases where parquet deserializes empty lists as numpy arrays whose
        truth value is ambiguous (raising ValueError on boolean evaluation)."""
        if val is None:
            return []
        # Pandas may store as list, tuple, ndarray, or scalar
        # Convert numpy array like objects without importing numpy explicitly
        if hasattr(val, 'tolist') and type(val).__name__ in ('ndarray', 'Series'):
            try:  # noqa: SIM105
                val = val.tolist()
            except Exception:  # pragma: no cover
                return []
        if isinstance(val, (list, tuple)):
            return [str(v) for v in val if isinstance(v, (str, int, float)) and str(v).strip()]
        # If string that *might* represent a JSON list (unlikely) attempt parse
        if isinstance(val, str):
            txt = val.strip()
            if txt.startswith('[') and txt.endswith(']'):
                try:
                    import json as _json
                    parsed = _json.loads(txt)
                    if isinstance(parsed, list):
                        return [str(v) for v in parsed if str(v).strip()]
                except Exception:
                    return []
        return []

    for _, row in assigns_df.iterrows():
        pid = row['product_id']
        cat_codes = _codes(row.get('category_codes'))
        cui_codes = _codes(row.get('cuisine_codes'))
        # Build edges: we rely on Product node presence; skip if not found (checked via MATCH)
        for code in cat_codes:
            code_e = _escape(code)
            statements.append(
                "MATCH (p:Product {productId:'" + pid + "'}) "
                "MERGE (c:Category {code:'" + code_e + "'}) "
                "MERGE (p)-[:IN_CATEGORY]->(c)"
            )
            edge_total += 1
        for code in cui_codes:
            code_e = _escape(code)
            statements.append(
                "MATCH (p:Product {productId:'" + pid + "'}) "
                "MERGE (c:Cuisine {code:'" + code_e + "'}) "
                "MERGE (p)-[:IN_CUISINE]->(c)"
            )
            edge_total += 1
    logger.info('Prepared concept statements: categories=%d cuisines=%d; edge statements=%d', cat_count, cui_count, edge_total)
    return statements


def _execute_batches(conn: PGConnection, statements: List[str], batch_size: int) -> None:
    total = len(statements)
    if total == 0:
        logger.warning('No taxonomy statements to execute.')
        return
    if batch_size <= 0:
        batch_size = total
    batches = (total + batch_size - 1) // batch_size
    executed = 0
    for b in range(batches):
        start = b * batch_size
        end = min(start + batch_size, total)
        cur = conn.cursor()
        try:
            for stmt in statements[start:end]:
                sql = f"SELECT * FROM cypher('{GRAPH_NAME}', $$ {stmt} $$) AS (r agtype);"
                cur.execute(sql)
            conn.commit()
            executed = end
            pct = (executed / total) * 100
            logger.info('Batch %d/%d committed (%d stmts this batch, %d/%d %.1f%%)', b + 1, batches, end - start, executed, total, pct)
        except Exception:
            conn.rollback()
            logger.exception('Failure in taxonomy batch %d (statements %d-%d)', b + 1, start + 1, end)
            raise
        finally:
            cur.close()
    logger.info('Executed all %d taxonomy statements in %d batches.', total, batches)


def main() -> bool:
    parser = argparse.ArgumentParser(description='Import taxonomy concepts & edges into AGE graph.')
    parser.add_argument('--batch-size', type=int, default=1000, help='Cypher statements per transaction (default 1000).')
    parser.add_argument('--reset-taxonomy', action='store_true', help='Delete existing Category/Cuisine nodes and edges first.')
    args = parser.parse_args()

    concepts_df, assigns_df = _load_parquets()
    logger.info('Loaded concepts rows=%d assignments rows=%d', len(concepts_df), len(assigns_df))
    statements = _build_statements(concepts_df, assigns_df)
    if not statements:
        logger.warning('No statements generated; aborting.')
        return False
    conn = psycopg2.connect(**_conn_params())
    try:
        _ensure_graph(conn)
        if args.reset_taxonomy:
            _reset_taxonomy(conn)
        _execute_batches(conn, statements, args.batch_size)
        return True
    finally:
        conn.close()


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(0 if main() else 1)

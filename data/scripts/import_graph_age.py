"""Import Producers / Products / Certifications / Allergens into Apache AGE graph `dreamfarm`.

Creates (idempotently) the following vertex labels with core properties:
  - Producer {producerId, name, description}
  - Product  {productId, name, description}
  - Certification {certificationId, name, description}
  - Allergen {allergenId, name, safetyScore, description}

And relationship types:
  - (Producer)-[:PRODUCES]->(Product)
  - (Producer)-[:HAS_CERTIFICATION]->(Certification)
  - (Product)-[:CONTAINS_ALLERGEN]->(Allergen)

Source data:
  ../source_json/producers.json
  ../source_json/allergens.json
  ../source_json/certifications.json

The richer tabular product details (embedding, VIP flag, etc.) live in PostgreSQL tables
(`products`, `simple_products`). Graph nodes intentionally keep a minimal descriptive
subset so that graph traversals stay light. This script can be re‑run safely; it uses
MERGE to avoid duplicate nodes / edges and updates properties each time.

Environment (same as other data scripts):
  PGHOST (default localhost)
  PGPORT (default 5432)
  PGDATABASE (default aidb)
  PGUSER (default admin)
  PGPASSWORD (default Admin12345678)

Optional CLI flags:
    --reset        Drop & recreate the `dreamfarm` graph before import (DESTRUCTIVE)
    --batch-size N Execute Cypher statements in batches of N (commit per batch, default 1000). Batching shortens lock duration,
                   provides progress (% completed) and safer partial commits vs one very large (~15k) transaction.

Usage:
  uv run python data/scripts/import_graph_age.py          # idempotent upsert
  uv run python data/scripts/import_graph_age.py --reset  # rebuild graph then import

Validation / summary queries are executed at the end and printed to stdout.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

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


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def _escape(s: str) -> str:
    """Make string safe for Cypher single-quoted literals by swapping ASCII apostrophes with Unicode.

    Using U+2019 avoids the need for escape doubling which triggers a syntax issue observed with AGE 1.5.0
    on very long literals containing many consecutive escaped quotes.
    """
    return s.replace("'", "’")


def _ensure_graph(conn: PGConnection, reset: bool) -> None:
    cur = conn.cursor()
    try:
        # Ensure AGE extension is loaded for this session so cypher() is available
        try:
            cur.execute("LOAD 'age';")
            # Ensure ag_catalog is on search_path for simpler function resolution
            cur.execute("SET search_path = ag_catalog, public;")
        except Exception:
            logger.exception("Failed to LOAD 'age' extension. Ensure AGE is installed (see sql/extensions/02_install_age.sql).")
            raise
        if reset:
            logger.warning('Dropping & recreating graph %s (reset requested)', GRAPH_NAME)
            cur.execute("SELECT ag_catalog.drop_graph(%s, true) FROM ag_catalog.ag_graph WHERE name=%s;", (GRAPH_NAME, GRAPH_NAME))
        cur.execute("SELECT 1 FROM ag_catalog.ag_graph WHERE name=%s;", (GRAPH_NAME,))
        if cur.fetchone() is None:
            logger.info('Creating graph %s', GRAPH_NAME)
            cur.execute("SELECT ag_catalog.create_graph(%s);", (GRAPH_NAME,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _execute_cypher_batches(conn: PGConnection, statements: List[str], batch_size: int) -> None:
    """Execute Cypher statements in batches, committing after each batch.

    Rationale: A single transaction with ~15k individual MERGE executions risks long locks and harder
    recovery on failure. Batch commits (default 1000) provide progress visibility and partial success
    while keeping each transaction reasonably small.
    """
    total = len(statements)
    if total == 0:
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
            for idx, stmt in enumerate(statements[start:end], start=1):
                sql = f"SELECT * FROM cypher('{GRAPH_NAME}', $$ {stmt} $$) AS (r agtype);"
                cur.execute(sql)
            conn.commit()
            executed = end
            pct = (executed / total) * 100
            logger.info('Batch %d/%d committed (%d statements this batch, %d total, %.1f%%)',
                        b + 1, batches, end - start, executed, pct)
        except Exception:
            conn.rollback()
            snippet = statements[start + idx - 1][:200] if (end - start) and idx else '<none>'
            logger.exception('Failure in batch %d (statements %d-%d). Last statement snippet: %s',
                             b + 1, start + 1, end, snippet)
            raise
        finally:
            cur.close()
    logger.info('Executed all %d graph statements in %d batches (batch size %d).', total, batches, batch_size)


def _build_statements(data: list, allergens: dict, certs: dict) -> List[str]:
    statements: List[str] = []
    producers: List[dict] = data

    unique_cert_ids = set()
    unique_allergen_ids = set()
    product_count = 0

    for prod in producers:
        producer_id = prod['producerId']
        pname = _escape(prod['name'])
        pdesc = _escape(prod.get('description', '')[:1000])
        cert_id = prod.get('certificationId')

        statements.append(
            f"MERGE (p:Producer {{producerId: '{producer_id}'}}) SET p.name='{pname}', p.description='{pdesc}' RETURN p"
        )

        if cert_id and cert_id in certs:
            c = certs[cert_id]
            cname = _escape(c['name'])
            cdesc = _escape(c.get('description', '')[:800])
            statements.append(
                "MERGE (c:Certification {certificationId:'" + cert_id + "'}) SET c.name='" + cname + "', c.description='" + cdesc + "' "
                f"WITH c MATCH (p:Producer {{producerId:'{producer_id}'}}) MERGE (p)-[:HAS_CERTIFICATION]->(c)"
            )
            unique_cert_ids.add(cert_id)
        elif cert_id:
            logger.warning('Certification %s referenced by producer %s not found in certifications.json', cert_id, producer_id)

        for product in prod.get('products', []):
            product_count += 1
            prod_id = product['productId']
            prod_name = _escape(product['name'])
            prod_desc = _escape(product.get('description', '')[:800])
            statements.append(
                f"MERGE (pr:Product {{productId:'{prod_id}'}}) SET pr.name='{prod_name}', pr.description='{prod_desc}' "
                f"WITH pr MATCH (p:Producer {{producerId:'{producer_id}'}}) MERGE (p)-[:PRODUCES]->(pr)"
            )
            for allergen_id in product.get('allergenIds', []) or []:
                unique_allergen_ids.add(allergen_id)
                if allergen_id in allergens:
                    a = allergens[allergen_id]
                    aname = _escape(a['name'])
                    ascore = a.get('safetyScore')
                    adesc = _escape(a.get('description', '')[:500])
                    score_fragment = f", a.safetyScore={int(ascore)}" if isinstance(ascore, int) else ''
                    statements.append(
                        "MERGE (a:Allergen {allergenId:'" + allergen_id + "'}) SET a.name='" + aname + "', a.description='" + adesc + f"'{score_fragment} "
                        f"WITH a MATCH (pr:Product {{productId:'{prod_id}'}}) MERGE (pr)-[:CONTAINS_ALLERGEN]->(a)"
                    )
                else:
                    logger.warning('Allergen %s referenced by product %s not found in allergens.json', allergen_id, prod_id)

    logger.info('Prepared %d producers, %d products, %d unique certifications, %d unique allergens',
                len(producers), product_count, len(unique_cert_ids), len(unique_allergen_ids))
    return statements


def _load_support_maps(allergens_raw: list, certs_raw: list) -> tuple[dict, dict]:
    return ({a['allergenId']: a for a in allergens_raw}, {c['certificationId']: c for c in certs_raw})


def _summary_queries(conn: PGConnection) -> None:
    cur = conn.cursor()
    try:
        def run(q: str, cols: List[str]):
            cur.execute(
                f"SELECT * FROM cypher('{GRAPH_NAME}', $$ {q} $$) AS (" + ','.join(f"{c} agtype" for c in cols) + ");"
            )
            rows = cur.fetchall()
            logger.info('Result (%d rows) for: %s', len(rows), q)
            for r in rows[:5]:
                logger.info('  %s', r)

        run("MATCH (p:Producer) RETURN count(p) AS producers", ["producers"])
        run("MATCH (pr:Product) RETURN count(pr) AS products", ["products"])
        run("MATCH (c:Certification) RETURN count(c) AS certs", ["certs"])
        run("MATCH (a:Allergen) RETURN count(a) AS allergens", ["allergens"])
        run("MATCH (p:Producer)-[:PRODUCES]->(pr:Product) RETURN p.name AS producer, count(pr) AS product_count ORDER BY 2 DESC LIMIT 5", ["producer", "product_count"])
    finally:
        cur.close()


def main() -> bool:
    parser = argparse.ArgumentParser(description='Import graph entities into AGE graph.')
    parser.add_argument('--reset', action='store_true', help='Drop & recreate the graph before import')
    parser.add_argument('--batch-size', type=int, default=1000, help='Number of Cypher statements per transaction commit (default 1000)')
    args = parser.parse_args()

    base = Path(__file__).parent / '../source_json'
    producers_path = (base / 'producers.json').resolve()
    allergens_path = (base / 'allergens.json').resolve()
    certs_path = (base / 'certifications.json').resolve()

    logger.info('Loading JSON sources...')
    producers_data = _read_json(producers_path)
    allergens_raw = _read_json(allergens_path)
    certs_raw = _read_json(certs_path)
    allergens_map, certs_map = _load_support_maps(allergens_raw, certs_raw)

    statements = _build_statements(producers_data, allergens_map, certs_map)
    if not statements:
        logger.warning('No statements generated; aborting.')
        return False

    conn = psycopg2.connect(**_conn_params())
    try:
        _ensure_graph(conn, args.reset)
        _execute_cypher_batches(conn, statements, args.batch_size)
        _summary_queries(conn)
        return True
    finally:
        conn.close()


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(0 if main() else 1)

"""Import rich products dataset with embeddings + VIP flag into PostgreSQL `products` table.

Reads `../processed/products.parquet` produced by `embeddings_products.py` and loads into
`public.products` (recreating / truncating data for dev convenience). Ensures embeddings
are converted to pgvector literal syntax and batches inserts.

Environment:
  PGHOST (default localhost)
  PGPORT (default 5432)
  PGDATABASE (default aidb)
  PGUSER (default admin)
  PGPASSWORD (default Admin12345678)

Usage:
  uv run python data/scripts/import_products.py
"""
from __future__ import annotations
import logging
import os
from pathlib import Path
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _conn_params() -> dict:
    load_dotenv()
    return {
        'host': os.getenv('PGHOST', 'localhost'),
        'port': int(os.getenv('PGPORT', 5432)),
        'database': os.getenv('PGDATABASE', 'aidb'),
        'user': os.getenv('PGUSER', 'admin'),
        'password': os.getenv('PGPASSWORD', 'Admin12345678'),
    }


def _load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f'Parquet file not found: {path}')
    df = pd.read_parquet(path)
    logger.info('Loaded %d rows from %s', len(df), path)
    expected_cols = {'product_id','producer_id','producer_name','product_name','product_description','combined_text','is_vip','embedding'}
    missing = expected_cols - set(df.columns)
    if missing:
        raise ValueError(f'Missing expected columns: {missing}')
    return df


def _prepare_rows(df: pd.DataFrame) -> list[tuple]:
    rows = []
    dropped = 0
    # Detect and log actual embedding dimension for the first non-null embedding
    detected_dim = None
    for _, r in df.iterrows():
        emb = r['embedding']
        # Explicit validation: must be sequence length 2000
        if emb is None:
            dropped += 1
            continue
        # Some parquet readers may give numpy arrays or lists
        try:
            length = len(emb)  # type: ignore[arg-type]
        except Exception:
            dropped += 1
            continue
        if detected_dim is None:
            detected_dim = length
            logger.info('Detected embedding dimension=%d (DB expects 2000)', detected_dim)
        if length != 2000:
            dropped += 1
            continue
        # Convert each value to float defensively
        emb_str = '[' + ','.join(str(float(v)) for v in emb) + ']'
        rows.append((
            r['product_id'], r['producer_id'], r['producer_name'], r['product_name'],
            r['product_description'], r['combined_text'], bool(r['is_vip']), emb_str
        ))
    if dropped:
        logger.warning('Skipped %d rows with missing/invalid embeddings', dropped)
    logger.info('Prepared %d rows for insert', len(rows))
    return rows


def _import(rows: list[tuple], params: dict) -> bool:
    if not rows:
        logger.warning('No rows to import')
        return False
    conn = psycopg2.connect(**params)
    cur = conn.cursor()
    try:
        logger.info('Truncating products table (dev reset)...')
        cur.execute('TRUNCATE TABLE products RESTART IDENTITY;')
        conn.commit()
        insert_sql = (
            'INSERT INTO products ('
            'product_id, producer_id, producer_name, product_name, '
            'product_description, combined_text, is_vip, embedding) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s::vector)'
        )
        execute_batch(cur, insert_sql, rows, page_size=200)
        conn.commit()
        cur.execute('SELECT COUNT(*) FROM products;')
        count = cur.fetchone()[0]
        logger.info('Imported %d rows into products', count)
        return count == len(rows)
    except Exception:
        conn.rollback()
        raise
    finally:
        # Ensure both cursor and connection close even on failure
        try:
            if cur:
                cur.close()
        finally:
            if conn:
                conn.close()


def main() -> bool:
    try:
        base_dir = Path(__file__).parent
        parquet_path = (base_dir / '../processed/products.parquet').resolve()
        df = _load_parquet(parquet_path)
        rows = _prepare_rows(df)
        ok = _import(rows, _conn_params())
        return ok
    except Exception as e:
        logger.exception('Products import failed: %s', e)
        return False


if __name__ == '__main__':
    raise SystemExit(0 if main() else 1)

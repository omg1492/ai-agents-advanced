"""
Import stock data from JSON into the PostgreSQL `stock` table.

This script loads `data/source_json/stock.json` and imports it into the
PostgreSQL `stock` table. It truncates the table first (overwrite existing).

Expected JSON item shape (per generator):
{
  "producerId": "<uuid>",
  "productId": "<uuid>",
  "onStock": <int>
}

If any record is missing required fields, it's skipped with a warning.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import psycopg2
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_connection_params() -> dict:
    """Load PostgreSQL connection parameters from environment variables.

    Returns:
        Dictionary with connection parameters compatible with psycopg2.
    """
    load_dotenv()
    return {
        'host': os.getenv('PGHOST', 'localhost'),
        'port': int(os.getenv('PGPORT', 5432)),
        'database': os.getenv('PGDATABASE', 'aidb'),
        'user': os.getenv('PGUSER', 'admin'),
        'password': os.getenv('PGPASSWORD', 'Admin12345678'),
    }


def load_stock_json(path: Path) -> List[Dict[str, Any]]:
    """Load stock records from JSON file.

    Args:
        path: Absolute path to `stock.json`.

    Returns:
        List of stock dicts.

    Raises:
        FileNotFoundError: When the file doesn't exist.
        ValueError: When the file is empty or not a list.
    """
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected stock.json to contain a JSON array")
    if not data:
        raise ValueError("stock.json is empty")
    return data


def prepare_rows(items: List[Dict[str, Any]]) -> Tuple[List[Tuple[str, str, int]], int]:
    """Validate and map raw JSON items to DB rows.

    Args:
        items: Raw records from JSON.

    Returns:
        (rows, skipped) where rows is a list of tuples (producer_id, product_id, on_stock)
        and skipped is the number of records dropped due to validation.
    """
    rows: List[Tuple[str, str, int]] = []
    skipped = 0
    for i, rec in enumerate(items):
        producer_id = rec.get('producerId')
        product_id = rec.get('productId')
        on_stock = rec.get('onStock')

        if not producer_id or not product_id or on_stock is None:
            skipped += 1
            if i < 5:  # limit log noise
                logger.warning("Skipping record missing required fields: %s", rec)
            continue

        try:
            on_stock_int = int(on_stock)
        except (TypeError, ValueError):
            skipped += 1
            if i < 5:
                logger.warning("Skipping record with invalid onStock value: %s", rec)
            continue

        rows.append((producer_id, product_id, on_stock_int))
    return rows, skipped


def import_rows(rows: List[Tuple[str, str, int]], conn_params: dict, batch_size: int = 1000) -> int:
    """Import prepared rows into the `stock` table, truncating first.

    Args:
        rows: Prepared rows (producer_id, product_id, on_stock).
        conn_params: psycopg2 connection parameters.
        batch_size: Number of rows per batch.

    Returns:
        Number of successfully imported rows.
    """
    conn = None
    imported = 0
    try:
        logger.info("Connecting to PostgreSQL database...")
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()

        logger.info("Truncating stock table (overwrite mode)...")
        cur.execute("TRUNCATE TABLE stock;")
        conn.commit()

        insert_sql = (
            "INSERT INTO stock (producer_id, product_id, on_stock) "
            "VALUES (%s::uuid, %s::uuid, %s)"
        )

        total = len(rows)
        if total == 0:
            logger.info("No valid rows to import.")
            return 0

        logger.info("Starting import: %s rows in batches of %s", total, batch_size)
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch = rows[start:end]
            try:
                cur.executemany(insert_sql, batch)
                conn.commit()
                imported += len(batch)
                logger.info("Imported %s/%s (%.1f%%)", imported, total, (imported / total) * 100)
            except Exception as e:
                conn.rollback()
                logger.error("Failed to import batch %s-%s: %s", start, end, e)
                # continue with next batch

        cur.close()
        conn.close()
        logger.info("Database connection closed")
        return imported
    except Exception as e:
        logger.error("Import error: %s", e)
        if conn:
            try:
                conn.close()
            except Exception:  # pragma: no cover
                pass
        return imported


def main() -> bool:
    """Entrypoint to import stock JSON into PostgreSQL.

    Returns:
        True if import finished without fatal errors, False otherwise.
    """
    try:
        script_dir = Path(__file__).parent
        json_path = script_dir.parent / 'source_json' / 'stock.json'

        logger.info("Loading stock data from %s", json_path)
        raw_items = load_stock_json(json_path)
        total_raw = len(raw_items)

        rows, skipped = prepare_rows(raw_items)
        logger.info("Prepared %s rows (skipped %s malformed of %s)", len(rows), skipped, total_raw)

        conn_params = load_connection_params()
        imported = import_rows(rows, conn_params)

        logger.info("✅ Import summary: %s prepared, %s imported, %s skipped", len(rows), imported, skipped)
        return True
    except Exception as e:
        logger.error("❌ Stock import failed: %s", e)
        return False


if __name__ == "__main__":
    ok = main()
    raise SystemExit(0 if ok else 1)

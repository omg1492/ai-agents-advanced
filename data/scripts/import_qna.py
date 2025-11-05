"""Import Q&A semantic cache embeddings into PostgreSQL semantic_cache table.

Pipeline:
1. Load ../processed/qna_embeddings.parquet (question, answer, embedding)
2. Truncate semantic_cache (development overwrite) and reset identity
3. Insert rows (question, answer, embedding::vector)

Environment variables (unified): PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD.

Usage:
    uv run import_qna.py
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable, List, Any
from collections.abc import Sequence as SeqABC

import pandas as pd
import psycopg2
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_connection_params() -> dict:
    """Return PostgreSQL connection parameters from env."""
    load_dotenv()
    return {
        "host": os.getenv("PGHOST", "localhost"),
        "port": int(os.getenv("PGPORT", 5432)),
        "database": os.getenv("PGDATABASE", "aidb"),
        "user": os.getenv("PGUSER", "admin"),
        "password": os.getenv("PGPASSWORD", "Admin12345678"),
    }


def load_qna_parquet(path: Path) -> pd.DataFrame:
    """Load Q&A parquet file; validate required columns."""
    if not path.exists():
        raise FileNotFoundError(f"Parquet file not found: {path}")
    df = pd.read_parquet(path)
    required = {"question", "answer", "embedding"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Parquet missing required columns: {missing}")
    return df


def to_vector_literal(vec: List[float]) -> str:
    """Convert list of floats to pgvector literal."""
    return "[" + ",".join(f"{float(x):.10f}" for x in vec) + "]"


def iter_prepared_rows(df: pd.DataFrame) -> Iterable[tuple[str, str, str]]:
    """Yield (question, answer, vector_literal) rows.

    Accept any non-string sequence (including numpy ndarray). Log a few skip reasons
    to help troubleshooting if count unexpectedly zero.
    """
    skipped_empty = skipped_type = 0
    for i, row in df.iterrows():
        q = str(row["question"]).strip()
        a = str(row["answer"]).strip()
        emb: Any = row["embedding"]
        if not q or not a or emb is None:
            if i < 5:
                logger.debug("Skipping row %d: missing q/a or embedding", i)
            continue
        # Check if it's a valid embedding: must have __len__ and __iter__, but not be string/bytes
        if isinstance(emb, (str, bytes)) or not (hasattr(emb, "__len__") and hasattr(emb, "__iter__")):
            skipped_type += 1
            if skipped_type <= 3:
                logger.debug("Skipping row %d: embedding type %r not sequence", i, type(emb))
            continue
        emb_list = list(emb)
        if not emb_list:
            skipped_empty += 1
            if skipped_empty <= 3:
                logger.debug("Skipping row %d: empty embedding sequence", i)
            continue
        yield (q, a, to_vector_literal(emb_list))
    if skipped_type or skipped_empty:
        logger.info(
            "Skipped embeddings (type=%d, empty=%d). If all rows skipped, parquet embedding dtype may be unexpected.",
            skipped_type,
            skipped_empty,
        )


def import_qna(df: pd.DataFrame, conn_params: dict, batch_size: int = 200) -> int:
    """Import Q&A rows into semantic_cache, truncating first.

    Returns number of inserted rows.
    """
    conn = None
    inserted = 0
    try:
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()
        logger.info("Truncating semantic_cache table...")
        cur.execute("TRUNCATE TABLE semantic_cache RESTART IDENTITY;")
        conn.commit()

        sql = (
            "INSERT INTO semantic_cache (question, answer, embedding) "
            "VALUES (%s, %s, %s::vector)"
        )
        batch: list[tuple[str, str, str]] = []
        for row in iter_prepared_rows(df):
            batch.append(row)
            if len(batch) >= batch_size:
                cur.executemany(sql, batch)
                conn.commit()
                inserted += len(batch)
                logger.info("Imported %d rows", inserted)
                batch.clear()
        if batch:
            cur.executemany(sql, batch)
            conn.commit()
            inserted += len(batch)
        cur.close()
        logger.info("Final import count: %d", inserted)
        return inserted
    except Exception:
        logger.exception("Import failed")
        if conn:
            try:
                conn.rollback()
            except Exception:  # pragma: no cover
                pass
        return inserted
    finally:
        if conn:
            try:
                conn.close()
            except Exception:  # pragma: no cover
                pass


def main() -> bool:
    try:
        base_dir = Path(__file__).parent
        parquet_path = (base_dir / "../processed/qna_embeddings.parquet").resolve()
        df = load_qna_parquet(parquet_path)
        logger.info("Loaded %d Q&A rows from %s", len(df), parquet_path)
        conn_params = load_connection_params()
        inserted = import_qna(df, conn_params)
        logger.info("✅ Q&A semantic cache import inserted %d rows", inserted)
        return True
    except Exception as e:
        logger.error("❌ Q&A import failed: %s", e)
        return False


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)

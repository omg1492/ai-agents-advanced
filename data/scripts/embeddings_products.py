"""Generate embeddings for rich products catalog with VIP fencing flag.

This script builds a flattened products dataset from `../source_json/producers.json`,
constructs a `combined_text` field, randomly marks ~10% of rows as VIP (`is_vip=True`),
requests embeddings (fixed 2000 dimensions) via unified OpenAI/Azure configuration and stores the
result to `../processed/products.parquet` (dimension matches `products.embedding vector(2000)`).

Environment (shared / unified):
    OPENAI_API_KEY (required)
    OPENAI_BASE_URL (optional Azure; must end with /openai/v1/)
    OPENAI_API_VERSION (optional Azure)
    OPENAI_EMBEDDING_MODEL (default text-embedding-3-large)
    PRODUCT_VIP_RATIO (optional, default 0.10)

Usage (from repo root):
  uv run python data/scripts/embeddings_products.py

The output parquet columns:
  product_id, producer_id, producer_name, product_name, product_description,
  combined_text, is_vip, embedding (list[float])
"""
from __future__ import annotations
import json
import logging
import os
import random
from pathlib import Path
from typing import Any, Sequence
from dotenv import load_dotenv
import pandas as pd
from openai import OpenAI, APIStatusError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, before_sleep_log

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in (429, 500, 502, 503, 504)
    return False


def _init_client() -> tuple[OpenAI, str]:
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError('OPENAI_API_KEY not set')
    base_url = os.getenv('OPENAI_BASE_URL')
    api_version = os.getenv('OPENAI_API_VERSION') or '2024-10-21'
    model = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large')
    default_query = {'api-version': api_version} if base_url else None
    client = OpenAI(api_key=api_key, base_url=base_url, default_query=default_query)
    return client, model


@retry(stop=stop_after_attempt(6), wait=wait_exponential(multiplier=1, min=2, max=60),
       retry=retry_if_exception(_is_retryable), before_sleep=before_sleep_log(logger, logging.WARNING), reraise=True)
def _embed_batch(client: OpenAI, model: str, texts: Sequence[str], dimensions: int) -> list[list[float]]:
    """Embed a batch of texts with explicit dimensions (2000)."""
    resp = client.embeddings.create(model=model, input=list(texts), dimensions=dimensions)
    vectors = [d.embedding for d in resp.data]
    return vectors


def _flatten_products(data: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for producer in data:
        producer_id = producer.get('producerId') or producer.get('producer_id')
        producer_name = producer.get('name') or producer.get('producerName')
        for product in producer.get('products', []) or []:
            rows.append({
                'product_id': product.get('productId') or product.get('id'),
                'producer_id': producer_id,
                'producer_name': producer_name,
                'product_name': product.get('name') or product.get('productName'),
                'product_description': product.get('description') or product.get('productDescription') or ''
            })
    df = pd.DataFrame(rows)
    logger.info('Flattened %d products from %d producers', len(df), len(data))
    return df


def _add_combined(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ['producer_name', 'product_name', 'product_description']:
        df[col] = df[col].fillna('').astype(str)
    df['combined_text'] = (
        'PRODUCER: ' + df['producer_name'].str.strip() +
        ' | PRODUCT: ' + df['product_name'].str.strip() +
        ' | DESCRIPTION: ' + df['product_description'].str.strip()
    )
    return df


def _assign_vip(df: pd.DataFrame, ratio: float) -> pd.DataFrame:
    df = df.copy()
    if ratio <= 0:
        df['is_vip'] = False
        return df
    rng = random.Random(42)  # deterministic for reproducibility
    flags = [rng.random() < ratio for _ in range(len(df))]
    df['is_vip'] = flags
    vip_count = sum(flags)
    total = len(df)
    pct = (100.0 * vip_count / total) if total else 0.0
    logger.info('Assigned VIP to %d / %d products (%.2f%%)', vip_count, total, pct)
    return df


def _generate_embeddings(df: pd.DataFrame, client: OpenAI, model: str, *, batch: int = 64) -> pd.DataFrame:
    texts = df['combined_text'].tolist()
    results: list[list[float] | None] = [None] * len(texts)
    target_dim = 2000
    for start in range(0, len(texts), batch):
        end = min(start + batch, len(texts))
        batch_vecs = _embed_batch(client, model, texts[start:end], dimensions=target_dim)
        for i, v in enumerate(batch_vecs):
            results[start + i] = v
        if end % 200 == 0 or end == len(texts):
            logger.info('Embedded %d/%d', end, len(texts))
    df = df.copy()
    df['embedding'] = results
    missing = df['embedding'].isna().sum()
    if missing:
        logger.warning('Dropping %d rows with missing embeddings', missing)
        df = df[df['embedding'].notna()].reset_index(drop=True)
    # Sanity check first vector dimension
    if not df.empty:
        first = df['embedding'].iloc[0]
        if first is not None and len(first) != target_dim:
            logger.error('Unexpected embedding dimension %d (expected %d) – check model / config.', len(first), target_dim)
    return df


def main() -> bool:
    try:
        base_dir = Path(__file__).parent
        src = (base_dir / '../source_json/producers.json').resolve()
        out = (base_dir / '../processed/products.parquet').resolve()
        if not src.exists():
            raise FileNotFoundError(f'Source file not found: {src}')
        with open(src, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and 'producers' in data:
            data = data['producers']
        if not isinstance(data, list):
            raise ValueError('Unexpected JSON structure (expected list or {"producers": [...]})')
        df = _flatten_products(data)
        if df.empty:
            logger.warning('No products found; aborting')
            return False
        df = _add_combined(df)
        ratio = float(os.getenv('PRODUCT_VIP_RATIO', '0.10'))
        df = _assign_vip(df, ratio)
        client, model = _init_client()
        logger.info('Embedding model=%s ratio=%.2f count=%d dim=2000', model, ratio, len(df))
        df = _generate_embeddings(df, client, model)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out, index=False)
        logger.info('Saved %d products to %s', len(df), out)
        return True
    except Exception as e:
        logger.exception('Products embeddings pipeline failed: %s', e)
        return False


if __name__ == '__main__':
    raise SystemExit(0 if main() else 1)

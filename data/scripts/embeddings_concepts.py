"""Generate embeddings for higher-level concepts (category, cuisine, certification, allergen).

Sources:
  processed/taxonomy_concepts.parquet (categories & cuisines)
  source_json/certifications.json
  source_json/allergens.json

Outputs:
  processed/concept_embeddings.parquet
  Upserts rows into concept_embeddings table (unless --no-db)

Usage:
  uv run python data/scripts/embeddings_concepts.py
  uv run python data/scripts/embeddings_concepts.py --no-db

Environment:
  OPENAI_API_KEY (required)
  OPENAI_BASE_URL, OPENAI_API_VERSION (Azure optional)
  OPENAI_EMBEDDING_MODEL (default text-embedding-3-large)
  PG* vars for DB upsert
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import unicodedata
from pathlib import Path
from typing import List, Sequence

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI, APIStatusError, RateLimitError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception, before_sleep_log

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('openai').setLevel(logging.WARNING)

EMBED_DIM = 2000


def _norm(text: str) -> str:
    if not text:
        return ''
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = text.lower()
    return ' '.join(text.split())


def _client() -> tuple[OpenAI, str]:
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError('OPENAI_API_KEY not set')
    base_url = os.getenv('OPENAI_BASE_URL')
    api_version = os.getenv('OPENAI_API_VERSION') or '2024-10-21'
    model = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large')
    default_query = {'api-version': api_version} if base_url else None
    return OpenAI(api_key=api_key, base_url=base_url, default_query=default_query), model


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in (429, 500, 502, 503, 504)
    return False


@retry(stop=stop_after_attempt(6), wait=wait_exponential(multiplier=1, min=2, max=60),
       retry=retry_if_exception(_retryable), before_sleep=before_sleep_log(logger, logging.WARNING), reraise=True)
def _embed_batch(client: OpenAI, model: str, inputs: Sequence[str]) -> List[List[float]]:
    resp = client.embeddings.create(model=model, input=list(inputs), dimensions=EMBED_DIM)
    return [d.embedding for d in resp.data]


def _load_taxonomy_concepts(processed_dir: Path) -> pd.DataFrame:
    path = (processed_dir / 'taxonomy_concepts.parquet').resolve()
    if not path.exists():
        raise FileNotFoundError(f'Missing {path}')
    df = pd.read_parquet(path)
    required = {'kind', 'code', 'name', 'description'}
    if not required.issubset(df.columns):
        raise ValueError(f'taxonomy_concepts.parquet missing columns: {required - set(df.columns)}')
    return df


def _load_json_list(path: Path) -> list:
    if not path.exists():
        logger.warning('File not found %s (skipping)', path)
        return []
    with path.open('r', encoding='utf-8') as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _assemble(processed_dir: Path, source_dir: Path) -> pd.DataFrame:
    tax = _load_taxonomy_concepts(processed_dir)
    rows = []
    for _, r in tax.iterrows():
        rows.append({'concept_type': r['kind'], 'concept_id': r['code'], 'name': r['name'], 'description': r.get('description') or ''})
    for c in _load_json_list(source_dir / 'certifications.json'):
        rows.append({'concept_type': 'certification', 'concept_id': c.get('certificationId'), 'name': c.get('name'), 'description': c.get('description') or ''})
    for a in _load_json_list(source_dir / 'allergens.json'):
        rows.append({'concept_type': 'allergen', 'concept_id': a.get('allergenId'), 'name': a.get('name'), 'description': a.get('description') or ''})
    df = pd.DataFrame(rows)
    df = df.dropna(subset=['concept_type', 'concept_id', 'name']).drop_duplicates(subset=['concept_type', 'concept_id'], keep='last')
    return df


def _embed(df: pd.DataFrame, client: OpenAI, model: str, batch_size: int) -> pd.DataFrame:
    texts = [_norm(f"{r.name} {r.description}") for r in df.itertuples(index=False)]
    vectors: List[List[float]] = []
    for start in range(0, len(texts), batch_size):
        end = min(start + batch_size, len(texts))
        vectors.extend(_embed_batch(client, model, texts[start:end]))
        logger.info('Embedding progress %d/%d', end, len(texts))
    df = df.copy()
    df['normalized_text'] = texts
    df['embedding'] = vectors
    if not df.empty and len(df['embedding'].iloc[0]) != EMBED_DIM:
        raise ValueError('Unexpected embedding dimension')
    return df


def main() -> bool:
    parser = argparse.ArgumentParser(description='Generate embeddings for higher-level concepts.')
    parser.add_argument('--batch-size', type=int, default=64, help='Embedding batch size (default 64)')
    args = parser.parse_args()
    base_dir = Path(__file__).parent
    processed_dir = (base_dir / '../processed').resolve()
    source_dir = (base_dir / '../source_json').resolve()
    processed_dir.mkdir(parents=True, exist_ok=True)
    try:
        df = _assemble(processed_dir, source_dir)
        if df.empty:
            logger.warning('No concept rows found. Exiting.')
            return True
        client, model = _client()
        logger.info('Embedding %d concepts with model %s dim=%d', len(df), model, EMBED_DIM)
        df = _embed(df, client, model, args.batch_size)
        out_path = processed_dir / 'concept_embeddings.parquet'
        df.to_parquet(out_path, index=False)
        logger.info('Wrote parquet %s (no DB operations performed; separate import script will load)', out_path)
        return True
    except Exception as e:  # pragma: no cover - unexpected failure path
        logger.exception('Concept embeddings generation failed: %s', e)
        return False


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(0 if main() else 1)

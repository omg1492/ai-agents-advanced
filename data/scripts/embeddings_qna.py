"""Generate embeddings for semantic cache Q&A (qna.json).

This script:
1. Loads ../source_json/qna.json (array[{question, answer}])
2. Generates 2000‑d embeddings for each question using the unified OpenAI/Azure client
3. Writes a Parquet file ../processed/qna_embeddings.parquet with columns:
      question (str), answer (str), embedding (list[float])

Environment (unified):
- OPENAI_API_KEY
- OPENAI_BASE_URL (Azure) optional
- OPENAI_API_VERSION (Azure) optional (default: preview)
- OPENAI_EMBEDDING_MODEL (defaults to text-embedding-3-large)

Usage:
    uv run embeddings_qna.py

Notes:
- Designed only for small (≈50) rows → simple sequential batching is fine
- Embedding dimension fixed to 2000 for consistency with other tables
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import List, Sequence

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI, APIStatusError, RateLimitError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("openai").setLevel(logging.WARNING)


def _unified_client() -> tuple[OpenAI, str]:
    """Return (OpenAI client, embedding model name/deployment)."""
    load_dotenv()  # local .env
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    base_url = os.getenv("OPENAI_BASE_URL")
    api_version = os.getenv("OPENAI_API_VERSION", "preview")
    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    default_query = {"api-version": api_version} if base_url else None
    client = OpenAI(api_key=api_key, base_url=base_url, default_query=default_query)
    return client, model


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code == 429 or 500 <= (exc.status_code or 0) < 600
    return False


class QnAEmbedder:
    """Embeds Q&A questions in small batches."""

    def __init__(self, batch_size: int = 25, dimensions: int = 2000):
        self.client, self.model = _unified_client()
        self.batch_size = max(1, batch_size)
        self.dimensions = dimensions
        logger.info("Embedding model=%s base_url=%s", self.model, getattr(self.client, "base_url", None))

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception(_retryable),
        reraise=True,
    )
    def _embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        resp = self.client.embeddings.create(
            model=self.model,
            input=list(texts),
            dimensions=self.dimensions,
        )
        return [d.embedding for d in resp.data]

    def embed(self, questions: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for i in range(0, len(questions), self.batch_size):
            batch = questions[i : i + self.batch_size]
            vecs = self._embed_batch(batch)
            out.extend(vecs)
            logger.info("Progress: %d/%d", len(out), len(questions))
        return out


def load_qna(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"qna.json not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("qna.json must be an array of objects")
    rows = []
    for obj in data:
        if not isinstance(obj, dict):
            continue
        q = str(obj.get("question", "")).strip()
        a = str(obj.get("answer", "")).strip()
        if q and a:
            rows.append({"question": q, "answer": a})
    if not rows:
        raise ValueError("No valid Q&A rows found in qna.json")
    df = pd.DataFrame(rows, columns=["question", "answer"])
    logger.info("Loaded %d Q&A rows", len(df))
    return df


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    logger.info("Saved embeddings parquet: %s (%d rows)", path, len(df))


def main() -> bool:
    try:
        base_dir = Path(__file__).parent
        in_path = (base_dir / "../source_json/qna.json").resolve()
        out_path = (base_dir / "../processed/qna_embeddings.parquet").resolve()
        df = load_qna(in_path)
        embedder = QnAEmbedder(batch_size=25, dimensions=2000)
        vectors = embedder.embed(df["question"].tolist())
        df["embedding"] = vectors
        save_parquet(df, out_path)
        return True
    except Exception as e:
        logger.exception("Failed to generate Q&A embeddings: %s", e)
        return False


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(0 if main() else 1)

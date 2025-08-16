"""Generate embeddings for product data from producers.json using unified envs.

This script:
- Loads ../source_json/producers.json
- Builds a flat table with columns: producerName, productName, productDescription, productId
- Creates combinedText in the format: "PRODUCER: name, PRODUCT: name, DESCRIPTION: description"
- Calls the OpenAI embeddings API (supports OpenAI and Azure OpenAI via unified env)
- Implements retries with respect for 429 Retry-After headers and exponential backoff
- Logs progress roughly every 100 records
- Saves output to ../processed/simple_products.parquet

Env variables (unified):
- OPENAI_API_KEY
- OPENAI_BASE_URL (for Azure, must end with /openai/v1/)
- OPENAI_API_VERSION (for Azure, e.g. 2024-10-21 or preview)
- OPENAI_EMBEDDING_MODEL (e.g. text-embedding-3-large or Azure deployment name)

Note: legacy Azure-specific env variables are not supported in this script.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, List, Optional, Sequence

import pandas as pd
from dotenv import load_dotenv
from openai import APIStatusError, OpenAI, RateLimitError
from tenacity import before_sleep_log, retry, retry_if_exception, stop_after_attempt, wait_exponential


# Configure logging: our logger INFO, third-party WARNING
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def _ensure_endswith(base: str, suffix: str) -> str:
    """Ensure a string ends with suffix exactly once."""
    if not base.endswith(suffix):
        return base.rstrip("/") + ("/" if not suffix.startswith("/") else "") + suffix.lstrip("/")
    return base


def _build_unified_openai_client() -> tuple[OpenAI, str]:
    """Create a unified OpenAI client and resolve embedding model name.

    Returns (client, model_or_deployment_name).
    """
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    api_version = os.getenv("OPENAI_API_VERSION")
    embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL") or "text-embedding-3-large"

    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    default_query: Optional[dict[str, str]] = None
    if base_url:
        default_query = {"api-version": api_version or "2024-10-21"}

    client = OpenAI(api_key=api_key, base_url=base_url, default_query=default_query)
    return client, embedding_model


def _is_retryable_error(exc: BaseException) -> bool:
    """Return True for rate limit and transient server errors."""
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code == 429 or 500 <= (exc.status_code or 0) < 600
    return False


class EmbeddingsGenerator:
    """Handles batch embedding generation with retries and progress logging."""

    def __init__(self, batch_size: int = 100, dimensions: int = 2000):
        """Init with a unified OpenAI client.

        Args:
            batch_size: Size of embedding batches.
            dimensions: Target embedding dimension for compatibility.
        """
        self.client, self.model = _build_unified_openai_client()
        self.batch_size = max(1, batch_size)
        self.dimensions = dimensions
        logger.info(
            "Embeddings client ready (base_url=%s, model=%s)", getattr(self.client, "base_url", None), self.model
        )

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=1, min=2, max=90),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed a batch of texts, honoring Retry-After when rate limited."""
        try:
            resp = self.client.embeddings.create(
                model=self.model, input=list(texts), dimensions=self.dimensions
            )
            return [d.embedding for d in resp.data]
        except APIStatusError as e:
            if e.status_code == 429:
                retry_after_s = 0
                try:
                    retry_after_s = int(e.response.headers.get("retry-after", "0")) if e.response else 0
                except Exception:
                    retry_after_s = 0
                if retry_after_s > 0:
                    logger.warning("429 received. Sleeping %s seconds per Retry-After", retry_after_s)
                    time.sleep(retry_after_s)
            raise
        except RateLimitError:
            raise

    def generate_embeddings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate embeddings for df['combinedText'] and return a new DataFrame.

        Raises ValueError if combinedText column is missing.
        """
        if "combinedText" not in df.columns:
            raise ValueError("DataFrame must contain 'combinedText' column")

        total = len(df)
        results: list[Optional[list[float]]] = [None] * total
        logger.info("Generating embeddings for %d records (batch=%d)", total, self.batch_size)

        for start in range(0, total, self.batch_size):
            end = min(start + self.batch_size, total)
            texts = df.loc[start : end - 1, "combinedText"].tolist()
            vectors = self._embed_batch(texts)
            for i, v in enumerate(vectors):
                results[start + i] = v
            if (end % 100 == 0) or (end == total):
                logger.info("Progress: %d/%d", end, total)

        out = df.copy()
        out["embedding"] = results
        missing = out["embedding"].isna().sum()
        if missing:
            logger.warning("%d missing embeddings; dropping those rows", missing)
            out = out[out["embedding"].notna()].reset_index(drop=True)
        return out


def load_producers_data(file_path: Path) -> List[dict[str, Any]]:
    """Load producers JSON; accept either list or {"producers": [...]}."""
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "producers" in data:
        data = data["producers"]
    if not isinstance(data, list):
        raise ValueError("Invalid JSON: expected list or object with 'producers'")
    logger.info("Loaded %d producers from %s", len(data), file_path)
    return data


def create_products_dataframe(producers_data: List[dict[str, Any]]) -> pd.DataFrame:
    """Flatten producers into a products DataFrame with required columns."""
    rows: list[dict[str, Any]] = []
    gen_id = 1
    for producer in producers_data:
        pname = (producer or {}).get("name") or (producer or {}).get("producerName") or ""
        for product in (producer or {}).get("products", []) or []:
            name = (product or {}).get("name") or (product or {}).get("productName") or ""
            desc = (product or {}).get("description") or (product or {}).get("productDescription") or ""
            pid = (product or {}).get("id") or (product or {}).get("productId") or gen_id
            rows.append(
                {
                    "producerName": str(pname),
                    "productName": str(name),
                    "productDescription": str(desc),
                    "productId": pid,
                }
            )
            gen_id += 1
    df = pd.DataFrame(rows, columns=["producerName", "productName", "productDescription", "productId"])
    logger.info("Created DataFrame with %d products", len(df))
    return df


def add_combined_text_column(df: pd.DataFrame) -> pd.DataFrame:
    """Add the combinedText column for embedding input."""
    df = df.copy()
    for c in ["producerName", "productName", "productDescription"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)
    df["combinedText"] = (
        "PRODUCER: "
        + df["producerName"].str.strip()
        + ", PRODUCT: "
        + df["productName"].str.strip()
        + ", DESCRIPTION: "
        + df["productDescription"].str.strip()
    )
    logger.info("Added combinedText column")
    return df


def save_to_parquet(df: pd.DataFrame, output_path: Path) -> None:
    """Save DataFrame to a Parquet file at output_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info("Saved %d records to %s", len(df), output_path)


def main() -> bool:
    """Run the pipeline end-to-end; return True on success."""
    try:
        base_dir = Path(__file__).parent
        input_path = (base_dir / "../source_json/producers.json").resolve()
        output_path = (base_dir / "../processed/simple_products.parquet").resolve()

        producers = load_producers_data(input_path)
        df = create_products_dataframe(producers)
        if df.empty:
            logger.warning("No products found; nothing to embed.")
            save_to_parquet(df.assign(combinedText="", embedding=[]), output_path)
            return True

        df = add_combined_text_column(df)
        generator = EmbeddingsGenerator(batch_size=100, dimensions=2000)
        df = generator.generate_embeddings(df)
        save_to_parquet(df, output_path)
        return True
    except Exception as e:
        logger.exception("Embedding pipeline failed: %s", e)
        return False


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)

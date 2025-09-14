"""Memory search service over conversation summaries.

Provides a function-callable tool for the Responses API allowing the model to
retrieve past conversation summaries for the CURRENT user only. Always enforces
strict user fencing at SQL layer (WHERE user_id = :uid). The model supplies a
HyDE-style expanded query (free-form description of what it is looking for).

Return payload shape (JSON string):
    { "memories": [ { "thread_id": str, "summary": str, "updated_at": str, "similarity_score": float } ] }

Design choices:
 - Embedding model reuses global OPENAI_EMBEDDING_MODEL for consistency.
 - Cosine similarity = 1 - (embedding <=> query_vec). We order by distance asc
   and also return similarity rounded to 4 decimals for readability.
 - Optional max_results cap from config (MEMORY_SEARCH_MAX_RESULTS, default 5).
 - HyDE prompt left to the model; we just embed the supplied text.
 - No cross-user leakage possible due to mandatory user_id predicate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any
import logging
import json

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from openai import OpenAI

from src.services.config_service import ConfigService, AppConfig


logger = logging.getLogger(__name__)


@dataclass
class MemorySearchResult:
    thread_id: str
    summary: str
    updated_at: str
    similarity: float


class MemorySearchService:
    """Service performing vector similarity search over conversation_summaries."""

    def __init__(self, config: AppConfig | None = None):
        cfg_service = ConfigService()
        self._app_config: AppConfig = config or cfg_service.config
        self._cfg = getattr(self._app_config, "memory_search", None)  # type: ignore[attr-defined]
        self.enabled: bool = bool(self._cfg and self._cfg.enabled)
        if not self.enabled:
            logger.info("Memory search disabled via configuration")
            return
        db = self._app_config.db
        url = f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.database}"
        self.engine: Engine = create_engine(url, echo=False)
        base_url = self._app_config.openai.base_url
        default_query = {"api-version": self._app_config.openai.api_version or "preview"} if base_url else None
        self.openai_client = OpenAI(
            api_key=self._app_config.openai.api_key,
            base_url=base_url,
            default_query=default_query,
        )
        self.embedding_model = (
            self._app_config.rag.embedding_model if self._app_config.rag else "text-embedding-3-large"
        )
        self.max_results = int(getattr(self._cfg, "max_results", 5))
        logger.info("Initialized MemorySearchService (max_results=%s)", self.max_results)

    async def _embed(self, text_value: str) -> List[float]:
        resp = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=text_value,
            encoding_format="float",
            dimensions=2000,
        )
        return resp.data[0].embedding

    async def search(self, query_text: str, user_id: str, k: int) -> List[MemorySearchResult]:
        if not self.enabled:
            return []
        k = max(1, min(int(k), self.max_results))
        emb = await self._embed(query_text[:4000])
        if not emb:
            return []
        emb_str = "[" + ",".join(map(str, emb)) + "]"
        sql = text(
            f"""
            SELECT thread_id, summary, updated_at,
                   1 - (embedding <=> '{emb_str}'::vector) AS similarity
            FROM conversation_summaries
            WHERE user_id = :uid
            ORDER BY embedding <=> '{emb_str}'::vector
            LIMIT :k
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"uid": user_id, "k": k}).fetchall()
        results = [
            MemorySearchResult(
                thread_id=str(r.thread_id),
                summary=r.summary,
                updated_at=(r.updated_at.isoformat() if hasattr(r.updated_at, "isoformat") else str(r.updated_at)),
                similarity=float(r.similarity),
            )
            for r in rows
        ]
        logger.info("Memory search returned %d rows (k=%s user=%s)", len(results), k, user_id)
        return results

    async def execute(self, arguments: Dict[str, Any], user_id: str) -> str:
        if not self.enabled:
            return json.dumps({"memories": []})
        k_raw = arguments.get("k")
        try:
            k = int(k_raw) if k_raw is not None else self.max_results
        except (TypeError, ValueError):  # pragma: no cover
            k = self.max_results
        if k < 1:
            k = 1
        if k > self.max_results:
            k = self.max_results
        query_text = str(arguments.get("query", ""))[:4000]
        if not query_text.strip():
            return json.dumps({"memories": []})
        rows = await self.search(query_text, user_id=user_id, k=k)
        payload = {
            "memories": [
                {
                    "thread_id": r.thread_id,
                    "summary": r.summary,
                    "updated_at": r.updated_at,
                    "similarity_score": round(r.similarity, 4),
                }
                for r in rows
            ]
        }
        return json.dumps(payload)

__all__ = ["MemorySearchService", "MemorySearchResult"]

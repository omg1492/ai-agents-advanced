"""Semantic cache service for ultra-fast first-turn responses.

The semantic cache holds (question, answer, embedding) pairs in the
`semantic_cache` PostgreSQL table (populated by data/scripts pipeline).

Usage contract:
1. Only the FIRST user message in a thread is eligible for cache lookup.
2. If a high-similarity hit (>= configured threshold) is found, we return the
   cached answer immediately and DO NOT invoke the LLM.
3. We still want downstream turns to have continuity. Since the Responses API
   conversation state is provider-managed via `previous_response_id` chains,
   and there is currently no documented way to append an artificial assistant
   turn without a model invocation, we fall back to manual state: we store the
   cached assistant reply in our in-memory history so the frontend shows it.
   For the next model invocation we simply start a *new* chain (no
   previous_response_id) because no model output exists yet. This slightly
   changes token accounting (one fewer prior turn) but preserves correctness.

Future option (if OpenAI exposes an API to create synthetic responses or
seed a chain): we could create a lightweight dummy response to obtain an
`id` and use that as `previous_response_id`.
"""
from __future__ import annotations

import logging
from typing import Optional, List

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from openai import OpenAI

from src.services.config_service import ConfigService, AppConfig, SemanticCacheConfig

logger = logging.getLogger(__name__)


class SemanticCacheHit:
    """Result object for a semantic cache lookup."""

    def __init__(self, question: str, answer: str, similarity: float):
        self.question = question
        self.answer = answer
        self.similarity = similarity


class SemanticCacheService:
    """Service performing high-threshold semantic similarity lookup.

    Table schema expectation (see data/scripts/sql/05_create_semantic_cache.sql):
        semantic_cache(id serial PK, question text, answer text, embedding vector(2000), created_at timestamptz default now())
    Indexed with HNSW/IVFFlat on embedding for fast cosine similarity.
    """

    def __init__(self, config: Optional[AppConfig] = None):
        cfg_service = ConfigService()
        self._app_config = config or cfg_service.config
        self._cfg: SemanticCacheConfig | None = self._app_config.semantic_cache
        self.enabled = bool(self._cfg and self._cfg.enabled)
        if not self.enabled:
            logger.info("Semantic cache disabled via configuration")
            return
        self.threshold = float(self._cfg.similarity_threshold)
        self.embedding_model = self._cfg.embedding_model
        self.engine = self._create_db_engine()
        self.openai_client = self._create_openai_client()
        logger.info(
            "Initialized SemanticCacheService (threshold=%s, model=%s)",
            self.threshold,
            self.embedding_model,
        )

    def _create_db_engine(self) -> Engine:
        db = self._app_config.db
        url = f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.database}"
        return create_engine(url, echo=False)

    def _create_openai_client(self) -> OpenAI:
        base_url = self._app_config.openai.base_url
        default_query = {"api-version": self._app_config.openai.api_version or "preview"} if base_url else None
        return OpenAI(
            api_key=self._app_config.openai.api_key,
            base_url=base_url,
            default_query=default_query,
        )

    async def _embed(self, text_value: str) -> List[float]:  # noqa: D401 simple forward method
        if not self.enabled:
            return []
        resp = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=text_value,
            encoding_format="float",
            dimensions=2000,
        )
        return resp.data[0].embedding

    async def lookup(self, user_text: str) -> Optional[SemanticCacheHit]:
        """Return highest-similarity cached answer if above threshold.

        Args:
            user_text: First user message text.

        Returns:
            SemanticCacheHit if similarity >= threshold else None.
        """
        if not self.enabled:
            return None
        try:
            emb = await self._embed(user_text)
            if not emb:
                return None
            emb_str = "[" + ",".join(map(str, emb)) + "]"
            sql = text(
                f"""
                SELECT question, answer, 1 - (embedding <=> '{emb_str}'::vector) AS sim
                FROM semantic_cache
                WHERE 1 - (embedding <=> '{emb_str}'::vector) >= :th
                ORDER BY embedding <=> '{emb_str}'::vector
                LIMIT 1
                """
            )
            with self.engine.connect() as conn:
                row = conn.execute(sql, {"th": self.threshold}).fetchone()
            if not row:
                logger.info("Semantic cache miss (no row >= %.3f)", self.threshold)
                return None
            hit = SemanticCacheHit(row.question, row.answer, float(row.sim))
            logger.info(
                "Semantic cache HIT similarity=%.3f question='%s'", hit.similarity, hit.question[:80]
            )
            return hit
        except Exception as e:  # pragma: no cover defensive
            logger.warning("Semantic cache lookup failed: %s", e)
            return None

    @staticmethod
    def seed_history_with_hit(history_list: list, thread_id: str, hit: SemanticCacheHit, message_model_cls):
        """Append a synthetic assistant message to in-memory history.

        Since we cannot currently inject a synthetic provider-side response
        into a Responses API chain (no documented endpoint for that), we add
        the cached answer locally so that the UI reflects an assistant reply.

        The next real model call will start a fresh chain (no previous_response_id).
        """
        from datetime import datetime, timezone
        import os
        now_iso = datetime.now(timezone.utc).isoformat()
        history_list.append(
            message_model_cls(
                message_id=os.urandom(8).hex(),
                thread_id=thread_id,
                role="assistant",
                content=hit.answer,
                timestamp=now_iso,
            )
        )

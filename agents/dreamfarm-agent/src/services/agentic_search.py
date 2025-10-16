"""Agentic search service providing semantic (vector) and keyword (FTS) product retrieval.

Implements two lightweight function-callable tools for the Responses API:

1. semantic_product_search(text, k=5)
   - The model supplies a HyDE style synthetic description / expansion of the
     user's need in ``text``. We embed it and perform a cosine similarity
     search over ``products.embedding`` (pgvector). Results are limited by
     ``k`` (3-10) and additionally fenced by VIP visibility.

2. keyword_product_search(keywords: list[str], k=5)
   - The model supplies a concise list of 1-5 short keywords / key phrases.
     We build a tsquery over ``products.fts_document`` and rank via ts_rank.
     Results are again limited by ``k`` (3-10) and fenced.

VIP Fencing
-----------
Both search modalities apply the predicate::

    (products.is_vip = false OR :user_is_vip = true)

so non‑VIP users never see VIP products while VIP users see the full catalog.

Return Format
-------------
Both functions return a JSON serializable dict::

    { "products": [ { product_id, producer_name, product_name,
                       product_description, similarity_score } ] }

Similarity score is cosine similarity (semantic) or ts_rank (FTS) and is
rounded to 4 decimals for brevity. The caller (LLM) is instructed via the
system prompt to ground any product claims ONLY in either these tool outputs
or the RAG <relevant_products> block when provided.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Dict, Any
from urllib.parse import quote_plus
import logging
import json

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from openai import OpenAI

from src.services.config_service import ConfigService, AppConfig


logger = logging.getLogger(__name__)


@dataclass
class AgenticSearchConfig:
    enabled: bool
    max_results: int


class AgenticSearchService:
    """Service encapsulating semantic + keyword product retrieval with fencing."""

    def __init__(self, config: AppConfig | None = None):  # noqa: D401
        cfg_service = ConfigService()
        self._app_config: AppConfig = config or cfg_service.config
        self._cfg: AgenticSearchConfig | None = getattr(self._app_config, "agentic_search", None)  # type: ignore[attr-defined]
        self.enabled: bool = bool(self._cfg and self._cfg.enabled)
        if not self.enabled:
            logger.info("Agentic search disabled via configuration")
            return
        self.max_results = int(self._cfg.max_results)
        # DB + embeddings
        self.engine: Engine = self._create_db_engine()
        self.openai_client: OpenAI = self._create_openai_client()
        logger.info("Initialized AgenticSearchService (max_results=%s)", self.max_results)

    # ---------------------- internal helpers ---------------------- #
    def _create_db_engine(self) -> Engine:
        db = self._app_config.db
        url = f"postgresql://{quote_plus(db.user)}:{quote_plus(db.password)}@{db.host}:{db.port}/{db.database}?sslmode={db.sslmode}"
        return create_engine(url, echo=False)

    def _create_openai_client(self) -> OpenAI:
        base_url = self._app_config.openai.base_url
        default_query = {"api-version": self._app_config.openai.api_version or "preview"} if base_url else None
        return OpenAI(
            api_key=self._app_config.openai.api_key,
            base_url=base_url,
            default_query=default_query,
        )

    async def _embed(self, text_value: str) -> List[float]:
        resp = self.openai_client.embeddings.create(
            model=self._app_config.rag.embedding_model,  # reuse RAG embedding model for consistency
            input=text_value,
            encoding_format="float",
            dimensions=2000,
        )
        return resp.data[0].embedding

    # --------------------------- searches --------------------------- #
    async def semantic_search(self, text_value: str, k: int, user_is_vip: bool) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        emb = await self._embed(text_value)
        if not emb:
            return []
        emb_str = "[" + ",".join(map(str, emb)) + "]"
        # Fence + similarity filter (optional threshold can be adjusted later)
        sql = text(
            f"""
            SELECT product_id, producer_name, product_name, product_description,
                   1 - (embedding <=> '{emb_str}'::vector) AS similarity
            FROM products
            WHERE (is_vip = false OR :user_is_vip = true)
            ORDER BY embedding <=> '{emb_str}'::vector
            LIMIT :k
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"user_is_vip": user_is_vip, "k": k}).fetchall()
        results = [
            {
                # Ensure UUID is serialized as string
                "product_id": str(r.product_id),
                "producer_name": r.producer_name,
                "product_name": r.product_name,
                "product_description": r.product_description,
                "similarity_score": round(float(r.similarity), 4),
            }
            for r in rows
        ]
        logger.info("Agentic semantic search returned %d rows (k=%s vip=%s)", len(results), k, user_is_vip)
        return results

    def keyword_search(self, keywords: Sequence[str], k: int, user_is_vip: bool) -> List[Dict[str, Any]]:
        if not self.enabled or not keywords:
            return []
        sanitized: List[str] = []
        for kw in keywords[:12]:  # cap incoming list
            if not isinstance(kw, str):
                continue
            s = kw.strip().lower()
            if not s:
                continue
            # keep alnum/_/- and spaces then transform spaces to &
            words = [
                ''.join(ch for ch in w if ch.isalnum() or ch in ('_', '-'))
                for w in s.split()
            ]
            words = [w for w in words if w]
            if not words:
                continue
            sanitized.append(' & '.join(words))
        if not sanitized:
            return []
        tsquery = ' | '.join(sanitized)
        sql = text(
                """
                SELECT product_id, producer_name, product_name, product_description,
                                ts_rank(fts_document, to_tsquery('english', :q)) AS similarity
                FROM products
                WHERE fts_document @@ to_tsquery('english', :q)
                    AND (is_vip = false OR :user_is_vip = true)
                ORDER BY similarity DESC
                LIMIT :k
                """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"q": tsquery, "user_is_vip": user_is_vip, "k": k}).fetchall()
        results = [
            {
                "product_id": str(r.product_id),
                "producer_name": r.producer_name,
                "product_name": r.product_name,
                "product_description": r.product_description,
                "similarity_score": round(float(r.similarity or 0.0), 4),
            }
            for r in rows
        ]
        logger.info("Agentic keyword search returned %d rows (k=%s vip=%s)", len(results), k, user_is_vip)
        return results

    # --------------------------- dispatcher --------------------------- #
    async def execute(self, name: str, arguments: Dict[str, Any], user_is_vip: bool) -> str:
        """Execute function call by name; returns JSON string output.

        The JSON schema is intentionally simple to reduce model parsing errors.
        """
        if not self.enabled:
            return json.dumps({"products": []})
        k_raw = arguments.get("k")
        try:
            k = int(k_raw) if k_raw is not None else 5
        except (TypeError, ValueError):  # pragma: no cover
            k = 5
        if k < 3:
            k = 3
        if k > 10:
            k = 10
        # Also respect global cap
        k = min(k, self.max_results)

        if name == "semantic_product_search":
            # Handle both direct and nested argument formats
            text_value = str(arguments.get("text", arguments.get("query", "")))[:4000]
            if not text_value.strip():
                logger.warning("semantic_product_search called with empty text. Arguments: %s", arguments)
                return json.dumps({"products": []})
            products = await self.semantic_search(text_value, k, user_is_vip)
            return json.dumps({"products": products})
        elif name == "keyword_product_search":
            # Handle both direct and nested argument formats
            kw = arguments.get("keywords", arguments.get("keyword_list", []))
            if not isinstance(kw, list):
                # Try to parse as comma-separated string
                if isinstance(kw, str):
                    kw = [x.strip() for x in kw.split(",") if x.strip()]
                else:
                    kw = []
            kw = [str(x) for x in kw][:12]
            if not kw:
                logger.warning("keyword_product_search called with empty keywords. Arguments: %s", arguments)
                return json.dumps({"products": []})
            products = self.keyword_search(kw, k, user_is_vip)
            return json.dumps({"products": products})
        else:
            logger.info("Unknown agentic search function: %s", name)
            return json.dumps({"products": []})


__all__ = ["AgenticSearchService", "AgenticSearchConfig"]

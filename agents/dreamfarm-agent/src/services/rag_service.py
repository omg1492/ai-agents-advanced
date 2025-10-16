"""RAG (Retrieval-Augmented Generation) service for semantic search.

This version relies solely on ConfigService-provided configuration. No
environment variables are read directly here.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Dict, Sequence
from dataclasses import dataclass
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from openai import OpenAI
from pydantic import BaseModel, Field

from src.services.config_service import AppConfig, ConfigService


logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Search result from semantic search."""
    id: int
    product_id: str
    producer_name: str
    product_name: str
    product_description: str
    combined_text: str
    similarity_score: float


class ExtractedKeywords(BaseModel):
    """Structured output schema for keyword extraction.

    The model is instructed to return a concise list of salient keywords / keyphrases
    (product names, producer names, categories, distinctive nouns). Duplicates and
    stop words should be removed; items are lowercase.
    """
    keywords: List[str] = Field(default_factory=list, description="Distinct important keywords")


class RAGService:
    """Service for Retrieval-Augmented Generation using PostgreSQL and pgvector."""

    def __init__(self, config: Optional[AppConfig] = None):
        """Initialize the RAG service with configuration.

        If `config` is not provided, configuration is loaded via ConfigService.
        """
        self._config = config or ConfigService().config
        self.enabled = self._config.rag.enabled
        if not self.enabled:
            logger.info("RAG service is disabled via configuration")
            return

        self.similarity_threshold = float(self._config.rag.similarity_threshold)
        self.max_results = int(self._config.rag.max_results)

        # Initialize dependencies
        self.engine = self._create_db_engine()
        self.openai_client = self._create_openai_client()
        logger.info(
            "Initialized RAG service (threshold=%s, max_results=%s, model=%s)",
            self.similarity_threshold,
            self.max_results,
            self._config.rag.embedding_model,
        )

    def _create_db_engine(self) -> Engine:
        host = self._config.db.host
        port = self._config.db.port
        database = self._config.db.database
        user = self._config.db.user
        password = self._config.db.password
        sslmode = self._config.db.sslmode
        if not all([host, database, user, password]):
            raise ValueError("Database configuration is incomplete (host, database, user, password)")
        url = f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{database}?sslmode={sslmode}"
        return create_engine(url, echo=False)

    def _create_openai_client(self) -> OpenAI:
        api_key = self._config.openai.api_key
        if not api_key:
            raise ValueError("Missing OpenAI API key in configuration")
        base_url = self._config.openai.base_url
        default_query = {"api-version": self._config.openai.api_version or "preview"} if base_url else None
        return OpenAI(api_key=api_key, base_url=base_url, default_query=default_query)

    # Async client removed – structured parsing now uses synchronous responses.parse

    def _get_embedding_model_name(self) -> str:
        return self._config.rag.embedding_model

    async def generate_embedding(self, text_value: str) -> List[float]:
        if not self.enabled:
            return []
        response = self.openai_client.embeddings.create(
            model=self._get_embedding_model_name(),
            input=text_value,
            encoding_format="float",
            dimensions=2000,
        )
        return response.data[0].embedding

    async def semantic_search(self, query: str) -> List[SearchResult]:
        if not self.enabled:
            return []
        query_embedding = await self.generate_embedding(query)
        if not query_embedding:
            return []
        return await self._vector_search(query_embedding)

    # ------------------ Keyword Extraction + FTS + Fusion ------------------ #
    async def _extract_keywords(self, user_query: str) -> List[str]:
        """Extract salient keywords using Responses API structured parsing.

        Uses ``responses.parse`` with Pydantic schema (synchronous call). If the
        call fails or returns empty data, returns an empty list.
        """
        try:
            instructions = (
                "Identify up to 8 concise important product, producer or category keywords "
                "from the user query. Use single or short noun phrases only. Lowercase."
            )
            # Synchronous parse call; acceptable small latency inside async context
            resp = self.openai_client.responses.parse(
                model=self._config.openai.model_name or "gpt-4o-mini",
                input=user_query,
                instructions=instructions,
                text_format=ExtractedKeywords,
            )
            parsed: ExtractedKeywords | None = getattr(resp, "output_parsed", None)
            if not parsed:
                return []
            kw = [k.strip().lower() for k in parsed.keywords if k.strip()]
            # Log the exact list (truncate if long)
            logger.info("RAG: extracted keywords: %s", ", ".join(kw) or "<none>")
            return kw
        except Exception as e:  # pragma: no cover
            logger.warning("RAG: keyword extraction failed: %s", e)
            return []

    def _fts_search(self, keywords: Sequence[str]) -> List[SearchResult]:
        """Execute full-text search using extracted keywords.

        Each original keyword phrase is preserved. Multi-word phrases are
        converted to an AND group: "chilli honey" -> "chilli & honey".
        Phrases are then OR-combined: (bio & honey) | (chilli & honey) | honey
        This keeps a direct mapping from LLM output to tsquery structure.
        """
        if not keywords:
            return []
        phrases: list[str] = []
        for raw_kw in keywords[:20]:  # cap to avoid huge queries
            raw_kw = raw_kw.strip()
            if not raw_kw:
                continue
            parts = [p for p in re.split(r"\s+", raw_kw) if p]
            if not parts:
                continue
            # Basic sanitation: keep alnum, underscore, hyphen
            clean_parts = [''.join(ch for ch in p if ch.isalnum() or ch in ('_', '-')) for p in parts]
            clean_parts = [p for p in clean_parts if p]
            if not clean_parts:
                continue
            if len(clean_parts) == 1:
                phrase = clean_parts[0]
            else:
                phrase = " & ".join(clean_parts)
            phrases.append(phrase)
        if not phrases:
            return []
        tsquery_string = " | ".join(phrases)
        sql = text(f"""
            SELECT 
                id,
                product_id,
                producer_name,
                product_name,
                product_description,
                combined_text,
                ts_rank(fts_combined, to_tsquery('simple', :q)) AS similarity_score
            FROM simple_products
            WHERE fts_combined @@ to_tsquery('simple', :q)
            ORDER BY similarity_score DESC
            LIMIT {self.max_results}
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"q": tsquery_string})
            results = [
                SearchResult(
                    id=r.id,
                    product_id=r.product_id,
                    producer_name=r.producer_name,
                    product_name=r.product_name,
                    product_description=r.product_description,
                    combined_text=r.combined_text,
                    similarity_score=float(r.similarity_score or 0.0),
                )
                for r in rows
            ]
        if results:
            logger.info("RAG: FTS phrase tsquery='%s' rows=%d", tsquery_string, len(results))
        else:
            logger.info("RAG: FTS phrase tsquery='%s' rows=0", tsquery_string)
        return results

    @staticmethod
    def _rrf_fuse(lists: List[List[SearchResult]], k: int = 60, limit: int = 10) -> List[SearchResult]:
        """Reciprocal Rank Fusion over multiple ranked lists.

        Items keyed by product_id. Score = Σ 1/(k + rank). rank is 1-based.
        Returns top `limit` fused, preserving original SearchResult of best (lowest) rank.
        """
        scores: Dict[str, float] = {}
        best_obj: Dict[str, SearchResult] = {}
        for lst in lists:
            for idx, item in enumerate(lst):
                rank = idx + 1
                inc = 1.0 / (k + rank)
                scores[item.product_id] = scores.get(item.product_id, 0.0) + inc
                # Keep highest quality representative (earliest rank overall)
                if item.product_id not in best_obj:
                    best_obj[item.product_id] = item
        fused = [
            (pid, scores[pid], best_obj[pid]) for pid in scores.keys()
        ]
        fused.sort(key=lambda x: x[1], reverse=True)
        out: List[SearchResult] = []
        for pid, score, obj in fused[:limit]:
            # Overwrite similarity_score with fused score for downstream formatting
            out.append(SearchResult(
                id=obj.id,
                product_id=obj.product_id,
                producer_name=obj.producer_name,
                product_name=obj.product_name,
                product_description=obj.product_description,
                combined_text=obj.combined_text,
                similarity_score=score,
            ))
        return out

    async def _vector_search(self, query_embedding: List[float]) -> List[SearchResult]:
        emb_str = "[" + ",".join(map(str, query_embedding)) + "]"
        sql_query = text(f"""
            SELECT 
                id,
                product_id,
                producer_name,
                product_name,
                product_description,
                combined_text,
                1 - (embedding <=> '{emb_str}'::vector) as similarity_score
            FROM simple_products
            WHERE 1 - (embedding <=> '{emb_str}'::vector) >= {self.similarity_threshold}
            ORDER BY embedding <=> '{emb_str}'::vector
            LIMIT {self.max_results}
        """)
        with self.engine.connect() as conn:
            result = conn.execute(sql_query)
            return [
                SearchResult(
                    id=row.id,
                    product_id=row.product_id,
                    producer_name=row.producer_name,
                    product_name=row.product_name,
                    product_description=row.product_description,
                    combined_text=row.combined_text,
                    similarity_score=float(row.similarity_score),
                )
                for row in result
            ]

    def format_search_results(self, results: List[SearchResult]) -> str:
        """Render search results as a readable block list.

        Each product is presented in a dedicated block that includes producer
        name, product name, product id, description, and similarity score.

        Returns an empty string when no results are provided.
        """
        if not results:
            return ""
        lines: list[str] = []
        for i, r in enumerate(results, 1):
            lines.append(
                f"--- Product {i} ----\n"
                f"Producer name: {r.producer_name}\n"
                f"Product name: {r.product_name}\n"
                f"Product id: {r.product_id}\n"
                f"Product description: {r.product_description}\n"
                f"Similarity score: {r.similarity_score:.2f}"
            )
        return "\n\n".join(lines)

    async def get_relevant_context(self, user_message: str) -> Optional[str]:
        if not self.enabled:
            return None
        logger.info("RAG: starting semantic + keyword hybrid retrieval")
        semantic_results = await self.semantic_search(user_message)
        logger.info("RAG: semantic search returned %d rows", len(semantic_results))
        # Extract keywords & FTS
        keywords = await self._extract_keywords(user_message)
        fts_results: List[SearchResult] = []
        if keywords:
            fts_results = self._fts_search(keywords)
        # Fusion
        fused: List[SearchResult]
        if fts_results:
            fused = self._rrf_fuse([semantic_results, fts_results], limit=self.max_results)
            logger.info(
                "RAG: fusion complete (semantic=%d, fts=%d, fused=%d)",
                len(semantic_results), len(fts_results), len(fused)
            )
        else:
            fused = semantic_results[: self.max_results]
            logger.info("RAG: fusion skipped (no FTS results)")
        if not fused:
            return None
        return self.format_search_results(fused)

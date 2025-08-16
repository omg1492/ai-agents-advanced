"""RAG (Retrieval-Augmented Generation) service for semantic search.

This version relies solely on ConfigService-provided configuration. No
environment variables are read directly here.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from openai import OpenAI

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
        if not all([host, database, user, password]):
            raise ValueError("Database configuration is incomplete (host, database, user, password)")
        url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        return create_engine(url, echo=False)

    def _create_openai_client(self) -> OpenAI:
        api_key = self._config.openai.api_key
        if not api_key:
            raise ValueError("Missing OpenAI API key in configuration")
        base_url = self._config.openai.base_url
        default_query = {"api-version": self._config.openai.api_version or "preview"} if base_url else None
        return OpenAI(api_key=api_key, base_url=base_url, default_query=default_query)

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
        if not results:
            return ""
        lines: list[str] = []
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i}. {r.producer_name} - {r.product_name}\n"
                f"   Description: {r.product_description}\n"
                f"   Similarity: {r.similarity_score:.2f}"
            )
        return "\n\n".join(lines)

    async def get_relevant_context(self, user_message: str) -> Optional[str]:
        if not self.enabled:
            return None
        # Info logs: when RAG is invoked and how many items were retrieved
        logger.info("RAG: starting semantic search for context")
        results = await self.semantic_search(user_message)
        logger.info("RAG: retrieved %d items", len(results))
        if not results:
            return None
        return self.format_search_results(results)

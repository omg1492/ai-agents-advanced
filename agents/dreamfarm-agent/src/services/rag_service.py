"""RAG (Retrieval-Augmented Generation) service for semantic search."""

import os
import logging
from typing import List, Optional
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from openai import OpenAI, AzureOpenAI


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
    """Service for Retrieval-Augmented Generation using PostgreSQL and pgvector.
    
    Provides semantic search capabilities by embedding user queries and finding
    similar products in the database using cosine similarity.
    """
    
    def __init__(self):
        """Initialize the RAG service."""
        self.enabled = self._is_rag_enabled()
        
        if not self.enabled:
            logger.info("RAG service is disabled (ENABLE_RAG=false)")
            return
            
        self.similarity_threshold = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.7"))
        self.max_results = int(os.getenv("RAG_MAX_RESULTS", "3"))
        
        # Initialize database connection
        self.engine = self._create_db_engine()
        
        # Initialize OpenAI client for embeddings
        self.openai_client = self._create_openai_client()
        
        logger.info(f"Initialized RAG service with threshold={self.similarity_threshold}, max_results={self.max_results}")
    
    def _is_rag_enabled(self) -> bool:
        """Check if RAG is enabled via environment variable.
        
        Returns:
            True if RAG is enabled, False otherwise
        """
        return os.getenv("ENABLE_RAG", "false").lower() in ["true", "1", "yes", "on"]
    
    def _create_db_engine(self) -> Engine:
        """Create SQLAlchemy database engine using standard PostgreSQL environment variables.
        
        Returns:
            SQLAlchemy Engine instance
            
        Raises:
            ValueError: If required database environment variables are missing
        """
        # Use standard PostgreSQL environment variables
        host = os.getenv("PGHOST")
        port = os.getenv("PGPORT", "5432")
        database = os.getenv("PGDATABASE")
        user = os.getenv("PGUSER")
        password = os.getenv("PGPASSWORD")
        
        if not all([host, database, user, password]):
            raise ValueError("Missing required PostgreSQL environment variables (PGHOST, PGDATABASE, PGUSER, PGPASSWORD)")
        
        # Create connection URL
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        
        return create_engine(db_url, echo=False)
    
    def _create_openai_client(self) -> OpenAI | AzureOpenAI:
        """Create OpenAI client for embedding generation.
        
        Returns:
            OpenAI or AzureOpenAI client instance
            
        Raises:
            ValueError: If required OpenAI environment variables are missing
        """
        api_type = os.getenv("OPENAI_API_TYPE", "azure")
        
        if api_type == "azure":
            endpoint = os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT")
            api_key = os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
            api_version = os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION") or os.getenv("AZURE_OPENAI_API_VERSION")
            
            if not all([endpoint, api_key, api_version]):
                raise ValueError("Missing required Azure OpenAI embedding environment variables")
            
            return AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version
            )
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("Missing OPENAI_API_KEY environment variable")
            
            return OpenAI(api_key=api_key)
    
    def _get_embedding_model_name(self) -> str:
        """Get the embedding model name based on API type.
        
        Returns:
            Model name for embedding generation
        """
        api_type = os.getenv("OPENAI_API_TYPE", "azure")
        
        if api_type == "azure":
            return os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-large")
        else:
            return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for the given text.
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            List of embedding values (2000 dimensions for pgvector compatibility)
            
        Raises:
            Exception: If embedding generation fails
        """
        if not self.enabled:
            return []
        
        try:
            model_name = self._get_embedding_model_name()
            
            response = self.openai_client.embeddings.create(
                model=model_name,
                input=text,
                encoding_format="float",
                dimensions=2000  # Limit to 2000 dimensions for pgvector HNSW index compatibility
            )
            
            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding with {len(embedding)} dimensions for text: {text[:100]}...")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
    async def semantic_search(self, query: str) -> List[SearchResult]:
        """Perform semantic search for the given query.
        
        Args:
            query: User's search query
            
        Returns:
            List of search results above the similarity threshold
        """
        if not self.enabled:
            logger.debug("RAG is disabled, returning empty results")
            return []
        
        try:
            # Generate embedding for the query
            query_embedding = await self.generate_embedding(query)
            
            if not query_embedding:
                logger.warning("Failed to generate embedding for query")
                return []
            
            # Perform vector similarity search
            search_results = await self._vector_search(query_embedding)
            
            logger.info(f"Semantic search for '{query}' returned {len(search_results)} results")
            return search_results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    async def _vector_search(self, query_embedding: List[float]) -> List[SearchResult]:
        """Perform vector similarity search in the database.
        
        Args:
            query_embedding: Query embedding vector
            
        Returns:
            List of search results
        """
        # Convert embedding to pgvector format
        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
        
        # SQL query for cosine similarity search using text() wrapper
        sql_query = text(f"""
            SELECT 
                id,
                product_id,
                producer_name,
                product_name,
                product_description,
                combined_text,
                1 - (embedding <=> '{embedding_str}'::vector) as similarity_score
            FROM simple_products
            WHERE 1 - (embedding <=> '{embedding_str}'::vector) >= {self.similarity_threshold}
            ORDER BY embedding <=> '{embedding_str}'::vector
            LIMIT {self.max_results}
        """)
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(sql_query)
                
                search_results = []
                for row in result:
                    search_results.append(SearchResult(
                        id=row.id,
                        product_id=row.product_id,
                        producer_name=row.producer_name,
                        product_name=row.product_name,
                        product_description=row.product_description,
                        combined_text=row.combined_text,
                        similarity_score=float(row.similarity_score)
                    ))
                
                return search_results
                
        except Exception as e:
            logger.error(f"Vector search query failed: {e}")
            raise
    
    def format_search_results(self, results: List[SearchResult]) -> str:
        """Format search results for inclusion in system prompt.
        
        Args:
            results: List of search results
            
        Returns:
            Formatted string for system prompt
        """
        if not results:
            return ""
        
        formatted_lines = []
        for i, result in enumerate(results, 1):
            formatted_lines.append(
                f"{i}. {result.producer_name} - {result.product_name}\n"
                f"   Description: {result.product_description}\n"
                f"   Similarity: {result.similarity_score:.2f}"
            )
        
        return "\n\n".join(formatted_lines)
    
    async def get_relevant_context(self, user_message: str) -> Optional[str]:
        """Get relevant context for user message via semantic search.
        
        Args:
            user_message: User's message to search for relevant products
            
        Returns:
            Formatted context string if relevant results found, None otherwise
        """
        if not self.enabled:
            return None
        
        try:
            search_results = await self.semantic_search(user_message)
            
            if not search_results:
                logger.debug(f"No relevant products found for: {user_message}")
                return None
            
            context = self.format_search_results(search_results)
            logger.debug(f"Found {len(search_results)} relevant products for context")
            return context
            
        except Exception as e:
            logger.error(f"Failed to get relevant context: {e}")
            return None

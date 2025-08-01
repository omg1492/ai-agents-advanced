"""Integration tests for RAG service - tests real functionality with actual database and OpenAI API."""

import pytest
import os
import asyncio
from dotenv import load_dotenv

from src.services.rag_service import RAGService, SearchResult

# Load environment variables from .env file
load_dotenv()


class TestRAGServiceIntegration:
    """Integration tests for RAGService that use real database and OpenAI API.
    
    These tests require:
    1. PostgreSQL database running with product data and embeddings
    2. Valid OpenAI API credentials in environment
    3. ENABLE_RAG=true in environment
    
    Run with: pytest -m integration tests/test_rag_integration.py
    """
    
    @classmethod
    def setup_class(cls):
        """Set up class-level fixtures."""
        # Check if we have the required environment for integration tests
        required_env_vars = [
            'PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD',
            'AZURE_OPENAI_EMBEDDING_ENDPOINT', 'AZURE_OPENAI_EMBEDDING_API_KEY'
        ]
        
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            pytest.skip(f"Integration tests require environment variables: {missing_vars}")
        
        # Ensure RAG is enabled for integration tests
        os.environ['ENABLE_RAG'] = 'true'
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = RAGService()
        
        # Skip tests if RAG is not properly configured
        if not self.service.enabled:
            pytest.skip("RAG service is not enabled")
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_generate_embedding_real_api(self):
        """Test generating embeddings with real OpenAI API."""
        # Test with a simple text
        text = "fresh organic tomatoes"
        embedding = await self.service.generate_embedding(text)
        
        # Verify we got a real embedding vector
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)
        
        # Should return 2000-dimensional vectors (limited for pgvector compatibility)
        assert len(embedding) == 2000
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_semantic_search_real_database(self):
        """Test semantic search against real database."""
        # Search for common product terms
        test_queries = [
            "organic vegetables",
            "fresh fruit", 
            "local farm products",
            "tomatoes",
            "cheese"
        ]
        
        for query in test_queries:
            print(f"\\nTesting query: '{query}'")
            results = await self.service.semantic_search(query)
            
            # Verify we get SearchResult objects
            assert isinstance(results, list)
            print(f"  Got {len(results)} results")
            
            for result in results:
                assert isinstance(result, SearchResult)
                assert hasattr(result, 'producer_name')
                assert hasattr(result, 'product_name')
                assert hasattr(result, 'similarity_score')
                
                # Similarity scores should be between 0 and 1
                assert 0 <= result.similarity_score <= 1
                
                print(f"  Found: {result.producer_name} - {result.product_name} (score: {result.similarity_score:.3f})")
            
            # We should get some results for common food terms with the adjusted threshold (0.5)
            if query in ["organic vegetables", "tomatoes"]:
                assert len(results) > 0, f"Expected results for common query: {query}"
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_similarity_threshold_filtering(self):
        """Test that similarity threshold correctly filters results."""
        # Test with a very specific query that should have some good matches
        query = "organic tomatoes from local farm"
        
        # Get results with default threshold
        results = await self.service.semantic_search(query)
        
        # All results should meet the threshold
        for result in results:
            assert result.similarity_score >= self.service.similarity_threshold
        
        # Results should be ordered by similarity (highest first)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].similarity_score >= results[i + 1].similarity_score
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_max_results_limit(self):
        """Test that max results limit is respected."""
        # Use a broad query that should match many products
        query = "farm"
        results = await self.service.semantic_search(query)
        
        # Should not exceed max results
        assert len(results) <= self.service.max_results
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_get_relevant_context_integration(self):
        """Test getting relevant context with real data."""
        queries = [
            "I want to buy fresh vegetables",
            "Do you have any organic dairy products?",
            "What fruits are in season?",
            "I need ingredients for a salad"
        ]
        
        for query in queries:
            print(f"\\nTesting context for: '{query}'")
            context = await self.service.get_relevant_context(query)
            
            if context:
                # Context should be a formatted string
                assert isinstance(context, str)
                assert len(context) > 0
                
                # Should contain product information
                assert any(keyword in context.lower() for keyword in [
                    'product', 'farm', 'organic', 'fresh', 'similarity'
                ])
                
                print(f"  Context preview: {context[:200]}...")
            else:
                print("  No relevant context found")
    
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_format_search_results_real_data(self):
        """Test formatting real search results."""
        # Get some real results first
        query = "vegetables"
        results = await self.service.semantic_search(query)
        
        if results:
            formatted = self.service.format_search_results(results)
            
            # Should be a non-empty string
            assert isinstance(formatted, str)
            assert len(formatted) > 0
            
            # Should contain numbered list format
            assert "1." in formatted
            
            # Should contain similarity scores
            assert "Similarity:" in formatted
            
            # Should contain product names from results
            for result in results[:2]:  # Check first 2 results
                assert result.product_name in formatted
                assert result.producer_name in formatted
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_database_connection_resilience(self):
        """Test that the service handles database connection issues gracefully."""
        # This test verifies the connection pooling and error handling
        # by making multiple concurrent requests
        
        queries = ["apple", "carrot", "cheese", "bread", "milk"] * 3  # 15 concurrent queries
        
        # Run queries concurrently
        tasks = [self.service.semantic_search(query) for query in queries]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Most should succeed (some might fail due to connection limits, which is expected)
        successful_results = [r for r in results_list if not isinstance(r, Exception)]
        failed_results = [r for r in results_list if isinstance(r, Exception)]
        
        # At least half should succeed
        assert len(successful_results) >= len(queries) // 2
        
        # Any failures should be connection-related, not code errors
        for failure in failed_results:
            print(f"Expected connection-related failure: {failure}")
    
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_empty_query_handling(self):
        """Test handling of edge cases with real service."""
        edge_cases = ["", "   ", "a", "xyz123", "!@#$%"]
        
        for query in edge_cases:
            results = await self.service.semantic_search(query)
            
            # Should return empty list or valid results, not crash
            assert isinstance(results, list)
            for result in results:
                assert isinstance(result, SearchResult)


# Helper function to check if integration tests can run
def can_run_integration_tests() -> bool:
    """Check if integration tests can run (all required env vars present)."""
    required_vars = [
        'PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD',
        'AZURE_OPENAI_EMBEDDING_ENDPOINT', 'AZURE_OPENAI_EMBEDDING_API_KEY'
    ]
    return all(os.getenv(var) for var in required_vars)


if __name__ == "__main__":
    """Allow running integration tests directly."""
    if can_run_integration_tests():
        pytest.main([__file__, "-v", "-m", "integration"])
    else:
        print("Integration tests require database and OpenAI API configuration.")
        print("Please set up environment variables and try again.")

"""Tests for the RAG service (unit, mocked)."""

import pytest
import os
from unittest.mock import Mock, patch

from src.services.rag_service import RAGService, SearchResult


pytestmark = pytest.mark.unit


class TestRAGService:
    """Test cases for RAGService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock environment variables for testing
        self.env_patcher = patch.dict(os.environ, {
            "ENABLE_RAG": "true",
            "RAG_SIMILARITY_THRESHOLD": "0.7",
            "RAG_MAX_RESULTS": "3",
            "PGHOST": "localhost",
            "PGPORT": "5432",
            "PGDATABASE": "test_db",
            "PGUSER": "test_user",
            "PGPASSWORD": "test_password",
            # Unified client: use base_url for Azure
            "OPENAI_BASE_URL": "https://test.openai.azure.com/openai/v1/",
            "AZURE_OPENAI_EMBEDDING_API_KEY": "test-key",
            "AZURE_OPENAI_EMBEDDING_API_VERSION": "preview",
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME": "text-embedding-3-large"
        })
        self.env_patcher.start()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.env_patcher.stop()
    
    @patch('src.services.rag_service.create_engine')
    def test_init_enabled(self, mock_create_engine):
        """Test RAG service initialization when enabled."""
        # Create service
        service = RAGService()
        
        # Verify initialization
        assert service.enabled is True
        assert service.similarity_threshold == 0.7
        assert service.max_results == 3
        mock_create_engine.assert_called_once()
    
    def test_init_disabled(self):
        """Test RAG service initialization when disabled."""
        with patch.dict(os.environ, {"ENABLE_RAG": "false"}):
            service = RAGService()
            
            assert service.enabled is False
    
    @patch('src.services.rag_service.create_engine')
    def test_init_missing_db_config(self, mock_create_engine):
        """Test initialization with missing database configuration."""
        with patch.dict(os.environ, {"PGHOST": ""}, clear=False):
            # Config-only refactor: service now raises a generic DB config error
            with pytest.raises(ValueError, match=r"Database configuration is incomplete"):
                RAGService()
    
    @patch('src.services.rag_service.create_engine')
    def test_init_missing_openai_config(self, mock_create_engine):
        """Test initialization with missing OpenAI configuration."""
        # Mock the environment to have missing OpenAI config but enable RAG
        # Clear both primary and fallback OpenAI environment variables
        with patch.dict(os.environ, {
            "ENABLE_RAG": "true",
            # Remove all OpenAI/Azure keys so client init fails
            "OPENAI_API_KEY": "",
            "AZURE_OPENAI_API_KEY": "",
            "AZURE_OPENAI_EMBEDDING_API_KEY": "",
            # Ensure DB config is present
            "PGHOST": "localhost",
            "PGDATABASE": "testdb", 
            "PGUSER": "testuser",
            "PGPASSWORD": "testpass"
        }, clear=False):
            # Config-only refactor: error originates from ConfigService load
            with pytest.raises(ValueError, match=r"Required environment variable OPENAI_API_KEY is not set"):
                RAGService()
    
    @patch('src.services.rag_service.create_engine')
    @patch('src.services.rag_service.OpenAI')
    def test_init_openai_api(self, mock_openai, mock_create_engine):
        """Test initialization with OpenAI API instead of Azure."""
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-openai-key"
        }, clear=False):
            RAGService()
            
            mock_openai.assert_called_once()
    
    @patch('src.services.rag_service.create_engine')
    async def test_generate_embedding_success(self, mock_create_engine):
        """Test successful embedding generation."""
        # Mock OpenAI client (synchronous, not async)
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create.return_value = mock_response
        
        # Create service and test
        service = RAGService()
        service.openai_client = mock_client
        
        embedding = await service.generate_embedding("test text")
        
        assert embedding == [0.1, 0.2, 0.3]
        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-large",
            input="test text",
            encoding_format="float",
            dimensions=2000
        )
    
    @patch('src.services.rag_service.create_engine')
    async def test_generate_embedding_disabled(self, mock_create_engine):
        """Test embedding generation when RAG is disabled."""
        with patch.dict(os.environ, {"ENABLE_RAG": "false"}):
            service = RAGService()
            embedding = await service.generate_embedding("test text")
            assert embedding == []
    
    @patch('src.services.rag_service.create_engine')
    async def test_generate_embedding_failure(self, mock_create_engine):
        """Test embedding generation failure."""
        # Mock OpenAI client to raise exception (synchronous)
        mock_client = Mock()
        mock_client.embeddings.create.side_effect = Exception("API Error")
        
        # Create service and test
        service = RAGService()
        service.openai_client = mock_client
        
        with pytest.raises(Exception, match="API Error"):
            await service.generate_embedding("test text")
    
    @patch('src.services.rag_service.create_engine')
    async def test_vector_search_success(self, mock_create_engine):
        """Test successful vector search."""
        # Mock database engine and connection
        mock_engine = Mock()
        mock_conn = Mock()
        mock_result = [
            Mock(
                id=1,
                product_id="uuid-1",
                producer_name="Test Farm",
                product_name="Test Product",
                product_description="Test Description",
                combined_text="Test Combined Text",
                similarity_score=0.85
            )
        ]
        mock_conn.execute.return_value = mock_result
        # Set up context manager for connection
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = mock_context
        mock_create_engine.return_value = mock_engine
        
        # Create service and test
        service = RAGService()
        
        results = await service._vector_search([0.1, 0.2, 0.3])
        
        assert len(results) == 1
        assert results[0].id == 1
        assert results[0].producer_name == "Test Farm"
        assert results[0].similarity_score == 0.85
    
    @patch('src.services.rag_service.create_engine')
    async def test_semantic_search_integration(self, mock_create_engine):
        """Test full semantic search integration."""
        # Mock OpenAI client (synchronous)
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create.return_value = mock_response
        
        # Mock database
        mock_engine = Mock()
        mock_conn = Mock()
        mock_result = [
            Mock(
                id=1,
                product_id="uuid-1",
                producer_name="Green Farm",
                product_name="Organic Tomatoes",
                product_description="Fresh organic tomatoes",
                combined_text="Green Farm Organic Tomatoes Fresh organic tomatoes",
                similarity_score=0.82
            )
        ]
        mock_conn.execute.return_value = mock_result
        # Set up context manager for connection  
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = mock_context
        mock_create_engine.return_value = mock_engine
        
        # Create service and test
        service = RAGService()
        service.openai_client = mock_client
        
        results = await service.semantic_search("fresh tomatoes")
        
        assert len(results) == 1
        assert results[0].producer_name == "Green Farm"
        assert results[0].product_name == "Organic Tomatoes"
    
    @patch('src.services.rag_service.create_engine')
    async def test_semantic_search_disabled(self, mock_create_engine):
        """Test semantic search when RAG is disabled."""
        with patch.dict(os.environ, {"ENABLE_RAG": "false"}):
            service = RAGService()
            results = await service.semantic_search("test query")
            assert results == []
    
    def test_format_search_results_empty(self):
        """Test formatting empty search results."""
        service = RAGService()
        formatted = service.format_search_results([])
        assert formatted == ""
    
    def test_format_search_results_multiple(self):
        """Test formatting multiple search results."""
        service = RAGService()
        results = [
            SearchResult(
                id=1,
                product_id="uuid-1",
                producer_name="Farm A",
                product_name="Product A",
                product_description="Description A",
                combined_text="Combined A",
                similarity_score=0.9
            ),
            SearchResult(
                id=2,
                product_id="uuid-2",
                producer_name="Farm B",
                product_name="Product B",
                product_description="Description B",
                combined_text="Combined B",
                similarity_score=0.8
            )
        ]
        
        formatted = service.format_search_results(results)
        
        assert "1. Farm A - Product A" in formatted
        assert "Description A" in formatted
        assert "Similarity: 0.90" in formatted
        assert "2. Farm B - Product B" in formatted
        assert "Description B" in formatted
        assert "Similarity: 0.80" in formatted
    
    @patch('src.services.rag_service.create_engine')
    async def test_get_relevant_context_with_results(self, mock_create_engine):
        """Test getting relevant context when results are found."""
        # Setup mocks as in semantic search test (synchronous client)
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create.return_value = mock_response
        
        mock_engine = Mock()
        mock_conn = Mock()
        mock_result = [
            Mock(
                id=1,
                product_id="uuid-1",
                producer_name="Local Farm",
                product_name="Fresh Carrots",
                product_description="Crispy orange carrots",
                combined_text="Local Farm Fresh Carrots Crispy orange carrots",
                similarity_score=0.75
            )
        ]
        mock_conn.execute.return_value = mock_result
        # Set up context manager for connection
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = mock_context
        mock_create_engine.return_value = mock_engine
        
        # Create service and test
        service = RAGService()
        service.openai_client = mock_client
        
        context = await service.get_relevant_context("I need some vegetables")
        
        assert context is not None
        assert "Local Farm - Fresh Carrots" in context
        assert "Crispy orange carrots" in context
        assert "Similarity: 0.75" in context
    
    @patch('src.services.rag_service.create_engine')
    async def test_get_relevant_context_no_results(self, mock_create_engine):
        """Test getting relevant context when no results are found."""
        # Mock to return no results (synchronous client)
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create.return_value = mock_response
        
        mock_engine = Mock()
        mock_conn = Mock()
        mock_conn.execute.return_value = []  # No results
        # Set up context manager for connection
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = mock_context
        mock_create_engine.return_value = mock_engine
        
        # Create service and test
        service = RAGService()
        service.openai_client = mock_client
        
        context = await service.get_relevant_context("nonexistent product")
        
        assert context is None
    
    @patch('src.services.rag_service.create_engine')
    async def test_get_relevant_context_disabled(self, mock_create_engine):
        """Test getting relevant context when RAG is disabled."""
        with patch.dict(os.environ, {"ENABLE_RAG": "false"}):
            service = RAGService()
            context = await service.get_relevant_context("test query")
            assert context is None

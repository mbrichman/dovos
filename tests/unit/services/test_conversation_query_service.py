"""
Unit tests for ConversationQueryService.

Tests conversation data retrieval logic with mocked backends.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from db.services.conversation_query_service import ConversationQueryService


@pytest.fixture
def mock_search_service():
    """Mock search service for testing."""
    return Mock()


@pytest.fixture
def query_service(mock_search_service):
    """Provide ConversationQueryService with mocked dependencies."""
    return ConversationQueryService(search_service=mock_search_service)


class TestGetAllConversations:
    """Test retrieving all conversations."""
    
    def test_get_all_conversations_returns_dict(self, query_service, mock_search_service):
        """Test that get_all_conversations returns proper structure."""
        mock_search_service.get_all_conversations.return_value = {
            "documents": [["doc1", "doc2"]],
            "metadatas": [{"title": "Conv1"}, {"title": "Conv2"}],
            "ids": ["id1", "id2"]
        }
        
        result = query_service.get_all_conversations()
        
        assert isinstance(result, dict)
        assert "documents" in result
        assert "metadatas" in result
        assert "ids" in result
    
    def test_get_all_conversations_with_limit(self, query_service, mock_search_service):
        """Test get_all_conversations with custom limit."""
        mock_search_service.get_all_conversations.return_value = {"documents": [], "metadatas": [], "ids": []}
        
        query_service.get_all_conversations(limit=100)
        
        mock_search_service.get_all_conversations.assert_called_once()
        call_kwargs = mock_search_service.get_all_conversations.call_args[1]
        assert call_kwargs.get('limit') == 100
    
    def test_get_all_conversations_with_includes(self, query_service, mock_search_service):
        """Test get_all_conversations with specific includes."""
        mock_search_service.get_all_conversations.return_value = {"documents": [], "metadatas": [], "ids": []}
        
        includes = ["documents", "metadatas"]
        query_service.get_all_conversations(include=includes)
        
        call_kwargs = mock_search_service.get_all_conversations.call_args[1]
        assert call_kwargs.get('include') == includes
    
    def test_get_all_conversations_empty_result(self, query_service, mock_search_service):
        """Test get_all_conversations when database is empty."""
        mock_search_service.get_all_conversations.return_value = {
            "documents": [],
            "metadatas": [],
            "ids": []
        }
        
        result = query_service.get_all_conversations()
        
        assert result["documents"] == []
        assert result["metadatas"] == []
        assert result["ids"] == []


class TestGetConversationById:
    """Test retrieving single conversation by ID."""
    
    def test_get_conversation_by_id_found(self, query_service, mock_search_service):
        """Test getting a conversation that exists."""
        mock_search_service.get_conversation_by_id.return_value = {
            "documents": [["conv text"]],
            "metadatas": [{"title": "Test Conversation"}],
            "ids": ["conv-123"]
        }
        
        result = query_service.get_conversation_by_id("conv-123")
        
        assert isinstance(result, dict)
        assert "documents" in result
        assert result["ids"] == ["conv-123"]
    
    def test_get_conversation_by_id_not_found(self, query_service, mock_search_service):
        """Test getting a conversation that doesn't exist."""
        mock_search_service.get_conversation_by_id.return_value = {
            "documents": [],
            "metadatas": [],
            "ids": []
        }
        
        result = query_service.get_conversation_by_id("nonexistent-id")
        
        assert result["documents"] == []
        assert result["ids"] == []
    
    def test_get_conversation_by_id_calls_search_service(self, query_service, mock_search_service):
        """Test that method delegates to search service."""
        mock_search_service.get_conversation_by_id.return_value = {"documents": [], "metadatas": [], "ids": []}
        
        query_service.get_conversation_by_id("test-id")
        
        mock_search_service.get_conversation_by_id.assert_called_once_with("test-id")


class TestSearchConversations:
    """Test searching conversations."""
    
    def test_search_conversations_basic(self, query_service, mock_search_service):
        """Test basic search with query."""
        mock_search_service.search_conversations.return_value = {
            "documents": [["result1"]],
            "metadatas": [{"title": "Match"}],
            "ids": ["search-1"]
        }
        
        result = query_service.search_conversations("test query")
        
        assert isinstance(result, dict)
        assert len(result["documents"]) > 0
    
    def test_search_conversations_with_filters(self, query_service, mock_search_service):
        """Test search with filter parameters."""
        mock_search_service.search_conversations.return_value = {"documents": [], "metadatas": [], "ids": []}
        
        query_service.search_conversations(
            "query",
            n_results=20,
            date_range=("2025-01-01", "2025-12-31"),
            search_type="hybrid"
        )
        
        call_kwargs = mock_search_service.search_conversations.call_args[1]
        assert call_kwargs.get('n_results') == 20
        assert call_kwargs.get('search_type') == "hybrid"
    
    def test_search_conversations_no_results(self, query_service, mock_search_service):
        """Test search that returns no results."""
        mock_search_service.search_conversations.return_value = {
            "documents": [],
            "metadatas": [],
            "ids": []
        }
        
        result = query_service.search_conversations("nonexistent term")
        
        assert result["documents"] == []
    
    def test_search_conversations_passes_params_correctly(self, query_service, mock_search_service):
        """Test that all search parameters are passed correctly."""
        mock_search_service.search_conversations.return_value = {"documents": [], "metadatas": [], "ids": []}
        
        query_service.search_conversations(
            query_text="test",
            n_results=15,
            date_range=("2025-01-01", "2025-06-30"),
            keyword_search=True,
            search_type="fts"
        )
        
        call_kwargs = mock_search_service.search_conversations.call_args[1]
        assert call_kwargs['n_results'] == 15
        assert call_kwargs['keyword_search'] is True
        assert call_kwargs['search_type'] == "fts"


class TestConversationQueryServiceInitialization:
    """Test service initialization."""
    
    def test_service_initializes_with_search_service(self, mock_search_service):
        """Test that service can be initialized with search service."""
        service = ConversationQueryService(search_service=mock_search_service)
        
        assert service is not None
        assert service.search_service == mock_search_service
    
    def test_service_default_limit(self, query_service):
        """Test that service has reasonable default limit."""
        # Should not raise error
        query_service.get_all_conversations()
        
        # Verify it was called with some limit
        query_service.search_service.get_all_conversations.assert_called_once()

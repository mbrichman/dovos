"""Tests for RAGController - TDD approach"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestRAGController:
    """Test suite for RAGController"""
    
    @pytest.fixture
    def mock_postgres_controller(self):
        """Create a mock PostgresController"""
        controller = Mock()
        controller.rag_query.return_value = {
            "query": "test query",
            "search_type": "semantic",
            "results": []
        }
        return controller
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock Flask request"""
        request = Mock()
        request.get_json.return_value = {
            "query": "test query"
        }
        return request
    
    @pytest.fixture
    def controller(self, mock_postgres_controller):
        """Create a RAGController instance"""
        from controllers.rag_controller import RAGController
        return RAGController(mock_postgres_controller)
    
    # ===== Initialization tests =====
    
    def test_controller_initialization(self, mock_postgres_controller):
        """Test RAGController initializes correctly"""
        from controllers.rag_controller import RAGController
        
        controller = RAGController(mock_postgres_controller)
        
        assert controller.postgres_controller == mock_postgres_controller
        assert hasattr(controller, 'default_window_size')
        assert hasattr(controller, 'max_window_size')
    
    # ===== Mode detection tests =====
    
    def test_detects_standard_mode_no_contextual_params(self, controller, mock_request):
        """Test that standard mode is used when no contextual params present"""
        mock_request.get_json.return_value = {
            "query": "test query",
            "n_results": 5
        }
        
        with patch('controllers.rag_controller.request', mock_request):
            result = controller.handle_rag_query()
        
        assert "retrieval_mode" not in result or result.get("retrieval_mode") != "contextual"
    
    def test_detects_contextual_mode_with_context_window(self, controller, mock_request):
        """Test that contextual mode is used when context_window is specified"""
        mock_request.get_json.return_value = {
            "query": "test query",
            "context_window": 3
        }
        
        with patch('controllers.rag_controller.request', mock_request):
            with patch.object(controller, '_execute_contextual_query') as mock_exec:
                mock_exec.return_value = {"retrieval_mode": "contextual"}
                result = controller.handle_rag_query()
        
        assert result["retrieval_mode"] == "contextual"
    
    def test_detects_contextual_mode_with_asymmetric_before(self, controller, mock_request):
        """Test contextual mode detected with asymmetric_before parameter"""
        mock_request.get_json.return_value = {
            "query": "test query",
            "asymmetric_before": 2
        }
        
        with patch('controllers.rag_controller.request', mock_request):
            with patch.object(controller, '_execute_contextual_query') as mock_exec:
                mock_exec.return_value = {"retrieval_mode": "contextual"}
                result = controller.handle_rag_query()
        
        assert result["retrieval_mode"] == "contextual"
    
    def test_detects_contextual_mode_with_use_contextual_flag(self, controller, mock_request):
        """Test contextual mode detected with use_contextual flag"""
        mock_request.get_json.return_value = {
            "query": "test query",
            "use_contextual": True
        }
        
        with patch('controllers.rag_controller.request', mock_request):
            with patch.object(controller, '_execute_contextual_query') as mock_exec:
                mock_exec.return_value = {"retrieval_mode": "contextual"}
                result = controller.handle_rag_query()
        
        assert result["retrieval_mode"] == "contextual"
    
    # ===== Parameter validation tests =====
    
    def test_validate_contextual_params_valid_context_window(self, controller):
        """Test validation accepts valid context_window"""
        data = {"context_window": 5}
        
        # Should not raise exception
        controller._validate_contextual_params(data)
    
    def test_validate_contextual_params_exceeds_max_window(self, controller):
        """Test validation rejects context_window exceeding max"""
        data = {"context_window": 9999}
        
        with pytest.raises(ValueError, match="context_window"):
            controller._validate_contextual_params(data)
    
    def test_validate_contextual_params_asymmetric_before_exceeds_max(self, controller):
        """Test validation rejects asymmetric_before exceeding max"""
        data = {"asymmetric_before": 9999}
        
        with pytest.raises(ValueError, match="asymmetric_before"):
            controller._validate_contextual_params(data)
    
    def test_validate_contextual_params_asymmetric_after_exceeds_max(self, controller):
        """Test validation rejects asymmetric_after exceeding max"""
        data = {"asymmetric_after": 9999}
        
        with pytest.raises(ValueError, match="asymmetric_after"):
            controller._validate_contextual_params(data)
    
    def test_validate_contextual_params_valid_asymmetric_params(self, controller):
        """Test validation accepts valid asymmetric parameters"""
        data = {
            "asymmetric_before": 3,
            "asymmetric_after": 2
        }
        
        # Should not raise exception
        controller._validate_contextual_params(data)
    
    # ===== Query execution tests =====
    
    def test_handle_rag_query_missing_query_parameter(self, controller, mock_request):
        """Test error handling when query parameter is missing"""
        mock_request.get_json.return_value = {}
        
        with patch('controllers.rag_controller.request', mock_request):
            result = controller.handle_rag_query()
        
        assert "error" in result
        assert "required" in result["error"].lower()
    
    def test_handle_rag_query_empty_query_string(self, controller, mock_request):
        """Test error handling when query string is empty"""
        mock_request.get_json.return_value = {"query": ""}
        
        with patch('controllers.rag_controller.request', mock_request):
            result = controller.handle_rag_query()
        
        assert "error" in result
    
    def test_execute_standard_query_delegates_to_postgres(self, controller, mock_request):
        """Test standard query delegates to postgres_controller"""
        mock_request.get_json.return_value = {
            "query": "test query",
            "n_results": 5
        }
        
        with patch('controllers.rag_controller.request', mock_request):
            result = controller.handle_rag_query()
        
        # Should have called postgres_controller.rag_query
        controller.postgres_controller.rag_query.assert_called_once()
    
    @patch('controllers.rag_controller.get_unit_of_work')
    @patch('controllers.rag_controller.ContextualRetrievalService')
    def test_execute_contextual_query_creates_service(self, mock_service_class, mock_uow, controller, mock_request):
        """Test contextual query creates ContextualRetrievalService"""
        mock_request.get_json.return_value = {
            "query": "test query",
            "context_window": 3
        }
        
        # Setup mocks
        mock_uow_instance = MagicMock()
        mock_uow.return_value.__enter__.return_value = mock_uow_instance
        
        mock_service = Mock()
        mock_service.retrieve_with_context.return_value = []
        mock_service_class.return_value = mock_service
        
        with patch('controllers.rag_controller.request', mock_request):
            result = controller.handle_rag_query()
        
        # Should have created service with UoW
        mock_service_class.assert_called_once_with(mock_uow_instance)
    
    # ===== Response formatting tests =====
    
    def test_format_contextual_results_empty_windows(self, controller):
        """Test formatting empty contextual results"""
        windows = []
        query = "test query"
        params = {"context_window": 3}
        
        result = controller._format_contextual_results(windows, query, params)
        
        assert result["query"] == query
        assert result["retrieval_mode"] == "contextual"
        assert result["results"] == []
    
    def test_format_contextual_results_with_windows(self, controller):
        """Test formatting contextual results with window data"""
        # Create mock window
        mock_window = Mock()
        mock_window.content = "Test content from conversation"
        mock_window.metadata = Mock(
            conversation_id="conv-123",
            window_id="win-1",
            conversation_title="Test Conversation",
            matched_message_id="msg-1",
            window_size=3,
            match_position=1,
            before_count=1,
            after_count=1,
            base_score=0.85,
            aggregated_score=0.90,
            roles=["user", "assistant"],
            token_estimate=100,
            retrieval_params={"context_window": 3}
        )
        
        windows = [mock_window]
        query = "test query"
        params = {"context_window": 3}
        
        result = controller._format_contextual_results(windows, query, params)
        
        assert result["retrieval_mode"] == "contextual"
        assert len(result["results"]) == 1
        assert result["results"][0]["id"] == "conv-123"
        assert result["results"][0]["title"] == "Test Conversation"
        assert result["results"][0]["content"] == "Test content from conversation"
        assert result["results"][0]["relevance"] == 0.90
    
    def test_format_contextual_results_truncates_long_preview(self, controller):
        """Test that long content is truncated in preview"""
        mock_window = Mock()
        mock_window.content = "a" * 600  # Long content
        mock_window.metadata = Mock(
            conversation_id="conv-123",
            window_id="win-1",
            conversation_title="Test",
            matched_message_id="msg-1",
            window_size=3,
            match_position=1,
            before_count=1,
            after_count=1,
            base_score=0.85,
            aggregated_score=0.90,
            roles=["user"],
            token_estimate=100,
            retrieval_params={}
        )
        
        windows = [mock_window]
        result = controller._format_contextual_results(windows, "query", {})
        
        # Preview should be truncated
        assert len(result["results"][0]["preview"]) <= 503  # 500 + "..."
        assert result["results"][0]["preview"].endswith("...")
    
    # ===== Error handling tests =====
    
    def test_handle_rag_query_handles_validation_error(self, controller, mock_request):
        """Test that validation errors are caught and returned"""
        mock_request.get_json.return_value = {
            "query": "test query",
            "context_window": 9999  # Invalid
        }
        
        with patch('controllers.rag_controller.request', mock_request):
            result = controller.handle_rag_query()
        
        assert "error" in result
        assert "context_window" in result["error"].lower()
    
    @patch('controllers.rag_controller.get_unit_of_work')
    @patch('controllers.rag_controller.ContextualRetrievalService')
    def test_handle_rag_query_handles_service_error(self, mock_service_class, mock_uow, controller, mock_request):
        """Test that service errors are caught and returned"""
        mock_request.get_json.return_value = {
            "query": "test query",
            "context_window": 3
        }
        
        # Setup mocks to raise error
        mock_uow_instance = MagicMock()
        mock_uow.return_value.__enter__.return_value = mock_uow_instance
        
        mock_service = Mock()
        mock_service.retrieve_with_context.side_effect = Exception("Service error")
        mock_service_class.return_value = mock_service
        
        with patch('controllers.rag_controller.request', mock_request):
            result = controller.handle_rag_query()
        
        assert "error" in result
    
    def test_handle_rag_query_standard_mode_handles_error(self, controller, mock_request):
        """Test error handling in standard mode"""
        mock_request.get_json.return_value = {
            "query": "test query"
        }
        
        # Make postgres_controller raise error
        controller.postgres_controller.rag_query.side_effect = Exception("DB error")
        
        with patch('controllers.rag_controller.request', mock_request):
            result = controller.handle_rag_query()
        
        assert "error" in result

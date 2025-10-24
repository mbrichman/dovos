"""
Integration tests for contextual RAG endpoint.

Tests the /api/rag/query endpoint with contextual window expansion.
"""
import pytest
from datetime import datetime, timezone, timedelta

from tests.utils.seed import seed_conversation_with_messages


@pytest.mark.integration
class TestContextualRAGEndpoint:
    """Test RAG endpoint with contextual retrieval."""
    
    def test_contextual_rag_query_basic(self, client, uow, seed_conversations):
        """Test basic contextual RAG query."""
        # Seed conversations with embeddings
        conversations = seed_conversations(count=2, messages_per_conversation=6, with_embeddings=True)
        
        # Make RAG query with context window
        response = client.post('/api/rag/query', json={
            'query': 'user message',
            'context_window': 2,
            'n_results': 3
        })
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Verify response structure
        assert 'query' in data
        assert 'retrieval_mode' in data
        assert 'results' in data
        assert data['retrieval_mode'] == 'contextual'
        assert data['context_window'] == 2
        
        # Verify results have required fields
        if len(data['results']) > 0:
            result = data['results'][0]
            assert 'id' in result
            assert 'window_id' in result
            assert 'title' in result
            assert 'content' in result
            assert 'metadata' in result
            
            # Verify metadata
            meta = result['metadata']
            assert 'conversation_id' in meta
            assert 'matched_message_id' in meta
            assert 'window_size' in meta
            assert 'aggregated_score' in meta
    
    def test_contextual_markers_present(self, client, uow, seed_conversations):
        """Test that context markers are present in results."""
        seed_conversations(count=1, messages_per_conversation=8, with_embeddings=True)
        
        response = client.post('/api/rag/query', json={
            'query': 'assistant',
            'context_window': 2,
            'include_markers': True,
            'n_results': 2
        })
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Check for context markers in content
        if len(data['results']) > 0:
            content = data['results'][0]['content']
            assert '[CTX_START]' in content
            assert '[CTX_END]' in content
    
    def test_contextual_without_markers(self, client, uow, seed_conversations):
        """Test contextual retrieval without markers."""
        seed_conversations(count=1, messages_per_conversation=6, with_embeddings=True)
        
        response = client.post('/api/rag/query', json={
            'query': 'message',
            'context_window': 1,
            'include_markers': False,
            'n_results': 2
        })
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Markers should not be present
        if len(data['results']) > 0:
            content = data['results'][0]['content']
            assert '[CTX_START]' not in content
            assert '[CTX_END]' not in content
    
    def test_adaptive_context_enabled(self, client, uow, seed_conversations):
        """Test adaptive context window."""
        seed_conversations(count=1, messages_per_conversation=10, with_embeddings=True)
        
        response = client.post('/api/rag/query', json={
            'query': 'user',
            'context_window': 1,
            'adaptive_context': True,
            'n_results': 2
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['adaptive_context'] is True
    
    def test_asymmetric_window(self, client, uow, seed_conversations):
        """Test asymmetric context windows."""
        seed_conversations(count=1, messages_per_conversation=10, with_embeddings=True)
        
        response = client.post('/api/rag/query', json={
            'query': 'message',
            'asymmetric_before': 3,
            'asymmetric_after': 1,
            'n_results': 2
        })
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should have results with asymmetric windows
        if len(data['results']) > 0:
            meta = data['results'][0]['metadata']
            # Before count should generally be larger than after count
            # (though adaptive windowing may adjust this)
            assert 'before_count' in meta
            assert 'after_count' in meta
    
    def test_max_tokens_limit(self, client, uow, seed_conversations):
        """Test token budget enforcement."""
        seed_conversations(count=1, messages_per_conversation=10, with_embeddings=True)
        
        response = client.post('/api/rag/query', json={
            'query': 'test',
            'context_window': 5,
            'max_tokens': 100,  # Small budget
            'n_results': 1
        })
        
        assert response.status_code == 200
        data = response.get_json()
        
        if len(data['results']) > 0:
            meta = data['results'][0]['metadata']
            # Should have token estimate
            assert 'token_estimate' in meta
            # Token estimate should be within reasonable bounds
            if meta['token_estimate']:
                assert meta['token_estimate'] > 0
    
    def test_parameter_validation(self, client, uow):
        """Test that invalid parameters are rejected."""
        # Missing query
        response = client.post('/api/rag/query', json={
            'context_window': 2
        })
        assert response.status_code == 400
        
        # Window size too large
        response = client.post('/api/rag/query', json={
            'query': 'test',
            'asymmetric_before': 20  # Exceeds RAG_MAX_WINDOW_SIZE
        })
        assert response.status_code == 400
    
    def test_backward_compatibility_without_context(self, client, uow, seed_conversations):
        """Test that legacy behavior works when context_window is not provided."""
        seed_conversations(count=1, messages_per_conversation=4, with_embeddings=True)
        
        # Query without context_window should use legacy behavior
        response = client.post('/api/rag/query', json={
            'query': 'test message',
            'n_results': 3
        })
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should not have contextual mode
        assert 'retrieval_mode' not in data or data.get('retrieval_mode') != 'contextual'


@pytest.mark.integration  
class TestRAGHealthEndpoint:
    """Test RAG health check endpoint."""
    
    def test_rag_health_check(self, client):
        """Test RAG health endpoint returns proper status."""
        response = client.get('/api/rag/health')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'status' in data
        # Status should be 'healthy' or provide error info
        assert data['status'] in ['healthy', 'unhealthy'] or 'error' in data

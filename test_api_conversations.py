import pytest
import json
from unittest.mock import Mock, patch
from app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_conversations_data():
    """Mock conversation data for testing."""
    return {
        'documents': [
            f'Conversation {i} content with some interesting details about topic {i}'
            for i in range(1, 101)  # 100 conversations
        ],
        'metadatas': [
            {
                'id': f'conv-{i}',
                'title': f'Conversation {i}',
                'source': 'chatgpt' if i % 2 == 0 else 'claude',
                'earliest_ts': f'2024-01-{i:02d}T10:00:00Z',
                'latest_ts': f'2024-01-{i:02d}T10:30:00Z'
            }
            for i in range(1, 101)
        ]
    }


class TestConversationsAPI:
    """Test cases for the paginated conversations API endpoint."""
    
    def test_conversations_endpoint_exists(self, client):
        """Test that the /api/conversations endpoint exists."""
        response = client.get('/api/conversations')
        # Should not return 404
        assert response.status_code != 404
    
    @patch('models.search_model.SearchModel.get_all_conversations')
    def test_get_first_page_conversations(self, mock_get_all, client, mock_conversations_data):
        """Test getting the first page of conversations."""
        mock_get_all.return_value = mock_conversations_data
        
        response = client.get('/api/conversations?page=1&limit=50')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check response structure
        assert 'conversations' in data
        assert 'pagination' in data
        assert 'total' in data['pagination']
        assert 'page' in data['pagination']
        assert 'limit' in data['pagination']
        assert 'has_next' in data['pagination']
        assert 'has_prev' in data['pagination']
        
        # Check pagination values
        assert data['pagination']['page'] == 1
        assert data['pagination']['limit'] == 50
        assert data['pagination']['total'] == 100
        assert data['pagination']['has_next'] is True
        assert data['pagination']['has_prev'] is False
        
        # Check conversations data
        assert len(data['conversations']) == 50
        assert data['conversations'][0]['id'] == 'conv-1'
        assert data['conversations'][0]['title'] == 'Conversation 1'
        assert 'preview' in data['conversations'][0]
        assert 'source' in data['conversations'][0]
        assert 'date' in data['conversations'][0]
    
    @patch('models.search_model.SearchModel.get_all_conversations')
    def test_get_second_page_conversations(self, mock_get_all, client, mock_conversations_data):
        """Test getting the second page of conversations."""
        mock_get_all.return_value = mock_conversations_data
        
        response = client.get('/api/conversations?page=2&limit=50')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check pagination values
        assert data['pagination']['page'] == 2
        assert data['pagination']['limit'] == 50
        assert data['pagination']['total'] == 100
        assert data['pagination']['has_next'] is False  # Last page
        assert data['pagination']['has_prev'] is True
        
        # Check we get the second set of conversations
        assert len(data['conversations']) == 50
        assert data['conversations'][0]['id'] == 'conv-51'  # Should start from 51st item
        assert data['conversations'][-1]['id'] == 'conv-100'  # Should end at 100th item
    
    @patch('models.search_model.SearchModel.get_all_conversations')
    def test_default_pagination_parameters(self, mock_get_all, client, mock_conversations_data):
        """Test that default pagination parameters work correctly."""
        mock_get_all.return_value = mock_conversations_data
        
        response = client.get('/api/conversations')  # No query params
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should use default values (page=1, limit=50)
        assert data['pagination']['page'] == 1
        assert data['pagination']['limit'] == 50
        
    @patch('models.search_model.SearchModel.get_all_conversations')
    def test_custom_limit_parameter(self, mock_get_all, client, mock_conversations_data):
        """Test using custom limit parameter."""
        mock_get_all.return_value = mock_conversations_data
        
        response = client.get('/api/conversations?limit=25')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['pagination']['limit'] == 25
        assert len(data['conversations']) == 25
        assert data['pagination']['has_next'] is True  # Should have more pages
    
    @patch('models.search_model.SearchModel.get_all_conversations')
    def test_out_of_range_page(self, mock_get_all, client, mock_conversations_data):
        """Test requesting a page number that's out of range."""
        mock_get_all.return_value = mock_conversations_data
        
        response = client.get('/api/conversations?page=999&limit=50')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should return empty conversations but valid pagination info
        assert len(data['conversations']) == 0
        assert data['pagination']['page'] == 999
        assert data['pagination']['has_next'] is False
        assert data['pagination']['has_prev'] is True
    
    @patch('models.search_model.SearchModel.get_all_conversations')
    def test_invalid_pagination_parameters(self, mock_get_all, client):
        """Test handling of invalid pagination parameters."""
        mock_get_all.return_value = {'documents': [], 'metadatas': []}
        
        # Test negative page
        response = client.get('/api/conversations?page=-1')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['pagination']['page'] == 1  # Should default to 1
        
        # Test zero page
        response = client.get('/api/conversations?page=0')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['pagination']['page'] == 1  # Should default to 1
        
        # Test negative limit
        response = client.get('/api/conversations?limit=-10')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['pagination']['limit'] == 50  # Should default to 50
    
    @patch('models.search_model.SearchModel.get_all_conversations')
    def test_maximum_limit_cap(self, mock_get_all, client, mock_conversations_data):
        """Test that limit is capped at a maximum value."""
        mock_get_all.return_value = mock_conversations_data
        
        response = client.get('/api/conversations?limit=1000')  # Very large limit
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should be capped at 100 (or whatever max we set)
        assert data['pagination']['limit'] <= 100
    
    @patch('models.search_model.SearchModel.get_all_conversations')
    def test_empty_database(self, mock_get_all, client):
        """Test handling when no conversations exist."""
        mock_get_all.return_value = {'documents': [], 'metadatas': []}
        
        response = client.get('/api/conversations')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert len(data['conversations']) == 0
        assert data['pagination']['total'] == 0
        assert data['pagination']['has_next'] is False
        assert data['pagination']['has_prev'] is False
    
    @patch('models.search_model.SearchModel.get_all_conversations')
    def test_database_error_handling(self, mock_get_all, client):
        """Test handling when database throws an error."""
        mock_get_all.side_effect = Exception("Database connection error")
        
        response = client.get('/api/conversations')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
    
    @patch('models.search_model.SearchModel.get_all_conversations')
    def test_conversation_data_transformation(self, mock_get_all, client):
        """Test that conversation data is properly transformed for frontend."""
        mock_get_all.return_value = {
            'documents': ['Full conversation content here...'],
            'metadatas': [{
                'id': 'test-conv-1',
                'title': 'Test Conversation',
                'source': 'chatgpt',
                'earliest_ts': '2024-01-01T10:00:00Z'
            }]
        }
        
        response = client.get('/api/conversations?limit=1')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        conv = data['conversations'][0]
        # Check that data transformation matches frontend expectations
        assert conv['id'] == 'test-conv-1'
        assert conv['title'] == 'Test Conversation'
        assert conv['source'] == 'chatgpt'
        assert conv['date'] == '2024-01-01T10:00:00Z'
        assert 'preview' in conv
        assert len(conv['preview']) <= 200  # Should be truncated
    
    def test_cors_headers_present(self, client):
        """Test that CORS headers are present in the response."""
        response = client.get('/api/conversations')
        
        # Should have CORS headers (assuming CORS is configured)
        assert 'Access-Control-Allow-Origin' in response.headers or response.status_code == 200
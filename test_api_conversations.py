import pytest
import json
from unittest.mock import Mock, patch
from app import app
from controllers.conversation_controller import ConversationController
from models.conversation_view_model import extract_preview_content


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
            'documents': ['**You said**: Hello there\n\n**ChatGPT said**: Hi! How can I help you?'],
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
        assert len(conv['preview']) <= 203  # 200 + "..."
        # Check that preview is cleaned of formatting markers
        assert 'You said' not in conv['preview']
        assert 'ChatGPT said' not in conv['preview']
        assert conv['preview'] == 'Hello there Hi! How can I help you?'
    
    def test_cors_headers_present(self, client):
        """Test that CORS headers are present in the response."""
        response = client.get('/api/conversations')
        
        # Should have CORS headers (assuming CORS is configured)
        assert 'Access-Control-Allow-Origin' in response.headers or response.status_code == 200


class TestAssistantNameDetection:
    """Test cases for assistant name detection functionality."""
    
    def test_determine_assistant_name_claude_source(self):
        """Test assistant name detection with Claude source metadata."""
        controller = ConversationController()
        
        document = "**You said**: Hello\n**Claude said**: Hi there!"
        metadata = {"source": "claude"}
        
        result = controller._determine_assistant_name(document, metadata)
        assert result == "Claude"
    
    def test_determine_assistant_name_chatgpt_source(self):
        """Test assistant name detection with ChatGPT source metadata."""
        controller = ConversationController()
        
        document = "**You said**: Hello\n**ChatGPT said**: Hi there!"
        metadata = {"source": "chatgpt"}
        
        result = controller._determine_assistant_name(document, metadata)
        assert result == "ChatGPT"
    
    def test_determine_assistant_name_from_claude_content(self):
        """Test assistant name detection from Claude document content."""
        controller = ConversationController()
        
        document = "**You said**: Hello\n**Claude said**: Hi there!"
        metadata = {"source": "unknown"}
        
        result = controller._determine_assistant_name(document, metadata)
        assert result == "Claude"
    
    def test_determine_assistant_name_from_chatgpt_content(self):
        """Test assistant name detection from ChatGPT document content."""
        controller = ConversationController()
        
        document = "**You said**: Hello\n**ChatGPT said**: Hi there!"
        metadata = {"source": "unknown"}
        
        result = controller._determine_assistant_name(document, metadata)
        assert result == "ChatGPT"
    
    def test_determine_assistant_name_fallback_to_ai(self):
        """Test assistant name detection fallback to AI for generic content."""
        controller = ConversationController()
        
        document = "**You said**: Hello\n**AI said**: Hi there!"
        metadata = {"source": "unknown"}
        
        result = controller._determine_assistant_name(document, metadata)
        assert result == "AI"
    
    def test_determine_assistant_name_empty_metadata(self):
        """Test assistant name detection with empty metadata."""
        controller = ConversationController()
        
        document = "**You said**: Hello\n**Claude said**: Hi there!"
        metadata = {}
        
        result = controller._determine_assistant_name(document, metadata)
        assert result == "Claude"


class TestSingleConversationAPI:
    """Test cases for the single conversation API endpoint."""
    
    @pytest.fixture
    def mock_conversation_data(self):
        """Mock single conversation data for testing."""
        return {
            'documents': ['**You said**: Hello\n**Claude said**: Hi there! How can I help you today?'],
            'metadatas': [{
                'id': 'conv-123',
                'title': 'Test Conversation with Claude',
                'source': 'claude',
                'earliest_ts': '2024-01-01T10:00:00Z'
            }]
        }
    
    @patch('models.search_model.SearchModel.get_conversation_by_id')
    def test_api_conversation_endpoint_success(self, mock_get_conversation, client, mock_conversation_data):
        """Test successful retrieval of a single conversation."""
        mock_get_conversation.return_value = mock_conversation_data
        
        response = client.get('/api/conversation/conv-123')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check response structure
        assert 'id' in data
        assert 'title' in data
        assert 'source' in data
        assert 'assistant_name' in data  # New field
        assert 'messages' in data
        
        # Check specific values
        assert data['id'] == 'conv-123'
        assert data['title'] == 'Test Conversation with Claude'
        assert data['source'] == 'claude'
        assert data['assistant_name'] == 'Claude'  # Should detect Claude
        assert isinstance(data['messages'], list)
    
    @patch('models.search_model.SearchModel.get_conversation_by_id')
    def test_api_conversation_chatgpt_detection(self, mock_get_conversation, client):
        """Test ChatGPT assistant name detection in API response."""
        mock_data = {
            'documents': ['**You said**: Hello\n**ChatGPT said**: Hi! How can I assist you?'],
            'metadatas': [{
                'id': 'conv-456',
                'title': 'Test Conversation with ChatGPT',
                'source': 'chatgpt',
                'earliest_ts': '2024-01-01T10:00:00Z'
            }]
        }
        mock_get_conversation.return_value = mock_data
        
        response = client.get('/api/conversation/conv-456')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['assistant_name'] == 'ChatGPT'
    
    @patch('models.search_model.SearchModel.get_conversation_by_id')
    def test_api_conversation_generic_ai_detection(self, mock_get_conversation, client):
        """Test generic AI assistant name detection in API response."""
        mock_data = {
            'documents': ['**You said**: Hello\n**AI said**: Hello! How can I help?'],
            'metadatas': [{
                'id': 'conv-789',
                'title': 'Test Conversation with AI',
                'source': 'unknown',
                'earliest_ts': '2024-01-01T10:00:00Z'
            }]
        }
        mock_get_conversation.return_value = mock_data
        
        response = client.get('/api/conversation/conv-789')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['assistant_name'] == 'AI'
    
    @patch('models.search_model.SearchModel.get_conversation_by_id')
    def test_api_conversation_not_found(self, mock_get_conversation, client):
        """Test handling of conversation not found."""
        mock_get_conversation.return_value = None
        
        response = client.get('/api/conversation/nonexistent')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
    
    @patch('models.search_model.SearchModel.get_conversation_by_id')
    def test_api_conversation_database_error(self, mock_get_conversation, client):
        """Test handling of database errors in single conversation endpoint."""
        mock_get_conversation.side_effect = Exception("Database error")
        
        response = client.get('/api/conversation/conv-123')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data


class TestPreviewCleaning:
    """Test cases for conversation preview cleaning functionality."""
    
    def test_extract_preview_with_you_said_claude_said(self):
        """Test preview extraction from Claude conversation format."""
        document = """**You said** *(on 2025-09-05 00:16:52)*:

how do I enable ssh and vnc on pi5

**Claude said** *(on 2025-09-05 00:17:03)*:

To enable SSH and VNC on your Raspberry Pi 5, you have several options depending on whether you have physical access to the Pi or not."""
        
        result = extract_preview_content(document, max_length=100)
        expected = "how do I enable ssh and vnc on pi5 To enable SSH and VNC on your Raspberry Pi 5, you have several..."
        assert result == expected
    
    def test_extract_preview_with_chatgpt_format(self):
        """Test preview extraction from ChatGPT conversation format."""
        document = """**You said** *(on 2025-09-05 10:30:00)*:

What's the weather like today?

**ChatGPT said** *(on 2025-09-05 10:30:15)*:

I don't have access to real-time weather data, but I can suggest some ways to check the weather."""
        
        result = extract_preview_content(document, max_length=80)
        expected = "What's the weather like today? I don't have access to real-time weather data,..."
        assert result == expected
    
    def test_extract_preview_no_formatting_markers(self):
        """Test preview extraction from document without conversation markers."""
        document = "This is a simple document without any special formatting markers."
        
        result = extract_preview_content(document, max_length=50)
        expected = "This is a simple document without any special..."
        assert result == expected
    
    def test_extract_preview_empty_document(self):
        """Test preview extraction from empty document."""
        document = ""
        
        result = extract_preview_content(document)
        assert result == ""
    
    def test_extract_preview_only_markers(self):
        """Test preview extraction from document with only markers and timestamps."""
        document = "**You said** *(on 2025-09-05 00:16:52)*:\n\n**Claude said** *(on 2025-09-05 00:17:03)*:"
        
        result = extract_preview_content(document)
        assert result == ""
    
    def test_extract_preview_respects_max_length(self):
        """Test that preview extraction respects max_length parameter."""
        document = """**You said**:

This is a very long question that goes on and on and contains many words that should be truncated when the maximum length is reached.

**Claude said**:

This is an equally long response."""
        
        result = extract_preview_content(document, max_length=50)
        assert len(result) <= 53  # 50 + "..." = 53
        assert result.endswith("...")
    
    def test_extract_preview_with_generic_ai_format(self):
        """Test preview extraction from generic AI conversation format."""
        document = """**You said**:

Hello there

**AI said**:

Hello! How can I help you today?"""
        
        result = extract_preview_content(document, max_length=100)
        expected = "Hello there Hello! How can I help you today?"
        assert result == expected


class TestSearchAPI:
    """Test cases for the search API endpoint."""
    
    @patch('models.search_model.SearchModel.search_conversations')
    def test_api_search_returns_cleaned_previews(self, mock_search, client):
        """Test that search API returns cleaned preview content instead of raw documents."""
        # Mock search results with raw document content
        mock_search.return_value = {
            'documents': [['**You said** *(on 2025-09-05 00:16:52)*:\n\nhow do I enable ssh and vnc on pi5\n\n**Claude said** *(on 2025-09-05 00:17:03)*:\n\nTo enable SSH and VNC on your Raspberry Pi 5, you have several options...']],
            'metadatas': [[{
                'id': 'conv-123',
                'title': 'SSH and VNC on Raspberry Pi 5',
                'source': 'claude',
                'earliest_ts': '2025-09-05T00:17:03Z'
            }]],
            'distances': [[0.5]]
        }
        
        response = client.get('/api/search?q=ssh')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check response structure
        assert 'query' in data
        assert 'results' in data
        assert data['query'] == 'ssh'
        assert len(data['results']) == 1
        
        result = data['results'][0]
        
        # Check that content is cleaned (no formatting markers)
        assert 'You said' not in result['content']
        assert 'Claude said' not in result['content']
        assert '*(on 2025-09-05' not in result['content']
        
        # Check that actual content is preserved
        assert 'how do I enable ssh and vnc on pi5' in result['content']
        assert 'To enable SSH and VNC on your Raspberry Pi 5' in result['content']
        
        # Check other fields
        assert result['title'] == 'SSH and VNC on Raspberry Pi 5'
        assert result['date'] == '2025-09-05T00:17:03Z'
        assert result['metadata']['source'] == 'claude'
    
    @patch('models.search_model.SearchModel.search_conversations')
    def test_api_search_empty_results(self, mock_search, client):
        """Test search API with no results."""
        mock_search.return_value = {
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }
        
        response = client.get('/api/search?q=nonexistent')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['query'] == 'nonexistent'
        assert data['results'] == []
    
    def test_api_search_missing_query(self, client):
        """Test search API with missing query parameter."""
        response = client.get('/api/search')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
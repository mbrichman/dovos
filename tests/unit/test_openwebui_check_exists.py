"""
Unit tests for OpenWebUI conversation existence check functionality.

Tests the check_conversation_exists_in_openwebui method that verifies if a
conversation still exists in the OpenWebUI instance.
"""
import pytest
from unittest.mock import MagicMock, patch, Mock
from uuid import uuid4
import requests


@pytest.fixture
def mock_uow():
    """Create a mock Unit of Work with necessary repositories."""
    uow = MagicMock()

    # Mock settings repository
    uow.settings = MagicMock()
    uow.settings.get_value = MagicMock()

    # Mock conversation repository
    uow.conversations = MagicMock()

    # Mock messages repository
    uow.messages = MagicMock()

    return uow


@pytest.fixture
def api_adapter(mock_uow):
    """Create an APIFormatAdapter instance with mocked dependencies."""
    with patch('db.adapters.api_format_adapter.get_unit_of_work') as mock_get_uow:
        mock_get_uow.return_value.__enter__.return_value = mock_uow
        mock_get_uow.return_value.__exit__.return_value = None

        from db.adapters.api_format_adapter import APIFormatAdapter
        adapter = APIFormatAdapter()

        yield adapter, mock_uow


@pytest.mark.unit
class TestCheckConversationExistsInOpenWebUI:
    """Test check_conversation_exists_in_openwebui method."""

    def test_conversation_exists_in_openwebui(self, api_adapter):
        """Test when conversation exists in OpenWebUI (returns 200)."""
        adapter, mock_uow = api_adapter

        # Setup: Create a conversation from OpenWebUI
        conv_id = str(uuid4())
        openwebui_uuid = str(uuid4())

        mock_conversation = MagicMock()
        mock_conversation.id = conv_id

        mock_message = MagicMock()
        mock_message.message_metadata = {
            'source': 'openwebui',
            'original_conversation_id': openwebui_uuid
        }

        mock_uow.conversations.get_by_id.return_value = mock_conversation
        mock_uow.messages.get_by_conversation.return_value = [mock_message]
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://oi.dovrichman.site',
            'openwebui_api_key': 'test-api-key'
        }.get(key)

        # Mock successful API response (conversation exists)
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            # Execute
            result = adapter.check_conversation_exists_in_openwebui(conv_id)

            # Verify
            assert result['exists'] is True
            assert result['is_openwebui_conversation'] is True
            assert result['openwebui_uuid'] == openwebui_uuid
            assert result['url'] == f'https://oi.dovrichman.site/c/{openwebui_uuid}'

            # Verify API was called correctly
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert f'/api/v1/chats/{openwebui_uuid}' in call_args[0][0]
            assert call_args[1]['headers']['Authorization'] == 'Bearer test-api-key'

    def test_conversation_not_exists_in_openwebui(self, api_adapter):
        """Test when conversation doesn't exist in OpenWebUI (returns 401)."""
        adapter, mock_uow = api_adapter

        # Setup
        conv_id = str(uuid4())
        openwebui_uuid = str(uuid4())

        mock_conversation = MagicMock()
        mock_message = MagicMock()
        mock_message.message_metadata = {
            'source': 'openwebui',
            'original_conversation_id': openwebui_uuid
        }

        mock_uow.conversations.get_by_id.return_value = mock_conversation
        mock_uow.messages.get_by_conversation.return_value = [mock_message]
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://oi.dovrichman.site',
            'openwebui_api_key': 'test-api-key'
        }.get(key)

        # Mock 401 response (conversation doesn't exist)
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_get.return_value = mock_response

            # Execute
            result = adapter.check_conversation_exists_in_openwebui(conv_id)

            # Verify
            assert result['exists'] is False
            assert result['is_openwebui_conversation'] is True
            assert result['openwebui_uuid'] == openwebui_uuid
            assert result['url'] == f'https://oi.dovrichman.site/c/{openwebui_uuid}'

    def test_not_openwebui_conversation(self, api_adapter):
        """Test when conversation is not from OpenWebUI."""
        adapter, mock_uow = api_adapter

        # Setup: Create a non-OpenWebUI conversation
        conv_id = str(uuid4())

        mock_conversation = MagicMock()
        mock_message = MagicMock()
        mock_message.message_metadata = {
            'source': 'chatgpt',  # Not OpenWebUI
            'original_conversation_id': str(uuid4())
        }

        mock_uow.conversations.get_by_id.return_value = mock_conversation
        mock_uow.messages.get_by_conversation.return_value = [mock_message]

        # Execute
        result = adapter.check_conversation_exists_in_openwebui(conv_id)

        # Verify - should return early without API call
        assert result['exists'] is False
        assert result['is_openwebui_conversation'] is False
        assert result['openwebui_uuid'] is None
        assert result['url'] is None

    def test_openwebui_not_configured(self, api_adapter):
        """Test when OpenWebUI is not configured in settings."""
        adapter, mock_uow = api_adapter

        # Setup
        conv_id = str(uuid4())

        mock_conversation = MagicMock()
        mock_message = MagicMock()
        mock_message.message_metadata = {
            'source': 'openwebui',
            'original_conversation_id': str(uuid4())
        }

        mock_uow.conversations.get_by_id.return_value = mock_conversation
        mock_uow.messages.get_by_conversation.return_value = [mock_message]
        mock_uow.settings.get_value.return_value = None  # Not configured

        # Execute
        result = adapter.check_conversation_exists_in_openwebui(conv_id)

        # Verify
        assert result['success'] is False
        assert 'not configured' in result['error'].lower()

    def test_network_error_handling(self, api_adapter):
        """Test graceful handling of network errors."""
        adapter, mock_uow = api_adapter

        # Setup
        conv_id = str(uuid4())
        openwebui_uuid = str(uuid4())

        mock_conversation = MagicMock()
        mock_message = MagicMock()
        mock_message.message_metadata = {
            'source': 'openwebui',
            'original_conversation_id': openwebui_uuid
        }

        mock_uow.conversations.get_by_id.return_value = mock_conversation
        mock_uow.messages.get_by_conversation.return_value = [mock_message]
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://oi.dovrichman.site',
            'openwebui_api_key': 'test-api-key'
        }.get(key)

        # Mock network error
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

            # Execute
            result = adapter.check_conversation_exists_in_openwebui(conv_id)

            # Verify - should return error gracefully
            assert result['success'] is False
            assert 'error' in result
            assert result['is_openwebui_conversation'] is True

    def test_conversation_not_found_in_db(self, api_adapter):
        """Test when conversation doesn't exist in local database."""
        adapter, mock_uow = api_adapter

        # Setup
        conv_id = str(uuid4())

        mock_uow.conversations.get_by_id.return_value = None

        # Execute
        result = adapter.check_conversation_exists_in_openwebui(conv_id)

        # Verify
        assert result['success'] is False
        assert 'not found' in result['error'].lower()

    def test_no_messages_in_conversation(self, api_adapter):
        """Test when conversation has no messages."""
        adapter, mock_uow = api_adapter

        # Setup
        conv_id = str(uuid4())

        mock_conversation = MagicMock()
        mock_uow.conversations.get_by_id.return_value = mock_conversation
        mock_uow.messages.get_by_conversation.return_value = []  # No messages

        # Execute
        result = adapter.check_conversation_exists_in_openwebui(conv_id)

        # Verify
        assert result['exists'] is False
        assert result['is_openwebui_conversation'] is False

    def test_missing_original_conversation_id(self, api_adapter):
        """Test when OpenWebUI conversation lacks original_conversation_id."""
        adapter, mock_uow = api_adapter

        # Setup
        conv_id = str(uuid4())

        mock_conversation = MagicMock()
        mock_message = MagicMock()
        mock_message.message_metadata = {
            'source': 'openwebui',
            # Missing 'original_conversation_id'
        }

        mock_uow.conversations.get_by_id.return_value = mock_conversation
        mock_uow.messages.get_by_conversation.return_value = [mock_message]

        # Execute
        result = adapter.check_conversation_exists_in_openwebui(conv_id)

        # Verify
        assert result['exists'] is False
        assert result['is_openwebui_conversation'] is False

    def test_ssl_verification_disabled(self, api_adapter):
        """Test that SSL verification is disabled (as per existing pattern)."""
        adapter, mock_uow = api_adapter

        # Setup
        conv_id = str(uuid4())
        openwebui_uuid = str(uuid4())

        mock_conversation = MagicMock()
        mock_message = MagicMock()
        mock_message.message_metadata = {
            'source': 'openwebui',
            'original_conversation_id': openwebui_uuid
        }

        mock_uow.conversations.get_by_id.return_value = mock_conversation
        mock_uow.messages.get_by_conversation.return_value = [mock_message]
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://oi.dovrichman.site',
            'openwebui_api_key': 'test-api-key'
        }.get(key)

        # Mock API response
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            # Execute
            adapter.check_conversation_exists_in_openwebui(conv_id)

            # Verify SSL verification is disabled
            call_args = mock_get.call_args
            assert call_args[1].get('verify') is False

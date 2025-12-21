"""
Unit tests for the conversation sync service.

Tests sync functionality with mocked OpenWebUI client and database.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from db.services.sync_service import (
    ConversationSyncService,
    SyncResult,
    SyncSource
)
from db.services.openwebui_client import (
    OpenWebUIChat,
    OpenWebUIClientError,
    OpenWebUIAuthError
)


class TestSyncResult:
    """Tests for the SyncResult dataclass."""

    def test_default_values(self):
        """Test SyncResult default initialization."""
        result = SyncResult()

        assert result.imported_count == 0
        assert result.updated_count == 0
        assert result.skipped_count == 0
        assert result.failed_count == 0
        assert result.messages_added == 0
        assert result.messages == []
        assert result.errors == []
        assert result.success is True

    def test_custom_values(self):
        """Test SyncResult with custom values."""
        result = SyncResult(
            imported_count=5,
            updated_count=3,
            skipped_count=10,
            failed_count=1,
            messages_added=15,
            messages=["Sync started"],
            errors=["One failure"],
            success=False
        )

        assert result.imported_count == 5
        assert result.updated_count == 3
        assert result.messages_added == 15
        assert result.success is False


class TestSyncSource:
    """Tests for the SyncSource enum."""

    def test_source_values(self):
        """Test sync source enum values."""
        assert SyncSource.OPENWEBUI.value == "openwebui"
        assert SyncSource.CLAUDE.value == "claude"
        assert SyncSource.CHATGPT.value == "chatgpt"


class TestConversationSyncService:
    """Tests for the ConversationSyncService."""

    @pytest.fixture
    def sync_service(self):
        """Create a sync service instance."""
        return ConversationSyncService()

    @pytest.fixture
    def mock_uow(self):
        """Create a mock unit of work."""
        uow = MagicMock()
        uow.__enter__ = Mock(return_value=uow)
        uow.__exit__ = Mock(return_value=False)
        uow.settings = MagicMock()
        uow.conversations = MagicMock()
        uow.messages = MagicMock()
        uow.jobs = MagicMock()
        return uow

    @pytest.fixture
    def mock_chat_summary(self):
        """Create a mock chat summary."""
        now = datetime.now(timezone.utc)
        return OpenWebUIChat(
            id="chat-123",
            title="Test Chat",
            updated_at=now,
            created_at=now - timedelta(hours=1)
        )

    @pytest.fixture
    def mock_full_chat(self):
        """Create a mock full chat with messages."""
        now = datetime.now(timezone.utc)
        return OpenWebUIChat(
            id="chat-123",
            title="Test Chat",
            updated_at=now,
            created_at=now - timedelta(hours=1),
            messages=[
                {"id": "msg-1", "role": "user", "content": "Hello!"},
                {"id": "msg-2", "role": "assistant", "content": "Hi there!"}
            ]
        )

    # ===== Configuration Tests =====

    @patch('db.services.sync_service.get_unit_of_work')
    def test_get_openwebui_client_success(self, mock_get_uow, sync_service, mock_uow):
        """Test getting client with valid configuration."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://test.openwebui.com',
            'openwebui_api_key': 'test-api-key'
        }.get(key)

        client = sync_service._get_openwebui_client()

        assert client.base_url == 'https://test.openwebui.com'
        assert client.api_key == 'test-api-key'

    @patch('db.services.sync_service.get_unit_of_work')
    def test_get_openwebui_client_missing_url(self, mock_get_uow, sync_service, mock_uow):
        """Test error when URL is missing."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': None,
            'openwebui_api_key': 'test-api-key'
        }.get(key)

        with pytest.raises(ValueError, match="URL and API key must be configured"):
            sync_service._get_openwebui_client()

    @patch('db.services.sync_service.get_unit_of_work')
    def test_get_openwebui_client_missing_key(self, mock_get_uow, sync_service, mock_uow):
        """Test error when API key is missing."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://test.openwebui.com',
            'openwebui_api_key': None
        }.get(key)

        with pytest.raises(ValueError, match="URL and API key must be configured"):
            sync_service._get_openwebui_client()

    # ===== sync_from_openwebui Tests =====

    @patch('db.services.sync_service.get_unit_of_work')
    def test_sync_from_openwebui_missing_config(self, mock_get_uow, sync_service, mock_uow):
        """Test sync fails gracefully when not configured."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.return_value = None

        result = sync_service.sync_from_openwebui()

        assert result.success is False
        assert len(result.errors) == 1
        assert "must be configured" in result.errors[0]

    @patch('db.services.sync_service.get_unit_of_work')
    @patch('db.services.sync_service.OpenWebUIClient')
    def test_sync_from_openwebui_auth_error(self, mock_client_class, mock_get_uow, sync_service, mock_uow):
        """Test sync handles authentication errors."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://test.com',
            'openwebui_api_key': 'bad-key'
        }.get(key)

        mock_client = MagicMock()
        mock_client.test_connection.side_effect = OpenWebUIAuthError("Invalid token")
        mock_client_class.return_value = mock_client

        result = sync_service.sync_from_openwebui()

        assert result.success is False
        assert "Authentication failed" in result.errors[0]

    @patch('db.services.sync_service.get_unit_of_work')
    @patch('db.services.sync_service.OpenWebUIClient')
    def test_sync_from_openwebui_connection_error(self, mock_client_class, mock_get_uow, sync_service, mock_uow):
        """Test sync handles connection errors."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://test.com',
            'openwebui_api_key': 'key'
        }.get(key)

        mock_client = MagicMock()
        mock_client.test_connection.side_effect = OpenWebUIClientError("Connection refused")
        mock_client_class.return_value = mock_client

        result = sync_service.sync_from_openwebui()

        assert result.success is False
        assert "Connection failed" in result.errors[0]

    @patch('db.services.sync_service.get_unit_of_work')
    @patch('db.services.sync_service.OpenWebUIClient')
    def test_sync_from_openwebui_success_no_chats(self, mock_client_class, mock_get_uow, sync_service, mock_uow):
        """Test sync with no chats to sync."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://test.com',
            'openwebui_api_key': 'key'
        }.get(key)
        mock_uow.conversations.get_source_tracking_map.return_value = {}

        mock_client = MagicMock()
        mock_client.test_connection.return_value = True
        mock_client.iter_all_chats.return_value = iter([])
        mock_client_class.return_value = mock_client

        result = sync_service.sync_from_openwebui()

        assert result.success is True
        assert result.imported_count == 0
        assert result.updated_count == 0
        assert result.skipped_count == 0

    @patch('db.services.sync_service.get_unit_of_work')
    @patch('db.services.sync_service.OpenWebUIClient')
    @patch.object(ConversationSyncService, '_create_conversation')
    def test_sync_from_openwebui_new_conversation(
        self, mock_create, mock_client_class, mock_get_uow,
        sync_service, mock_uow, mock_chat_summary, mock_full_chat
    ):
        """Test syncing a new conversation."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://test.com',
            'openwebui_api_key': 'key'
        }.get(key)
        mock_uow.conversations.get_source_tracking_map.return_value = {}
        mock_create.return_value = uuid4()

        mock_client = MagicMock()
        mock_client.test_connection.return_value = True
        mock_client.iter_all_chats.return_value = iter([mock_chat_summary])
        mock_client.get_chat.return_value = mock_full_chat
        mock_client_class.return_value = mock_client

        result = sync_service.sync_from_openwebui()

        assert result.success is True
        assert result.imported_count == 1
        assert result.updated_count == 0
        mock_create.assert_called_once()

    @patch('db.services.sync_service.get_unit_of_work')
    @patch('db.services.sync_service.OpenWebUIClient')
    def test_sync_from_openwebui_skip_unchanged(
        self, mock_client_class, mock_get_uow,
        sync_service, mock_uow, mock_chat_summary
    ):
        """Test skipping unchanged conversation."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://test.com',
            'openwebui_api_key': 'key'
        }.get(key)

        # Existing conversation with same timestamp
        existing_id = uuid4()
        mock_uow.conversations.get_source_tracking_map.return_value = {
            'chat-123': (existing_id, mock_chat_summary.updated_at)
        }

        mock_client = MagicMock()
        mock_client.test_connection.return_value = True
        mock_client.iter_all_chats.return_value = iter([mock_chat_summary])
        mock_client_class.return_value = mock_client

        result = sync_service.sync_from_openwebui()

        assert result.success is True
        assert result.skipped_count == 1
        assert result.imported_count == 0
        assert result.updated_count == 0

    @patch('db.services.sync_service.get_unit_of_work')
    @patch('db.services.sync_service.OpenWebUIClient')
    @patch.object(ConversationSyncService, '_upsert_messages')
    def test_sync_from_openwebui_update_changed(
        self, mock_upsert, mock_client_class, mock_get_uow,
        sync_service, mock_uow, mock_chat_summary, mock_full_chat
    ):
        """Test updating changed conversation."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://test.com',
            'openwebui_api_key': 'key'
        }.get(key)

        # Existing conversation with older timestamp
        existing_id = uuid4()
        older_time = mock_chat_summary.updated_at - timedelta(hours=1)
        mock_uow.conversations.get_source_tracking_map.return_value = {
            'chat-123': (existing_id, older_time)
        }
        mock_uow.conversations.get_by_id.return_value = Mock(title="Old Title")
        mock_upsert.return_value = 3

        mock_client = MagicMock()
        mock_client.test_connection.return_value = True
        mock_client.iter_all_chats.return_value = iter([mock_chat_summary])
        mock_client.get_chat.return_value = mock_full_chat
        mock_client_class.return_value = mock_client

        result = sync_service.sync_from_openwebui()

        assert result.success is True
        assert result.updated_count == 1
        assert result.messages_added == 3
        mock_upsert.assert_called_once()

    # ===== _sync_single_chat Tests =====

    @patch('db.services.sync_service.get_unit_of_work')
    @patch.object(ConversationSyncService, '_create_conversation')
    def test_sync_single_chat_new(
        self, mock_create, mock_get_uow,
        sync_service, mock_uow, mock_chat_summary, mock_full_chat
    ):
        """Test syncing a new chat."""
        mock_get_uow.return_value = mock_uow
        mock_create.return_value = uuid4()

        mock_client = MagicMock()
        mock_client.get_chat.return_value = mock_full_chat

        result = SyncResult()
        existing_map = {}

        sync_service._sync_single_chat(mock_client, mock_chat_summary, existing_map, result)

        assert result.imported_count == 1
        mock_create.assert_called_once_with(mock_full_chat, SyncSource.OPENWEBUI)

    @patch('db.services.sync_service.get_unit_of_work')
    def test_sync_single_chat_unchanged(
        self, mock_get_uow,
        sync_service, mock_uow, mock_chat_summary
    ):
        """Test skipping unchanged chat."""
        existing_id = uuid4()
        existing_map = {
            'chat-123': (existing_id, mock_chat_summary.updated_at)
        }

        result = SyncResult()
        mock_client = MagicMock()

        sync_service._sync_single_chat(mock_client, mock_chat_summary, existing_map, result)

        assert result.skipped_count == 1
        mock_client.get_chat.assert_not_called()

    @patch('db.services.sync_service.get_unit_of_work')
    @patch.object(ConversationSyncService, '_upsert_messages')
    def test_sync_single_chat_updated(
        self, mock_upsert, mock_get_uow,
        sync_service, mock_uow, mock_chat_summary, mock_full_chat
    ):
        """Test updating changed chat."""
        mock_get_uow.return_value = mock_uow
        mock_uow.conversations.get_by_id.return_value = Mock(title="Old Title")

        existing_id = uuid4()
        older_time = mock_chat_summary.updated_at - timedelta(hours=1)
        existing_map = {
            'chat-123': (existing_id, older_time)
        }

        mock_client = MagicMock()
        mock_client.get_chat.return_value = mock_full_chat
        mock_upsert.return_value = 2

        result = SyncResult()
        sync_service._sync_single_chat(mock_client, mock_chat_summary, existing_map, result)

        assert result.updated_count == 1
        assert result.messages_added == 2

    # ===== _compute_message_hash Tests =====

    def test_compute_message_hash(self, sync_service):
        """Test message hash computation."""
        hash1 = sync_service._compute_message_hash("Hello", "user")
        hash2 = sync_service._compute_message_hash("Hello", "user")
        hash3 = sync_service._compute_message_hash("Hello", "assistant")
        hash4 = sync_service._compute_message_hash("Goodbye", "user")

        # Same content and role should produce same hash
        assert hash1 == hash2
        # Different role should produce different hash
        assert hash1 != hash3
        # Different content should produce different hash
        assert hash1 != hash4
        # Hash should be 16 characters
        assert len(hash1) == 16

    # ===== _upsert_messages Tests =====

    @patch('db.services.sync_service.get_unit_of_work')
    @patch('db.services.sync_service.extract_messages')
    def test_upsert_messages_all_new(
        self, mock_extract, mock_get_uow,
        sync_service, mock_uow, mock_full_chat
    ):
        """Test upserting all new messages."""
        mock_get_uow.return_value = mock_uow
        mock_extract.return_value = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        mock_uow.messages.get_source_message_ids.return_value = set()
        mock_uow.messages.get_by_conversation.return_value = []
        mock_uow.messages.get_max_sequence.return_value = 0
        mock_uow.messages.create.return_value = Mock(id=uuid4())

        conversation_id = uuid4()
        count = sync_service._upsert_messages(
            conversation_id,
            mock_full_chat,
            SyncSource.OPENWEBUI
        )

        assert count == 2
        assert mock_uow.messages.create.call_count == 2
        assert mock_uow.jobs.enqueue.call_count == 2

    @patch('db.services.sync_service.get_unit_of_work')
    @patch('db.services.sync_service.extract_messages')
    def test_upsert_messages_skip_by_source_id(
        self, mock_extract, mock_get_uow,
        sync_service, mock_uow, mock_full_chat
    ):
        """Test skipping messages that exist by source ID."""
        mock_get_uow.return_value = mock_uow
        mock_extract.return_value = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        # First message already exists
        mock_uow.messages.get_source_message_ids.return_value = {"msg-1"}
        mock_uow.messages.get_by_conversation.return_value = []
        mock_uow.messages.get_max_sequence.return_value = 1
        mock_uow.messages.create.return_value = Mock(id=uuid4())

        conversation_id = uuid4()
        count = sync_service._upsert_messages(
            conversation_id,
            mock_full_chat,
            SyncSource.OPENWEBUI
        )

        # Only second message should be added
        assert count == 1
        assert mock_uow.messages.create.call_count == 1

    @patch('db.services.sync_service.get_unit_of_work')
    @patch('db.services.sync_service.extract_messages')
    def test_upsert_messages_skip_by_content_hash(
        self, mock_extract, mock_get_uow,
        sync_service, mock_uow, mock_full_chat
    ):
        """Test skipping messages that exist by content hash."""
        mock_get_uow.return_value = mock_uow
        mock_extract.return_value = [
            {"role": "user", "content": "Hello!"}
        ]
        mock_uow.messages.get_source_message_ids.return_value = set()
        # Existing message with same content
        existing_msg = Mock()
        existing_msg.content = "Hello!"
        existing_msg.role = "user"
        mock_uow.messages.get_by_conversation.return_value = [existing_msg]
        mock_uow.messages.get_max_sequence.return_value = 1

        conversation_id = uuid4()
        count = sync_service._upsert_messages(
            conversation_id,
            mock_full_chat,
            SyncSource.OPENWEBUI
        )

        # Should skip due to content match
        assert count == 0
        mock_uow.messages.create.assert_not_called()

    @patch('db.services.sync_service.get_unit_of_work')
    @patch('db.services.sync_service.extract_messages')
    def test_upsert_messages_skip_empty_content(
        self, mock_extract, mock_get_uow,
        sync_service, mock_uow, mock_full_chat
    ):
        """Test skipping messages with empty content."""
        mock_get_uow.return_value = mock_uow
        mock_extract.return_value = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "   "},
            {"role": "assistant", "content": "Valid message"}
        ]
        mock_uow.messages.get_source_message_ids.return_value = set()
        mock_uow.messages.get_by_conversation.return_value = []
        mock_uow.messages.get_max_sequence.return_value = 0
        mock_uow.messages.create.return_value = Mock(id=uuid4())

        conversation_id = uuid4()
        count = sync_service._upsert_messages(
            conversation_id,
            mock_full_chat,
            SyncSource.OPENWEBUI
        )

        # Only the valid message should be added
        assert count == 1

    # ===== get_sync_status Tests =====

    @patch('db.services.sync_service.get_unit_of_work')
    def test_get_sync_status(self, mock_get_uow, sync_service, mock_uow):
        """Test getting sync status."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.side_effect = lambda key: {
            'last_openwebui_sync': '2024-01-15T10:30:00Z',
            'openwebui_url': 'https://test.com',
            'openwebui_api_key': 'key'
        }.get(key)
        mock_uow.conversations.get_all_by_source_type.return_value = [Mock(), Mock()]
        mock_uow.conversations.count.return_value = 100

        status = sync_service.get_sync_status()

        assert status['last_openwebui_sync'] == '2024-01-15T10:30:00Z'
        assert status['total_conversations'] == 100
        assert status['openwebui_configured'] is True
        assert 'conversations_by_source' in status

    @patch('db.services.sync_service.get_unit_of_work')
    def test_get_sync_status_not_configured(self, mock_get_uow, sync_service, mock_uow):
        """Test sync status when not configured."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.return_value = None
        mock_uow.conversations.get_all_by_source_type.return_value = []
        mock_uow.conversations.count.return_value = 0

        status = sync_service.get_sync_status()

        assert status['last_openwebui_sync'] is None
        assert status['openwebui_configured'] is False

    # ===== _is_openwebui_configured Tests =====

    @patch('db.services.sync_service.get_unit_of_work')
    def test_is_openwebui_configured_true(self, mock_get_uow, sync_service, mock_uow):
        """Test when OpenWebUI is configured."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://test.com',
            'openwebui_api_key': 'key'
        }.get(key)

        assert sync_service._is_openwebui_configured() is True

    @patch('db.services.sync_service.get_unit_of_work')
    def test_is_openwebui_configured_false_no_url(self, mock_get_uow, sync_service, mock_uow):
        """Test when URL is missing."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': None,
            'openwebui_api_key': 'key'
        }.get(key)

        assert sync_service._is_openwebui_configured() is False

    @patch('db.services.sync_service.get_unit_of_work')
    def test_is_openwebui_configured_false_no_key(self, mock_get_uow, sync_service, mock_uow):
        """Test when API key is missing."""
        mock_get_uow.return_value = mock_uow
        mock_uow.settings.get_value.side_effect = lambda key: {
            'openwebui_url': 'https://test.com',
            'openwebui_api_key': None
        }.get(key)

        assert sync_service._is_openwebui_configured() is False

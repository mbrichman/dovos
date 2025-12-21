"""
Unit tests for repository source tracking methods.

Tests the new methods added for conversation sync functionality.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from db.models.models import Conversation, Message
from db.repositories.conversation_repository import ConversationRepository
from db.repositories.message_repository import MessageRepository


class TestConversationRepositorySourceTracking:
    """Tests for ConversationRepository source tracking methods."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock SQLAlchemy session."""
        session = MagicMock()
        return session

    @pytest.fixture
    def repo(self, mock_session):
        """Create a ConversationRepository with mocked session."""
        return ConversationRepository(mock_session)

    # ===== get_by_source Tests =====

    def test_get_by_source_found(self, repo, mock_session):
        """Test finding a conversation by source."""
        expected_conv = Conversation(
            id=uuid4(),
            title="Test Conv",
            source_type="openwebui",
            source_id="owui-123"
        )

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = expected_conv

        result = repo.get_by_source("openwebui", "owui-123")

        assert result == expected_conv
        mock_session.query.assert_called_once_with(Conversation)

    def test_get_by_source_not_found(self, repo, mock_session):
        """Test when conversation not found by source."""
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = repo.get_by_source("openwebui", "nonexistent")

        assert result is None

    def test_get_by_source_filters_correctly(self, repo, mock_session):
        """Test that get_by_source filters by both source_type and source_id."""
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        repo.get_by_source("claude", "claude-conv-456")

        # Verify filter was called twice (for source_type and source_id)
        assert mock_query.filter.call_count == 2

    # ===== get_all_by_source_type Tests =====

    def test_get_all_by_source_type_returns_list(self, repo, mock_session):
        """Test getting all conversations from a source type."""
        now = datetime.now(timezone.utc)
        expected_convs = [
            Conversation(id=uuid4(), title="Conv 1", source_type="openwebui", source_id="id-1"),
            Conversation(id=uuid4(), title="Conv 2", source_type="openwebui", source_id="id-2"),
        ]

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = expected_convs

        result = repo.get_all_by_source_type("openwebui")

        assert len(result) == 2
        assert result == expected_convs

    def test_get_all_by_source_type_empty(self, repo, mock_session):
        """Test when no conversations exist for source type."""
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        result = repo.get_all_by_source_type("unknown")

        assert result == []

    # ===== get_source_tracking_map Tests =====

    def test_get_source_tracking_map_builds_dict(self, repo, mock_session):
        """Test building the source tracking map."""
        now = datetime.now(timezone.utc)
        earlier = now - timedelta(hours=2)

        conv_id_1 = uuid4()
        conv_id_2 = uuid4()

        # Mock the query result as namedtuple-like rows
        mock_row_1 = MagicMock()
        mock_row_1.source_id = "owui-1"
        mock_row_1.id = conv_id_1
        mock_row_1.source_updated_at = now

        mock_row_2 = MagicMock()
        mock_row_2.source_id = "owui-2"
        mock_row_2.id = conv_id_2
        mock_row_2.source_updated_at = earlier

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_row_1, mock_row_2]

        result = repo.get_source_tracking_map("openwebui")

        assert "owui-1" in result
        assert "owui-2" in result
        assert result["owui-1"] == (conv_id_1, now)
        assert result["owui-2"] == (conv_id_2, earlier)

    def test_get_source_tracking_map_empty(self, repo, mock_session):
        """Test empty source tracking map."""
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        result = repo.get_source_tracking_map("openwebui")

        assert result == {}

    # ===== update_source_tracking Tests =====

    def test_update_source_tracking_success(self, repo, mock_session):
        """Test updating source tracking timestamp."""
        conv_id = uuid4()
        new_timestamp = datetime.now(timezone.utc)

        mock_conv = MagicMock()

        # Mock get_by_id
        with patch.object(repo, 'get_by_id', return_value=mock_conv):
            result = repo.update_source_tracking(conv_id, new_timestamp)

        assert result is True
        assert mock_conv.source_updated_at == new_timestamp
        mock_session.flush.assert_called_once()

    def test_update_source_tracking_not_found(self, repo, mock_session):
        """Test updating source tracking for nonexistent conversation."""
        conv_id = uuid4()
        new_timestamp = datetime.now(timezone.utc)

        with patch.object(repo, 'get_by_id', return_value=None):
            result = repo.update_source_tracking(conv_id, new_timestamp)

        assert result is False
        mock_session.flush.assert_not_called()


class TestMessageRepositorySourceTracking:
    """Tests for MessageRepository source tracking methods."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock SQLAlchemy session."""
        session = MagicMock()
        return session

    @pytest.fixture
    def repo(self, mock_session):
        """Create a MessageRepository with mocked session."""
        return MessageRepository(mock_session)

    # ===== get_by_source_message_id Tests =====

    def test_get_by_source_message_id_found(self, repo, mock_session):
        """Test finding a message by source message ID."""
        conv_id = uuid4()
        expected_msg = Message(
            id=uuid4(),
            conversation_id=conv_id,
            role="user",
            content="Hello",
            source_message_id="src-msg-1"
        )

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = expected_msg

        result = repo.get_by_source_message_id(conv_id, "src-msg-1")

        assert result == expected_msg

    def test_get_by_source_message_id_not_found(self, repo, mock_session):
        """Test when message not found by source message ID."""
        conv_id = uuid4()

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = repo.get_by_source_message_id(conv_id, "nonexistent")

        assert result is None

    def test_get_by_source_message_id_filters_by_conversation(self, repo, mock_session):
        """Test that get_by_source_message_id filters by conversation_id."""
        conv_id = uuid4()

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        repo.get_by_source_message_id(conv_id, "msg-id")

        # Verify filter was called twice (for conversation_id and source_message_id)
        assert mock_query.filter.call_count == 2

    # ===== get_max_sequence Tests =====

    def test_get_max_sequence_returns_value(self, repo, mock_session):
        """Test getting max sequence number."""
        conv_id = uuid4()

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 15

        result = repo.get_max_sequence(conv_id)

        assert result == 15

    def test_get_max_sequence_no_messages(self, repo, mock_session):
        """Test getting max sequence when no messages exist."""
        conv_id = uuid4()

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = None

        result = repo.get_max_sequence(conv_id)

        assert result == 0

    def test_get_max_sequence_zero(self, repo, mock_session):
        """Test getting max sequence when it's actually zero."""
        conv_id = uuid4()

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 0

        result = repo.get_max_sequence(conv_id)

        assert result == 0

    # ===== get_source_message_ids Tests =====

    def test_get_source_message_ids_returns_set(self, repo, mock_session):
        """Test getting source message IDs as a set."""
        conv_id = uuid4()

        mock_row_1 = MagicMock()
        mock_row_1.source_message_id = "msg-1"
        mock_row_2 = MagicMock()
        mock_row_2.source_message_id = "msg-2"
        mock_row_3 = MagicMock()
        mock_row_3.source_message_id = "msg-3"

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_row_1, mock_row_2, mock_row_3]

        result = repo.get_source_message_ids(conv_id)

        assert result == {"msg-1", "msg-2", "msg-3"}
        assert isinstance(result, set)

    def test_get_source_message_ids_empty(self, repo, mock_session):
        """Test getting source message IDs when none exist."""
        conv_id = uuid4()

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        result = repo.get_source_message_ids(conv_id)

        assert result == set()

    def test_get_source_message_ids_excludes_none(self, repo, mock_session):
        """Test that get_source_message_ids filters out None values."""
        conv_id = uuid4()

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        repo.get_source_message_ids(conv_id)

        # Verify two filters: conversation_id and source_message_id IS NOT NULL
        assert mock_query.filter.call_count == 2

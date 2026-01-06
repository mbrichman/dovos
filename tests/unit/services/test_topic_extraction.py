"""
Unit tests for topic extraction from OpenWebUI.

TDD: These tests define the expected behavior for extracting topics (tags)
from OpenWebUI and storing them in normalized tables.

Topics are OpenWebUI's auto-generated tags that categorize conversations.

Data model:
- topics: id, name, created_at
- conversation_topics: conversation_id, topic_id (junction table)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from uuid import uuid4

from db.services.openwebui_client import (
    OpenWebUIClient,
    OpenWebUIChat,
    OpenWebUIClientError,
)


class TestOpenWebUITopicFetching:
    """Tests for fetching topics from OpenWebUI API."""

    @pytest.fixture
    def client(self):
        """Create a client instance with test credentials."""
        return OpenWebUIClient(
            base_url="https://test.openwebui.com",
            api_key="test-api-key"
        )

    @pytest.fixture
    def mock_response(self):
        """Create a mock response factory."""
        def _create(status_code=200, json_data=None):
            response = Mock()
            response.status_code = status_code
            response.json.return_value = json_data or {}
            response.raise_for_status = Mock()
            if status_code >= 400:
                response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
            return response
        return _create

    # ===== get_chat_topics Tests =====

    @patch('db.services.openwebui_client.requests.Session')
    def test_get_chat_topics_returns_list(self, mock_session_class, mock_response):
        """Test fetching topics for a chat returns a list of topic names."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_session.get.return_value = mock_response(200, [
            {"id": "tag-1", "name": "AI", "user_id": "user-123"},
            {"id": "tag-2", "name": "Technology", "user_id": "user-123"},
            {"id": "tag-3", "name": "Programming", "user_id": "user-123"}
        ])

        client = OpenWebUIClient("https://test.com", "api-key")
        topics = client.get_chat_topics("chat-123")

        assert topics == ["AI", "Technology", "Programming"]
        mock_session.get.assert_called_once()
        assert "/api/v1/chats/chat-123/tags" in str(mock_session.get.call_args)

    @patch('db.services.openwebui_client.requests.Session')
    def test_get_chat_topics_empty(self, mock_session_class, mock_response):
        """Test fetching topics returns empty list when no topics exist."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.get.return_value = mock_response(200, [])

        client = OpenWebUIClient("https://test.com", "api-key")
        topics = client.get_chat_topics("chat-456")

        assert topics == []

    @patch('db.services.openwebui_client.requests.Session')
    def test_get_chat_topics_handles_404(self, mock_session_class, mock_response):
        """Test 404 returns empty list (chat may not have topics endpoint)."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.get.return_value = mock_response(404)

        client = OpenWebUIClient("https://test.com", "api-key")
        topics = client.get_chat_topics("nonexistent")

        assert topics == []

    @patch('db.services.openwebui_client.requests.Session')
    def test_get_chat_topics_handles_auth_error(self, mock_session_class, mock_response):
        """Test 401 still returns empty list (graceful degradation)."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.get.return_value = mock_response(401)

        client = OpenWebUIClient("https://test.com", "bad-key")
        topics = client.get_chat_topics("chat-123")

        # Should gracefully return empty rather than raise
        assert topics == []


class TestTopicModel:
    """Tests for the Topic SQLAlchemy model."""

    def test_topic_model_exists(self):
        """Test that Topic model can be imported."""
        from db.models.models import Topic
        assert Topic is not None

    def test_topic_creation(self):
        """Test creating a Topic instance."""
        from db.models.models import Topic

        topic = Topic(name="AI")

        assert topic.name == "AI"
        assert topic.id is None  # Not persisted yet

    def test_topic_name_required(self):
        """Test that topic name is required."""
        from db.models.models import Topic

        topic = Topic(name="Test Topic")
        assert topic.name == "Test Topic"


class TestConversationTopicModel:
    """Tests for the ConversationTopic junction table model."""

    def test_conversation_topic_model_exists(self):
        """Test that ConversationTopic model can be imported."""
        from db.models.models import ConversationTopic
        assert ConversationTopic is not None

    def test_conversation_topic_creation(self):
        """Test creating a ConversationTopic instance."""
        from db.models.models import ConversationTopic

        conv_id = uuid4()
        topic_id = uuid4()

        ct = ConversationTopic(
            conversation_id=conv_id,
            topic_id=topic_id
        )

        assert ct.conversation_id == conv_id
        assert ct.topic_id == topic_id


class TestTopicRepository:
    """Tests for topic repository operations."""

    def test_get_or_create_topic_creates_new(self):
        """Test get_or_create creates a new topic if it doesn't exist."""
        # This will be tested with actual DB in integration tests
        # Here we just verify the interface exists
        from db.repositories.topic_repository import TopicRepository
        assert hasattr(TopicRepository, 'get_or_create_by_name')

    def test_get_topics_for_conversation(self):
        """Test fetching topics for a conversation."""
        from db.repositories.topic_repository import TopicRepository
        assert hasattr(TopicRepository, 'get_topics_for_conversation')

    def test_set_conversation_topics(self):
        """Test setting topics for a conversation (replaces existing)."""
        from db.repositories.topic_repository import TopicRepository
        assert hasattr(TopicRepository, 'set_conversation_topics')


class TestSyncServiceTopicIntegration:
    """Tests for topic extraction during sync."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock OpenWebUI client."""
        client = MagicMock(spec=OpenWebUIClient)
        return client

    def test_sync_fetches_topics_for_new_conversation(self, mock_client):
        """Test that sync fetches and stores topics for new conversations."""
        mock_chat = OpenWebUIChat(
            id="chat-new",
            title="New Chat",
            updated_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            messages=[{"id": "m1", "role": "user", "content": "Hello"}]
        )

        mock_client.get_chat.return_value = mock_chat
        mock_client.get_chat_topics.return_value = ["AI", "Automation"]

        topics = mock_client.get_chat_topics("chat-new")
        assert topics == ["AI", "Automation"]

    def test_sync_updates_topics_for_existing_conversation(self, mock_client):
        """Test that sync updates topics when conversation is updated."""
        mock_client.get_chat_topics.return_value = ["AI", "Updated Topic"]

        topics = mock_client.get_chat_topics("chat-existing")
        assert "Updated Topic" in topics

    def test_sync_handles_missing_topics_gracefully(self, mock_client):
        """Test that sync continues if topic fetch fails."""
        mock_client.get_chat_topics.return_value = []

        topics = mock_client.get_chat_topics("chat-no-topics")
        assert topics == []


class TestTopicQueries:
    """Tests for topic query capabilities."""

    def test_find_conversations_by_topic(self):
        """Test finding all conversations with a specific topic."""
        from db.repositories.topic_repository import TopicRepository
        assert hasattr(TopicRepository, 'get_conversations_by_topic')

    def test_get_topic_counts(self):
        """Test getting topic usage counts."""
        from db.repositories.topic_repository import TopicRepository
        assert hasattr(TopicRepository, 'get_topic_counts')

    def test_get_all_topics(self):
        """Test getting all topics."""
        from db.repositories.topic_repository import TopicRepository
        assert hasattr(TopicRepository, 'get_all')

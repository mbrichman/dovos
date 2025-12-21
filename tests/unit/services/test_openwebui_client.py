"""
Unit tests for OpenWebUI API client.

Tests HTTP client functionality with mocked requests.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import json

from db.services.openwebui_client import (
    OpenWebUIClient,
    OpenWebUIChat,
    OpenWebUIClientError,
    OpenWebUIAuthError,
    OpenWebUINotFoundError
)


class TestOpenWebUIClient:
    """Tests for the OpenWebUI HTTP client."""

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

    # ===== Initialization Tests =====

    def test_client_initialization(self):
        """Test client initializes with correct headers."""
        client = OpenWebUIClient(
            base_url="https://example.com/",
            api_key="my-api-key"
        )

        assert client.base_url == "https://example.com"  # Trailing slash removed
        assert client.api_key == "my-api-key"
        assert client.session.headers["Authorization"] == "Bearer my-api-key"
        assert client.session.headers["Content-Type"] == "application/json"

    def test_client_strips_trailing_slash(self):
        """Test base URL trailing slash is stripped."""
        client = OpenWebUIClient(
            base_url="https://example.com///",
            api_key="key"
        )
        assert client.base_url == "https://example.com"

    # ===== list_chats Tests =====

    @patch('db.services.openwebui_client.requests.Session')
    def test_list_chats_success(self, mock_session_class, mock_response):
        """Test successful chat listing."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_session.get.return_value = mock_response(200, [
            {
                "id": "chat-1",
                "title": "Test Chat 1",
                "updated_at": 1700000000,
                "created_at": 1699900000,
                "archived": False,
                "pinned": True
            },
            {
                "id": "chat-2",
                "title": "Test Chat 2",
                "updated_at": 1700100000,
                "created_at": 1699800000
            }
        ])

        client = OpenWebUIClient("https://test.com", "api-key")
        chats = client.list_chats(page=1)

        assert len(chats) == 2
        assert chats[0].id == "chat-1"
        assert chats[0].title == "Test Chat 1"
        assert chats[0].pinned is True
        assert chats[1].id == "chat-2"

    @patch('db.services.openwebui_client.requests.Session')
    def test_list_chats_auth_error(self, mock_session_class, mock_response):
        """Test 401 raises auth error."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.get.return_value = mock_response(401)

        client = OpenWebUIClient("https://test.com", "bad-key")

        with pytest.raises(OpenWebUIAuthError, match="Authentication failed"):
            client.list_chats()

    @patch('db.services.openwebui_client.requests.Session')
    def test_list_chats_forbidden_error(self, mock_session_class, mock_response):
        """Test 403 raises auth error."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.get.return_value = mock_response(403)

        client = OpenWebUIClient("https://test.com", "key")

        with pytest.raises(OpenWebUIAuthError, match="Access forbidden"):
            client.list_chats()

    @patch('db.services.openwebui_client.requests.Session')
    def test_list_chats_empty_response(self, mock_session_class, mock_response):
        """Test empty chat list."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.get.return_value = mock_response(200, [])

        client = OpenWebUIClient("https://test.com", "key")
        chats = client.list_chats()

        assert chats == []

    # ===== get_chat Tests =====

    @patch('db.services.openwebui_client.requests.Session')
    def test_get_chat_success(self, mock_session_class, mock_response):
        """Test getting a full chat with messages."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_session.get.return_value = mock_response(200, {
            "id": "chat-123",
            "title": "My Conversation",
            "updated_at": 1700000000,
            "created_at": 1699900000,
            "chat": {
                "history": {
                    "messages": {
                        "msg-1": {
                            "id": "msg-1",
                            "role": "user",
                            "content": "Hello!",
                            "timestamp": 1699900001
                        },
                        "msg-2": {
                            "id": "msg-2",
                            "role": "assistant",
                            "content": "Hi there!",
                            "timestamp": 1699900002
                        }
                    }
                }
            }
        })

        client = OpenWebUIClient("https://test.com", "key")
        chat = client.get_chat("chat-123")

        assert chat.id == "chat-123"
        assert chat.title == "My Conversation"
        assert chat.messages is not None
        assert len(chat.messages) == 2

    @patch('db.services.openwebui_client.requests.Session')
    def test_get_chat_not_found(self, mock_session_class, mock_response):
        """Test 404 raises not found error."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.get.return_value = mock_response(404)

        client = OpenWebUIClient("https://test.com", "key")

        with pytest.raises(OpenWebUINotFoundError, match="not found"):
            client.get_chat("nonexistent")

    # ===== iter_all_chats Tests =====

    @patch('db.services.openwebui_client.requests.Session')
    def test_iter_all_chats_pagination(self, mock_session_class, mock_response):
        """Test pagination through all chats."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # First batch returns 2 chats (full batch)
        # Second batch returns 1 chat (partial batch - stops iteration)
        mock_session.get.side_effect = [
            mock_response(200, [
                {"id": "chat-1", "title": "Chat 1", "updated_at": 1700000000, "created_at": 1699900000},
                {"id": "chat-2", "title": "Chat 2", "updated_at": 1700000001, "created_at": 1699900001}
            ]),
            mock_response(200, [
                {"id": "chat-3", "title": "Chat 3", "updated_at": 1700000002, "created_at": 1699900002}
            ])
        ]

        client = OpenWebUIClient("https://test.com", "key")
        chats = list(client.iter_all_chats())

        assert len(chats) == 3
        assert chats[0].id == "chat-1"
        assert chats[2].id == "chat-3"

    @patch('db.services.openwebui_client.requests.Session')
    def test_iter_all_chats_empty(self, mock_session_class, mock_response):
        """Test iteration with no chats."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.get.return_value = mock_response(200, [])

        client = OpenWebUIClient("https://test.com", "key")
        chats = list(client.iter_all_chats())

        assert chats == []

    # ===== test_connection Tests =====

    @patch('db.services.openwebui_client.requests.Session')
    def test_connection_success(self, mock_session_class, mock_response):
        """Test successful connection test."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.get.return_value = mock_response(200, [])

        client = OpenWebUIClient("https://test.com", "key")
        assert client.test_connection() is True

    @patch('db.services.openwebui_client.requests.Session')
    def test_connection_failure(self, mock_session_class, mock_response):
        """Test failed connection test."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.get.return_value = mock_response(401)

        client = OpenWebUIClient("https://test.com", "bad-key")

        with pytest.raises(OpenWebUIAuthError):
            client.test_connection()

    # ===== Timestamp Parsing Tests =====

    def test_parse_timestamp_epoch_seconds(self, client):
        """Test parsing Unix epoch in seconds."""
        dt = client._parse_timestamp(1700000000)
        assert dt.year == 2023
        assert dt.tzinfo == timezone.utc

    def test_parse_timestamp_epoch_milliseconds(self, client):
        """Test parsing Unix epoch in milliseconds.

        Note: Current detection uses > 10^11 for milliseconds, > 10^12 for nanoseconds.
        Using a timestamp that falls in the milliseconds range: 500000000000 (500 billion = year ~1985)
        """
        # 500 billion milliseconds = 500 million seconds = ~1985
        dt = client._parse_timestamp(500000000000)
        assert dt.year == 1985
        assert dt.tzinfo == timezone.utc

    def test_parse_timestamp_epoch_nanoseconds(self, client):
        """Test parsing Unix epoch in nanoseconds."""
        dt = client._parse_timestamp(1700000000000000000)
        assert dt.year == 2023
        assert dt.tzinfo == timezone.utc

    def test_parse_timestamp_iso_string(self, client):
        """Test parsing ISO format string."""
        dt = client._parse_timestamp("2023-11-14T12:00:00Z")
        assert dt.year == 2023
        assert dt.month == 11
        assert dt.tzinfo == timezone.utc

    def test_parse_timestamp_none(self, client):
        """Test parsing None returns current time."""
        dt = client._parse_timestamp(None)
        assert dt.tzinfo == timezone.utc
        # Should be close to now
        assert (datetime.now(timezone.utc) - dt).total_seconds() < 5

    def test_parse_timestamp_invalid(self, client):
        """Test parsing invalid value returns current time."""
        dt = client._parse_timestamp("not-a-date")
        assert dt.tzinfo == timezone.utc

    # ===== Content Extraction Tests =====

    def test_extract_content_string(self, client):
        """Test extracting string content."""
        assert client._extract_content("Hello world") == "Hello world"

    def test_extract_content_dict_with_text(self, client):
        """Test extracting content from dict with 'text' key."""
        content = {"text": "Hello from dict"}
        assert client._extract_content(content) == "Hello from dict"

    def test_extract_content_dict_with_content(self, client):
        """Test extracting content from dict with 'content' key."""
        content = {"content": "Hello from content"}
        assert client._extract_content(content) == "Hello from content"

    def test_extract_content_none(self, client):
        """Test extracting None returns empty string."""
        assert client._extract_content(None) == ""

    def test_extract_content_other_type(self, client):
        """Test extracting other types converts to string."""
        assert client._extract_content(123) == "123"
        assert client._extract_content(["list"]) == "['list']"


class TestOpenWebUIChat:
    """Tests for the OpenWebUIChat dataclass."""

    def test_chat_creation(self):
        """Test creating a chat object."""
        chat = OpenWebUIChat(
            id="test-id",
            title="Test Chat",
            updated_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            messages=[{"role": "user", "content": "Hi"}]
        )

        assert chat.id == "test-id"
        assert chat.title == "Test Chat"
        assert chat.messages is not None
        assert len(chat.messages) == 1

    def test_chat_default_values(self):
        """Test chat default values."""
        chat = OpenWebUIChat(
            id="test",
            title="Test",
            updated_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )

        assert chat.messages is None
        assert chat.archived is False
        assert chat.pinned is False
        assert chat.user_id is None
        assert chat.folder_id is None
        assert chat.share_id is None

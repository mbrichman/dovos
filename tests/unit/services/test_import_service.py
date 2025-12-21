"""
Unit tests for ConversationImportService.

Tests the import service without Flask dependency or actual file I/O.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from db.services.import_service import ConversationImportService
from db.models.import_result import ImportResult


@pytest.fixture
def import_service():
    """Provide a fresh import service instance for each test."""
    return ConversationImportService()


class TestImportResultDataclass:
    """Test ImportResult dataclass."""
    
    def test_import_result_initialization(self):
        """Test ImportResult initializes with defaults."""
        result = ImportResult()
        
        assert result.imported_count == 0
        assert result.skipped_duplicates == 0
        assert result.failed_count == 0
        assert result.format_detected == "Unknown"
        assert result.messages == []
        assert result.errors == []
    
    def test_import_result_str_representation(self):
        """Test ImportResult string representation."""
        result = ImportResult(
            imported_count=5,
            skipped_duplicates=2,
            format_detected="ChatGPT"
        )
        
        result_str = str(result)
        assert "5" in result_str
        assert "2" in result_str
        assert "ChatGPT" in result_str
    
    def test_import_result_to_dict(self):
        """Test ImportResult converts to dict for JSON serialization."""
        result = ImportResult(
            imported_count=3,
            skipped_duplicates=1,
            format_detected="Claude",
            messages=["Test message"],
            errors=[]
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["imported_count"] == 3
        assert result_dict["skipped_duplicates"] == 1
        assert result_dict["format_detected"] == "Claude"
        assert "summary" in result_dict
        assert isinstance(result_dict["summary"], str)


class TestImportServiceInitialization:
    """Test service initialization."""
    
    def test_service_initializes(self, import_service):
        """Test ConversationImportService initializes without error."""
        assert import_service is not None


class TestFormatDetection:
    """Test format detection functionality."""
    
    def test_detect_format_with_chatgpt_data(self, import_service):
        """Test format detection for ChatGPT format."""
        chatgpt_data = {
            "conversations": [
                {
                    "id": "conv-123",
                    "title": "Python Help",
                    "mapping": {
                        "node-1": {
                            "message": {
                                "content": {"parts": ["Hello"]},
                                "role": "user"
                            }
                        }
                    },
                    "create_time": 1695000000,
                    "update_time": 1695001000
                }
            ]
        }
        
        conversations, format_type = import_service._detect_format(chatgpt_data)
        
        assert format_type == "ChatGPT"
        assert len(conversations) == 1
    
    def test_detect_format_with_claude_data(self, import_service):
        """Test format detection for Claude format."""
        claude_data = {
            "conversations": [
                {
                    "uuid": "uuid-123",
                    "name": "Claude Conversation",
                    "chat_messages": [
                        {
                            "uuid": "msg-1",
                            "text": "Hello",
                            "created_at": "2023-09-18T10:00:00Z"
                        }
                    ],
                    "created_at": "2023-09-18T10:00:00Z",
                    "updated_at": "2023-09-18T10:05:00Z"
                }
            ]
        }
        
        conversations, format_type = import_service._detect_format(claude_data)
        
        assert format_type == "Claude"
        assert len(conversations) == 1
    
    def test_detect_format_with_unknown_data(self, import_service):
        """Test format detection returns Unknown for unrecognized format."""
        unknown_data = {
            "conversations": [
                {
                    "random_field": "value",
                    "unrecognized": "format"
                }
            ]
        }
        
        conversations, format_type = import_service._detect_format(unknown_data)
        
        assert format_type == "Unknown"
        assert len(conversations) == 1


class TestImportJsonData:
    """Test JSON import functionality."""
    
    @patch('db.services.import_service.get_unit_of_work')
    def test_import_json_with_unknown_format(self, mock_uow, import_service):
        """Test import_json_data raises error for unknown format."""
        unknown_data = {
            "conversations": [
                {
                    "random_field": "value",
                    "unrecognized": "format"
                }
            ]
        }
        
        with pytest.raises(ValueError):
            import_service.import_json_data(unknown_data)
    
    @patch('db.services.import_service.get_unit_of_work')
    def test_import_json_with_empty_conversations(self, mock_uow, import_service):
        """Test import_json_data with empty conversations list."""
        empty_data = {"conversations": []}
        
        with pytest.raises(ValueError):
            import_service.import_json_data(empty_data)


class TestBuildExistingConversationsMap:
    """Test duplicate detection map building."""
    
    @patch('db.services.import_service.get_unit_of_work')
    def test_build_existing_conversations_map_empty_db(self, mock_uow, import_service):
        """Test building map with no existing conversations."""
        # Mock empty database
        mock_unit_of_work = MagicMock()
        mock_unit_of_work.conversations.get_all.return_value = []
        mock_uow.return_value.__enter__.return_value = mock_unit_of_work
        
        result_map = import_service._build_existing_conversations_map()
        
        assert isinstance(result_map, dict)
        assert len(result_map) == 0
    
    @patch('db.services.import_service.get_unit_of_work')
    def test_build_existing_conversations_map_with_data(self, mock_uow, import_service):
        """Test building map with existing conversations."""
        # Mock existing conversation with source_id (new approach)
        mock_conv = Mock()
        mock_conv.id = "conv-uuid-123"
        mock_conv.source_id = "source-123"  # New source tracking field
        mock_conv.source_updated_at = None

        mock_msg = Mock()
        mock_msg.content = "Test content"
        mock_msg.message_metadata = {'original_conversation_id': 'original-123'}

        mock_unit_of_work = MagicMock()
        mock_unit_of_work.conversations.get_all.return_value = [mock_conv]
        mock_unit_of_work.messages.get_by_conversation.return_value = [mock_msg]
        mock_uow.return_value.__enter__.return_value = mock_unit_of_work

        result_map = import_service._build_existing_conversations_map()

        assert isinstance(result_map, dict)
        # Now uses source_id instead of original_conversation_id
        assert 'source-123' in result_map

    @patch('db.services.import_service.get_unit_of_work')
    def test_build_existing_conversations_map_legacy_fallback(self, mock_uow, import_service):
        """Test building map falls back to message metadata for legacy data."""
        # Mock existing conversation without source_id (legacy)
        mock_conv = Mock()
        mock_conv.id = "conv-uuid-123"
        mock_conv.source_id = None  # No source_id

        mock_msg = Mock()
        mock_msg.content = "Test content"
        mock_msg.message_metadata = {'original_conversation_id': 'legacy-123'}

        mock_unit_of_work = MagicMock()
        mock_unit_of_work.conversations.get_all.return_value = [mock_conv]
        mock_unit_of_work.messages.get_by_conversation.return_value = [mock_msg]
        mock_uow.return_value.__enter__.return_value = mock_unit_of_work

        result_map = import_service._build_existing_conversations_map()

        assert isinstance(result_map, dict)
        # Falls back to original_conversation_id from message metadata
        assert 'legacy-123' in result_map


class TestImportResultMessages:
    """Test ImportResult message formatting."""
    
    def test_import_result_with_all_counts(self):
        """Test ImportResult with imported, skipped, and failed conversations."""
        result = ImportResult(
            imported_count=10,
            skipped_duplicates=3,
            failed_count=1,
            format_detected="ChatGPT"
        )
        
        result_str = str(result)
        
        assert "10" in result_str
        assert "3" in result_str
        assert "1" in result_str
        assert "ChatGPT" in result_str
    
    def test_import_result_messages_list(self):
        """Test ImportResult maintains list of messages."""
        result = ImportResult()
        result.messages.append("Starting import")
        result.messages.append("Processing conversation")
        
        assert len(result.messages) == 2
        assert result.messages[0] == "Starting import"
        assert result.messages[1] == "Processing conversation"
    
    def test_import_result_errors_list(self):
        """Test ImportResult maintains list of errors."""
        result = ImportResult()
        result.errors.append("Error 1")
        result.errors.append("Error 2")
        
        assert len(result.errors) == 2
        assert result.errors[0] == "Error 1"


class TestImportServiceIntegration:
    """Integration tests for ConversationImportService."""
    
    def test_service_has_all_public_methods(self, import_service):
        """Test service has expected public methods."""
        assert hasattr(import_service, 'import_json_data')
        assert hasattr(import_service, 'import_docx_file')
        assert callable(import_service.import_json_data)
        assert callable(import_service.import_docx_file)
    
    def test_service_has_private_helper_methods(self, import_service):
        """Test service has expected private helper methods."""
        assert hasattr(import_service, '_detect_format')
        assert hasattr(import_service, '_build_existing_conversations_map')
        assert hasattr(import_service, '_import_single_conversation')
        assert callable(import_service._detect_format)


class TestExtractSourceUpdatedAt:
    """Tests for _extract_source_updated_at method."""

    def test_extract_chatgpt_update_time(self, import_service):
        """Test extracting update_time from ChatGPT data."""
        from datetime import datetime, timezone

        conv_data = {
            'update_time': 1700000000,
            'create_time': 1699900000
        }

        result = import_service._extract_source_updated_at(conv_data, 'ChatGPT')

        assert result is not None
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    def test_extract_chatgpt_falls_back_to_create_time(self, import_service):
        """Test ChatGPT falls back to create_time when update_time missing."""
        from datetime import datetime, timezone

        conv_data = {
            'create_time': 1699900000
        }

        result = import_service._extract_source_updated_at(conv_data, 'ChatGPT')

        assert result is not None
        assert isinstance(result, datetime)

    def test_extract_claude_updated_at(self, import_service):
        """Test extracting updated_at from Claude data."""
        from datetime import datetime, timezone

        conv_data = {
            'updated_at': '2023-11-14T12:00:00Z',
            'created_at': '2023-11-14T10:00:00Z'
        }

        result = import_service._extract_source_updated_at(conv_data, 'Claude')

        assert result is not None
        assert result.month == 11
        assert result.day == 14

    def test_extract_openwebui_updated_at(self, import_service):
        """Test extracting updated_at from OpenWebUI data."""
        from datetime import datetime, timezone

        conv_data = {
            'updated_at': 1700000000
        }

        result = import_service._extract_source_updated_at(conv_data, 'OpenWebUI')

        assert result is not None

    def test_extract_milliseconds_timestamp(self, import_service):
        """Test handling millisecond epoch timestamps.

        Note: Current detection uses > 10^11 for milliseconds, > 10^12 for nanoseconds.
        Using a timestamp that falls in the milliseconds range.
        """
        from datetime import datetime, timezone

        # 500 billion milliseconds = 500 million seconds = ~1985
        conv_data = {
            'update_time': 500000000000  # Milliseconds
        }

        result = import_service._extract_source_updated_at(conv_data, 'ChatGPT')

        assert result is not None
        assert result.year == 1985

    def test_extract_nanoseconds_timestamp(self, import_service):
        """Test handling nanosecond epoch timestamps."""
        from datetime import datetime, timezone

        conv_data = {
            'update_time': 1700000000000000000  # Nanoseconds
        }

        result = import_service._extract_source_updated_at(conv_data, 'ChatGPT')

        assert result is not None
        assert result.year == 2023

    def test_extract_returns_none_for_missing_data(self, import_service):
        """Test returns None when no timestamp available."""
        result = import_service._extract_source_updated_at({}, 'ChatGPT')

        assert result is None

    def test_extract_handles_invalid_timestamp(self, import_service):
        """Test gracefully handles invalid timestamp format."""
        conv_data = {
            'update_time': 'not-a-date'
        }

        result = import_service._extract_source_updated_at(conv_data, 'ChatGPT')

        assert result is None


class TestShouldUpdate:
    """Tests for _should_update method."""

    def test_should_update_newer_timestamp(self, import_service):
        """Test returns True when new timestamp is newer."""
        from datetime import datetime, timezone, timedelta

        existing = datetime.now(timezone.utc) - timedelta(hours=2)
        new = datetime.now(timezone.utc)

        result = import_service._should_update(existing, new)

        assert result is True

    def test_should_not_update_older_timestamp(self, import_service):
        """Test returns False when new timestamp is older."""
        from datetime import datetime, timezone, timedelta

        existing = datetime.now(timezone.utc)
        new = datetime.now(timezone.utc) - timedelta(hours=2)

        result = import_service._should_update(existing, new)

        assert result is False

    def test_should_not_update_same_timestamp(self, import_service):
        """Test returns False when timestamps are equal."""
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc)

        result = import_service._should_update(timestamp, timestamp)

        assert result is False

    def test_should_not_update_new_is_none(self, import_service):
        """Test returns False when new timestamp is None."""
        from datetime import datetime, timezone

        existing = datetime.now(timezone.utc)

        result = import_service._should_update(existing, None)

        assert result is False

    def test_should_update_existing_is_none(self, import_service):
        """Test returns True when existing is None but new has value."""
        from datetime import datetime, timezone

        new = datetime.now(timezone.utc)

        result = import_service._should_update(None, new)

        assert result is True

    def test_should_not_update_both_none(self, import_service):
        """Test returns False when both timestamps are None."""
        result = import_service._should_update(None, None)

        assert result is False


class TestUpdateExistingConversation:
    """Tests for _update_existing_conversation method."""

    @patch('db.services.import_service.get_unit_of_work')
    def test_update_adds_new_messages(self, mock_uow, import_service):
        """Test updating adds new messages to existing conversation."""
        from datetime import datetime, timezone
        from uuid import uuid4

        conv_id = uuid4()

        # Mock existing messages
        existing_msg = Mock()
        existing_msg.role = "user"
        existing_msg.content = "Hello"

        mock_unit_of_work = MagicMock()
        mock_unit_of_work.messages.get_by_conversation.return_value = [existing_msg]
        mock_unit_of_work.messages.get_max_sequence.return_value = 1
        mock_unit_of_work.messages.create.return_value = Mock(id=uuid4())
        mock_uow.return_value.__enter__.return_value = mock_unit_of_work

        # New messages (one existing, one new)
        messages = [
            {'role': 'user', 'content': 'Hello'},  # This exists
            {'role': 'assistant', 'content': 'Hi there!'}  # This is new
        ]

        result = import_service._update_existing_conversation(
            conv_id,
            {'id': 'test-123'},
            'ChatGPT',
            messages,
            datetime.now(timezone.utc)
        )

        assert result == 1  # Only one new message added
        mock_unit_of_work.messages.create.assert_called_once()

    @patch('db.services.import_service.get_unit_of_work')
    def test_update_skips_empty_content(self, mock_uow, import_service):
        """Test updating skips messages with empty content."""
        from datetime import datetime, timezone
        from uuid import uuid4

        conv_id = uuid4()

        mock_unit_of_work = MagicMock()
        mock_unit_of_work.messages.get_by_conversation.return_value = []
        mock_unit_of_work.messages.get_max_sequence.return_value = 0
        mock_uow.return_value.__enter__.return_value = mock_unit_of_work

        messages = [
            {'role': 'user', 'content': ''},  # Empty
            {'role': 'user', 'content': '   '}  # Whitespace only
        ]

        result = import_service._update_existing_conversation(
            conv_id,
            {'id': 'test-123'},
            'ChatGPT',
            messages,
            datetime.now(timezone.utc)
        )

        assert result == 0
        mock_unit_of_work.messages.create.assert_not_called()

    @patch('db.services.import_service.get_unit_of_work')
    def test_update_increments_sequence(self, mock_uow, import_service):
        """Test updating increments sequence for new messages."""
        from datetime import datetime, timezone
        from uuid import uuid4

        conv_id = uuid4()

        mock_unit_of_work = MagicMock()
        mock_unit_of_work.messages.get_by_conversation.return_value = []
        mock_unit_of_work.messages.get_max_sequence.return_value = 5
        mock_unit_of_work.messages.create.return_value = Mock(id=uuid4())
        mock_uow.return_value.__enter__.return_value = mock_unit_of_work

        messages = [
            {'role': 'user', 'content': 'First new message'},
            {'role': 'assistant', 'content': 'Second new message'}
        ]

        result = import_service._update_existing_conversation(
            conv_id,
            {'id': 'test-123'},
            'ChatGPT',
            messages,
            datetime.now(timezone.utc)
        )

        assert result == 2
        # Check that sequences were set correctly
        calls = mock_unit_of_work.messages.create.call_args_list
        assert calls[0][1]['message_metadata']['sequence'] == 6
        assert calls[1][1]['message_metadata']['sequence'] == 7

    @patch('db.services.import_service.get_unit_of_work')
    def test_update_enqueues_embedding_jobs(self, mock_uow, import_service):
        """Test updating enqueues embedding jobs for new messages."""
        from datetime import datetime, timezone
        from uuid import uuid4

        conv_id = uuid4()

        mock_unit_of_work = MagicMock()
        mock_unit_of_work.messages.get_by_conversation.return_value = []
        mock_unit_of_work.messages.get_max_sequence.return_value = 0
        mock_unit_of_work.messages.create.return_value = Mock(id=uuid4())
        mock_uow.return_value.__enter__.return_value = mock_unit_of_work

        messages = [
            {'role': 'user', 'content': 'New message'}
        ]

        import_service._update_existing_conversation(
            conv_id,
            {'id': 'test-123'},
            'ChatGPT',
            messages,
            datetime.now(timezone.utc)
        )

        mock_unit_of_work.jobs.enqueue.assert_called_once()
        call_kwargs = mock_unit_of_work.jobs.enqueue.call_args[1]
        assert call_kwargs['kind'] == 'generate_embedding'

    @patch('db.services.import_service.get_unit_of_work')
    def test_update_updates_source_tracking(self, mock_uow, import_service):
        """Test updating updates source tracking timestamp."""
        from datetime import datetime, timezone
        from uuid import uuid4

        conv_id = uuid4()
        source_updated_at = datetime.now(timezone.utc)

        mock_unit_of_work = MagicMock()
        mock_unit_of_work.messages.get_by_conversation.return_value = []
        mock_unit_of_work.messages.get_max_sequence.return_value = 0
        mock_uow.return_value.__enter__.return_value = mock_unit_of_work

        messages = []  # No new messages

        import_service._update_existing_conversation(
            conv_id,
            {'id': 'test-123'},
            'ChatGPT',
            messages,
            source_updated_at
        )

        mock_unit_of_work.conversations.update_source_tracking.assert_called_once_with(
            conv_id, source_updated_at
        )


class TestImportResultUpdatedFields:
    """Tests for new ImportResult fields for update tracking."""

    def test_import_result_has_updated_count(self):
        """Test ImportResult has updated_count field."""
        result = ImportResult()

        assert hasattr(result, 'updated_count')
        assert result.updated_count == 0

    def test_import_result_has_messages_added(self):
        """Test ImportResult has messages_added field."""
        result = ImportResult()

        assert hasattr(result, 'messages_added')
        assert result.messages_added == 0

    def test_import_result_updated_fields_in_dict(self):
        """Test updated fields appear in to_dict."""
        result = ImportResult(
            updated_count=3,
            messages_added=10
        )

        result_dict = result.to_dict()

        assert result_dict['updated_count'] == 3
        assert result_dict['messages_added'] == 10

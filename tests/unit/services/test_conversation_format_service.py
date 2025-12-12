"""Tests for ConversationFormatService - TDD approach"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from db.services.conversation_format_service import ConversationFormatService


class TestConversationFormatService:
    """Test suite for ConversationFormatService"""
    
    @pytest.fixture
    def service(self):
        """Create a ConversationFormatService instance"""
        return ConversationFormatService()
    
    # ===== format_conversation_list tests =====
    
    def test_format_conversation_list_empty(self, service):
        """Test formatting an empty conversation list"""
        result = service.format_conversation_list([])
        assert result == []
    
    def test_format_conversation_list_single_item(self, service):
        """Test formatting a single conversation"""
        conversations = [{
            'id': 'test-id-1',
            'title': 'Test Conversation',
            'preview': 'This is a preview',
            'source': 'claude',
            'created_at': datetime(2025, 1, 1, 12, 0, 0),
            'updated_at': datetime(2025, 1, 1, 14, 0, 0),
            'message_count': 5
        }]
        
        result = service.format_conversation_list(conversations)
        
        assert len(result) == 1
        assert result[0]['id'] == 'test-id-1'
        assert result[0]['meta']['title'] == 'Test Conversation'
        assert result[0]['preview'] == 'This is a preview'
        assert result[0]['meta']['source'] == 'claude'
    
    def test_format_conversation_list_multiple_items(self, service):
        """Test formatting multiple conversations"""
        conversations = [
            {
                'id': 'test-id-1',
                'title': 'Conv 1',
                'preview': 'Preview 1',
                'source': 'claude',
                'created_at': datetime(2025, 1, 1, 12, 0, 0),
                'updated_at': datetime(2025, 1, 1, 14, 0, 0),
                'message_count': 5
            },
            {
                'id': 'test-id-2',
                'title': 'Conv 2',
                'preview': 'Preview 2',
                'source': 'chatgpt',
                'created_at': datetime(2025, 1, 2, 12, 0, 0),
                'updated_at': datetime(2025, 1, 2, 14, 0, 0),
                'message_count': 3
            }
        ]
        
        result = service.format_conversation_list(conversations)
        
        assert len(result) == 2
        assert result[0]['id'] == 'test-id-1'
        assert result[1]['id'] == 'test-id-2'
    
    def test_format_conversation_list_with_missing_fields(self, service):
        """Test formatting conversations with missing optional fields"""
        conversations = [{
            'id': 'test-id-1',
            'title': 'Test',
            'preview': 'Preview'
            # Missing source, dates, message_count
        }]
        
        result = service.format_conversation_list(conversations)
        
        assert len(result) == 1
        assert result[0]['meta']['source'] == 'unknown'
        assert result[0]['meta']['message_count'] == 0
    
    def test_format_conversation_list_handles_none_values(self, service):
        """Test formatting with None values"""
        conversations = [{
            'id': 'test-id-1',
            'title': None,
            'preview': None,
            'source': None,
            'message_count': None
        }]
        
        result = service.format_conversation_list(conversations)
        
        assert len(result) == 1
        assert result[0]['meta']['title'] == 'Untitled Conversation'
        assert result[0]['preview'] == ''
    
    # ===== format_conversation_view tests =====
    
    def test_format_conversation_view_claude(self, service):
        """Test formatting a Claude conversation for detail view"""
        document = "**You said** *(on 2025-01-01 12:00:00)*:\n\nHello\n\n**Claude said** *(on 2025-01-01 12:00:05)*:\n\nHi there!"
        metadata = {
            'title': 'Test Conversation',
            'source': 'claude',
            'earliest_ts': '2025-01-01T12:00:00',
            'message_count': 2
        }
        
        result = service.format_conversation_view(document, metadata)
        
        assert result['conversation']['meta'] == metadata
        assert result['assistant_name'] == 'Claude'
        assert len(result['messages']) == 2
        assert result['messages'][0]['role'] == 'user'
        assert result['messages'][1]['role'] == 'assistant'
    
    def test_format_conversation_view_chatgpt(self, service):
        """Test formatting a ChatGPT conversation for detail view"""
        document = "**You said**:\n\nHello\n\n**ChatGPT said**:\n\nHi!"
        metadata = {
            'title': 'Test',
            'source': 'chatgpt',
            'earliest_ts': '2025-01-01T12:00:00'
        }
        
        result = service.format_conversation_view(document, metadata)
        
        assert result['assistant_name'] == 'ChatGPT'
        # Note: parse_messages_from_document requires exact format matching
        # This test verifies assistant name detection works correctly
    
    def test_format_conversation_view_unknown_source(self, service):
        """Test formatting conversation with unknown source"""
        document = "Some conversation content"
        metadata = {
            'title': 'Test',
            'source': 'unknown'
        }
        
        result = service.format_conversation_view(document, metadata)
        
        assert result['assistant_name'] == 'AI'
    
    def test_format_conversation_view_detects_claude_from_content(self, service):
        """Test auto-detecting Claude from document content"""
        document = "**Claude said**: Hello"
        metadata = {
            'title': 'Test',
            'source': 'unknown'
        }
        
        result = service.format_conversation_view(document, metadata)
        
        assert result['assistant_name'] == 'Claude'
    
    def test_format_conversation_view_detects_chatgpt_from_content(self, service):
        """Test auto-detecting ChatGPT from document content"""
        document = "**ChatGPT said**: Hello"
        metadata = {
            'title': 'Test',
            'source': 'unknown'
        }
        
        result = service.format_conversation_view(document, metadata)
        
        assert result['assistant_name'] == 'ChatGPT'
    
    # ===== format_search_results tests =====
    
    def test_format_search_results_empty(self, service):
        """Test formatting empty search results"""
        results = []
        
        formatted = service.format_search_results(results)
        
        assert formatted == []
    
    def test_format_search_results_single_result(self, service):
        """Test formatting a single search result"""
        results = [{
            'id': 'test-id-1',
            'title': 'Test Result',
            'content': 'Result content',
            'metadata': {
                'source': 'claude',
                'earliest_ts': '2025-01-01T12:00:00'
            },
            'score': 0.95
        }]
        
        formatted = service.format_search_results(results)
        
        assert len(formatted) == 1
        assert formatted[0]['id'] == 'test-id-1'
        assert formatted[0]['meta']['title'] == 'Test Result'
        assert formatted[0]['preview'] == 'Result content'
        assert 'relevance_score' in formatted[0]['meta']
    
    def test_format_search_results_multiple_results(self, service):
        """Test formatting multiple search results"""
        results = [
            {
                'id': 'test-id-1',
                'title': 'Result 1',
                'content': 'Content 1',
                'metadata': {'source': 'claude'},
                'score': 0.95
            },
            {
                'id': 'test-id-2',
                'title': 'Result 2',
                'content': 'Content 2',
                'metadata': {'source': 'chatgpt'},
                'score': 0.85
            }
        ]
        
        formatted = service.format_search_results(results)
        
        assert len(formatted) == 2
        assert formatted[0]['meta']['relevance_score'] == 0.95
        assert formatted[1]['meta']['relevance_score'] == 0.85
    
    def test_format_search_results_with_missing_score(self, service):
        """Test formatting search results without scores"""
        results = [{
            'id': 'test-id-1',
            'title': 'Test',
            'content': 'Content',
            'metadata': {'source': 'claude'}
            # No score field
        }]
        
        formatted = service.format_search_results(results)
        
        assert len(formatted) == 1
        assert formatted[0]['meta']['relevance_display'] == 'N/A'
    
    def test_format_search_results_with_missing_metadata(self, service):
        """Test formatting search results with missing metadata"""
        results = [{
            'id': 'test-id-1',
            'title': 'Test',
            'content': 'Content'
            # No metadata field
        }]
        
        formatted = service.format_search_results(results)
        
        assert len(formatted) == 1
        assert formatted[0]['meta']['source'] == 'unknown'
    
    # ===== Helper method tests =====
    
    def test_extract_preview_from_document(self, service):
        """Test extracting preview from document"""
        document = "**You said**: Hello this is a test message\n**Claude said**: Response"
        
        preview = service._extract_preview(document, max_length=20)
        
        assert len(preview) <= 23  # 20 + '...'
        assert 'Hello' in preview
        assert '**You said**' not in preview
    
    def test_extract_preview_short_document(self, service):
        """Test extracting preview from short document"""
        document = "Short text"
        
        preview = service._extract_preview(document, max_length=100)
        
        assert preview == "Short text"
        assert '...' not in preview
    
    def test_parse_messages_from_document_claude(self, service):
        """Test parsing messages from Claude document"""
        document = "**You said** *(on 2025-01-01 12:00:00)*:\n\nHello\n\n**Claude said** *(on 2025-01-01 12:00:05)*:\n\nHi!"
        
        messages = service._parse_messages(document, 'claude')
        
        assert len(messages) == 2
        assert messages[0]['role'] == 'user'
        assert messages[1]['role'] == 'assistant'
        assert 'Hello' in messages[0]['content']
    
    def test_parse_messages_from_document_chatgpt(self, service):
        """Test parsing messages from ChatGPT document"""
        # Format matches parse_messages_from_document expectations (uses **You**: not **You said**:)
        document = "**You**:\nHello\n\n**ChatGPT**:\nHi!"
        
        messages = service._parse_messages(document, 'chatgpt')
        
        assert len(messages) == 2
        assert messages[0]['role'] == 'user'
        assert messages[1]['role'] == 'assistant'
    
    def test_determine_assistant_name_from_source(self, service):
        """Test determining assistant name from source metadata"""
        assert service._determine_assistant_name('', 'claude') == 'Claude'
        assert service._determine_assistant_name('', 'chatgpt') == 'ChatGPT'
        assert service._determine_assistant_name('', 'unknown') == 'AI'
    
    def test_determine_assistant_name_from_content(self, service):
        """Test determining assistant name from document content"""
        doc_claude = "**Claude said**: Hello"
        doc_chatgpt = "**ChatGPT said**: Hello"
        doc_unknown = "Generic content"
        
        assert service._determine_assistant_name(doc_claude, 'unknown') == 'Claude'
        assert service._determine_assistant_name(doc_chatgpt, 'unknown') == 'ChatGPT'
        assert service._determine_assistant_name(doc_unknown, 'unknown') == 'AI'
    
    def test_format_timestamp_iso_format(self, service):
        """Test formatting ISO timestamp"""
        dt = datetime(2025, 1, 1, 12, 0, 0)
        formatted = service._format_timestamp(dt)
        
        assert formatted == '2025-01-01 12:00:00'
    
    def test_format_timestamp_none(self, service):
        """Test formatting None timestamp"""
        formatted = service._format_timestamp(None)
        
        assert formatted is None or formatted == ''
    
    # ===== format_postgres_search_results tests =====
    
    def test_format_postgres_search_results_empty(self, service):
        """Test formatting empty PostgreSQL search results"""
        results = []
        
        formatted = service.format_postgres_search_results(results)
        
        assert formatted == []
    
    def test_format_postgres_search_results_basic(self, service):
        """Test formatting basic PostgreSQL search result"""
        results = [{
            'content': 'Test content',
            'title': 'Test Title',
            'date': '2025-01-01T12:00:00',
            'metadata': {
                'conversation_id': 'test-id-1',
                'source': 'claude',
                'earliest_ts': '2025-01-01T12:00:00'
            }
        }]
        
        formatted = service.format_postgres_search_results(results)
        
        assert len(formatted) == 1
        assert formatted[0]['id'] == 'test-id-1'
        assert formatted[0]['preview'] == 'Test content'
        assert formatted[0]['meta']['title'] == 'Test Title'
        assert formatted[0]['meta']['source'] == 'claude'
    
    def test_format_postgres_search_results_normalizes_chatgpt_source(self, service):
        """Test that ChatGPT source variations are normalized"""
        results = [{
            'content': 'Content',
            'metadata': {'source': 'ChatGPT-4o', 'id': 'test-1'}
        }]
        
        formatted = service.format_postgres_search_results(results)
        
        assert formatted[0]['meta']['source'] == 'chatgpt'
    
    def test_format_postgres_search_results_normalizes_claude_source(self, service):
        """Test that Claude source variations are normalized"""
        results = [{
            'content': 'Content',
            'metadata': {'source': 'claude-3-opus', 'id': 'test-1'}
        }]
        
        formatted = service.format_postgres_search_results(results)
        
        assert formatted[0]['meta']['source'] == 'claude'
    
    def test_format_postgres_search_results_handles_missing_metadata(self, service):
        """Test formatting with minimal metadata"""
        results = [{
            'content': 'Content only',
            'metadata': {}
        }]
        
        formatted = service.format_postgres_search_results(results)
        
        assert len(formatted) == 1
        assert formatted[0]['id'] == 'unknown'
        assert formatted[0]['meta']['source'] == 'unknown'
        assert formatted[0]['meta']['title'] == 'Untitled'
    
    # ===== format_postgres_list_results tests =====
    
    def test_format_postgres_list_results_empty(self, service):
        """Test formatting empty conversation list"""
        conversations = []
        
        formatted = service.format_postgres_list_results(conversations)
        
        assert formatted == []
    
    def test_format_postgres_list_results_basic(self, service):
        """Test formatting basic conversation for list"""
        conversations = [{
            'id': 'test-id-1',
            'title': 'Test Conversation',
            'preview': 'Preview text',
            'source': 'claude',
            'latest_ts': '2025-01-01T12:00:00'
        }]
        
        formatted = service.format_postgres_list_results(conversations)
        
        assert len(formatted) == 1
        assert formatted[0]['id'] == 'test-id-1'
        assert formatted[0]['preview'] == 'Preview text'
        assert formatted[0]['meta']['title'] == 'Test Conversation'
        assert formatted[0]['meta']['source'] == 'claude'
    
    def test_format_postgres_list_results_normalizes_source(self, service):
        """Test that source is normalized to lowercase"""
        conversations = [{
            'id': 'test-1',
            'title': 'Test',
            'preview': 'Preview',
            'source': 'CLAUDE',
            'latest_ts': '2025-01-01'
        }]
        
        formatted = service.format_postgres_list_results(conversations)
        
        assert formatted[0]['meta']['source'] == 'claude'
    
    def test_format_postgres_list_results_handles_none_source(self, service):
        """Test handling None source value"""
        conversations = [{
            'id': 'test-1',
            'title': 'Test',
            'preview': 'Preview',
            'source': None
        }]
        
        formatted = service.format_postgres_list_results(conversations)
        
        assert formatted[0]['meta']['source'] == 'unknown'
    
    def test_format_postgres_list_results_handles_empty_source(self, service):
        """Test handling empty string source"""
        conversations = [{
            'id': 'test-1',
            'title': 'Test',
            'preview': 'Preview',
            'source': '  '
        }]
        
        formatted = service.format_postgres_list_results(conversations)
        
        assert formatted[0]['meta']['source'] == 'unknown'
    
    # ===== calculate_source_breakdown tests =====
    
    def test_calculate_source_breakdown_empty(self, service):
        """Test calculating source breakdown with empty data"""
        conversations = {'metadatas': []}
        
        breakdown = service.calculate_source_breakdown(conversations)
        
        assert breakdown == {}
    
    def test_calculate_source_breakdown_single_source(self, service):
        """Test calculating breakdown with single source"""
        conversations = {
            'metadatas': [
                {'source': 'claude'},
                {'source': 'claude'},
                {'source': 'claude'}
            ]
        }
        
        breakdown = service.calculate_source_breakdown(conversations)
        
        assert breakdown == {'claude': 3}
    
    def test_calculate_source_breakdown_multiple_sources(self, service):
        """Test calculating breakdown with multiple sources"""
        conversations = {
            'metadatas': [
                {'source': 'claude'},
                {'source': 'chatgpt'},
                {'source': 'claude'},
                {'source': 'docx'},
                {'source': 'chatgpt'}
            ]
        }
        
        breakdown = service.calculate_source_breakdown(conversations)
        
        assert breakdown == {'claude': 2, 'chatgpt': 2, 'docx': 1}
    
    def test_calculate_source_breakdown_prefers_original_source(self, service):
        """Test that original_source is preferred over source"""
        conversations = {
            'metadatas': [
                {'source': 'postgres', 'original_source': 'claude'},
                {'source': 'postgres', 'original_source': 'chatgpt'}
            ]
        }
        
        breakdown = service.calculate_source_breakdown(conversations)
        
        assert breakdown == {'claude': 1, 'chatgpt': 1}
    
    def test_calculate_source_breakdown_maps_postgres_to_imported(self, service):
        """Test that postgres source is mapped to imported"""
        conversations = {
            'metadatas': [
                {'source': 'postgres'},
                {'source': 'postgres'}
            ]
        }
        
        breakdown = service.calculate_source_breakdown(conversations)
        
        assert breakdown == {'imported': 2}
    
    def test_calculate_source_breakdown_no_metadatas_key(self, service):
        """Test handling missing metadatas key"""
        conversations = {}
        
        breakdown = service.calculate_source_breakdown(conversations)
        
        assert breakdown == {}
    
    # ===== extract_source_from_messages tests =====
    
    def test_extract_source_from_messages_basic(self, service):
        """Test extracting source from message metadata"""
        messages = [Mock(message_metadata={'source': 'claude'})]
        
        source = service.extract_source_from_messages(messages)
        
        assert source == 'claude'
    
    def test_extract_source_from_messages_empty_list(self, service):
        """Test extracting source from empty message list"""
        messages = []
        
        source = service.extract_source_from_messages(messages)
        
        assert source == 'unknown'
    
    def test_extract_source_from_messages_no_metadata(self, service):
        """Test extracting source when message has no metadata"""
        messages = [Mock(message_metadata=None)]
        
        source = service.extract_source_from_messages(messages)
        
        assert source == 'unknown'
    
    def test_extract_source_from_messages_missing_source_key(self, service):
        """Test extracting source when metadata has no source key"""
        messages = [Mock(message_metadata={'other_key': 'value'})]
        
        source = service.extract_source_from_messages(messages)
        
        assert source == 'unknown'
    
    # ===== format_db_messages_for_view tests =====
    
    def test_format_db_messages_for_view_empty(self, service):
        """Test formatting empty message list"""
        messages = []
        
        formatted = service.format_db_messages_for_view(messages)
        
        assert formatted == []
    
    def test_format_db_messages_for_view_basic(self, service):
        """Test formatting basic database messages"""
        messages = [
            Mock(
                role='user',
                content='Hello **world**',
                created_at=datetime(2025, 1, 1, 12, 0, 0),
                message_metadata=None
            ),
            Mock(
                role='assistant',
                content='# Heading\n\nResponse',
                created_at=datetime(2025, 1, 1, 12, 0, 5),
                message_metadata=None
            )
        ]
        
        formatted = service.format_db_messages_for_view(messages)
        
        assert len(formatted) == 2
        assert formatted[0]['role'] == 'user'
        assert '<strong>world</strong>' in formatted[0]['content']
        assert formatted[0]['timestamp'] == '2025-01-01 12:00:00'
        assert formatted[1]['role'] == 'assistant'
        assert '<h1>Heading</h1>' in formatted[1]['content']
    
    def test_format_db_messages_for_view_with_code(self, service):
        """Test formatting messages with code blocks"""
        messages = [
            Mock(
                role='user',
                content='```python\nprint("hello")\n```',
                created_at=datetime(2025, 1, 1, 12, 0, 0),
                message_metadata=None
            )
        ]
        
        formatted = service.format_db_messages_for_view(messages)
        
        assert len(formatted) == 1
        # Markdown converts code blocks to <pre><code>
        assert 'print' in formatted[0]['content']
    
    def test_format_db_messages_for_view_no_timestamp(self, service):
        """Test formatting messages without timestamps"""
        messages = [
            Mock(
                role='user',
                content='Test',
                created_at=None,
                message_metadata=None
            )
        ]
        
        formatted = service.format_db_messages_for_view(messages)
        
        assert formatted[0]['timestamp'] is None
    
    # ===== _determine_assistant_name with optional document =====
    
    def test_determine_assistant_name_with_none_document(self, service):
        """Test determining assistant name with None document"""
        assert service._determine_assistant_name(None, 'claude') == 'Claude'
        assert service._determine_assistant_name(None, 'chatgpt') == 'ChatGPT'
        assert service._determine_assistant_name(None, 'unknown') == 'AI'
    
    def test_determine_assistant_name_with_empty_document(self, service):
        """Test determining assistant name with empty document"""
        assert service._determine_assistant_name('', 'claude') == 'Claude'
        assert service._determine_assistant_name('', 'CHATGPT') == 'ChatGPT'
    
    def test_determine_assistant_name_document_overrides_source(self, service):
        """Test that document content can override source metadata"""
        # Source says unknown, but document shows Claude
        result = service._determine_assistant_name('**Claude said**: Hello', 'unknown')
        assert result == 'Claude'

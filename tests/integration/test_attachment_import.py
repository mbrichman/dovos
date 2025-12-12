"""
Integration tests for attachment import across all formats.

Tests that attachments are correctly extracted during import and
stored in message metadata for all supported formats:
- Claude (files with extracted_content, image references)
- ChatGPT (reasoning traces, code, citations)
- OpenWebUI (images as data URLs)
"""

import json
import pytest
from pathlib import Path
from db.services.import_service import ConversationImportService


@pytest.fixture
def import_service():
    """Create import service instance."""
    return ConversationImportService()


@pytest.fixture
def claude_with_attachment():
    """Load Claude test fixture with Python file attachments."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_claude_with_attachment.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def chatgpt_with_reasoning():
    """Load ChatGPT test fixture with reasoning trace."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_chatgpt_with_reasoning.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def openwebui_with_image():
    """Load OpenWebUI test fixture with image attachment."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_openwebui_with_image.json"
    with open(fixture_path) as f:
        return json.load(f)


class TestClaudeAttachmentImport:
    """Test Claude format attachment import."""
    
    def test_imports_file_with_extracted_content(self, import_service, claude_with_attachment):
        """Test that Claude files with extracted_content are imported as available attachments."""
        result = import_service.import_json_data(claude_with_attachment)
        
        assert result.imported_count == 2
        assert result.format_detected == "Claude"
        assert len(result.errors) == 0
        
        # Verify the conversation was imported
        from db.repositories.unit_of_work import get_unit_of_work
        with get_unit_of_work() as uow:
            convs = uow.conversations.get_all()
            # Find the Python Hello World conversation
            test_conv = next((c for c in convs if "Python Hello World" in c.title), None)
            assert test_conv is not None
            
            messages = uow.messages.get_by_conversation(test_conv.id)
            
            # First message should have hello.py attachment
            msg1 = messages[0]
            assert msg1.message_metadata is not None
            assert 'attachments' in msg1.message_metadata
            attachments = msg1.message_metadata['attachments']
            assert len(attachments) == 1
            
            att = attachments[0]
            assert att['file_name'] == 'hello.py'
            assert att['type'] == 'file'
            assert att['available'] is True
            assert 'def greet' in att['extracted_content']
            
            # Fourth message should have hello_enhanced.py
            msg4 = messages[3]
            attachments4 = msg4.message_metadata['attachments']
            assert len(attachments4) == 1
            assert attachments4[0]['file_name'] == 'hello_enhanced.py'
            assert 'argparse' in attachments4[0]['extracted_content']
    
    def test_imports_image_without_content(self, import_service, claude_with_attachment):
        """Test that Claude image references without content are marked as unavailable."""
        result = import_service.import_json_data(claude_with_attachment)
        
        from db.repositories.unit_of_work import get_unit_of_work
        with get_unit_of_work() as uow:
            convs = uow.conversations.get_all()
            # Find the Image Analysis conversation
            test_conv = next((c for c in convs if "Image Analysis" in c.title), None)
            assert test_conv is not None
            
            messages = uow.messages.get_by_conversation(test_conv.id)
            
            # First message should have PNG file reference
            msg1 = messages[0]
            attachments = msg1.message_metadata['attachments']
            assert len(attachments) == 1
            
            att = attachments[0]
            assert att['file_name'] == 'architecture_diagram.png'
            assert att['type'] == 'image'
            assert att['available'] is False  # No content in export
            assert att['extracted_content'] is None


class TestChatGPTAttachmentImport:
    """Test ChatGPT format attachment import."""
    
    def test_imports_reasoning_trace(self, import_service, chatgpt_with_reasoning):
        """Test that ChatGPT reasoning traces are imported as attachments."""
        result = import_service.import_json_data(chatgpt_with_reasoning)
        
        assert result.imported_count == 1
        assert result.format_detected == "ChatGPT"
        assert len(result.errors) == 0
        
        from db.repositories.unit_of_work import get_unit_of_work
        with get_unit_of_work() as uow:
            convs = uow.conversations.get_all()
            test_conv = convs[0]
            
            messages = uow.messages.get_by_conversation(test_conv.id)
            
            # Should have 3 messages: user query, reasoning, answer
            assert len(messages) == 3
            
            # Second message should have reasoning attachment
            msg2 = messages[1]
            assert msg2.role == 'assistant'
            assert msg2.content == '[Reasoning process]'  # Placeholder
            
            attachments = msg2.message_metadata['attachments']
            assert len(attachments) == 1
            
            att = attachments[0]
            assert att['type'] == 'reasoning'
            assert att['reasoning_type'] == 'thoughts'
            assert att['available'] is True
            assert len(att['thoughts']) > 0
            assert 'Sieve of Eratosthenes' in att['thoughts'][0]['content']


class TestOpenWebUIAttachmentImport:
    """Test OpenWebUI format attachment import."""
    
    def test_imports_image_as_data_url(self, import_service, openwebui_with_image):
        """Test that OpenWebUI images (data URLs) are imported."""
        result = import_service.import_json_data(openwebui_with_image)
        
        assert result.imported_count == 1
        assert result.format_detected == "OpenWebUI"
        assert len(result.errors) == 0
        
        from db.repositories.unit_of_work import get_unit_of_work
        with get_unit_of_work() as uow:
            convs = uow.conversations.get_all()
            test_conv = convs[0]
            
            messages = uow.messages.get_by_conversation(test_conv.id)
            
            # First message should have image attachment
            msg1 = messages[0]
            attachments = msg1.message_metadata['attachments']
            assert len(attachments) == 1
            
            att = attachments[0]
            assert att['file_name'] == 'diagram.png'
            assert att['type'] == 'image'
            assert att['available'] is True  # Data URLs are now stored for rendering
            assert att['metadata']['data_url']  # Data URL is stored in metadata
            # extracted_content contains the data URL for rendering
            assert att['extracted_content'].startswith('data:image/')


class TestAttachmentRendering:
    """Test that attachments are properly passed to views."""
    
    def test_format_service_includes_attachments(self, import_service, claude_with_attachment):
        """Test that format_db_messages_for_view includes attachments."""
        # Import the test data
        import_service.import_json_data(claude_with_attachment)
        
        from db.repositories.unit_of_work import get_unit_of_work
        from db.services.conversation_format_service import ConversationFormatService
        
        format_service = ConversationFormatService()
        
        with get_unit_of_work() as uow:
            convs = uow.conversations.get_all()
            test_conv = next((c for c in convs if "Python Hello World" in c.title), None)
            
            db_messages = uow.messages.get_by_conversation(test_conv.id)
            formatted_messages = format_service.format_db_messages_for_view(db_messages)
            
            # First formatted message should have attachments
            assert 'attachments' in formatted_messages[0]
            assert len(formatted_messages[0]['attachments']) == 1
            assert formatted_messages[0]['attachments'][0]['file_name'] == 'hello.py'

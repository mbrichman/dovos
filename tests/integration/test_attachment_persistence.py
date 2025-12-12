"""
Integration test to verify attachments persist through the entire import pipeline.

This test verifies that:
1. Extractors add attachments to message dicts
2. Import service preserves attachments in message_metadata
3. Attachments are stored in the database
4. Attachments are retrieved when fetching messages
"""

import json
import pytest
from pathlib import Path

from db.services.import_service import ConversationImportService
from db.repositories.unit_of_work import get_unit_of_work


@pytest.fixture
def import_service():
    """Fixture providing import service instance."""
    return ConversationImportService()


@pytest.fixture
def sample_claude_data():
    """Load sample Claude data with attachments."""
    fixture_path = Path(__file__).parent.parent / 'fixtures' / 'sample_claude_with_attachment.json'
    with open(fixture_path, 'r') as f:
        return json.load(f)


def test_claude_attachments_persist_to_database(import_service, sample_claude_data):
    """Test that Claude attachments survive the full import pipeline."""
    # Import the data
    result = import_service.import_json_data(sample_claude_data)
    
    # Should have imported successfully
    assert result.imported_count == 2, f"Expected 2 conversations, got {result.imported_count}"
    
    # Find the "Python Hello World with File" conversation
    with get_unit_of_work() as uow:
        conversations = uow.conversations.get_all()
        python_conv = None
        for conv in conversations:
            if conv.title == "Python Hello World with File":
                python_conv = conv
                break
        
        assert python_conv is not None, "Python Hello World conversation not found"
        
        # Get messages for this conversation
        messages = uow.messages.get_by_conversation(python_conv.id)
        
        # The first user message should have 1 attachment (hello.py)
        user_msg_1 = messages[0]
        assert user_msg_1.role == 'user'
        assert user_msg_1.message_metadata is not None, "message_metadata is None"
        assert 'attachments' in user_msg_1.message_metadata, "No attachments key in message_metadata"
        
        attachments_1 = user_msg_1.message_metadata['attachments']
        assert len(attachments_1) == 1, f"Expected 1 attachment, got {len(attachments_1)}"
        assert attachments_1[0]['file_name'] == 'hello.py'
        assert attachments_1[0]['type'] == 'file'
        assert attachments_1[0]['available'] is True
        assert 'print(f"Hello, {name}!")' in attachments_1[0]['extracted_content']
        
        # The second assistant message should have 1 attachment (hello_enhanced.py)
        assistant_msg_2 = messages[3]
        assert assistant_msg_2.role == 'assistant'
        assert assistant_msg_2.message_metadata is not None
        assert 'attachments' in assistant_msg_2.message_metadata
        
        attachments_2 = assistant_msg_2.message_metadata['attachments']
        assert len(attachments_2) == 1, f"Expected 1 attachment, got {len(attachments_2)}"
        assert attachments_2[0]['file_name'] == 'hello_enhanced.py'
        assert attachments_2[0]['type'] == 'file'
        assert attachments_2[0]['available'] is True
        assert 'def greet' in attachments_2[0]['extracted_content']


def test_chatgpt_reasoning_attachments_persist(import_service):
    """Test that ChatGPT reasoning trace attachments survive import."""
    fixture_path = Path(__file__).parent.parent / 'fixtures' / 'sample_chatgpt_with_reasoning.json'
    with open(fixture_path, 'r') as f:
        data = json.load(f)
    
    result = import_service.import_json_data(data)
    assert result.imported_count == 1
    
    with get_unit_of_work() as uow:
        conversations = uow.conversations.get_all()
        reasoning_conv = None
        for conv in conversations:
            if 'o1' in conv.title.lower() or 'reasoning' in conv.title.lower():
                reasoning_conv = conv
                break
        
        assert reasoning_conv is not None, "Reasoning conversation not found"
        
        messages = uow.messages.get_by_conversation(reasoning_conv.id)
        
        # Find the assistant message with reasoning
        assistant_msg = None
        for msg in messages:
            if msg.role == 'assistant' and '[Reasoning' in msg.content:
                assistant_msg = msg
                break
        
        assert assistant_msg is not None, "Assistant message with reasoning not found"
        assert assistant_msg.message_metadata is not None
        assert 'attachments' in assistant_msg.message_metadata, "No attachments in reasoning message"
        
        attachments = assistant_msg.message_metadata['attachments']
        # Should have at least one reasoning attachment
        reasoning_atts = [a for a in attachments if a['type'] in ('reasoning', 'reasoning_summary')]
        assert len(reasoning_atts) > 0, "No reasoning attachments found"


def test_openwebui_image_attachments_persist(import_service):
    """Test that OpenWebUI image attachments survive import."""
    fixture_path = Path(__file__).parent.parent / 'fixtures' / 'sample_openwebui_with_image.json'
    with open(fixture_path, 'r') as f:
        data = json.load(f)
    
    result = import_service.import_json_data(data)
    assert result.imported_count == 1
    
    with get_unit_of_work() as uow:
        conversations = uow.conversations.get_all()
        image_conv = conversations[0]  # Only one conversation
        
        messages = uow.messages.get_by_conversation(image_conv.id)
        
        # Find user message with image
        user_msg = None
        for msg in messages:
            if msg.role == 'user':
                user_msg = msg
                break
        
        assert user_msg is not None
        assert user_msg.message_metadata is not None
        assert 'attachments' in user_msg.message_metadata, "No attachments in image message"
        
        attachments = user_msg.message_metadata['attachments']
        image_atts = [a for a in attachments if a['type'] == 'image']
        assert len(image_atts) > 0, f"No image attachments found. Attachments: {attachments}"
        
        # Verify the image is available and has data URL
        image_att = image_atts[0]
        assert image_att['available'] is True, "Image should be marked as available"
        assert image_att['extracted_content'].startswith('data:'), "Image should have data URL"
        assert 'data_url' in image_att['metadata'], "Image metadata should have data_url field"

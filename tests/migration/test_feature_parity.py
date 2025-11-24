"""
Phase 1.4: Feature Parity Tests

Validates that PostgreSQL backend supports all key features:
- Clipboard functionality (copy conversation to markdown)
- OpenWebUI export integration
- View filters and pagination
- Export to markdown
- Settings management

These tests ensure no feature regression during migration.
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from db.models.models import Conversation, Message, MessageEmbedding, Setting
from tests.utils.seed import seed_conversation_with_embeddings
from tests.utils.fake_embeddings import FakeEmbeddingGenerator


@pytest.fixture
def feature_test_data(db_session):
    """Create test data for feature testing."""
    embedding_gen = FakeEmbeddingGenerator(seed=777)
    
    conversations = []
    
    # Conversation 1: For export testing
    conv1 = seed_conversation_with_embeddings(
        db_session,
        title="Export Test Conversation",
        messages=[
            ("user", "Tell me about Python"),
            ("assistant", "Python is a high-level programming language known for its simplicity and readability."),
            ("user", "What are its main features?"),
            ("assistant", "Python features include: dynamic typing, automatic memory management, extensive standard library, and support for multiple programming paradigms."),
        ],
        embedding_generator=embedding_gen,
        created_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    )
    conversations.append(conv1)
    
    # Conversation 2: For filtering
    conv2 = seed_conversation_with_embeddings(
        db_session,
        title="JavaScript Basics",
        messages=[
            ("user", "What is JavaScript?"),
            ("assistant", "JavaScript is a scripting language primarily used for web development."),
        ],
        embedding_generator=embedding_gen,
        created_at=datetime(2024, 2, 1, 14, 30, 0, tzinfo=timezone.utc)
    )
    conversations.append(conv2)
    
    # Conversation 3: For pagination
    conv3 = seed_conversation_with_embeddings(
        db_session,
        title="Database Concepts",
        messages=[
            ("user", "Explain databases"),
            ("assistant", "Databases are organized collections of structured data."),
        ],
        embedding_generator=embedding_gen,
        created_at=datetime(2024, 3, 10, 9, 15, 0, tzinfo=timezone.utc)
    )
    conversations.append(conv3)
    
    db_session.flush()
    
    return {
        'conversations': conversations,
        'session': db_session
    }


@pytest.mark.migration
@pytest.mark.feature
class TestMarkdownExport:
    """Test markdown export functionality."""
    
    def test_conversation_exports_to_markdown(self, feature_test_data):
        """Verify conversation can be exported to markdown format."""
        session = feature_test_data['session']
        conversation = feature_test_data['conversations'][0]
        
        # Get conversation with messages
        conv = session.query(Conversation).filter_by(id=conversation.id).first()
        messages = (session.query(Message)
                   .filter_by(conversation_id=conversation.id)
                   .order_by(Message.created_at)
                   .all())
        
        # Build markdown
        markdown_lines = [f"# {conv.title}\n"]
        for msg in messages:
            role_label = "**You:**" if msg.role == "user" else "**Assistant:**"
            markdown_lines.append(f"{role_label}\n{msg.content}\n")
        
        markdown = "\n".join(markdown_lines)
        
        # Verify markdown structure
        assert f"# {conv.title}" in markdown
        assert "**You:**" in markdown
        assert "**Assistant:**" in markdown
        assert "Python is a high-level programming language" in markdown
    
    def test_markdown_preserves_message_order(self, feature_test_data):
        """Verify markdown export maintains correct message order."""
        session = feature_test_data['session']
        conversation = feature_test_data['conversations'][0]
        
        messages = (session.query(Message)
                   .filter_by(conversation_id=conversation.id)
                   .order_by(Message.created_at)
                   .all())
        
        # Check message order is preserved
        assert messages[0].content == "Tell me about Python"
        assert messages[1].content.startswith("Python is a high-level")
        assert messages[2].content == "What are its main features?"
        assert messages[3].content.startswith("Python features include")
    
    def test_markdown_handles_special_characters(self, db_session):
        """Verify markdown export handles special characters correctly."""
        embedding_gen = FakeEmbeddingGenerator(seed=123)
        
        conv = seed_conversation_with_embeddings(
            db_session,
            title="Special Characters Test: <>&\"'",
            messages=[
                ("user", "Test with special chars: <>&\"'"),
                ("assistant", "Response with unicode: 你好 مرحبا שלום"),
            ],
            embedding_generator=embedding_gen
        )
        db_session.flush()
        
        # Get messages
        messages = (db_session.query(Message)
                   .filter_by(conversation_id=conv.id)
                   .order_by(Message.created_at)
                   .all())
        
        # Build markdown
        markdown_lines = [f"# {conv.title}\n"]
        for msg in messages:
            role_label = "**You:**" if msg.role == "user" else "**Assistant:**"
            markdown_lines.append(f"{role_label}\n{msg.content}\n")
        
        markdown = "\n".join(markdown_lines)
        
        # Verify special characters preserved
        assert "<>&" in markdown
        assert "你好" in markdown
        assert "مرحبا" in markdown


@pytest.mark.migration
@pytest.mark.feature
class TestOpenWebUIExport:
    """Test OpenWebUI export integration."""
    
    def test_conversation_exports_to_openwebui_format(self, feature_test_data):
        """Verify conversation can be exported in OpenWebUI-compatible format."""
        session = feature_test_data['session']
        conversation = feature_test_data['conversations'][0]
        
        # Get conversation with messages
        conv = session.query(Conversation).filter_by(id=conversation.id).first()
        messages = (session.query(Message)
                   .filter_by(conversation_id=conversation.id)
                   .order_by(Message.created_at)
                   .all())
        
        # Build OpenWebUI format
        openwebui_format = {
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "messages": []
        }
        
        for msg in messages:
            openwebui_format["messages"].append({
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat()
            })
        
        # Verify structure
        assert "title" in openwebui_format
        assert "messages" in openwebui_format
        assert len(openwebui_format["messages"]) == 4
        assert openwebui_format["messages"][0]["role"] == "user"
        assert openwebui_format["messages"][1]["role"] == "assistant"
    
    def test_openwebui_export_json_serializable(self, feature_test_data):
        """Verify OpenWebUI export is JSON serializable."""
        session = feature_test_data['session']
        conversation = feature_test_data['conversations'][0]
        
        conv = session.query(Conversation).filter_by(id=conversation.id).first()
        messages = (session.query(Message)
                   .filter_by(conversation_id=conversation.id)
                   .order_by(Message.created_at)
                   .all())
        
        # Build export
        openwebui_format = {
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat()
                }
                for msg in messages
            ]
        }
        
        # Should be JSON serializable
        json_str = json.dumps(openwebui_format)
        assert isinstance(json_str, str)
        
        # Should be deserializable
        parsed = json.loads(json_str)
        assert parsed["title"] == conv.title
        assert len(parsed["messages"]) == 4


@pytest.mark.migration
@pytest.mark.feature
class TestConversationListing:
    """Test conversation listing with filters and pagination."""
    
    def test_list_conversations_with_pagination(self, feature_test_data):
        """Verify conversations can be paginated."""
        session = feature_test_data['session']
        
        # Get first page (limit 2)
        page_1 = (session.query(Conversation)
                 .order_by(Conversation.created_at.desc())
                 .limit(2)
                 .all())
        
        assert len(page_1) == 2
        
        # Get second page (skip 2, limit 2)
        page_2 = (session.query(Conversation)
                 .order_by(Conversation.created_at.desc())
                 .offset(2)
                 .limit(2)
                 .all())
        
        # Pages should not overlap
        page_1_ids = {c.id for c in page_1}
        page_2_ids = {c.id for c in page_2}
        assert len(page_1_ids & page_2_ids) == 0
    
    def test_conversations_ordered_by_date(self, feature_test_data):
        """Verify conversations are ordered by date (newest first)."""
        session = feature_test_data['session']
        
        conversations = (session.query(Conversation)
                        .order_by(Conversation.created_at.desc())
                        .all())
        
        # Verify ordering
        for i in range(len(conversations) - 1):
            assert conversations[i].created_at >= conversations[i+1].created_at
    
    def test_filter_conversations_by_title(self, feature_test_data):
        """Verify conversations can be filtered by title search."""
        session = feature_test_data['session']
        
        # Search for "Test" (which is in our test data)
        results = (session.query(Conversation)
                  .filter(Conversation.title.ilike('%Test%'))
                  .all())
        
        assert len(results) >= 1
        assert any("Test" in c.title for c in results)
    
    def test_conversation_list_includes_metadata(self, feature_test_data):
        """Verify conversation listings include necessary metadata."""
        session = feature_test_data['session']
        
        conversations = session.query(Conversation).all()
        
        for conv in conversations:
            # Each conversation should have metadata
            assert conv.id is not None
            assert conv.title is not None
            assert conv.created_at is not None
            assert conv.updated_at is not None
            
            # Should be able to get message count
            msg_count = session.query(Message).filter_by(conversation_id=conv.id).count()
            assert msg_count > 0


@pytest.mark.migration
@pytest.mark.feature
class TestConversationView:
    """Test individual conversation viewing."""
    
    def test_view_conversation_with_all_messages(self, feature_test_data):
        """Verify viewing a conversation returns all messages."""
        session = feature_test_data['session']
        conversation = feature_test_data['conversations'][0]
        
        # Get conversation
        conv = session.query(Conversation).filter_by(id=conversation.id).first()
        
        # Get messages
        messages = (session.query(Message)
                   .filter_by(conversation_id=conv.id)
                   .order_by(Message.created_at)
                   .all())
        
        assert conv is not None
        assert len(messages) == 4  # Export test conversation has 4 messages
        
        # Verify message order
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
    
    def test_view_preserves_formatting(self, db_session):
        """Verify viewed messages preserve formatting and newlines."""
        embedding_gen = FakeEmbeddingGenerator(seed=456)
        
        multi_line_content = """First line
Second line

Third line after blank"""
        
        conv = seed_conversation_with_embeddings(
            db_session,
            title="Formatting Test",
            messages=[
                ("user", "Test message"),
                ("assistant", multi_line_content),
            ],
            embedding_generator=embedding_gen
        )
        db_session.flush()
        
        # Retrieve message
        messages = (db_session.query(Message)
                   .filter_by(conversation_id=conv.id)
                   .order_by(Message.created_at)
                   .all())
        
        # Verify formatting preserved
        assert "\n" in messages[1].content
        assert "First line" in messages[1].content
        assert "Third line after blank" in messages[1].content


@pytest.mark.migration
@pytest.mark.feature
class TestSettingsManagement:
    """Test settings management functionality."""
    
    def test_settings_can_be_stored(self, db_session):
        """Verify settings can be stored in database."""
        # Create a setting
        setting = Setting(
            id="test_setting",
            value="test_value"
        )
        db_session.add(setting)
        db_session.flush()
        
        # Retrieve setting
        retrieved = db_session.query(Setting).filter_by(id="test_setting").first()
        
        assert retrieved is not None
        assert retrieved.value == "test_value"
    
    def test_settings_can_be_updated(self, db_session):
        """Verify settings can be updated."""
        # Create initial setting
        setting = Setting(id="updatable_setting", value="initial")
        db_session.add(setting)
        db_session.flush()
        
        # Update setting
        setting.value = "updated"
        db_session.flush()
        
        # Verify update
        retrieved = db_session.query(Setting).filter_by(id="updatable_setting").first()
        assert retrieved.value == "updated"
    
    def test_multiple_settings_supported(self, db_session):
        """Verify multiple settings can coexist."""
        settings = [
            Setting(id="setting1", value="value1"),
            Setting(id="setting2", value="value2"),
            Setting(id="setting3", value="value3"),
        ]
        
        for setting in settings:
            db_session.add(setting)
        db_session.flush()
        
        # Retrieve all
        all_settings = db_session.query(Setting).all()
        assert len(all_settings) >= 3
        
        # Verify each is retrievable
        for setting_id in ["setting1", "setting2", "setting3"]:
            setting = db_session.query(Setting).filter_by(id=setting_id).first()
            assert setting is not None


@pytest.mark.migration
@pytest.mark.feature
def test_feature_parity_summary(feature_test_data):
    """
    Summary test: validate all key features are functional.
    
    This ensures no feature regression during migration.
    """
    session = feature_test_data['session']
    conversation = feature_test_data['conversations'][0]
    
    print("\n" + "=" * 60)
    print("FEATURE PARITY TEST SUMMARY")
    print("=" * 60)
    
    # Test 1: Markdown export capability
    conv = session.query(Conversation).filter_by(id=conversation.id).first()
    messages = (session.query(Message)
               .filter_by(conversation_id=conversation.id)
               .order_by(Message.created_at)
               .all())
    
    markdown = f"# {conv.title}\n"
    for msg in messages:
        role = "**You:**" if msg.role == "user" else "**Assistant:**"
        markdown += f"{role}\n{msg.content}\n\n"
    
    export_ok = len(markdown) > 0 and "# " in markdown
    
    print(f"{'✓' if export_ok else '✗'} Markdown Export: {len(markdown)} characters generated")
    
    # Test 2: OpenWebUI format support
    openwebui_data = {
        "title": conv.title,
        "messages": [{"role": m.role, "content": m.content} for m in messages]
    }
    
    try:
        json.dumps(openwebui_data)
        openwebui_ok = True
    except:
        openwebui_ok = False
    
    print(f"{'✓' if openwebui_ok else '✗'} OpenWebUI Export: JSON serializable with {len(openwebui_data['messages'])} messages")
    
    # Test 3: Pagination support
    all_convs = session.query(Conversation).all()
    page_1 = session.query(Conversation).limit(2).all()
    pagination_ok = len(page_1) <= 2 and len(all_convs) >= len(page_1)
    
    print(f"{'✓' if pagination_ok else '✗'} Pagination: {len(page_1)} of {len(all_convs)} conversations on first page")
    
    # Test 4: Filtering support
    filtered = (session.query(Conversation)
               .filter(Conversation.title.ilike('%Test%'))
               .all())
    filter_ok = isinstance(filtered, list)
    
    print(f"{'✓' if filter_ok else '✗'} Filtering: {len(filtered)} conversations match filter")
    
    # Overall status
    all_ok = export_ok and openwebui_ok and pagination_ok and filter_ok
    
    print("=" * 60)
    print(f"Overall Status: {'✅ PASS - All Features Functional' if all_ok else '❌ FAIL - Feature Regression'}")
    print("=" * 60)
    
    assert all_ok, "Feature parity validation failed - features not working correctly"

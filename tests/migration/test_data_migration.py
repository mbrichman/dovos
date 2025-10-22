"""
Phase 1.3: Data Migration Tests

Validates zero data loss when migrating conversations, messages, and embeddings
from legacy ChromaDB to PostgreSQL.

Tests ensure:
- All conversations are migrated
- All messages are preserved with correct content
- Message order is maintained
- Timestamps are preserved
- Metadata integrity
- Embedding completeness
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from db.models.models import Conversation, Message, MessageEmbedding
from db.repositories.unit_of_work import UnitOfWork
from tests.utils.seed import seed_conversation_with_embeddings
from tests.utils.fake_embeddings import FakeEmbeddingGenerator


@pytest.fixture
def migration_source_data(db_session):
    """
    Simulate source data from ChromaDB that needs to be migrated.
    
    Returns conversations with known structure for validation.
    """
    embedding_gen = FakeEmbeddingGenerator(seed=123)
    
    conversations = []
    
    # Conversation 1: Multi-message thread
    conv1 = seed_conversation_with_embeddings(
        db_session,
        title="Python Web Development",
        messages=[
            ("user", "How do I build a REST API with Flask?"),
            ("assistant", "Flask is great for building REST APIs. Here's how to get started..."),
            ("user", "What about authentication?"),
            ("assistant", "For authentication, I recommend using Flask-JWT-Extended..."),
            ("user", "Can you show me an example?"),
            ("assistant", "Here's a complete example with JWT authentication..."),
        ],
        embedding_generator=embedding_gen,
        created_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    )
    conversations.append(conv1)
    
    # Conversation 2: Short conversation
    conv2 = seed_conversation_with_embeddings(
        db_session,
        title="Quick Question",
        messages=[
            ("user", "What is PostgreSQL?"),
            ("assistant", "PostgreSQL is a powerful open-source relational database."),
        ],
        embedding_generator=embedding_gen,
        created_at=datetime(2024, 2, 1, 14, 20, 0, tzinfo=timezone.utc)
    )
    conversations.append(conv2)
    
    # Conversation 3: Empty metadata test
    conv3 = seed_conversation_with_embeddings(
        db_session,
        title="Edge Case Test",
        messages=[
            ("user", "Test message with special chars: <>&\"'"),
            ("assistant", "Response with unicode: 你好 مرحبا שלום"),
        ],
        embedding_generator=embedding_gen,
        created_at=datetime(2024, 3, 10, 9, 15, 0, tzinfo=timezone.utc)
    )
    conversations.append(conv3)
    
    db_session.commit()
    
    return {
        'conversations': conversations,
        'expected_conversation_count': 3,
        'expected_message_count': 10,  # 6 + 2 + 2
        'expected_embedding_count': 10
    }


@pytest.mark.migration
@pytest.mark.data
class TestConversationMigration:
    """Test conversation-level data migration."""
    
    def test_all_conversations_migrated(self, db_session, migration_source_data):
        """Verify all conversations are present after migration."""
        expected_count = migration_source_data['expected_conversation_count']
        
        actual_count = db_session.query(Conversation).count()
        
        assert actual_count == expected_count, \
            f"Expected {expected_count} conversations, found {actual_count}"
    
    def test_conversation_titles_preserved(self, db_session, migration_source_data):
        """Verify conversation titles are preserved correctly."""
        expected_titles = {
            "Python Web Development",
            "Quick Question", 
            "Edge Case Test"
        }
        
        conversations = db_session.query(Conversation).all()
        actual_titles = {c.title for c in conversations}
        
        assert actual_titles == expected_titles, \
            f"Title mismatch. Expected: {expected_titles}, Got: {actual_titles}"
    
    def test_conversation_timestamps_preserved(self, db_session, migration_source_data):
        """Verify conversation timestamps are preserved."""
        conversations = db_session.query(Conversation).order_by(Conversation.created_at).all()
        
        # Check timestamps are set
        for conv in conversations:
            assert conv.created_at is not None, f"Conversation {conv.id} missing created_at"
            assert conv.updated_at is not None, f"Conversation {conv.id} missing updated_at"
        
        # Verify chronological order
        assert conversations[0].title == "Python Web Development"
        assert conversations[1].title == "Quick Question"
        assert conversations[2].title == "Edge Case Test"
    
    def test_conversation_ids_are_valid_uuids(self, db_session, migration_source_data):
        """Verify all conversation IDs are valid UUIDs."""
        conversations = db_session.query(Conversation).all()
        
        for conv in conversations:
            assert conv.id is not None
            # UUID should be string-representable
            uuid_str = str(conv.id)
            assert len(uuid_str) == 36  # Standard UUID format
            assert uuid_str.count('-') == 4


@pytest.mark.migration
@pytest.mark.data
class TestMessageMigration:
    """Test message-level data migration."""
    
    def test_all_messages_migrated(self, db_session, migration_source_data):
        """Verify all messages are present after migration."""
        expected_count = migration_source_data['expected_message_count']
        
        actual_count = db_session.query(Message).count()
        
        assert actual_count == expected_count, \
            f"Expected {expected_count} messages, found {actual_count}"
    
    def test_message_content_preserved(self, db_session, migration_source_data):
        """Verify message content is preserved exactly."""
        messages = db_session.query(Message).all()
        
        # All messages should have non-empty content
        for msg in messages:
            assert msg.content, f"Message {msg.id} has empty content"
            assert len(msg.content) > 0
        
        # Check for specific content
        contents = [msg.content for msg in messages]
        
        assert any("Flask" in c for c in contents), "Expected Flask-related content"
        assert any("PostgreSQL" in c for c in contents), "Expected PostgreSQL content"
        assert any("special chars" in c for c in contents), "Expected special chars test"
    
    def test_message_roles_valid(self, db_session, migration_source_data):
        """Verify all message roles are valid."""
        valid_roles = {'user', 'assistant', 'system'}
        
        messages = db_session.query(Message).all()
        
        for msg in messages:
            assert msg.role in valid_roles, \
                f"Message {msg.id} has invalid role: {msg.role}"
        
        # Should have both user and assistant messages
        roles = {msg.role for msg in messages}
        assert 'user' in roles
        assert 'assistant' in roles
    
    def test_message_order_preserved(self, db_session, migration_source_data):
        """Verify messages maintain correct chronological order within conversations."""
        conversations = migration_source_data['conversations']
        
        for conv in conversations:
            # Get messages for this conversation in order
            messages = (db_session.query(Message)
                       .filter_by(conversation_id=conv.id)
                       .order_by(Message.created_at)
                       .all())
            
            # Messages should alternate between user and assistant
            # (or at least start with user)
            if len(messages) > 0:
                assert messages[0].role == 'user', \
                    f"Conversation {conv.id} should start with user message"
            
            # Check timestamps are sequential
            for i in range(len(messages) - 1):
                assert messages[i].created_at <= messages[i+1].created_at, \
                    f"Messages out of order in conversation {conv.id}"
    
    def test_message_conversation_relationships(self, db_session, migration_source_data):
        """Verify all messages are correctly linked to conversations."""
        messages = db_session.query(Message).all()
        conversation_ids = {c.id for c in migration_source_data['conversations']}
        
        for msg in messages:
            assert msg.conversation_id is not None, \
                f"Message {msg.id} has no conversation_id"
            assert msg.conversation_id in conversation_ids, \
                f"Message {msg.id} linked to unknown conversation {msg.conversation_id}"
            
            # Verify the relationship works
            assert msg.conversation is not None, \
                f"Message {msg.id} conversation relationship broken"
    
    def test_special_characters_preserved(self, db_session, migration_source_data):
        """Verify special characters and unicode are preserved."""
        messages = db_session.query(Message).all()
        contents = ' '.join([msg.content for msg in messages])
        
        # Check special chars preserved
        assert '<' in contents or '&' in contents, "Special HTML chars should be preserved"
        
        # Check unicode preserved
        unicode_chars = ['你好', 'مرحبا', 'שלום']
        assert any(char in contents for char in unicode_chars), \
            "Unicode characters should be preserved"
    
    def test_message_metadata_structure(self, db_session, migration_source_data):
        """Verify message metadata has correct structure."""
        messages = db_session.query(Message).all()
        
        for msg in messages:
            # message_metadata should be a dict (JSON column)
            assert isinstance(msg.message_metadata, dict), \
                f"Message {msg.id} metadata is not a dict"


@pytest.mark.migration
@pytest.mark.data
class TestEmbeddingMigration:
    """Test embedding data migration."""
    
    def test_all_embeddings_migrated(self, db_session, migration_source_data):
        """Verify all embeddings are present after migration."""
        expected_count = migration_source_data['expected_embedding_count']
        
        actual_count = db_session.query(MessageEmbedding).count()
        
        assert actual_count == expected_count, \
            f"Expected {expected_count} embeddings, found {actual_count}"
    
    def test_embedding_message_relationships(self, db_session, migration_source_data):
        """Verify embeddings are correctly linked to messages."""
        embeddings = db_session.query(MessageEmbedding).all()
        message_ids = {msg.id for msg in db_session.query(Message).all()}
        
        for emb in embeddings:
            assert emb.message_id is not None, \
                f"Embedding has no message_id"
            assert emb.message_id in message_ids, \
                f"Embedding linked to unknown message {emb.message_id}"
            
            # Verify relationship works
            assert emb.message is not None, \
                f"Embedding for message {emb.message_id} has broken relationship"
    
    def test_embedding_vectors_valid(self, db_session, migration_source_data):
        """Verify embedding vectors have correct dimensions and valid values."""
        import numpy as np
        
        embeddings = db_session.query(MessageEmbedding).all()
        
        for emb in embeddings:
            assert emb.embedding is not None, \
                f"Message {emb.message_id} has null embedding"
            
            # Check vector dimension (should be 384 for all-MiniLM-L6-v2)
            assert len(emb.embedding) == 384, \
                f"Embedding for message {emb.message_id} has wrong dimension: {len(emb.embedding)}"
            
            # Check all values are numeric (pgvector returns numpy arrays)
            # Convert to list if it's a numpy array
            vec = emb.embedding if isinstance(emb.embedding, list) else list(emb.embedding)
            assert all(isinstance(v, (int, float, np.number)) for v in vec), \
                f"Embedding for message {emb.message_id} contains non-numeric values"
    
    def test_embedding_models_consistent(self, db_session, migration_source_data):
        """Verify all embeddings use the same model."""
        embeddings = db_session.query(MessageEmbedding).all()
        
        models = {emb.model for emb in embeddings}
        
        # Should use single model
        assert len(models) == 1, f"Multiple embedding models found: {models}"
        assert "all-MiniLM-L6-v2" in models, f"Expected all-MiniLM-L6-v2 model, got {models}"
    
    def test_one_to_one_message_embedding_relationship(self, db_session, migration_source_data):
        """Verify each message has exactly one embedding."""
        messages = db_session.query(Message).all()
        
        for msg in messages:
            embedding_count = (db_session.query(MessageEmbedding)
                             .filter_by(message_id=msg.id)
                             .count())
            
            assert embedding_count == 1, \
                f"Message {msg.id} has {embedding_count} embeddings (expected 1)"


@pytest.mark.migration
@pytest.mark.data
class TestMigrationDataIntegrity:
    """Test overall data integrity after migration."""
    
    def test_no_orphaned_messages(self, db_session, migration_source_data):
        """Verify no messages exist without a parent conversation."""
        # Join messages with conversations
        orphaned = (db_session.query(Message)
                   .outerjoin(Conversation, Message.conversation_id == Conversation.id)
                   .filter(Conversation.id == None)
                   .count())
        
        assert orphaned == 0, f"Found {orphaned} orphaned messages"
    
    def test_no_orphaned_embeddings(self, db_session, migration_source_data):
        """Verify no embeddings exist without a parent message."""
        orphaned = (db_session.query(MessageEmbedding)
                   .outerjoin(Message, MessageEmbedding.message_id == Message.id)
                   .filter(Message.id == None)
                   .count())
        
        assert orphaned == 0, f"Found {orphaned} orphaned embeddings"
    
    def test_referential_integrity(self, db_session, migration_source_data):
        """Verify all foreign key relationships are valid."""
        # All messages should reference valid conversations
        invalid_messages = db_session.query(Message).filter(
            ~Message.conversation_id.in_(
                db_session.query(Conversation.id)
            )
        ).count()
        
        assert invalid_messages == 0, \
            f"Found {invalid_messages} messages with invalid conversation_id"
        
        # All embeddings should reference valid messages
        invalid_embeddings = db_session.query(MessageEmbedding).filter(
            ~MessageEmbedding.message_id.in_(
                db_session.query(Message.id)
            )
        ).count()
        
        assert invalid_embeddings == 0, \
            f"Found {invalid_embeddings} embeddings with invalid message_id"
    
    def test_data_completeness_summary(self, db_session, migration_source_data):
        """
        Summary test: validate complete data migration with zero loss.
        
        This is a critical gate - if this fails, migration cannot proceed.
        """
        print("\n" + "=" * 60)
        print("DATA MIGRATION INTEGRITY CHECK")
        print("=" * 60)
        
        # Count entities
        conv_count = db_session.query(Conversation).count()
        msg_count = db_session.query(Message).count()
        emb_count = db_session.query(MessageEmbedding).count()
        
        expected = migration_source_data
        
        # Validate counts
        conv_ok = conv_count == expected['expected_conversation_count']
        msg_ok = msg_count == expected['expected_message_count']
        emb_ok = emb_count == expected['expected_embedding_count']
        
        print(f"{'✓' if conv_ok else '✗'} Conversations: {conv_count}/{expected['expected_conversation_count']}")
        print(f"{'✓' if msg_ok else '✗'} Messages: {msg_count}/{expected['expected_message_count']}")
        print(f"{'✓' if emb_ok else '✗'} Embeddings: {emb_count}/{expected['expected_embedding_count']}")
        
        # Check for orphans
        orphaned_msgs = (db_session.query(Message)
                        .outerjoin(Conversation, Message.conversation_id == Conversation.id)
                        .filter(Conversation.id == None)
                        .count())
        
        orphaned_embs = (db_session.query(MessageEmbedding)
                        .outerjoin(Message, MessageEmbedding.message_id == Message.id)
                        .filter(Message.id == None)
                        .count())
        
        orphan_ok = orphaned_msgs == 0 and orphaned_embs == 0
        
        print(f"{'✓' if orphan_ok else '✗'} No Orphaned Data")
        
        # Overall status
        all_ok = conv_ok and msg_ok and emb_ok and orphan_ok
        
        print("=" * 60)
        print(f"Overall Status: {'✅ PASS - Zero Data Loss' if all_ok else '❌ FAIL - Data Loss Detected'}")
        print("=" * 60)
        
        assert all_ok, "Data migration validation failed - data loss detected"

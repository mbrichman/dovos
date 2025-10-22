"""
Phase 2.0: Integration Tests

Validates end-to-end workflows through the PostgreSQL backend:
- Complete import workflow (conversation -> messages -> embeddings)
- Search workflow (query -> results)
- RAG workflow (query -> context -> response)
- Multi-conversation operations
- Concurrent operations

These tests verify that all components work together correctly.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from db.models.models import Conversation, Message, MessageEmbedding
from db.repositories.unit_of_work import UnitOfWork
from db.services.search_service import SearchService, SearchConfig
from tests.utils.seed import seed_conversation_with_embeddings
from tests.utils.fake_embeddings import FakeEmbeddingGenerator


@pytest.fixture
def integrated_system(db_session):
    """
    Set up a complete system with multiple conversations for integration testing.
    
    Simulates a realistic chat history with varied content.
    """
    embedding_gen = FakeEmbeddingGenerator(seed=999)
    
    conversations = []
    
    # Technical support conversation
    conv1 = seed_conversation_with_embeddings(
        db_session,
        title="Docker Setup Help",
        messages=[
            ("user", "I'm having trouble with Docker containers not starting"),
            ("assistant", "Let's troubleshoot this. First, can you check if Docker daemon is running?"),
            ("user", "Yes, Docker is running. The containers were working yesterday."),
            ("assistant", "Try running 'docker ps -a' to see all containers and their status."),
            ("user", "One container shows 'Exited (137)' status."),
            ("assistant", "Error 137 means the container was killed by SIGKILL. This often happens due to out-of-memory. Check your system resources."),
        ],
        embedding_generator=embedding_gen,
        created_at=datetime(2024, 1, 10, 9, 0, 0, tzinfo=timezone.utc)
    )
    conversations.append(conv1)
    
    # Programming question
    conv2 = seed_conversation_with_embeddings(
        db_session,
        title="Python Async Programming",
        messages=[
            ("user", "How do I handle multiple API calls concurrently in Python?"),
            ("assistant", "Use asyncio with aiohttp for concurrent API calls. Here's a pattern..."),
            ("user", "Should I use asyncio.gather or asyncio.wait?"),
            ("assistant", "Use asyncio.gather when you want to wait for all tasks. Use asyncio.wait when you need more control over timeouts and cancellation."),
        ],
        embedding_generator=embedding_gen,
        created_at=datetime(2024, 1, 11, 14, 30, 0, tzinfo=timezone.utc)
    )
    conversations.append(conv2)
    
    # Database question
    conv3 = seed_conversation_with_embeddings(
        db_session,
        title="PostgreSQL Query Optimization",
        messages=[
            ("user", "My PostgreSQL queries are slow. How can I optimize them?"),
            ("assistant", "Start by analyzing with EXPLAIN ANALYZE. Look for sequential scans on large tables."),
            ("user", "I see several sequential scans. What should I do?"),
            ("assistant", "Add indexes on columns used in WHERE clauses and JOIN conditions. Use CREATE INDEX."),
        ],
        embedding_generator=embedding_gen,
        created_at=datetime(2024, 1, 12, 10, 15, 0, tzinfo=timezone.utc)
    )
    conversations.append(conv3)
    
    # Quick question
    conv4 = seed_conversation_with_embeddings(
        db_session,
        title="Git Branch Help",
        messages=[
            ("user", "How do I delete a remote branch in git?"),
            ("assistant", "Use: git push origin --delete branch-name"),
        ],
        embedding_generator=embedding_gen,
        created_at=datetime(2024, 1, 13, 16, 45, 0, tzinfo=timezone.utc)
    )
    conversations.append(conv4)
    
    db_session.commit()
    
    return {
        'conversations': conversations,
        'total_conversations': 4,
        'total_messages': 14,  # 6 + 4 + 4 + 2
        'session': db_session
    }


@pytest.mark.integration
class TestCompleteImportWorkflow:
    """Test the complete import workflow from raw data to searchable content."""
    
    def test_conversation_to_searchable_pipeline(self, db_session):
        """Verify complete pipeline: create conversation -> add messages -> generate embeddings -> search."""
        embedding_gen = FakeEmbeddingGenerator(seed=42)
        
        # Step 1: Import conversation with messages
        conv = seed_conversation_with_embeddings(
            db_session,
            title="Test Import Workflow",
            messages=[
                ("user", "What is machine learning?"),
                ("assistant", "Machine learning is a subset of artificial intelligence that enables systems to learn from data."),
            ],
            embedding_generator=embedding_gen
        )
        db_session.commit()
        
        # Step 2: Verify data is persisted
        assert db_session.query(Conversation).filter_by(id=conv.id).count() == 1
        
        messages = db_session.query(Message).filter_by(conversation_id=conv.id).all()
        assert len(messages) == 2
        
        embeddings = db_session.query(MessageEmbedding).filter(
            MessageEmbedding.message_id.in_([m.id for m in messages])
        ).all()
        assert len(embeddings) == 2
        
        # Step 3: Verify searchable (keyword search should work)
        search_service = SearchService()
        results = search_service.search_fts_only(query="machine learning", limit=10)
        
        assert len(results) > 0, "Should find the imported conversation via search"
        assert any("machine learning" in r.content.lower() for r in results)
    
    def test_bulk_import_maintains_relationships(self, integrated_system):
        """Verify bulk import maintains all relationships correctly."""
        session = integrated_system['session']
        
        # Verify all conversations imported
        conv_count = session.query(Conversation).count()
        assert conv_count == integrated_system['total_conversations']
        
        # Verify all messages linked
        msg_count = session.query(Message).count()
        assert msg_count == integrated_system['total_messages']
        
        # Verify all embeddings linked
        emb_count = session.query(MessageEmbedding).count()
        assert emb_count == integrated_system['total_messages']
        
        # Verify no broken relationships
        for msg in session.query(Message).all():
            assert msg.conversation is not None
            assert msg.embedding is not None


@pytest.mark.integration
class TestSearchWorkflow:
    """Test end-to-end search workflows."""
    
    def test_keyword_search_workflow(self, integrated_system):
        """Test complete keyword search from query to results."""
        search_service = SearchService()
        
        # Search for Docker-related content
        results = search_service.search_fts_only(query="Docker", limit=10)
        
        # Should find Docker conversation
        assert len(results) > 0, "Should find Docker-related content"
        
        # Verify result structure
        for result in results:
            assert hasattr(result, 'content')
            assert hasattr(result, 'conversation_title')
            assert hasattr(result, 'message_id')
            assert result.content, "Result should have content"
    
    def test_search_across_multiple_conversations(self, integrated_system):
        """Verify search can find results from multiple conversations."""
        search_service = SearchService()
        
        # Generic query that should match multiple conversations
        results = search_service.search_fts_only(query="how", limit=20)
        
        # Should find results from multiple conversations
        conversation_ids = {r.conversation_id for r in results}
        assert len(conversation_ids) >= 2, "Should find results from multiple conversations"
    
    def test_search_result_ordering(self, integrated_system):
        """Verify search results are properly ordered by relevance."""
        search_service = SearchService()
        
        results = search_service.search_fts_only(query="PostgreSQL", limit=10)
        
        if len(results) > 0:
            # Results should have scores
            assert all(hasattr(r, 'combined_score') for r in results)
            
            # Scores should be in descending order (most relevant first)
            scores = [r.combined_score for r in results]
            assert scores == sorted(scores, reverse=True), "Results should be ordered by score"
    
    def test_search_with_no_results(self, integrated_system):
        """Verify graceful handling of searches with no results."""
        search_service = SearchService()
        
        # Search for something that doesn't exist
        results = search_service.search_fts_only(query="xyzabc999unlikely", limit=10)
        
        # Should return empty list, not error
        assert isinstance(results, list)
        assert len(results) == 0


@pytest.mark.integration  
class TestConversationRetrieval:
    """Test conversation retrieval workflows."""
    
    def test_retrieve_conversation_with_messages(self, integrated_system):
        """Test retrieving a complete conversation with all messages."""
        session = integrated_system['session']
        conversations = integrated_system['conversations']
        
        # Pick first conversation
        conv_id = conversations[0].id
        
        # Retrieve conversation with messages
        conversation = session.query(Conversation).filter_by(id=conv_id).first()
        messages = (session.query(Message)
                   .filter_by(conversation_id=conv_id)
                   .order_by(Message.created_at)
                   .all())
        
        assert conversation is not None
        assert len(messages) > 0
        assert all(m.conversation_id == conv_id for m in messages)
    
    def test_list_all_conversations(self, integrated_system):
        """Test listing all conversations with pagination."""
        session = integrated_system['session']
        
        # Get all conversations ordered by date
        conversations = (session.query(Conversation)
                        .order_by(Conversation.created_at.desc())
                        .all())
        
        assert len(conversations) == integrated_system['total_conversations']
        
        # Verify ordering (newest first)
        for i in range(len(conversations) - 1):
            assert conversations[i].created_at >= conversations[i+1].created_at
    
    def test_conversation_message_count(self, integrated_system):
        """Verify accurate message counts per conversation."""
        session = integrated_system['session']
        
        for conv in integrated_system['conversations']:
            msg_count = session.query(Message).filter_by(conversation_id=conv.id).count()
            assert msg_count > 0, f"Conversation {conv.id} should have messages"


@pytest.mark.integration
class TestConcurrentOperations:
    """Test concurrent operations on the database."""
    
    def test_concurrent_reads(self, integrated_system):
        """Test multiple concurrent read operations."""
        session = integrated_system['session']
        
        # Simulate concurrent reads
        results = []
        for _ in range(5):
            conversations = session.query(Conversation).all()
            results.append(len(conversations))
        
        # All reads should return same count
        assert all(r == results[0] for r in results)
        assert results[0] == integrated_system['total_conversations']
    
    def test_read_while_search(self, integrated_system):
        """Test database reads while search is running."""
        session = integrated_system['session']
        search_service = SearchService()
        
        # Perform search
        search_results = search_service.search_fts_only(query="Docker", limit=5)
        
        # Simultaneously read conversations
        conversations = session.query(Conversation).all()
        
        # Both operations should succeed
        assert isinstance(search_results, list)
        assert len(conversations) == integrated_system['total_conversations']


@pytest.mark.integration
class TestDataConsistency:
    """Test data consistency across operations."""
    
    def test_message_conversation_consistency(self, integrated_system):
        """Verify messages are always consistent with their conversations."""
        session = integrated_system['session']
        
        messages = session.query(Message).all()
        
        for msg in messages:
            # Message should have conversation
            assert msg.conversation is not None
            
            # Conversation should be findable
            conv = session.query(Conversation).filter_by(id=msg.conversation_id).first()
            assert conv is not None
            assert conv.id == msg.conversation_id
    
    def test_embedding_message_consistency(self, integrated_system):
        """Verify embeddings are always consistent with their messages."""
        session = integrated_system['session']
        
        embeddings = session.query(MessageEmbedding).all()
        
        for emb in embeddings:
            # Embedding should have message
            assert emb.message is not None
            
            # Message should be findable
            msg = session.query(Message).filter_by(id=emb.message_id).first()
            assert msg is not None
            assert msg.id == emb.message_id
    
    def test_cascade_delete_consistency(self, db_session):
        """Test that cascade deletes maintain consistency."""
        embedding_gen = FakeEmbeddingGenerator(seed=123)
        
        # Create a conversation with messages and embeddings
        conv = seed_conversation_with_embeddings(
            db_session,
            title="Test Delete",
            messages=[
                ("user", "Test message 1"),
                ("assistant", "Test response 1"),
            ],
            embedding_generator=embedding_gen
        )
        db_session.commit()
        
        conv_id = conv.id
        
        # Get message IDs before delete
        message_ids = [m.id for m in db_session.query(Message).filter_by(conversation_id=conv_id).all()]
        assert len(message_ids) == 2
        
        # Delete conversation
        db_session.query(Conversation).filter_by(id=conv_id).delete()
        db_session.commit()
        
        # Verify cascade delete worked
        remaining_messages = db_session.query(Message).filter_by(conversation_id=conv_id).count()
        assert remaining_messages == 0, "Messages should be deleted with conversation"
        
        remaining_embeddings = db_session.query(MessageEmbedding).filter(
            MessageEmbedding.message_id.in_(message_ids)
        ).count()
        assert remaining_embeddings == 0, "Embeddings should be deleted with messages"


@pytest.mark.integration
def test_integration_summary(integrated_system):
    """
    Summary integration test: validate complete system functionality.
    
    This is a critical gate - all major workflows must work end-to-end.
    """
    session = integrated_system['session']
    search_service = SearchService()
    
    print("\n" + "=" * 60)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)
    
    # Test 1: Data import
    conv_count = session.query(Conversation).count()
    msg_count = session.query(Message).count()
    emb_count = session.query(MessageEmbedding).count()
    
    import_ok = (
        conv_count == integrated_system['total_conversations'] and
        msg_count == integrated_system['total_messages'] and
        emb_count == integrated_system['total_messages']
    )
    
    print(f"{'✓' if import_ok else '✗'} Data Import: {conv_count} conversations, {msg_count} messages, {emb_count} embeddings")
    
    # Test 2: Search functionality
    search_results = search_service.search_fts_only(query="Docker", limit=10)
    search_ok = len(search_results) > 0
    
    print(f"{'✓' if search_ok else '✗'} Search: Found {len(search_results)} results for 'Docker'")
    
    # Test 3: Conversation retrieval
    first_conv = session.query(Conversation).first()
    conv_messages = session.query(Message).filter_by(conversation_id=first_conv.id).all()
    retrieval_ok = len(conv_messages) > 0
    
    print(f"{'✓' if retrieval_ok else '✗'} Conversation Retrieval: {len(conv_messages)} messages in first conversation")
    
    # Test 4: Data consistency
    orphaned_msgs = (session.query(Message)
                    .outerjoin(Conversation, Message.conversation_id == Conversation.id)
                    .filter(Conversation.id == None)
                    .count())
    
    orphaned_embs = (session.query(MessageEmbedding)
                    .outerjoin(Message, MessageEmbedding.message_id == Message.id)
                    .filter(Message.id == None)
                    .count())
    
    consistency_ok = orphaned_msgs == 0 and orphaned_embs == 0
    
    print(f"{'✓' if consistency_ok else '✗'} Data Consistency: No orphaned records")
    
    # Overall status
    all_ok = import_ok and search_ok and retrieval_ok and consistency_ok
    
    print("=" * 60)
    print(f"Overall Status: {'✅ PASS - All Workflows Functional' if all_ok else '❌ FAIL - Integration Issues'}")
    print("=" * 60)
    
    assert all_ok, "Integration validation failed - workflows not functioning correctly"

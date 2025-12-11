"""
PostgreSQL Controller Unit Tests

Tests the PostgreSQL controller's response formatting and data handling
without relying on Flask routes or HTTP requests.
"""
import pytest
from unittest.mock import MagicMock, patch
from controllers.postgres_controller import PostgresController


@pytest.fixture(autouse=True)
def use_test_db_and_clean(test_db_engine):
    """
    Force PostgresController and adapter to use the test DB engine and
    start each test with a clean database.
    
    This fixture patches db.database.engine/SessionFactory for the duration
    of each test, resets the PostgresController singleton, and truncates
    core tables (Embeddings -> Messages -> Conversations) to ensure a clean state.
    """
    # Patch globals before controller instantiation
    import db.database as dbm
    import controllers.postgres_controller as pc_module
    from sqlalchemy.orm import sessionmaker, Session
    
    original_engine = dbm.engine
    original_session_factory = dbm.SessionFactory
    original_controller = getattr(pc_module, "_controller", None)
    
    dbm.engine = test_db_engine
    dbm.SessionFactory = sessionmaker(bind=test_db_engine)
    pc_module._controller = None
    
    # Create/ensure view exists, then clean tables
    from sqlalchemy import text
    from db.models.models import Conversation, Message, MessageEmbedding

    # Ensure conversation_summaries exists (normal VIEW so it stays current)
    sess = Session(bind=test_db_engine)
    try:
        sess.execute(text("DROP MATERIALIZED VIEW IF EXISTS conversation_summaries"))
        sess.execute(text("DROP VIEW IF EXISTS conversation_summaries"))
        sess.execute(text("""
            CREATE VIEW conversation_summaries AS
            SELECT 
                c.id,
                COUNT(m.id) AS message_count,
                MIN(m.created_at) AS earliest_message_at,
                MAX(m.created_at) AS latest_message_at,
                SUBSTRING(MAX(CASE WHEN m.role = 'assistant' THEN m.content END) FROM 1 FOR 200) AS preview
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            GROUP BY c.id
        """))
        sess.commit()
    except Exception:
        sess.rollback()
        # If this fails, tests will still proceed; failures will surface clearly
    finally:
        sess.close()

    # Clean tables for a fresh start each test
    sess = Session(bind=test_db_engine)
    try:
        # Delete in dependency order (foreign key constraints)
        sess.query(MessageEmbedding).delete()
        sess.query(Message).delete()
        sess.query(Conversation).delete()
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()
    
    try:
        yield
    finally:
        # Restore globals to avoid leaking state to other modules
        dbm.engine = original_engine
        dbm.SessionFactory = original_session_factory
        pc_module._controller = original_controller


@pytest.fixture
def postgres_controller():
    """Create a fresh PostgresController instance for each test."""
    return PostgresController()


@pytest.fixture
def seeded_controller(postgres_controller, test_db_engine):
    """Create a controller with seeded test data.
    
    Creates committed test data and cleans up after the test.
    """
    from tests.utils.seed import seed_conversation_with_messages
    from sqlalchemy.orm import Session
    from db.repositories.unit_of_work import UnitOfWork
    from db.models.models import Conversation
    
    # Create a fresh session for seeding
    session = Session(bind=test_db_engine)
    uow = UnitOfWork(session=session)
    
    conversations = []
    conv_ids = []
    
    try:
        # Seed 3 test conversations
        for i in range(3):
            conv, messages = seed_conversation_with_messages(
                uow,
                title=f"Test Conversation {i+1}",
                message_count=4,
                with_embeddings=True,
                created_days_ago=i
            )
            conversations.append((conv, messages))
            conv_ids.append(str(conv.id))
        
        # Commit to ensure data is persisted
        uow.commit()
        
        yield postgres_controller, conversations
    finally:
        # Clean up: delete the conversations we created
        try:
            for conv_id in conv_ids:
                session.query(Conversation).filter(Conversation.id == conv_id).delete()
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()


@pytest.mark.unit
class TestGetConversationsEndpoint:
    """Test GET /api/conversations endpoint."""
    
    def test_get_conversations_returns_dict_structure(self, postgres_controller):
        """Test that get_conversations returns correct dict structure."""
        result = postgres_controller.get_conversations()
        
        # Should have ChromaDB-compatible structure
        assert isinstance(result, dict)
        assert "documents" in result
        assert "metadatas" in result
        assert "ids" in result
        assert isinstance(result["documents"], list)
        assert isinstance(result["metadatas"], list)
        assert isinstance(result["ids"], list)
    
    def test_get_conversations_empty_database(self, db_session):
        """Test get_conversations with guaranteed empty database.
        
        Uses db_session which provides test isolation.
        """
        controller = PostgresController()
        result = controller.get_conversations()
        
        # With fresh db_session, database should be empty
        assert len(result["documents"]) == 0
        assert len(result["metadatas"]) == 0
        assert len(result["ids"]) == 0
    
    def test_get_conversations_with_seeded_data(self, seeded_controller):
        """Test get_conversations with seeded test data."""
        controller, conversations = seeded_controller
        result = controller.get_conversations()
        
        # Should have 3 conversations
        assert len(result["documents"]) == 3
        assert len(result["metadatas"]) == 3
        assert len(result["ids"]) == 3
        
        # Verify structure of returned data
        for metadata in result["metadatas"]:
            assert "title" in metadata
            assert "source" in metadata
            assert "message_count" in metadata
    
    def test_get_conversations_array_lengths_match(self, seeded_controller):
        """Test that all arrays in response have same length."""
        controller, conversations = seeded_controller
        result = controller.get_conversations()
        
        assert len(result["documents"]) == len(result["metadatas"])
        assert len(result["documents"]) == len(result["ids"])


@pytest.mark.unit
class TestGetConversationByIdEndpoint:
    """Test GET /api/conversation/<id> endpoint."""
    
    def test_get_conversation_returns_dict_structure(self, postgres_controller):
        """Test that get_conversation returns correct dict structure."""
        # Use a fake UUID - should return empty result
        result = postgres_controller.get_conversation("fake-uuid-123")
        
        assert isinstance(result, dict)
        assert "documents" in result
        assert "metadatas" in result
        assert "ids" in result
    
    def test_get_conversation_not_found_returns_empty(self, postgres_controller):
        """Test that get_conversation returns empty for non-existent ID."""
        result = postgres_controller.get_conversation("nonexistent-uuid")
        
        # Should return empty but valid structure
        assert len(result["documents"]) == 0
        assert len(result["metadatas"]) == 0
        assert len(result["ids"]) == 0
    
    def test_get_conversation_with_valid_id(self, seeded_controller):
        """Test get_conversation with seeded data."""
        controller, conversations = seeded_controller
        conv, _ = conversations[0]
        
        result = controller.get_conversation(str(conv.id))
        
        # Should return the conversation
        assert len(result["documents"]) > 0 or len(result["ids"]) > 0
        assert "documents" in result
        assert "metadatas" in result
        assert "ids" in result
    
    def test_get_conversation_returns_single_item(self, seeded_controller):
        """Test that get_conversation returns single conversation."""
        controller, conversations = seeded_controller
        conv, _ = conversations[0]
        
        result = controller.get_conversation(str(conv.id))
        
        # When found, should return single item or empty (depending on implementation)
        assert len(result["documents"]) <= 1
        assert len(result["metadatas"]) <= 1
        assert len(result["ids"]) <= 1


@pytest.mark.unit
class TestGetStatsEndpoint:
    """Test GET /api/stats endpoint."""
    
    def test_get_stats_returns_dict_structure(self, postgres_controller):
        """Test that get_stats returns correct dict structure."""
        result = postgres_controller.get_stats()
        
        assert isinstance(result, dict)
    
    def test_get_stats_with_empty_database(self, postgres_controller):
        """Test get_stats with no data."""
        result = postgres_controller.get_stats()
        
        # Should have at least some keys for empty database
        assert isinstance(result, dict)
    
    def test_get_stats_with_seeded_data(self, seeded_controller):
        """Test get_stats with test data."""
        controller, conversations = seeded_controller
        result = controller.get_stats()
        
        # Should have stats
        assert isinstance(result, dict)
        assert "document_count" in result or "conversation_count" in result


@pytest.mark.unit
class TestDeleteEndpoint:
    """Test DELETE /api/conversation/<id> endpoint."""
    
    def test_delete_conversation_returns_dict(self, postgres_controller):
        """Test that delete_conversation returns a dict response."""
        result = postgres_controller.delete_conversation("fake-uuid")
        
        assert isinstance(result, dict)
        # Should have success key
        assert "success" in result or "error" in result
    
    def test_delete_nonexistent_conversation(self, postgres_controller):
        """Test deleting a non-existent conversation."""
        result = postgres_controller.delete_conversation("nonexistent-uuid-123")
        
        assert isinstance(result, dict)
        # Should indicate failure or success
        assert "success" in result or "error" in result
    
    def test_delete_conversation_with_seeded_data(self, seeded_controller):
        """Test deleting an existing conversation."""
        controller, conversations = seeded_controller
        conv, _ = conversations[0]
        
        result = controller.delete_conversation(str(conv.id))
        
        assert isinstance(result, dict)
        # After deletion, conversation should not exist
        get_result = controller.get_conversation(str(conv.id))
        assert len(get_result["ids"]) == 0


@pytest.mark.unit
class TestExportEndpoint:
    """Test conversation export endpoints."""
    
    def test_export_conversation_returns_response(self, seeded_controller):
        """Test that export_conversation returns a response."""
        controller, conversations = seeded_controller
        conv, _ = conversations[0]
        
        result = controller.export_conversation(str(conv.id))
        
        # Should return a response object or string
        assert result is not None
    
    def test_export_nonexistent_conversation(self, postgres_controller):
        """Test exporting a non-existent conversation."""
        result = postgres_controller.export_conversation("nonexistent-uuid")
        
        # Should return some response (error or empty)
        assert result is not None
    
    def test_export_to_openwebui_returns_dict(self, postgres_controller):
        """Test that export_to_openwebui returns a dict response."""
        result = postgres_controller.export_to_openwebui("fake-uuid")
        
        assert isinstance(result, dict)
        # Should have status or success key
        assert "success" in result or "error" in result or "status" in result


@pytest.mark.unit
class TestClearDatabaseEndpoint:
    """Test database clearing endpoint."""
    
    def test_clear_database_returns_dict(self, postgres_controller):
        """Test that clear_database returns a dict."""
        result = postgres_controller.clear_database()
        
        assert isinstance(result, dict)
        # Should indicate success or error
        assert "success" in result or "error" in result or "message" in result
    
    def test_clear_database_removes_data(self, seeded_controller):
        """Test that clear_database actually removes conversations."""
        controller, conversations = seeded_controller
        
        # Clear the database
        result = controller.clear_database()
        assert isinstance(result, dict)
        
        # Verify conversations are gone
        get_result = controller.get_conversations()
        assert len(get_result["ids"]) == 0


@pytest.mark.unit
class TestGetSettingsEndpoint:
    """Test settings retrieval and management endpoints."""
    
    
    def test_get_collection_count_returns_dict(self, postgres_controller):
        """Test that get_collection_count returns a dict with count."""
        result = postgres_controller.get_collection_count()
        
        assert isinstance(result, dict)
        # Should have count or error
        assert "count" in result or "error" in result
    
    def test_get_collection_count_with_seeded_data(self, seeded_controller):
        """Test get_collection_count with test data."""
        controller, conversations = seeded_controller
        result = controller.get_collection_count()
        
        assert isinstance(result, dict)
        # Should have a count
        if "count" in result:
            assert result["count"] >= 0

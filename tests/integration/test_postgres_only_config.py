"""
Test PostgreSQL-Only Configuration

Validates that the application works correctly without the USE_POSTGRES
feature flag, ensuring we can safely remove ChromaDB legacy code.
"""

import os
import pytest


def test_app_starts_without_use_postgres_flag():
    """Verify app initializes with PostgreSQL by default."""
    # Save and remove USE_POSTGRES from environment
    old_env = os.environ.pop('USE_POSTGRES', None)
    
    try:
        # Import app factory (should work without flag)
        from app import create_app
        app = create_app()
        
        # Verify app created successfully
        assert app is not None
        assert app.config.get('SECRET_KEY') is not None
        
        # Verify database connection works
        from db.database import test_connection
        assert test_connection(), "PostgreSQL connection should work without USE_POSTGRES flag"
        
    finally:
        # Restore original environment
        if old_env:
            os.environ['USE_POSTGRES'] = old_env


def test_api_format_adapter_uses_postgres(uow):
    """Verify API format adapter uses PostgreSQL backend."""
    from db.adapters.api_format_adapter import get_api_format_adapter
    
    # Get adapter instance
    adapter = get_api_format_adapter()
    
    # Should return stats from PostgreSQL
    stats = adapter.get_stats()
    
    # Verify PostgreSQL-specific response
    assert stats is not None, "Adapter should return stats"
    assert 'status' in stats, "Stats should include status"
    assert stats['status'] in ['healthy', 'ready'], f"Unexpected status: {stats.get('status')}"
    
    # Should have document count (even if 0)
    assert 'document_count' in stats or 'total_conversations' in stats, \
        "Stats should include document/conversation count"


def test_routes_use_postgres_controller(client, seed_conversations):
    """Verify API routes use PostgreSQL controller."""
    # Seed test data
    seed_conversations(count=3)
    
    # Test stats endpoint
    response = client.get('/api/stats')
    
    assert response.status_code == 200, f"Stats endpoint failed: {response.status_code}"
    data = response.json
    
    # Verify PostgreSQL backend is being used (legacy adapter format)
    # This format comes from legacy_api_adapter.get_stats()
    assert 'status' in data, "Stats should include status"
    assert 'document_count' in data, "Stats should include document_count"
    assert data['document_count'] >= 3, "Should show seeded conversations"


def test_conversation_retrieval_uses_postgres(client, seed_conversations):
    """Verify conversation retrieval uses PostgreSQL."""
    # Seed test conversations
    convos = seed_conversations(count=2, messages_per_conversation=3)
    
    # Get conversations via API
    response = client.get('/api/conversations')
    
    assert response.status_code == 200, f"Conversations endpoint failed: {response.status_code}"
    data = response.json
    
    # Verify response structure (PostgreSQL format)
    assert 'documents' in data or 'conversations' in data, \
        "Response should contain documents or conversations"
    
    # Verify we got our seeded data
    if 'documents' in data:
        assert len(data['documents']) >= 2, "Should retrieve seeded conversations"
    elif 'conversations' in data:
        assert len(data['conversations']) >= 2, "Should retrieve seeded conversations"


def test_search_functionality_uses_postgres(uow, seed_conversations):
    """Verify search functionality uses PostgreSQL backend."""
    from db.services.search_service import SearchService
    
    # Seed conversations with searchable content
    seed_conversations(count=1, messages_per_conversation=2)
    
    # Create search service (without passing uow)
    search_service = SearchService()
    
    # Verify search stats show PostgreSQL data
    stats = search_service.get_search_stats()
    
    assert stats is not None, "Search service should return stats"
    assert stats.get('total_messages', 0) >= 2, "Should show seeded messages"
    
    # Verify FTS search works (PostgreSQL-specific)
    fts_results = search_service.search_fts_only("test", limit=5)
    
    # FTS should work (may return 0 results, but shouldn't error)
    assert isinstance(fts_results, list), "FTS search should return a list"


def test_database_operations_without_flag(uow):
    """Verify core database operations work without feature flag."""
    # Create a conversation
    conversation = uow.conversations.create(
        title="Test Conversation Without Flag"
    )
    uow.session.flush()
    
    assert conversation.id is not None, "Should create conversation with ID"
    
    # Create a message
    message = uow.messages.create(
        conversation_id=conversation.id,
        role="user",
        content="Test message content",
        message_metadata={"test": True}
    )
    uow.session.flush()
    
    assert message.id is not None, "Should create message with ID"
    
    # Retrieve conversation with messages
    retrieved = uow.conversations.get_with_messages(conversation.id)
    
    assert retrieved is not None, "Should retrieve conversation"
    assert len(retrieved.messages) >= 1, "Should include messages"
    assert retrieved.messages[0].content == "Test message content"


@pytest.mark.integration
def test_no_chromadb_dependencies_in_runtime():
    """Verify no ChromaDB code is imported during normal operation."""
    import sys
    
    # Get all loaded modules
    loaded_modules = list(sys.modules.keys())
    
    # Check for ChromaDB imports
    chromadb_modules = [m for m in loaded_modules if 'chroma' in m.lower()]
    
    # Should not have any ChromaDB modules loaded
    # (The app should work entirely without ChromaDB)
    assert len(chromadb_modules) == 0, \
        f"ChromaDB modules should not be loaded: {chromadb_modules}"

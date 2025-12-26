"""
Integration tests for conversation saving (bookmark) API endpoints.

TDD: These tests are written first to define the expected API behavior.

Note: These tests use the TEST database (port 5433) via client_postgres_test.
The integration/conftest.py clears data before/after each test.
"""

import pytest
import json
from uuid import uuid4
from sqlalchemy.orm import Session

from db.models.models import Conversation, Message


@pytest.fixture
def create_test_conversation(test_db_engine):
    """Create a test conversation in the TEST database."""
    created_ids = []

    def _create(title="Test Conversation"):
        with Session(test_db_engine) as session:
            conv = Conversation(title=title)
            session.add(conv)
            session.flush()

            # Create at least one message for the conversation
            msg = Message(
                conversation_id=conv.id,
                role='user',
                content='Test message content'
            )
            session.add(msg)
            session.commit()

            created_ids.append(conv.id)
            return conv.id

    yield _create

    # Cleanup: delete created conversations
    with Session(test_db_engine) as session:
        for conv_id in created_ids:
            session.execute(
                Message.__table__.delete().where(Message.conversation_id == conv_id)
            )
            session.execute(
                Conversation.__table__.delete().where(Conversation.id == conv_id)
            )
        session.commit()


class TestToggleSaveConversationAPI:
    """Test POST /api/conversation/<id>/save endpoint."""

    def test_toggle_save_endpoint_exists(self, client_postgres_test, create_test_conversation):
        """The toggle save endpoint should exist."""
        conv_id = str(create_test_conversation())

        response = client_postgres_test.post(f'/api/conversation/{conv_id}/save')

        assert response.status_code != 404, "Endpoint should exist"

    def test_toggle_save_conversation_success(self, client_postgres_test, create_test_conversation):
        """Toggle save should return 200 and new saved state."""
        conv_id = str(create_test_conversation())

        response = client_postgres_test.post(f'/api/conversation/{conv_id}/save')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'is_saved' in data
        assert data['is_saved'] is True

    def test_toggle_save_twice_returns_false(self, client_postgres_test, create_test_conversation):
        """Toggling twice should return is_saved=False."""
        conv_id = str(create_test_conversation())

        # First toggle: False -> True
        response1 = client_postgres_test.post(f'/api/conversation/{conv_id}/save')
        assert response1.status_code == 200
        data1 = json.loads(response1.data)
        assert data1['is_saved'] is True

        # Second toggle: True -> False
        response2 = client_postgres_test.post(f'/api/conversation/{conv_id}/save')
        assert response2.status_code == 200
        data2 = json.loads(response2.data)
        assert data2['is_saved'] is False

    def test_toggle_save_nonexistent_conversation(self, client_postgres_test):
        """Toggling a non-existent conversation should return 404."""
        fake_id = str(uuid4())

        response = client_postgres_test.post(f'/api/conversation/{fake_id}/save')

        assert response.status_code == 404

    def test_toggle_save_includes_conversation_id(self, client_postgres_test, create_test_conversation):
        """Response should include the conversation ID."""
        conv_id = str(create_test_conversation())

        response = client_postgres_test.post(f'/api/conversation/{conv_id}/save')

        data = json.loads(response.data)
        assert 'id' in data or 'conversation_id' in data


class TestGetSavedConversationsAPI:
    """Test GET /api/conversations/saved endpoint."""

    def test_saved_endpoint_exists(self, client_postgres_test):
        """The saved conversations endpoint should exist."""
        response = client_postgres_test.get('/api/conversations/saved')

        assert response.status_code != 404, "Endpoint should exist"

    def test_get_saved_returns_empty_list_when_none_saved(self, client_postgres_test, create_test_conversation):
        """Should return empty list when no conversations are saved."""
        # Create some unsaved conversations
        create_test_conversation("Unsaved 1")
        create_test_conversation("Unsaved 2")

        response = client_postgres_test.get('/api/conversations/saved')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'metadatas' in data
        assert len(data['metadatas']) == 0

    def test_get_saved_returns_only_saved(self, client_postgres_test, create_test_conversation):
        """Should return only saved conversations."""
        conv_id1 = str(create_test_conversation("Conv 1"))
        conv_id2 = str(create_test_conversation("Conv 2"))
        create_test_conversation("Conv 3 Unsaved")

        # Save the first two
        client_postgres_test.post(f'/api/conversation/{conv_id1}/save')
        client_postgres_test.post(f'/api/conversation/{conv_id2}/save')

        response = client_postgres_test.get('/api/conversations/saved')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['metadatas']) == 2

    def test_get_saved_has_consistent_structure(self, client_postgres_test, create_test_conversation):
        """Saved endpoint should return same structure as regular conversations."""
        conv_id = str(create_test_conversation())
        client_postgres_test.post(f'/api/conversation/{conv_id}/save')

        response = client_postgres_test.get('/api/conversations/saved')

        data = json.loads(response.data)
        assert 'documents' in data
        assert 'metadatas' in data
        assert 'ids' in data
        assert len(data['documents']) == len(data['metadatas'])
        assert len(data['ids']) == len(data['metadatas'])


class TestIsSavedInConversationResponses:
    """Test that is_saved is included in existing conversation API responses."""

    def test_conversations_list_includes_is_saved(self, client_postgres_test, create_test_conversation):
        """GET /api/conversations should include is_saved in metadata."""
        conv_id1 = str(create_test_conversation("Conv 1"))
        create_test_conversation("Conv 2")
        # Save one conversation
        client_postgres_test.post(f'/api/conversation/{conv_id1}/save')

        response = client_postgres_test.get('/api/conversations')

        assert response.status_code == 200
        data = json.loads(response.data)

        # All metadatas should have is_saved field
        for meta in data['metadatas']:
            assert 'is_saved' in meta

    def test_conversation_detail_includes_is_saved(self, client_postgres_test, create_test_conversation):
        """GET /api/conversation/<id> should include is_saved."""
        conv_id = str(create_test_conversation())

        # First check unsaved
        response1 = client_postgres_test.get(f'/api/conversation/{conv_id}')
        data1 = json.loads(response1.data)
        assert 'is_saved' in data1
        assert data1['is_saved'] is False

        # Save it
        client_postgres_test.post(f'/api/conversation/{conv_id}/save')

        # Check saved
        response2 = client_postgres_test.get(f'/api/conversation/{conv_id}')
        data2 = json.loads(response2.data)
        assert data2['is_saved'] is True

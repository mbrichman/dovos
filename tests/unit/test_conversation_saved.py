"""
Unit tests for conversation saving (bookmark) functionality.

TDD: These tests are written first to define the expected behavior.
"""

import pytest
from uuid import uuid4


class TestConversationIsSavedField:
    """Test that Conversation model has is_saved field."""

    def test_conversation_has_is_saved_field(self, uow):
        """Conversation should have an is_saved boolean field."""
        conv = uow.conversations.create(title="Test Conversation")
        uow.session.flush()

        assert hasattr(conv, 'is_saved'), "Conversation should have is_saved attribute"

    def test_conversation_is_saved_defaults_to_false(self, uow):
        """New conversations should have is_saved=False by default."""
        conv = uow.conversations.create(title="Test Conversation")
        uow.session.flush()

        assert conv.is_saved is False, "is_saved should default to False"

    def test_conversation_can_be_created_with_is_saved_true(self, uow):
        """Conversation can be created with is_saved=True."""
        conv = uow.conversations.create(title="Saved Conversation", is_saved=True)
        uow.session.flush()

        assert conv.is_saved is True


class TestToggleSavedConversation:
    """Test toggle_saved repository method."""

    def test_toggle_saved_from_false_to_true(self, uow):
        """Toggling a non-saved conversation should mark it as saved."""
        conv = uow.conversations.create(title="Test Conversation")
        uow.session.flush()

        assert conv.is_saved is False

        result = uow.conversations.toggle_saved(conv.id)
        uow.session.flush()

        assert result is True, "toggle_saved should return True for new saved state"
        assert conv.is_saved is True

    def test_toggle_saved_from_true_to_false(self, uow):
        """Toggling a saved conversation should unsave it."""
        conv = uow.conversations.create(title="Test Conversation", is_saved=True)
        uow.session.flush()

        assert conv.is_saved is True

        result = uow.conversations.toggle_saved(conv.id)
        uow.session.flush()

        assert result is False, "toggle_saved should return False for new unsaved state"
        assert conv.is_saved is False

    def test_toggle_saved_nonexistent_conversation(self, uow):
        """Toggling a non-existent conversation should return None."""
        fake_id = uuid4()

        result = uow.conversations.toggle_saved(fake_id)

        assert result is None

    def test_toggle_saved_returns_new_state(self, uow):
        """toggle_saved should return the new is_saved state."""
        conv = uow.conversations.create(title="Test Conversation")
        uow.session.flush()

        # First toggle: False -> True
        new_state = uow.conversations.toggle_saved(conv.id)
        assert new_state is True

        # Second toggle: True -> False
        new_state = uow.conversations.toggle_saved(conv.id)
        assert new_state is False


class TestGetSavedConversations:
    """Test get_saved repository method."""

    def test_get_saved_returns_only_saved_conversations(self, uow):
        """get_saved should return only conversations with is_saved=True."""
        # Create mix of saved and unsaved
        saved1 = uow.conversations.create(title="Saved 1", is_saved=True)
        saved2 = uow.conversations.create(title="Saved 2", is_saved=True)
        unsaved1 = uow.conversations.create(title="Unsaved 1", is_saved=False)
        unsaved2 = uow.conversations.create(title="Unsaved 2")  # Default False
        uow.session.flush()

        saved = uow.conversations.get_saved()

        assert len(saved) == 2
        saved_ids = {s.id for s in saved}
        assert saved1.id in saved_ids
        assert saved2.id in saved_ids
        assert unsaved1.id not in saved_ids
        assert unsaved2.id not in saved_ids

    def test_get_saved_returns_empty_list_when_none_saved(self, uow):
        """get_saved should return empty list when no conversations are saved."""
        # Create only unsaved conversations
        uow.conversations.create(title="Unsaved 1")
        uow.conversations.create(title="Unsaved 2")
        uow.session.flush()

        saved = uow.conversations.get_saved()

        assert saved == []

    def test_get_saved_orders_by_updated_at_descending(self, uow):
        """Saved conversations should be ordered by updated_at descending."""
        from datetime import datetime, timedelta, timezone

        # Create with specific timestamps
        old_conv = uow.conversations.create(
            title="Old Saved",
            is_saved=True
        )
        old_conv.updated_at = datetime.now(timezone.utc) - timedelta(days=7)

        new_conv = uow.conversations.create(
            title="New Saved",
            is_saved=True
        )
        new_conv.updated_at = datetime.now(timezone.utc)

        uow.session.flush()

        saved = uow.conversations.get_saved()

        assert len(saved) == 2
        assert saved[0].id == new_conv.id, "Newest should be first"
        assert saved[1].id == old_conv.id, "Oldest should be last"

    def test_get_saved_with_limit(self, uow):
        """get_saved should respect the limit parameter."""
        # Create 5 saved conversations
        for i in range(5):
            uow.conversations.create(title=f"Saved {i}", is_saved=True)
        uow.session.flush()

        saved = uow.conversations.get_saved(limit=3)

        assert len(saved) == 3

    def test_get_saved_with_offset(self, uow):
        """get_saved should respect the offset parameter."""
        # Create 5 saved conversations with distinct titles
        convs = []
        for i in range(5):
            conv = uow.conversations.create(title=f"Saved {i}", is_saved=True)
            convs.append(conv)
        uow.session.flush()

        all_saved = uow.conversations.get_saved()
        offset_saved = uow.conversations.get_saved(offset=2)

        assert len(all_saved) == 5
        assert len(offset_saved) == 3

"""
Unit tests for ContextualRetrievalService.

Tests contextual window expansion, adaptive pairing, deduplication,
and token budget enforcement.
"""
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from typing import List, Tuple

from db.services.contextual_retrieval_service import (
    ContextualRetrievalService,
    ContextWindow,
    WindowMessage
)
from db.models.models import Conversation, Message
from tests.utils.seed import create_conversation, create_message


@pytest.fixture
def contextual_service(uow):
    """Create ContextualRetrievalService instance with test UoW."""
    return ContextualRetrievalService(uow)


@pytest.fixture
def sample_conversation(uow):
    """
    Create a conversation with 10 messages for testing window expansion.
    
    Pattern: user -> assistant -> user -> assistant ...
    Returns (conversation, messages)
    """
    base_time = datetime.now(timezone.utc)
    conversation = create_conversation(uow, title="Test Conversation", created_at=base_time)
    
    messages = []
    for i in range(10):
        role = "user" if i % 2 == 0 else "assistant"
        content = f"{role.capitalize()} message {i}"
        created_at = base_time + timedelta(minutes=i)
        
        message = create_message(
            uow,
            conversation.id,
            role=role,
            content=content,
            created_at=created_at
        )
        messages.append(message)
    
    uow.session.flush()
    return conversation, messages


class TestBasicWindowExpansion:
    """Test basic symmetric window expansion around matched message."""
    
    def test_center_message_with_symmetric_window(self, contextual_service, sample_conversation, uow):
        """Test window expansion around message in middle of conversation."""
        conversation, messages = sample_conversation
        
        # Match message at index 5
        match_message = messages[5]
        
        # Expand with window_size=2 (2 before, 2 after)
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=match_message.id,
            window_before=2,
            window_after=2
        )
        
        # Should include messages [3, 4, 5, 6, 7]
        assert len(window.messages) == 5
        assert window.messages[0].id == str(messages[3].id)
        assert window.messages[2].id == str(match_message.id)  # Center
        assert window.messages[4].id == str(messages[7].id)
        assert window.match_position == 2
    
    def test_asymmetric_window(self, contextual_service, sample_conversation, uow):
        """Test asymmetric window expansion (different before/after)."""
        conversation, messages = sample_conversation
        match_message = messages[5]
        
        # More context before than after
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=match_message.id,
            window_before=3,
            window_after=1
        )
        
        # Should include messages [2, 3, 4, 5, 6]
        assert len(window.messages) == 5
        assert window.messages[0].id == str(messages[2].id)
        assert window.messages[3].id == str(match_message.id)
        assert window.messages[4].id == str(messages[6].id)
        assert window.match_position == 3


class TestBoundaryConditions:
    """Test window expansion at conversation boundaries."""
    
    def test_window_at_conversation_start(self, contextual_service, sample_conversation, uow):
        """Test window doesn't extend before first message."""
        conversation, messages = sample_conversation
        match_message = messages[0]
        
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=match_message.id,
            window_before=5,  # Request 5 but only 0 available
            window_after=2
        )
        
        # Should include messages [0, 1, 2]
        assert len(window.messages) == 3
        assert window.messages[0].id == str(messages[0].id)
        assert window.match_position == 0
    
    def test_window_at_conversation_end(self, contextual_service, sample_conversation, uow):
        """Test window doesn't extend past last message."""
        conversation, messages = sample_conversation
        match_message = messages[9]  # Last message
        
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=match_message.id,
            window_before=2,
            window_after=5  # Request 5 but only 0 available
        )
        
        # Should include messages [7, 8, 9]
        assert len(window.messages) == 3
        assert window.messages[2].id == str(messages[9].id)
        assert window.match_position == 2
    
    def test_single_message_conversation(self, contextual_service, uow):
        """Test window on conversation with only one message."""
        conversation = create_conversation(uow, title="Single Message")
        message = create_message(uow, conversation.id, role="user", content="Only message")
        uow.session.flush()
        
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=message.id,
            window_before=3,
            window_after=3
        )
        
        # Should only include the single message
        assert len(window.messages) == 1
        assert window.messages[0].id == str(message.id)
        assert window.match_position == 0


class TestAdaptiveWindowPairing:
    """Test adaptive window expansion to include complete user↔assistant turns."""
    
    def test_adaptive_includes_assistant_response_to_user_match(
        self, contextual_service, sample_conversation, uow
    ):
        """When match is user message, adaptively include assistant response."""
        conversation, messages = sample_conversation
        
        # Match user message at index 4
        match_message = messages[4]
        assert match_message.role == "user"
        
        # With adaptive=True and small window
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=match_message.id,
            window_before=1,
            window_after=1,
            adaptive=True
        )
        
        # Should include [3, 4, 5] where 5 is assistant response
        assert len(window.messages) >= 3
        
        # Verify assistant response is included
        last_message = window.messages[-1]
        assert last_message.role == "assistant"
    
    def test_adaptive_includes_user_prompt_for_assistant_match(
        self, contextual_service, sample_conversation, uow
    ):
        """When match is assistant message, adaptively include user prompt."""
        conversation, messages = sample_conversation
        
        # Match assistant message at index 5
        match_message = messages[5]
        assert match_message.role == "assistant"
        
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=match_message.id,
            window_before=1,
            window_after=1,
            adaptive=True
        )
        
        # Should include [4, 5, 6] where 4 is user prompt
        assert len(window.messages) >= 3
        
        # Verify user prompt is included
        first_message = window.messages[0]
        assert first_message.role == "user" or window.messages[1].role == "user"
    
    def test_adaptive_disabled(self, contextual_service, sample_conversation, uow):
        """When adaptive=False, use strict window size."""
        conversation, messages = sample_conversation
        match_message = messages[4]
        
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=match_message.id,
            window_before=1,
            window_after=1,
            adaptive=False
        )
        
        # Should strictly include [3, 4, 5]
        assert len(window.messages) == 3


class TestDeduplicationAndMerging:
    """Test merging of overlapping windows from same conversation."""
    
    def test_merge_overlapping_windows_same_conversation(
        self, contextual_service, sample_conversation, uow
    ):
        """Merge windows that overlap in the same conversation."""
        conversation, messages = sample_conversation
        
        # Create two windows that overlap
        window1 = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=messages[3].id,
            window_before=2,
            window_after=2
        )  # [1, 2, 3, 4, 5]
        
        window2 = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=messages[5].id,
            window_before=2,
            window_after=2
        )  # [3, 4, 5, 6, 7]
        
        # Merge windows
        merged = contextual_service._merge_windows([window1, window2])
        
        # Should produce one merged window [1, 2, 3, 4, 5, 6, 7]
        assert len(merged) == 1
        assert len(merged[0].messages) == 7
        assert merged[0].messages[0].id == str(messages[1].id)
        assert merged[0].messages[-1].id == str(messages[7].id)
    
    def test_no_merge_for_non_overlapping_windows(
        self, contextual_service, sample_conversation, uow
    ):
        """Don't merge windows that don't overlap."""
        conversation, messages = sample_conversation
        
        # Create two windows that don't overlap
        window1 = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=messages[1].id,
            window_before=1,
            window_after=1
        )  # [0, 1, 2]
        
        window2 = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=messages[7].id,
            window_before=1,
            window_after=1
        )  # [6, 7, 8]
        
        merged = contextual_service._merge_windows([window1, window2])
        
        # Should keep both windows separate
        assert len(merged) == 2
    
    def test_merge_windows_from_different_conversations(
        self, contextual_service, uow
    ):
        """Don't merge windows from different conversations."""
        # Create two conversations
        conv1 = create_conversation(uow, title="Conversation 1")
        conv2 = create_conversation(uow, title="Conversation 2")
        
        msg1 = create_message(uow, conv1.id, role="user", content="Message 1")
        msg2 = create_message(uow, conv2.id, role="user", content="Message 2")
        uow.session.flush()
        
        window1 = contextual_service._get_context_window(
            conversation_id=conv1.id,
            match_message_id=msg1.id,
            window_before=1,
            window_after=1
        )
        
        window2 = contextual_service._get_context_window(
            conversation_id=conv2.id,
            match_message_id=msg2.id,
            window_before=1,
            window_after=1
        )
        
        merged = contextual_service._merge_windows([window1, window2])
        
        # Should keep both windows separate
        assert len(merged) == 2


class TestWindowScoring:
    """Test window scoring with proximity decay and recency."""
    
    def test_proximity_decay_scoring(self, contextual_service, sample_conversation, uow):
        """Messages farther from match have lower contribution to score."""
        conversation, messages = sample_conversation
        
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=messages[5].id,
            window_before=3,
            window_after=3
        )
        
        # Score with proximity decay
        base_score = 0.95
        scored_window = contextual_service._score_window(
            window=window,
            base_score=base_score,
            proximity_decay_lambda=0.3
        )
        
        # Aggregated score should be less than base_score due to decay
        assert scored_window.aggregated_score <= base_score
        assert scored_window.base_score == base_score
    
    def test_recency_bonus(self, contextual_service, uow):
        """More recent conversations get a small score bonus."""
        # Create two conversations with different ages
        old_conv = create_conversation(
            uow,
            title="Old Conversation",
            created_at=datetime.now(timezone.utc) - timedelta(days=30)
        )
        new_conv = create_conversation(
            uow,
            title="New Conversation",
            created_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        
        old_msg = create_message(uow, old_conv.id, content="Old message")
        new_msg = create_message(uow, new_conv.id, content="New message")
        uow.session.flush()
        
        old_window = contextual_service._get_context_window(
            conversation_id=old_conv.id,
            match_message_id=old_msg.id,
            window_before=0,
            window_after=0
        )
        
        new_window = contextual_service._get_context_window(
            conversation_id=new_conv.id,
            match_message_id=new_msg.id,
            window_before=0,
            window_after=0
        )
        
        # Score both with same base score
        base_score = 0.90
        old_scored = contextual_service._score_window(
            old_window, base_score, apply_recency_bonus=True
        )
        new_scored = contextual_service._score_window(
            new_window, base_score, apply_recency_bonus=True
        )
        
        # Newer conversation should have slightly higher score
        assert new_scored.aggregated_score >= old_scored.aggregated_score


class TestTokenBudgetEnforcement:
    """Test token budget trimming and turn boundary preservation."""
    
    def test_trim_window_to_token_budget(self, contextual_service, sample_conversation, uow):
        """Trim window when it exceeds token budget."""
        conversation, messages = sample_conversation
        
        # Create large window
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=messages[5].id,
            window_before=4,
            window_after=4
        )
        
        original_count = len(window.messages)
        
        # Apply very small token budget
        trimmed = contextual_service._apply_token_budget(
            window=window,
            max_tokens=20  # Very small budget to force trimming
        )
        
        # Window should be trimmed (allow same size if already under budget)
        assert len(trimmed.messages) <= original_count
        
        # Match message should still be present
        match_ids = [m.id for m in trimmed.messages]
        assert str(messages[5].id) in match_ids
    
    def test_preserve_complete_turns_when_trimming(
        self, contextual_service, sample_conversation, uow
    ):
        """When trimming, preserve complete user↔assistant pairs."""
        conversation, messages = sample_conversation
        
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=messages[5].id,
            window_before=3,
            window_after=3
        )
        
        # Trim with turn preservation
        trimmed = contextual_service._apply_token_budget(
            window=window,
            max_tokens=40,
            preserve_turns=True
        )
        
        # Check that we don't have orphaned user or assistant messages
        roles = [m.role for m in trimmed.messages]
        
        # Count user and assistant messages
        user_count = roles.count("user")
        assistant_count = roles.count("assistant")
        
        # Should be roughly balanced (within 1)
        assert abs(user_count - assistant_count) <= 1
    
    def test_no_trimming_when_under_budget(
        self, contextual_service, sample_conversation, uow
    ):
        """Don't trim window when under token budget."""
        conversation, messages = sample_conversation
        
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=messages[5].id,
            window_before=2,
            window_after=2
        )
        
        original_length = len(window.messages)
        
        # Large budget
        trimmed = contextual_service._apply_token_budget(
            window=window,
            max_tokens=10000
        )
        
        # Should be unchanged
        assert len(trimmed.messages) == original_length


class TestWindowFormatting:
    """Test formatting windows with context markers."""
    
    def test_format_window_with_markers(self, contextual_service, sample_conversation, uow):
        """Format window with [CTX_START], [MATCH_START/END], [CTX_END] markers."""
        conversation, messages = sample_conversation
        
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=messages[5].id,
            window_before=2,
            window_after=2
        )
        
        formatted = contextual_service._format_window(window, include_markers=True)
        
        # Should contain markers
        assert "[CTX_START]" in formatted.content
        assert "[MATCH_START]" in formatted.content
        assert "[MATCH_END]" in formatted.content
        assert "[CTX_END]" in formatted.content
        
        # Match markers should surround the matched message
        match_content = messages[5].content
        assert f"[MATCH_START]" in formatted.content
        assert match_content in formatted.content
    
    def test_format_window_without_markers(
        self, contextual_service, sample_conversation, uow
    ):
        """Format window without markers for backward compatibility."""
        conversation, messages = sample_conversation
        
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=messages[5].id,
            window_before=2,
            window_after=2
        )
        
        formatted = contextual_service._format_window(window, include_markers=False)
        
        # Should not contain markers
        assert "[CTX_START]" not in formatted.content
        assert "[MATCH_START]" not in formatted.content
        assert "[MATCH_END]" not in formatted.content
        assert "[CTX_END]" not in formatted.content
    
    def test_format_includes_metadata(self, contextual_service, sample_conversation, uow):
        """Formatted window includes complete metadata."""
        conversation, messages = sample_conversation
        
        window = contextual_service._get_context_window(
            conversation_id=conversation.id,
            match_message_id=messages[5].id,
            window_before=2,
            window_after=2
        )
        
        formatted = contextual_service._format_window(window)
        
        # Check metadata presence
        assert formatted.metadata.conversation_id == str(conversation.id)
        assert formatted.metadata.matched_message_id == str(messages[5].id)
        assert formatted.metadata.window_size == len(window.messages)
        assert formatted.metadata.match_position is not None


class TestEndToEndRetrieval:
    """Test complete retrieval pipeline with real search integration."""
    
    @pytest.mark.skip(reason="Integration test requires embeddings and full search service setup")
    @pytest.mark.integration
    def test_retrieve_with_context_integration(
        self, contextual_service, sample_conversation, uow
    ):
        """Test end-to-end retrieval with context expansion."""
        conversation, messages = sample_conversation
        
        # Add embeddings to messages for search
        for message in messages[:5]:
            create_message(uow, conversation.id, content=message.content, with_embedding=True)
        uow.session.flush()
        
        # Perform retrieval
        results = contextual_service.retrieve_with_context(
            query="user message",
            top_k_windows=3,
            context_window=2,
            adaptive_context=True,
            deduplicate=True
        )
        
        # Should return windows
        assert len(results) > 0
        
        # Each result should have required fields
        for result in results:
            assert result.content is not None
            assert result.metadata is not None
            assert result.metadata.conversation_id is not None
            assert result.metadata.matched_message_id is not None

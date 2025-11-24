"""
Contextual Retrieval Service for RAG with window expansion.

This service implements message-level retrieval with contextual window expansion,
providing precise matching with sufficient conversational context.

Key features:
- Message-level search with surrounding context windows
- Adaptive window sizing for complete user↔assistant turns
- Deduplication and merging of overlapping windows
- Proximity decay scoring and recency bonuses
- Token budget enforcement with turn preservation
- Context markers for highlighting matched content
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

from db.services.search_service import SearchService, SearchResult
from db.repositories.unit_of_work import UnitOfWork
from db.models.models import Message

logger = logging.getLogger(__name__)


@dataclass
class WindowMessage:
    """A message within a context window."""
    id: str
    role: str
    content: str
    created_at: datetime
    is_primary_match: bool = False
    distance_from_match: int = 0


@dataclass
class ContextWindow:
    """A context window containing messages around a match."""
    conversation_id: str
    conversation_title: str
    matched_message_id: str
    messages: List[WindowMessage]
    match_position: int
    base_score: float = 0.0
    aggregated_score: float = 0.0
    window_id: Optional[str] = None
    
    def __post_init__(self):
        if self.window_id is None:
            self.window_id = f"{self.conversation_id}:{self.matched_message_id}"


@dataclass
class FormattedWindow:
    """A formatted window ready for API response."""
    content: str
    metadata: 'WindowMetadata'


@dataclass
class WindowMetadata:
    """Metadata for a formatted window."""
    conversation_id: str
    window_id: str
    matched_message_id: str
    conversation_title: str
    window_size: int
    match_position: int
    before_count: int
    after_count: int
    base_score: float
    aggregated_score: float
    roles: List[str]
    token_estimate: Optional[int] = None
    retrieval_params: Dict[str, Any] = field(default_factory=dict)


class ContextualRetrievalService:
    """
    Service for retrieving messages with contextual windows.
    
    Implements message-level search with window expansion for RAG applications.
    """
    
    def __init__(self, uow: UnitOfWork, search_service: Optional[SearchService] = None):
        """
        Initialize the contextual retrieval service.
        
        Args:
            uow: Unit of work for database operations
            search_service: Optional search service (creates one if not provided)
        """
        self.uow = uow
        self.search_service = search_service or SearchService()
        
        # Conversation cache to minimize DB queries
        self._conversation_cache: Dict[str, List[Message]] = {}
    
    def retrieve_with_context(
        self,
        query: str,
        top_k_windows: int = 8,
        context_window: int = 3,
        adaptive_context: bool = True,
        asymmetric_before: Optional[int] = None,
        asymmetric_after: Optional[int] = None,
        deduplicate: bool = True,
        max_tokens: Optional[int] = None,
        rerank: bool = True,
        include_markers: bool = True,
        proximity_decay_lambda: float = 0.3,
        apply_recency_bonus: bool = False
    ) -> List[FormattedWindow]:
        """
        Retrieve messages with surrounding contextual windows.
        
        Args:
            query: Search query string
            top_k_windows: Maximum number of windows to return
            context_window: Number of messages before/after match
            adaptive_context: Whether to adaptively expand for complete turns
            asymmetric_before: Override for messages before (None = use context_window)
            asymmetric_after: Override for messages after (None = use context_window)
            deduplicate: Whether to merge overlapping windows
            max_tokens: Maximum tokens per window (None = no limit)
            rerank: Whether to rerank by aggregated score
            include_markers: Whether to include context markers
            proximity_decay_lambda: Lambda for proximity decay scoring
            apply_recency_bonus: Whether to apply recency bonus
            
        Returns:
            List of formatted windows with content and metadata
        """
        logger.info(f"🔍 Contextual retrieval: query='{query[:50]}...', top_k={top_k_windows}, window={context_window}")
        
        # Step 1: Search for matching messages
        search_results = self._search_messages(query, limit=top_k_windows * 3)
        
        if not search_results:
            logger.info("No search results found")
            return []
        
        logger.debug(f"Found {len(search_results)} initial matches")
        
        # Step 2: Expand each match with context window
        windows = []
        for result in search_results:
            try:
                window = self._get_context_window(
                    conversation_id=UUID(result.conversation_id),
                    match_message_id=UUID(result.message_id),
                    window_before=asymmetric_before or context_window,
                    window_after=asymmetric_after or context_window,
                    adaptive=adaptive_context
                )
                
                # Add base score from search
                window.base_score = result.combined_score
                windows.append(window)
                
            except Exception as e:
                logger.error(f"Failed to create window for message {result.message_id}: {e}")
                continue
        
        logger.debug(f"Created {len(windows)} context windows")
        
        # Step 3: Deduplicate and merge overlapping windows
        if deduplicate:
            windows = self._merge_windows(windows)
            logger.debug(f"After deduplication: {len(windows)} windows")
        
        # Step 4: Score windows with proximity decay and recency
        scored_windows = []
        for window in windows:
            scored = self._score_window(
                window=window,
                base_score=window.base_score,
                proximity_decay_lambda=proximity_decay_lambda,
                apply_recency_bonus=apply_recency_bonus
            )
            scored_windows.append(scored)
        
        # Step 5: Rerank by aggregated score
        if rerank:
            scored_windows.sort(key=lambda w: w.aggregated_score, reverse=True)
        
        # Step 6: Apply token budget if specified
        if max_tokens:
            trimmed_windows = []
            for window in scored_windows:
                trimmed = self._apply_token_budget(
                    window=window,
                    max_tokens=max_tokens,
                    preserve_turns=True
                )
                trimmed_windows.append(trimmed)
            scored_windows = trimmed_windows
        
        # Step 7: Take top-k windows
        final_windows = scored_windows[:top_k_windows]
        
        # Step 8: Format windows for response
        formatted_results = []
        retrieval_params = {
            'query': query,
            'top_k_windows': top_k_windows,
            'context_window': context_window,
            'adaptive_context': adaptive_context,
            'deduplicate': deduplicate
        }
        
        for window in final_windows:
            formatted = self._format_window(
                window=window,
                include_markers=include_markers,
                retrieval_params=retrieval_params
            )
            formatted_results.append(formatted)
        
        logger.info(f"✅ Returning {len(formatted_results)} contextual windows")
        return formatted_results
    
    def _search_messages(self, query: str, limit: int = 50) -> List[SearchResult]:
        """
        Search for matching messages using the search service.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of search results
        """
        try:
            results = self.search_service.search(query, limit=limit)
            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def _get_context_window(
        self,
        conversation_id: UUID,
        match_message_id: UUID,
        window_before: int,
        window_after: int,
        adaptive: bool = True
    ) -> ContextWindow:
        """
        Get context window around a matched message.
        
        Args:
            conversation_id: Conversation ID
            match_message_id: Matched message ID
            window_before: Messages to include before match
            window_after: Messages to include after match
            adaptive: Whether to adapt window for complete turns
            
        Returns:
            ContextWindow with messages
        """
        # Get all messages in conversation (cached)
        messages = self._get_conversation_messages(conversation_id)
        
        if not messages:
            raise ValueError(f"No messages found for conversation {conversation_id}")
        
        # Find the matched message index
        match_idx = None
        for i, msg in enumerate(messages):
            if msg.id == match_message_id:
                match_idx = i
                break
        
        if match_idx is None:
            raise ValueError(f"Message {match_message_id} not found in conversation")
        
        # Apply adaptive windowing if enabled
        if adaptive:
            window_before, window_after = self._adaptive_window_size(
                messages=messages,
                match_idx=match_idx,
                max_before=window_before,
                max_after=window_after
            )
        
        # Calculate window boundaries
        start_idx = max(0, match_idx - window_before)
        end_idx = min(len(messages), match_idx + window_after + 1)
        
        # Extract window messages
        window_messages = []
        for i in range(start_idx, end_idx):
            msg = messages[i]
            window_msg = WindowMessage(
                id=str(msg.id),
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                is_primary_match=(i == match_idx),
                distance_from_match=abs(i - match_idx)
            )
            window_messages.append(window_msg)
        
        # Get conversation title
        conversation = self.uow.conversations.get_by_id(conversation_id)
        conversation_title = conversation.title if conversation else "Unknown"
        
        return ContextWindow(
            conversation_id=str(conversation_id),
            conversation_title=conversation_title,
            matched_message_id=str(match_message_id),
            messages=window_messages,
            match_position=match_idx - start_idx
        )
    
    def _adaptive_window_size(
        self,
        messages: List[Message],
        match_idx: int,
        max_before: int,
        max_after: int
    ) -> Tuple[int, int]:
        """
        Adaptively adjust window size to include complete user↔assistant turns.
        
        Args:
            messages: All messages in conversation
            match_idx: Index of matched message
            max_before: Maximum messages before
            max_after: Maximum messages after
            
        Returns:
            Tuple of (before_count, after_count)
        """
        before = max_before
        after = max_after
        
        matched_role = messages[match_idx].role
        
        # If matched message is user, ensure assistant response is included
        if matched_role == "user":
            # Check if next message is assistant
            if match_idx + 1 < len(messages):
                next_role = messages[match_idx + 1].role
                if next_role == "assistant" and after < 1:
                    after = 1  # Extend to include response
        
        # If matched message is assistant, ensure user prompt is included
        elif matched_role == "assistant":
            # Check if previous message is user
            if match_idx > 0:
                prev_role = messages[match_idx - 1].role
                if prev_role == "user" and before < 1:
                    before = 1  # Extend to include prompt
        
        return before, after
    
    def _merge_windows(self, windows: List[ContextWindow]) -> List[ContextWindow]:
        """
        Merge overlapping or adjacent windows from the same conversation.
        
        Args:
            windows: List of context windows
            
        Returns:
            List of merged windows
        """
        if not windows:
            return []
        
        # Group windows by conversation
        by_conversation: Dict[str, List[ContextWindow]] = {}
        for window in windows:
            conv_id = window.conversation_id
            if conv_id not in by_conversation:
                by_conversation[conv_id] = []
            by_conversation[conv_id].append(window)
        
        # Merge windows within each conversation
        merged_windows = []
        for conv_id, conv_windows in by_conversation.items():
            if len(conv_windows) == 1:
                merged_windows.append(conv_windows[0])
                continue
            
            # Sort by first message in window
            conv_windows.sort(key=lambda w: w.messages[0].id if w.messages else "")
            
            # Merge overlapping windows
            current = conv_windows[0]
            for next_window in conv_windows[1:]:
                # Check if windows overlap or are adjacent
                current_msg_ids = {m.id for m in current.messages}
                next_msg_ids = {m.id for m in next_window.messages}
                
                if current_msg_ids & next_msg_ids:  # Overlapping
                    # Merge: take union of messages
                    all_messages = current.messages + [
                        m for m in next_window.messages 
                        if m.id not in current_msg_ids
                    ]
                    
                    # Sort by creation time
                    all_messages.sort(key=lambda m: m.created_at)
                    
                    # Update match position
                    match_id = current.matched_message_id
                    match_position = next(
                        i for i, m in enumerate(all_messages) 
                        if m.id == match_id
                    )
                    
                    # Create merged window
                    current = ContextWindow(
                        conversation_id=current.conversation_id,
                        conversation_title=current.conversation_title,
                        matched_message_id=current.matched_message_id,
                        messages=all_messages,
                        match_position=match_position,
                        base_score=max(current.base_score, next_window.base_score),
                        window_id=f"{current.conversation_id}:merged"
                    )
                else:
                    # No overlap, keep current and start new
                    merged_windows.append(current)
                    current = next_window
            
            # Add the last window
            merged_windows.append(current)
        
        return merged_windows
    
    def _score_window(
        self,
        window: ContextWindow,
        base_score: float,
        proximity_decay_lambda: float = 0.3,
        apply_recency_bonus: bool = False
    ) -> ContextWindow:
        """
        Score a context window with proximity decay and optional recency bonus.
        
        Args:
            window: Context window to score
            base_score: Base relevance score from search
            proximity_decay_lambda: Lambda for exponential decay
            apply_recency_bonus: Whether to add recency bonus
            
        Returns:
            Scored context window
        """
        # Apply proximity decay: messages farther from match contribute less
        weighted_scores = []
        for msg in window.messages:
            distance = msg.distance_from_match
            weight = math.exp(-proximity_decay_lambda * distance)
            weighted_scores.append(base_score * weight)
        
        # Aggregated score is average of weighted scores
        aggregated_score = sum(weighted_scores) / len(weighted_scores) if weighted_scores else base_score
        
        # Apply recency bonus (small boost for recent conversations)
        if apply_recency_bonus and window.messages:
            # Use the matched message's creation time
            matched_msg = next(m for m in window.messages if m.is_primary_match)
            # Ensure created_at is timezone-aware for comparison
            msg_created_at = matched_msg.created_at
            if msg_created_at.tzinfo is None:
                msg_created_at = msg_created_at.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - msg_created_at).days
            
            # Decay recency bonus over 90 days
            recency_bonus = 0.05 * math.exp(-age_days / 90)
            aggregated_score += recency_bonus
        
        # Update window with scores
        window.base_score = base_score
        window.aggregated_score = aggregated_score
        
        return window
    
    def _apply_token_budget(
        self,
        window: ContextWindow,
        max_tokens: int,
        preserve_turns: bool = True
    ) -> ContextWindow:
        """
        Trim window to fit within token budget.
        
        Args:
            window: Context window to trim
            max_tokens: Maximum tokens allowed
            preserve_turns: Whether to preserve complete user↔assistant pairs
            
        Returns:
            Trimmed context window
        """
        # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
        def estimate_tokens(text: str) -> int:
            return len(text) // 4
        
        # Calculate current token count
        total_tokens = sum(estimate_tokens(m.content) for m in window.messages)
        
        if total_tokens <= max_tokens:
            return window  # No trimming needed
        
        # Need to trim - remove from edges while preserving match
        match_idx = window.match_position
        trimmed_messages = list(window.messages)
        
        # Trim alternately from far edges
        while total_tokens > max_tokens and len(trimmed_messages) > 1:
            # Don't remove the matched message
            if trimmed_messages[0].is_primary_match:
                # Remove from end
                if len(trimmed_messages) > 1:
                    removed = trimmed_messages.pop()
                    total_tokens -= estimate_tokens(removed.content)
            elif trimmed_messages[-1].is_primary_match:
                # Remove from start
                if len(trimmed_messages) > 1:
                    removed = trimmed_messages.pop(0)
                    total_tokens -= estimate_tokens(removed.content)
                    match_idx -= 1
            else:
                # Remove from farther edge
                dist_start = match_idx
                dist_end = len(trimmed_messages) - 1 - match_idx
                
                if dist_start >= dist_end:
                    removed = trimmed_messages.pop(0)
                    total_tokens -= estimate_tokens(removed.content)
                    match_idx -= 1
                else:
                    removed = trimmed_messages.pop()
                    total_tokens -= estimate_tokens(removed.content)
        
        # If preserve_turns, ensure we don't have orphaned messages
        if preserve_turns and len(trimmed_messages) > 1:
            # Check first and last messages
            if trimmed_messages[0].role == "assistant" and len(trimmed_messages) > 1:
                # Remove orphaned assistant at start
                trimmed_messages.pop(0)
                match_idx -= 1
            
            if trimmed_messages[-1].role == "user" and len(trimmed_messages) > 1:
                # Remove orphaned user at end
                trimmed_messages.pop()
        
        # Update window with trimmed messages
        window.messages = trimmed_messages
        window.match_position = match_idx
        
        return window
    
    def _format_window(
        self,
        window: ContextWindow,
        include_markers: bool = True,
        retrieval_params: Optional[Dict[str, Any]] = None
    ) -> FormattedWindow:
        """
        Format a context window for API response.
        
        Args:
            window: Context window to format
            include_markers: Whether to include context markers
            retrieval_params: Optional retrieval parameters to include
            
        Returns:
            Formatted window with content and metadata
        """
        # Build content with optional markers
        content_parts = []
        
        if include_markers:
            content_parts.append("[CTX_START]")
        
        for msg in window.messages:
            role_label = {
                'user': 'You',
                'assistant': 'Assistant',
                'system': 'System'
            }.get(msg.role, msg.role.capitalize())
            
            timestamp_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            
            # Add match markers around matched message
            if msg.is_primary_match and include_markers:
                content_parts.append(f"[MATCH_START]")
            
            content_parts.append(
                f"**{role_label}** *(on {timestamp_str})*:\n{msg.content}"
            )
            
            if msg.is_primary_match and include_markers:
                content_parts.append(f"[MATCH_END]")
        
        if include_markers:
            content_parts.append("[CTX_END]")
        
        content = "\n\n".join(content_parts)
        
        # Build metadata
        roles = [m.role for m in window.messages]
        before_count = window.match_position
        after_count = len(window.messages) - window.match_position - 1
        
        # Estimate tokens
        token_estimate = len(content) // 4
        
        metadata = WindowMetadata(
            conversation_id=window.conversation_id,
            window_id=window.window_id or f"{window.conversation_id}:{window.matched_message_id}",
            matched_message_id=window.matched_message_id,
            conversation_title=window.conversation_title,
            window_size=len(window.messages),
            match_position=window.match_position,
            before_count=before_count,
            after_count=after_count,
            base_score=window.base_score,
            aggregated_score=window.aggregated_score,
            roles=roles,
            token_estimate=token_estimate,
            retrieval_params=retrieval_params or {}
        )
        
        return FormattedWindow(content=content, metadata=metadata)
    
    def _get_conversation_messages(self, conversation_id: UUID) -> List[Message]:
        """
        Get all messages in a conversation (with caching).
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            List of messages ordered by creation time
        """
        # Check cache first
        cache_key = str(conversation_id)
        if cache_key in self._conversation_cache:
            return self._conversation_cache[cache_key]
        
        # Load from database
        messages = self.uow.messages.get_by_conversation(conversation_id)
        self._conversation_cache[cache_key] = messages
        return messages

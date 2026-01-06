"""
Repository for Topic and ConversationTopic operations.

Handles:
- Topic CRUD operations
- Conversation-topic associations
- Topic queries and statistics
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.repositories.base_repository import BaseRepository
from db.models.models import Topic, ConversationTopic, Conversation


class TopicRepository(BaseRepository[Topic]):
    """Repository for Topic operations."""

    def __init__(self, session: Session):
        super().__init__(session, Topic)

    def get_by_name(self, name: str) -> Optional[Topic]:
        """Get a topic by its name (case-insensitive)."""
        return self.session.query(Topic).filter(
            func.lower(Topic.name) == func.lower(name)
        ).first()

    def get_or_create_by_name(self, name: str) -> Topic:
        """
        Get an existing topic by name or create a new one.

        Args:
            name: The topic name

        Returns:
            The existing or newly created Topic
        """
        # Normalize the name (strip whitespace)
        normalized_name = name.strip()

        existing = self.get_by_name(normalized_name)
        if existing:
            return existing

        return self.create(name=normalized_name)

    def get_topics_for_conversation(self, conversation_id: UUID) -> List[Topic]:
        """
        Get all topics associated with a conversation.

        Args:
            conversation_id: The conversation UUID

        Returns:
            List of Topic objects
        """
        return self.session.query(Topic).join(
            ConversationTopic,
            Topic.id == ConversationTopic.topic_id
        ).filter(
            ConversationTopic.conversation_id == conversation_id
        ).order_by(Topic.name).all()

    def get_topic_names_for_conversation(self, conversation_id: UUID) -> List[str]:
        """
        Get all topic names for a conversation.

        Args:
            conversation_id: The conversation UUID

        Returns:
            List of topic name strings
        """
        topics = self.get_topics_for_conversation(conversation_id)
        return [t.name for t in topics]

    def set_conversation_topics(self, conversation_id: UUID, topic_names: List[str]) -> List[Topic]:
        """
        Set the topics for a conversation, replacing any existing associations.

        Args:
            conversation_id: The conversation UUID
            topic_names: List of topic names to associate

        Returns:
            List of Topic objects that were associated
        """
        # Remove existing associations
        self.session.query(ConversationTopic).filter(
            ConversationTopic.conversation_id == conversation_id
        ).delete()

        # Add new associations
        topics = []
        for name in topic_names:
            if not name or not name.strip():
                continue

            topic = self.get_or_create_by_name(name)
            topics.append(topic)

            # Create the association
            assoc = ConversationTopic(
                conversation_id=conversation_id,
                topic_id=topic.id
            )
            self.session.add(assoc)

        self.session.flush()
        return topics

    def add_topic_to_conversation(self, conversation_id: UUID, topic_name: str) -> Topic:
        """
        Add a single topic to a conversation.

        Args:
            conversation_id: The conversation UUID
            topic_name: The topic name to add

        Returns:
            The Topic that was added
        """
        topic = self.get_or_create_by_name(topic_name)

        # Check if association already exists
        existing = self.session.query(ConversationTopic).filter(
            ConversationTopic.conversation_id == conversation_id,
            ConversationTopic.topic_id == topic.id
        ).first()

        if not existing:
            assoc = ConversationTopic(
                conversation_id=conversation_id,
                topic_id=topic.id
            )
            self.session.add(assoc)
            self.session.flush()

        return topic

    def remove_topic_from_conversation(self, conversation_id: UUID, topic_name: str) -> bool:
        """
        Remove a topic from a conversation.

        Args:
            conversation_id: The conversation UUID
            topic_name: The topic name to remove

        Returns:
            True if removed, False if not found
        """
        topic = self.get_by_name(topic_name)
        if not topic:
            return False

        deleted = self.session.query(ConversationTopic).filter(
            ConversationTopic.conversation_id == conversation_id,
            ConversationTopic.topic_id == topic.id
        ).delete()

        return deleted > 0

    def get_conversations_by_topic(self, topic_name: str) -> List[UUID]:
        """
        Get all conversation IDs that have a specific topic.

        Args:
            topic_name: The topic name to search for

        Returns:
            List of conversation UUIDs
        """
        topic = self.get_by_name(topic_name)
        if not topic:
            return []

        results = self.session.query(ConversationTopic.conversation_id).filter(
            ConversationTopic.topic_id == topic.id
        ).all()

        return [r[0] for r in results]

    def get_topic_counts(self) -> List[Dict[str, Any]]:
        """
        Get all topics with their usage counts.

        Returns:
            List of dicts with 'name', 'id', and 'count' keys, ordered by count desc
        """
        results = self.session.query(
            Topic.id,
            Topic.name,
            func.count(ConversationTopic.conversation_id).label('count')
        ).outerjoin(
            ConversationTopic,
            Topic.id == ConversationTopic.topic_id
        ).group_by(
            Topic.id,
            Topic.name
        ).order_by(
            func.count(ConversationTopic.conversation_id).desc()
        ).all()

        return [
            {'id': str(r.id), 'name': r.name, 'count': r.count}
            for r in results
        ]

    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> List[Topic]:
        """Get all topics ordered by name."""
        query = self.session.query(Topic).order_by(Topic.name)
        if offset > 0:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        return query.all()

    def search_topics(self, query: str, limit: int = 10) -> List[Topic]:
        """
        Search for topics by name prefix (for autocomplete).

        Args:
            query: The search query
            limit: Maximum results to return

        Returns:
            List of matching Topic objects
        """
        return self.session.query(Topic).filter(
            Topic.name.ilike(f"{query}%")
        ).order_by(Topic.name).limit(limit).all()

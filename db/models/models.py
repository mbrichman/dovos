"""
SQLAlchemy models for the PostgreSQL schema.
Corresponds to the schema defined in db/schema.sql.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, JSON, BigInteger, CheckConstraint, Index, Computed, Boolean
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class Conversation(Base):
    __tablename__ = 'conversations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Source tracking for sync (OpenWebUI, Claude, ChatGPT)
    source_id = Column(String(255), nullable=True)  # Original ID from source system
    source_type = Column(String(50), nullable=True)  # 'openwebui', 'claude', 'chatgpt'
    source_updated_at = Column(DateTime(timezone=True), nullable=True)  # Last known update time at source

    # Saved/bookmarked status
    is_saved = Column(Boolean, nullable=False, default=False)

    # Relationship to messages
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    # Relationship to topics via junction table
    topics = relationship(
        "Topic",
        secondary="conversation_topics",
        back_populates="conversations"
    )

    def __repr__(self):
        return f"<Conversation(id='{self.id}', title='{self.title[:50]}...')>"


class Message(Base):
    __tablename__ = 'messages'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    message_metadata = Column('metadata', JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    version = Column(Integer, nullable=False, default=1)
    message_search = Column(TSVECTOR, Computed("to_tsvector('english', coalesce(content, ''))"))  # Generated column

    # Source tracking for sync
    source_message_id = Column(String(255), nullable=True)  # Original message ID from source system

    # Constraints
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name='messages_role_check'),
    )
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    embedding = relationship("MessageEmbedding", back_populates="message", cascade="all, delete-orphan", uselist=False)
    
    def __repr__(self):
        return f"<Message(id='{self.id}', role='{self.role}', content='{self.content[:50]}...')>"


class MessageEmbedding(Base):
    __tablename__ = 'message_embeddings'

    message_id = Column(UUID(as_uuid=True), ForeignKey('messages.id', ondelete='CASCADE'), primary_key=True)
    embedding = Column(Vector(384))  # Default dimension for all-MiniLM-L6-v2
    model = Column(String, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationship
    message = relationship("Message", back_populates="embedding")

    def __repr__(self):
        return f"<MessageEmbedding(message_id='{self.message_id}', model='{self.model}')>"


class Topic(Base):
    """Topics (tags) for categorizing conversations."""
    __tablename__ = 'topics'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationship to conversations via junction table
    conversations = relationship(
        "Conversation",
        secondary="conversation_topics",
        back_populates="topics"
    )

    def __repr__(self):
        return f"<Topic(id='{self.id}', name='{self.name}')>"


class ConversationTopic(Base):
    """Junction table linking conversations to topics."""
    __tablename__ = 'conversation_topics'

    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey('conversations.id', ondelete='CASCADE'),
        primary_key=True
    )
    topic_id = Column(
        UUID(as_uuid=True),
        ForeignKey('topics.id', ondelete='CASCADE'),
        primary_key=True
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<ConversationTopic(conversation_id='{self.conversation_id}', topic_id='{self.topic_id}')>"


class Job(Base):
    __tablename__ = 'jobs'
    
    id = Column(BigInteger, primary_key=True)
    kind = Column(String, nullable=False)
    payload = Column(JSON, default=dict)
    status = Column(String, nullable=False, default='pending')
    attempts = Column(Integer, nullable=False, default=0)
    not_before = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')", name='jobs_status_check'),
    )
    
    def __repr__(self):
        return f"<Job(id={self.id}, kind='{self.kind}', status='{self.status}')>"


class Setting(Base):
    __tablename__ = 'settings'
    
    id = Column(String, primary_key=True)  # e.g., 'openwebui_url', 'openwebui_api_key'
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)  # For documentation
    category = Column(String, default='general')  # e.g., 'openwebui', 'search', 'general'
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Setting(id='{self.id}', value='{self.value[:50] if self.value else None}...')>"


# Add indexes programmatically (these match the schema.sql indexes)
Index('idx_conversations_created_at', Conversation.created_at.desc())
Index('idx_conversations_updated_at', Conversation.updated_at.desc())
Index('idx_messages_conversation_id', Message.conversation_id)
Index('idx_messages_conv_created', Message.conversation_id, Message.created_at.desc())
Index('idx_messages_created_at', Message.created_at.desc())
Index('idx_messages_role', Message.role)
Index('idx_embeddings_model', MessageEmbedding.model)
Index('idx_embeddings_updated_at', MessageEmbedding.updated_at.desc())
Index('idx_jobs_status_kind', Job.status, Job.kind)
Index('idx_jobs_created_at', Job.created_at.desc())
Index('idx_topics_name', Topic.name)
Index('idx_conversation_topics_topic_id', ConversationTopic.topic_id)
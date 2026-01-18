"""
SQLAlchemy models for the PostgreSQL schema.
Corresponds to the schema defined in db/schema.sql.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, JSON, BigInteger, CheckConstraint, Index, Computed, Boolean, LargeBinary
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from pgvector.sqlalchemy import Vector
from flask_security import UserMixin, RoleMixin, AsaList
from sqlalchemy.ext.mutable import MutableList

Base = declarative_base()


# ============================================================================
# Authentication Models (Flask-Security-Too)
# ============================================================================

class RolesUsers(Base):
    """Junction table linking users to roles."""
    __tablename__ = 'roles_users'

    id = Column(Integer, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'))
    role_id = Column(UUID(as_uuid=True), ForeignKey('roles.id', ondelete='CASCADE'))


class Role(Base, RoleMixin):
    """User roles for permission management."""
    __tablename__ = 'roles'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(80), unique=True, nullable=False)
    description = Column(String(255))

    # Flask-Security permissions field
    permissions = Column(MutableList.as_mutable(AsaList()), nullable=True)

    def __repr__(self):
        return f"<Role(name='{self.name}')>"


class User(Base, UserMixin):
    """User model for authentication."""
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(255), unique=True, nullable=True)

    # Password (optional - can be null for passkey-only users)
    password = Column(String(255), nullable=True)

    # Flask-Security required fields
    active = Column(Boolean, default=True, nullable=False)
    fs_uniquifier = Column(String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)

    # Unified signin fields (required for passwordless)
    us_totp_secrets = Column(Text, nullable=True)
    us_phone_number = Column(String(128), nullable=True)

    # WebAuthn user handle (required for passkey support)
    fs_webauthn_user_handle = Column(String(64), unique=True, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    current_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(100), nullable=True)
    current_login_ip = Column(String(100), nullable=True)
    login_count = Column(Integer, default=0)

    # Two-factor authentication
    tf_primary_method = Column(String(64), nullable=True)
    tf_totp_secret = Column(String(255), nullable=True)

    # Relationships
    roles = relationship(
        'Role',
        secondary='roles_users',
        backref='users'
    )
    webauthn = relationship(
        'WebAuthn',
        back_populates='user',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<User(email='{self.email}')>"


class WebAuthn(Base):
    """WebAuthn/Passkey credentials for passwordless authentication."""
    __tablename__ = 'webauthn'

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign key to user
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    # Credential info
    credential_id = Column(LargeBinary, unique=True, nullable=False, index=True)
    public_key = Column(LargeBinary, nullable=False)
    sign_count = Column(Integer, default=0, nullable=False)

    # Transports for this credential (e.g., ['usb', 'nfc', 'ble', 'internal'])
    transports = Column(MutableList.as_mutable(AsaList()), nullable=True)

    # Device info
    name = Column(String(64), nullable=False)  # User-friendly name for the passkey
    usage = Column(String(64), nullable=False)  # 'first' or 'secondary'
    backup_state = Column(Boolean, nullable=False)
    device_type = Column(String(64), nullable=False)  # 'single_device' or 'multi_device'

    # Extensions data (JSON-encoded)
    extensions = Column(String(255), nullable=True)

    # Timestamps
    lastuse_datetime = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    registered_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationship
    user = relationship('User', back_populates='webauthn')

    # Flask-Security requires this method
    def get_user_mapping(self):
        return {"id": self.user_id, "email": self.user.email}

    def __repr__(self):
        return f"<WebAuthn(name='{self.name}', user_id='{self.user_id}')>"


# Indexes for auth tables
Index('idx_users_email', User.email)
Index('idx_users_fs_uniquifier', User.fs_uniquifier)
Index('idx_webauthn_user_id', WebAuthn.user_id)


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
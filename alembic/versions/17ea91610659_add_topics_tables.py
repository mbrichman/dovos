"""add_topics_tables

Revision ID: 17ea91610659
Revises: a1b2c3d4e5f6
Create Date: 2026-01-05 21:00:24.596355

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '17ea91610659'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create topics and conversation_topics tables."""
    # Create topics table
    op.create_table(
        'topics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.Text(), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    # Create conversation_topics junction table
    op.create_table(
        'conversation_topics',
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('topic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('topics.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    # Create indexes
    op.create_index('idx_topics_name', 'topics', ['name'], unique=False)
    op.create_index('idx_conversation_topics_topic_id', 'conversation_topics', ['topic_id'], unique=False)


def downgrade() -> None:
    """Drop topics and conversation_topics tables."""
    op.drop_index('idx_conversation_topics_topic_id', table_name='conversation_topics')
    op.drop_index('idx_topics_name', table_name='topics')
    op.drop_table('conversation_topics')
    op.drop_table('topics')

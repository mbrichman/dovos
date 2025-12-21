"""add_source_tracking_columns

Revision ID: 8e2e6b4cd475
Revises: 77880427c10b
Create Date: 2025-12-20 23:13:34.794350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e2e6b4cd475'
down_revision: Union[str, Sequence[str], None] = '77880427c10b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add source tracking columns to conversations and messages tables."""
    # Add source tracking columns to conversations table
    op.add_column('conversations', sa.Column('source_id', sa.String(255), nullable=True))
    op.add_column('conversations', sa.Column('source_type', sa.String(50), nullable=True))
    op.add_column('conversations', sa.Column('source_updated_at', sa.DateTime(timezone=True), nullable=True))

    # Create unique partial index for source lookup (only where source_id is not null)
    op.create_index(
        'idx_conversations_source_lookup',
        'conversations',
        ['source_type', 'source_id'],
        unique=True,
        postgresql_where=sa.text('source_id IS NOT NULL')
    )

    # Add source_message_id column to messages table
    op.add_column('messages', sa.Column('source_message_id', sa.String(255), nullable=True))

    # Create index for message source lookup
    op.create_index(
        'idx_messages_source_lookup',
        'messages',
        ['conversation_id', 'source_message_id'],
        postgresql_where=sa.text('source_message_id IS NOT NULL')
    )


def downgrade() -> None:
    """Remove source tracking columns."""
    # Drop indexes first
    op.drop_index('idx_messages_source_lookup', table_name='messages')
    op.drop_index('idx_conversations_source_lookup', table_name='conversations')

    # Drop columns
    op.drop_column('messages', 'source_message_id')
    op.drop_column('conversations', 'source_updated_at')
    op.drop_column('conversations', 'source_type')
    op.drop_column('conversations', 'source_id')

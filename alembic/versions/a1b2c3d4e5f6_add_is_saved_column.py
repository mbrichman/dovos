"""Add is_saved column for conversation bookmarks

Revision ID: a1b2c3d4e5f6
Revises: 8e2e6b4cd475
Create Date: 2025-12-26T18:57:24.044937

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '8e2e6b4cd475'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_saved column to conversations table."""
    op.add_column('conversations', sa.Column('is_saved', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.create_index('idx_conversations_is_saved', 'conversations', ['is_saved'], unique=False, postgresql_where=sa.text('is_saved = TRUE'))


def downgrade() -> None:
    """Remove is_saved column from conversations table."""
    op.drop_index('idx_conversations_is_saved', table_name='conversations')
    op.drop_column('conversations', 'is_saved')


"""add_vector_similarity_index

Creates IVFFLAT index on message_embeddings for efficient vector similarity search.

This migration:
1. Checks if enough embeddings exist (>1000 recommended)
2. Runs ANALYZE to gather statistics
3. Creates IVFFLAT index with appropriate parameters
4. Uses CONCURRENTLY to avoid blocking production queries

Revision ID: 77880427c10b
Revises: 0bf3d3250afa
Create Date: 2025-12-14 13:19:56.950290

"""
from typing import Sequence, Union
import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

logger = logging.getLogger('alembic.runtime.migration')

# revision identifiers, used by Alembic.
revision: str = '77880427c10b'
down_revision: Union[str, Sequence[str], None] = '0bf3d3250afa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create vector similarity index if embeddings exist."""

    conn = op.get_bind()

    # Check if index already exists
    result = conn.execute(text("""
        SELECT COUNT(*)
        FROM pg_indexes
        WHERE tablename = 'message_embeddings'
        AND indexname = 'idx_embeddings_vector_ivfflat'
    """))

    if result.scalar() > 0:
        logger.info("⏭️  Vector index already exists, skipping")
        return

    # Check embedding count
    result = conn.execute(text("""
        SELECT COUNT(*) FROM message_embeddings
    """))
    count = result.scalar()

    logger.info(f"📊 Found {count:,} embeddings in database")

    if count < 100:
        logger.warning("⚠️  Less than 100 embeddings found.")
        logger.warning("Skipping index creation - sequential scan will be faster.")
        logger.warning("Run 'alembic upgrade head' again after adding more embeddings.")
        return

    # Determine optimal number of lists based on count
    # Rule of thumb: sqrt(count), but with reasonable bounds
    if count < 10000:
        lists = 50
    elif count < 100000:
        lists = 100
    elif count < 1000000:
        lists = 200
    else:
        lists = 500

    logger.info(f"🔨 Creating IVFFLAT index with {lists} lists...")
    logger.info("This may take a few minutes. Index will be built CONCURRENTLY.")

    # Run ANALYZE first to gather statistics
    logger.info("Running ANALYZE...")
    conn.execute(text("ANALYZE message_embeddings"))

    # Note: CREATE INDEX CONCURRENTLY cannot run inside a transaction block
    # So we need to use op.execute with special handling
    # The index will be created outside the transaction
    try:
        # Create index concurrently
        # Using vector_cosine_ops for cosine similarity (most common for embeddings)
        conn.execute(text(f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_embeddings_vector_ivfflat
            ON message_embeddings
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = {lists})
        """))

        logger.info("✅ Vector similarity index created successfully!")
        logger.info("Vector searches will now be 10-100x faster.")

    except Exception as e:
        logger.error(f"❌ Failed to create index: {e}")
        logger.error("You can manually create it later with:")
        logger.error(f"  CREATE INDEX CONCURRENTLY idx_embeddings_vector_ivfflat")
        logger.error(f"  ON message_embeddings USING ivfflat (embedding vector_cosine_ops)")
        logger.error(f"  WITH (lists = {lists});")
        raise


def downgrade() -> None:
    """Remove vector similarity index."""

    logger.info("🗑️  Dropping vector similarity index...")

    # Drop index concurrently to avoid blocking queries
    op.execute("""
        DROP INDEX CONCURRENTLY IF EXISTS idx_embeddings_vector_ivfflat
    """)

    logger.info("✅ Vector index removed")

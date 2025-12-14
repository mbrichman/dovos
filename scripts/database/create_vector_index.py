#!/usr/bin/env python3
"""
Create vector similarity index on message_embeddings table.

This script creates an IVFFLAT or HNSW index for efficient vector similarity search.
Should only be run when you have >1000 embeddings.

Usage:
    python scripts/database/create_vector_index.py [--index-type ivfflat|hnsw]

Index Types:
    - IVFFLAT: Good balance of speed and recall, default choice
    - HNSW: Better recall, slightly slower build time, better for production
"""

import argparse
import logging
import sys
from sqlalchemy import text

from db.database import engine

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_embedding_count():
    """Check how many embeddings exist."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) as count FROM message_embeddings
        """))
        count = result.scalar()
        logger.info(f"Found {count:,} embeddings in database")
        return count


def check_existing_indexes():
    """Check for existing vector indexes."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'message_embeddings'
            AND indexdef LIKE '%USING%ivfflat%' OR indexdef LIKE '%USING%hnsw%'
        """))
        indexes = result.fetchall()
        if indexes:
            logger.info("Found existing vector indexes:")
            for idx in indexes:
                logger.info(f"  - {idx.indexname}")
            return True
        return False


def create_ivfflat_index(lists: int = 100):
    """
    Create IVFFLAT index for approximate nearest neighbor search.

    Args:
        lists: Number of inverted lists (clusters).
               Rule of thumb: sqrt(row_count) for datasets < 1M rows
               For 64k rows: sqrt(64000) ≈ 253, but 100 is a good default
    """
    logger.info(f"Creating IVFFLAT index with {lists} lists...")

    with engine.begin() as conn:
        # Run ANALYZE first to gather statistics
        logger.info("Running ANALYZE on message_embeddings...")
        conn.execute(text("ANALYZE message_embeddings"))

        # Create the index
        logger.info("Creating index (this may take a few minutes)...")
        conn.execute(text(f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_embeddings_vector_ivfflat
            ON message_embeddings
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = {lists})
        """))

    logger.info("✅ IVFFLAT index created successfully!")
    logger.info("Vector similarity searches will now be much faster.")


def create_hnsw_index(m: int = 16, ef_construction: int = 64):
    """
    Create HNSW index for approximate nearest neighbor search.

    Args:
        m: Maximum number of connections per layer (default 16)
           Higher = better recall but more memory
        ef_construction: Size of dynamic candidate list (default 64)
                        Higher = better index quality but slower build

    HNSW generally provides better recall than IVFFLAT but takes longer to build.
    """
    logger.info(f"Creating HNSW index (m={m}, ef_construction={ef_construction})...")

    with engine.begin() as conn:
        # Run ANALYZE first
        logger.info("Running ANALYZE on message_embeddings...")
        conn.execute(text("ANALYZE message_embeddings"))

        # Create the index
        logger.info("Creating index (this may take several minutes)...")
        conn.execute(text(f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_embeddings_vector_hnsw
            ON message_embeddings
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = {m}, ef_construction = {ef_construction})
        """))

    logger.info("✅ HNSW index created successfully!")
    logger.info("Vector similarity searches will now be much faster with better recall.")


def recommend_index_params(count: int, index_type: str):
    """Recommend optimal index parameters based on dataset size."""
    if index_type == 'ivfflat':
        # Rule of thumb: lists = sqrt(row_count)
        # But cap at reasonable values
        if count < 10000:
            lists = 50
        elif count < 100000:
            lists = 100
        elif count < 1000000:
            lists = 200
        else:
            lists = 500

        logger.info(f"Recommended IVFFLAT parameters for {count:,} embeddings:")
        logger.info(f"  lists = {lists}")
        return lists

    elif index_type == 'hnsw':
        # HNSW parameters are less sensitive to dataset size
        m = 16  # Good default
        ef_construction = 64  # Good default

        if count > 1000000:
            # For very large datasets, increase ef_construction
            ef_construction = 128

        logger.info(f"Recommended HNSW parameters for {count:,} embeddings:")
        logger.info(f"  m = {m}")
        logger.info(f"  ef_construction = {ef_construction}")
        return m, ef_construction


def main():
    parser = argparse.ArgumentParser(description='Create vector similarity index')
    parser.add_argument(
        '--index-type',
        choices=['ivfflat', 'hnsw'],
        default='ivfflat',
        help='Type of index to create (default: ivfflat)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Create index even if one already exists'
    )
    args = parser.parse_args()

    try:
        # Check embedding count
        count = check_embedding_count()

        if count < 1000:
            logger.warning(f"⚠️  Only {count} embeddings found.")
            logger.warning("Vector indexes are most beneficial with >1000 embeddings.")
            logger.warning("For small datasets, sequential scan may be faster.")

            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                logger.info("Cancelled.")
                return

        # Check for existing indexes
        if not args.force and check_existing_indexes():
            logger.warning("Vector index already exists!")
            response = input("Create another index anyway? (y/N): ")
            if response.lower() != 'y':
                logger.info("Cancelled. Use --force to override.")
                return

        # Create the index
        if args.index_type == 'ivfflat':
            lists = recommend_index_params(count, 'ivfflat')
            create_ivfflat_index(lists)
        else:  # hnsw
            m, ef_construction = recommend_index_params(count, 'hnsw')
            create_hnsw_index(m, ef_construction)

        logger.info("\n📊 Performance tip:")
        logger.info("Monitor query performance with EXPLAIN ANALYZE on your vector similarity queries.")
        logger.info("You can adjust ivf_probes or hnsw.ef_search for recall vs speed tradeoff.")

    except Exception as e:
        logger.error(f"❌ Error creating index: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

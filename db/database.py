"""
Database connection and session management for PostgreSQL.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
import logging

from config import DATABASE_URL, PGAPPNAME

logger = logging.getLogger(__name__)

# Create engine with PostgreSQL-specific settings
engine = create_engine(
    DATABASE_URL,
    # Use NullPool for simplicity in development
    poolclass=NullPool,
    # Set application name for connection tracking
    connect_args={"application_name": PGAPPNAME},
    # Log SQL in debug mode
    echo=False  # Set to True for SQL logging
)

# Create session factory
SessionFactory = sessionmaker(bind=engine)


def get_session() -> Session:
    """Get a new database session."""
    return SessionFactory()


@contextmanager
def get_session_context():
    """Context manager for database sessions with automatic cleanup."""
    session = get_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def test_connection() -> bool:
    """Test database connection and return True if successful."""
    try:
        with get_session_context() as session:
            result = session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


def check_extensions() -> dict:
    """Check if required PostgreSQL extensions are installed."""
    extensions = {}
    try:
        with get_session_context() as session:
            # Check pg_trgm
            result = session.execute(text(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')"
            ))
            extensions['pg_trgm'] = result.scalar()
            
            # Check vector
            result = session.execute(text(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
            ))
            extensions['vector'] = result.scalar()
            
    except Exception as e:
        logger.error(f"Extension check failed: {e}")
        
    return extensions


def create_tables(database_url=None):
    """Create all tables defined in the ORM models.
    
    Args:
        database_url: Optional database URL. If provided, uses a separate engine for this operation.
    """
    try:
        from db.models.models import Base
        # Use provided URL or the global engine
        if database_url:
            temp_engine = create_engine(
                database_url,
                poolclass=NullPool,
                connect_args={"application_name": PGAPPNAME},
                echo=False
            )
            Base.metadata.create_all(temp_engine)
            temp_engine.dispose()
        else:
            Base.metadata.create_all(engine)
        logger.info("All tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        raise

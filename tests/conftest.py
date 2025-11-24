"""
Test configuration and fixtures
"""
import pytest
import json
import os
from typing import Dict, Any, Generator
import tempfile
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from api.contracts.api_contract import APIContract
from db.models.models import Base
from db.repositories.unit_of_work import UnitOfWork
from tests.utils.seed import (
    seed_conversation_with_messages,
    seed_multiple_conversations,
    seed_test_corpus,
    clear_test_data
)


@pytest.fixture(scope="session")
def app():
    """Create application for testing"""
    # Use test configuration
    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        # Force legacy mode for consistent testing
        "USE_PG_SINGLE_STORE": False
    })
    
    # Create a test context
    with app.app_context():
        yield app


@pytest.fixture(scope="session") 
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def test_data():
    """Sample test data for API testing"""
    return {
        "conversations": [
            {
                "id": "test-conv-1",
                "title": "Test Conversation 1",
                "content": "This is a test conversation with multiple messages between a user and assistant.",
                "metadata": {
                    "id": "test-conv-1",
                    "title": "Test Conversation 1",
                    "source": "chatgpt",
                    "earliest_ts": "2025-01-01T10:00:00Z"
                }
            },
            {
                "id": "test-conv-2", 
                "title": "Test Conversation 2",
                "content": "Another test conversation with different content for search testing.",
                "metadata": {
                    "id": "test-conv-2",
                    "title": "Test Conversation 2", 
                    "source": "claude",
                    "earliest_ts": "2025-01-02T15:30:00Z"
                }
            }
        ],
        "messages": [
            {"id": "user-1", "role": "user", "content": "Hello, how are you?", "timestamp": "2025-01-01T10:00:00Z"},
            {"id": "assistant-1", "role": "assistant", "content": "I'm doing well, thank you for asking!", "timestamp": "2025-01-01T10:01:00Z"},
            {"id": "user-2", "role": "user", "content": "What can you help me with?", "timestamp": "2025-01-01T10:02:00Z"},
            {"id": "assistant-2", "role": "assistant", "content": "I can help with various tasks...", "timestamp": "2025-01-01T10:03:00Z"}
        ],
        "search_query": "test conversation",
        "rag_query": {
            "query": "help with tasks",
            "n_results": 5,
            "search_type": "semantic"
        }
    }


@pytest.fixture
def golden_responses_dir():
    """Directory for golden response files"""
    golden_dir = os.path.join(os.path.dirname(__file__), "golden_responses")
    os.makedirs(golden_dir, exist_ok=True)
    return golden_dir


@pytest.fixture
def contract_validator():
    """Contract validation fixture"""
    return APIContract


def save_golden_response(response_data: Dict[str, Any], endpoint: str, golden_dir: str):
    """Helper to save golden responses"""
    # Clean endpoint name for filename
    filename = endpoint.replace("/", "_").replace("<", "").replace(">", "").replace(" ", "_")
    filepath = os.path.join(golden_dir, f"{filename}.json")
    
    with open(filepath, 'w') as f:
        json.dump(response_data, f, indent=2, sort_keys=True)


def load_golden_response(endpoint: str, golden_dir: str) -> Dict[str, Any]:
    """Helper to load golden responses"""
    filename = endpoint.replace("/", "_").replace("<", "").replace(">", "").replace(" ", "_")
    filepath = os.path.join(golden_dir, f"{filename}.json")
    
    if not os.path.exists(filepath):
        return None
        
    with open(filepath, 'r') as f:
        return json.load(f)


@pytest.fixture
def golden_response_helpers(golden_responses_dir):
    """Provide golden response helper functions"""
    return {
        "save": lambda data, endpoint: save_golden_response(data, endpoint, golden_responses_dir),
        "load": lambda endpoint: load_golden_response(endpoint, golden_responses_dir),
        "dir": golden_responses_dir
    }


@pytest.fixture(scope="session")
def performance_baseline():
    """Performance baseline metrics"""
    return {
        "response_time_thresholds": {
            "GET /api/conversations": 2.0,  # seconds
            "GET /api/conversation/<id>": 1.0,
            "GET /api/search": 3.0,
            "POST /api/rag/query": 5.0,
            "GET /api/stats": 0.5,
            "GET /api/rag/health": 0.5
        },
        "content_length_thresholds": {
            "GET /api/conversations": 10000,  # bytes
            "GET /api/conversation/<id>": 50000,
            "GET /api/search": 20000,
            "POST /api/rag/query": 30000
        }
    }


# ===== PostgreSQL Test Database Fixtures =====

@pytest.fixture(scope="session")
def test_db_url():
    """Test database URL (uses docker-compose.test.yml database)"""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://test_user:test_password@localhost:5433/dovos_test"
    )


@pytest.fixture(scope="session")
def test_db_engine(test_db_url):
    """
    Create test database engine with proper configuration.
    
    Uses docker-compose.test.yml PostgreSQL instance on port 5433.
    Schema is created once per test session.
    """
    engine = create_engine(
        test_db_url,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,
        max_overflow=10
    )
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    # Verify extensions are loaded
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pg_trgm', 'uuid-ossp')"
        ))
        extensions = [row[0] for row in result]
        assert 'vector' in extensions, "pgvector extension not loaded"
        assert 'pg_trgm' in extensions, "pg_trgm extension not loaded"
    
    yield engine
    
    # Cleanup: drop all tables after test session
    # Drop views first to avoid dependency issues
    with engine.connect() as conn:
        conn.execute(text("DROP VIEW IF EXISTS embedding_coverage CASCADE"))
        conn.execute(text("DROP VIEW IF EXISTS conversation_summaries CASCADE"))
        conn.commit()
    
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_db_engine) -> Generator[Session, None, None]:
    """
    Provide a clean database session for each test.
    
    Uses transaction rollback to ensure test isolation:
    - Each test gets a fresh database state
    - Changes are rolled back after test completes
    - Fast test execution (no table recreation)
    """
    connection = test_db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    yield session
    
    # Rollback transaction to undo all changes
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def uow(db_session) -> UnitOfWork:
    """
    Provide a Unit of Work instance with test database session.
    
    Note: This UoW uses the test session, so changes are automatically
    rolled back after the test completes.
    """
    return UnitOfWork(session=db_session)


@pytest.fixture
def seed_conversations(uow):
    """
    Factory fixture for seeding test conversations.
    
    Usage:
        def test_something(seed_conversations):
            conversations = seed_conversations(count=5, with_embeddings=True)
    """
    def _seed(count=10, messages_per_conversation=4, with_embeddings=False):
        return seed_multiple_conversations(
            uow,
            count=count,
            messages_per_conversation=messages_per_conversation,
            with_embeddings=with_embeddings
        )
    return _seed


@pytest.fixture
def seed_test_corpus_fixture(uow):
    """
    Seed curated test corpus for search testing.
    
    Returns a dict with conversations labeled by topic:
    - 'python': Python web scraping conversation
    - 'database': PostgreSQL optimization conversation
    - 'ml': Machine learning conversation
    """
    return seed_test_corpus(uow, with_embeddings=True)


@pytest.fixture
def search_service(uow):
    """Provide SearchService instance with test database."""
    from db.services.search_service import SearchService
    return SearchService(uow)


@pytest.fixture
def conv_id(uow, seed_conversations):
    """Provide a conversation ID with test messages for search service tests."""
    from db.services.message_service import MessageService
    
    # Seed a conversation with messages
    convs = seed_conversations(count=1, messages_per_conversation=5, with_embeddings=True)
    conversation, messages = convs[0]
    
    return conversation.id


@pytest.fixture
def toggle_postgres_mode(monkeypatch):
    """
    Toggle USE_POSTGRES environment variable for side-by-side testing.
    
    Usage:
        def test_both_backends(toggle_postgres_mode):
            # Test with PostgreSQL
            toggle_postgres_mode(True)
            result_pg = api_call()
            
            # Test with legacy ChromaDB
            toggle_postgres_mode(False)
            result_legacy = api_call()
            
            assert result_pg == result_legacy
    """
    def _toggle(use_postgres: bool):
        value = "true" if use_postgres else "false"
        monkeypatch.setenv("USE_POSTGRES", value)
        # Also update config module
        import config
        monkeypatch.setattr(config, "USE_PG_SINGLE_STORE", use_postgres)
    
    return _toggle


@pytest.fixture
def both_backends(toggle_postgres_mode, db_session, seed_conversations):
    """
    Fixture for testing both backends with identical data.
    
    Seeds both PostgreSQL and legacy ChromaDB with same data.
    Returns helper object for running tests against both.
    
    Usage:
        def test_api_parity(both_backends):
            result_pg = both_backends.postgres_api_call()
            result_legacy = both_backends.legacy_api_call()
            assert result_pg == result_legacy
    """
    class BothBackends:
        def __init__(self):
            self.toggle = toggle_postgres_mode
            
        def with_postgres(self, func, *args, **kwargs):
            self.toggle(True)
            return func(*args, **kwargs)
        
        def with_legacy(self, func, *args, **kwargs):
            self.toggle(False)
            return func(*args, **kwargs)
    
    # Seed PostgreSQL with test data
    toggle_postgres_mode(True)
    seed_conversations(count=5, with_embeddings=True)
    
    return BothBackends()


# ===== Existing Fixtures =====

# Marks for organizing tests
pytestmark = pytest.mark.contract

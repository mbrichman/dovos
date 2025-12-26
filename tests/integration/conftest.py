"""
Shared fixtures for integration tests.

Provides database isolation between tests using the TEST database (port 5433).
IMPORTANT: These tests use dovos-test-db Docker container, NOT the production database.

Note: This module uses fixtures from the main tests/conftest.py:
- test_db_engine: Creates engine for the test database
- client_postgres_test: Flask test client that uses the test database
"""

import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True)
def clear_test_database(test_db_engine):
    """
    Clear TEST database before each integration test to ensure isolation.

    IMPORTANT: This clears the TEST database on port 5433, NOT the production database.
    Uses test_db_engine from the main conftest.py.
    """
    with test_db_engine.connect() as conn:
        # Clear in correct order to avoid foreign key constraint violations
        conn.execute(text('DELETE FROM message_embeddings'))
        conn.execute(text('DELETE FROM messages'))
        conn.execute(text('DELETE FROM conversations'))
        conn.commit()

    yield

    # Clear after test as well
    with test_db_engine.connect() as conn:
        conn.execute(text('DELETE FROM message_embeddings'))
        conn.execute(text('DELETE FROM messages'))
        conn.execute(text('DELETE FROM conversations'))
        conn.commit()

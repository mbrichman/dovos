"""
Shared fixtures for integration tests.

Provides database isolation between tests.
"""

import pytest
from sqlalchemy import text
from db.repositories.unit_of_work import get_unit_of_work


@pytest.fixture(autouse=True)
def clear_database():
    """Clear database before each integration test to ensure isolation."""
    with get_unit_of_work() as uow:
        # Clear in correct order to avoid foreign key constraint violations
        uow.session.execute(text('DELETE FROM messages'))
        uow.session.execute(text('DELETE FROM conversations'))
        uow.commit()
    
    yield
    
    # Optionally clear after test as well
    with get_unit_of_work() as uow:
        uow.session.execute(text('DELETE FROM messages'))
        uow.session.execute(text('DELETE FROM conversations'))
        uow.commit()

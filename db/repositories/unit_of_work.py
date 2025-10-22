"""
Unit of Work pattern implementation for managing transactions and repository instances.
"""

from contextlib import contextmanager
from typing import Optional
import logging

from sqlalchemy.orm import Session
from db.database import get_session
from db.repositories.conversation_repository import ConversationRepository
from db.repositories.message_repository import MessageRepository
from db.repositories.embedding_repository import EmbeddingRepository
from db.repositories.job_repository import JobRepository
from db.repositories.setting_repository import SettingRepository

logger = logging.getLogger(__name__)


class UnitOfWork:
    """
    Unit of Work pattern implementation that manages a database session
    and provides access to all repositories within a single transaction.
    """
    
    def __init__(self, session: Optional[Session] = None):
        self._session = session
        self._owns_session = session is None
        self._conversations: Optional[ConversationRepository] = None
        self._messages: Optional[MessageRepository] = None
        self._embeddings: Optional[EmbeddingRepository] = None
        self._jobs: Optional[JobRepository] = None
        self._settings: Optional[SettingRepository] = None
    
    @property
    def session(self) -> Session:
        """Get the database session, creating one if needed."""
        if self._session is None:
            self._session = get_session()
        return self._session
    
    @property
    def conversations(self) -> ConversationRepository:
        """Get the conversations repository."""
        if self._conversations is None:
            self._conversations = ConversationRepository(self.session)
        return self._conversations
    
    @property
    def messages(self) -> MessageRepository:
        """Get the messages repository."""
        if self._messages is None:
            self._messages = MessageRepository(self.session)
        return self._messages
    
    @property
    def embeddings(self) -> EmbeddingRepository:
        """Get the embeddings repository."""
        if self._embeddings is None:
            self._embeddings = EmbeddingRepository(self.session)
        return self._embeddings
    
    @property
    def jobs(self) -> JobRepository:
        """Get the jobs repository."""
        if self._jobs is None:
            self._jobs = JobRepository(self.session)
        return self._jobs
    
    @property
    def settings(self) -> SettingRepository:
        """Get the settings repository."""
        if self._settings is None:
            self._settings = SettingRepository(self.session)
        return self._settings
    
    def commit(self):
        """Commit the current transaction."""
        try:
            self.session.commit()
            logger.debug("Transaction committed successfully")
        except Exception as e:
            logger.error(f"Transaction commit failed: {e}")
            self.session.rollback()
            raise
    
    def rollback(self):
        """Rollback the current transaction."""
        self.session.rollback()
        logger.debug("Transaction rolled back")
    
    def close(self):
        """Close the session if we own it."""
        if self._owns_session and self._session:
            self._session.close()
            self._session = None
            logger.debug("Database session closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic transaction management."""
        if exc_type is not None:
            # Exception occurred, rollback
            logger.warning(f"Exception in UnitOfWork context: {exc_type.__name__}: {exc_val}")
            self.rollback()
        else:
            # No exception, commit
            self.commit()
        
        # Always close if we own the session
        self.close()


@contextmanager
def get_unit_of_work():
    """Context manager for creating a Unit of Work with automatic cleanup."""
    uow = UnitOfWork()
    try:
        yield uow
        # If we get here without exception, commit
        uow.commit()
    except Exception as e:
        logger.error(f"Exception in Unit of Work: {e}")
        uow.rollback()
        raise
    finally:
        # Always close
        uow.close()

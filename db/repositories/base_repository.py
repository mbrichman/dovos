"""
Base repository interface for common CRUD operations.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Any, Dict
from sqlalchemy.orm import Session
from uuid import UUID

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """Base repository interface with common CRUD operations."""
    
    def __init__(self, session: Session, model_class: type):
        self.session = session
        self.model_class = model_class
    
    def create(self, **kwargs) -> T:
        """Create a new entity."""
        entity = self.model_class(**kwargs)
        self.session.add(entity)
        self.session.flush()  # Ensure ID is generated
        return entity
    
    def get_by_id(self, entity_id: UUID) -> Optional[T]:
        """Get entity by ID."""
        return self.session.query(self.model_class).filter(
            self.model_class.id == entity_id
        ).first()
    
    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> List[T]:
        """Get all entities with optional pagination."""
        query = self.session.query(self.model_class)
        if offset > 0:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def update(self, entity_id: UUID, **kwargs) -> Optional[T]:
        """Update entity by ID."""
        entity = self.get_by_id(entity_id)
        if entity:
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            self.session.flush()
        return entity
    
    def delete(self, entity_id: UUID) -> bool:
        """Delete entity by ID."""
        entity = self.get_by_id(entity_id)
        if entity:
            self.session.delete(entity)
            self.session.flush()
            return True
        return False
    
    def exists(self, entity_id: UUID) -> bool:
        """Check if entity exists."""
        return self.session.query(
            self.session.query(self.model_class).filter(
                self.model_class.id == entity_id
            ).exists()
        ).scalar()
    
    def count(self) -> int:
        """Count total entities."""
        return self.session.query(self.model_class).count()
"""
Repository for message operations with full-text search capabilities.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import desc, func, text, or_
from sqlalchemy.orm import Session, joinedload

from db.models.models import Message, Conversation, MessageEmbedding
from db.repositories.base_repository import BaseRepository


class MessageRepository(BaseRepository[Message]):
    """Repository for message operations with search capabilities."""
    
    def __init__(self, session: Session):
        super().__init__(session, Message)
    
    def create_with_version_increment(self, **kwargs) -> Message:
        """
        Create a new message. If this is an update to existing content,
        the version will be automatically incremented by PostgreSQL triggers.
        """
        return self.create(**kwargs)
    
    def get_by_conversation(self, conversation_id: UUID, 
                          limit: Optional[int] = None, 
                          offset: int = 0) -> List[Message]:
        """Get all messages for a conversation, ordered by creation time."""
        query = self.session.query(Message)\
            .filter(Message.conversation_id == conversation_id)\
            .order_by(Message.created_at)
        
        if offset > 0:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
            
        return query.all()
    
    def get_with_embedding(self, message_id: UUID) -> Optional[Message]:
        """Get a message with its embedding loaded."""
        return self.session.query(Message)\
            .options(joinedload(Message.embedding))\
            .filter(Message.id == message_id)\
            .first()
    
    def search_full_text(self, query: str, limit: int = 10, 
                        conversation_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        """
        Perform full-text search using PostgreSQL's generated tsvector column.
        Returns results in a format compatible with the legacy search API.
        """
        # Build the search query using PostgreSQL FTS
        if conversation_id:
            sql_query = text("""
                SELECT 
                    m.id,
                    m.conversation_id,
                    m.role,
                    m.content,
                    m.created_at,
                    m.metadata,
                    c.title as conversation_title,
                    ts_rank(m.message_search, plainto_tsquery('english', :query)) as rank
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE m.message_search @@ plainto_tsquery('english', :query)
                AND m.conversation_id = :conversation_id
                ORDER BY rank DESC, m.created_at DESC
                LIMIT :limit
            """)
        else:
            sql_query = text("""
                SELECT 
                    m.id,
                    m.conversation_id,
                    m.role,
                    m.content,
                    m.created_at,
                    m.metadata,
                    c.title as conversation_title,
                    ts_rank(m.message_search, plainto_tsquery('english', :query)) as rank
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE m.message_search @@ plainto_tsquery('english', :query)
                ORDER BY rank DESC, m.created_at DESC
                LIMIT :limit
            """)
        
        if conversation_id:
            params = {
                'query': query,
                'conversation_id': conversation_id,
                'limit': limit
            }
        else:
            params = {
                'query': query,
                'limit': limit
            }
        
        result = self.session.execute(sql_query, params)
        messages = []
        
        for row in result:
            # Format timestamp for legacy compatibility
            timestamp_str = row.created_at.strftime("%Y-%m-%d %H:%M:%S")
            
            # Build document content in legacy format
            if row.role == 'user':
                document_content = f"**You said** *(on {timestamp_str})*:\n\n{row.content}"
            elif row.role == 'assistant':
                document_content = f"**Assistant said** *(on {timestamp_str})*:\n\n{row.content}"
            elif row.role == 'system':
                document_content = f"**System** *(on {timestamp_str})*:\n\n{row.content}"
            else:
                document_content = f"**{row.role.capitalize()}** *(on {timestamp_str})*:\n\n{row.content}"
            
            messages.append({
                'id': str(row.conversation_id),  # Use conversation ID for API compatibility
                'document': document_content,
                'metadata': {
                    'title': row.conversation_title,
                    'source': 'postgres',
                    'message_count': 1,  # Single message
                    'earliest_ts': row.created_at.isoformat(),
                    'latest_ts': row.created_at.isoformat(),
                    'conversation_id': str(row.conversation_id),
                    'message_id': str(row.id),
                    'role': row.role,
                    'rank': float(row.rank)
                }
            })
        
        return messages
    
    def search_trigram(self, query: str, limit: int = 10, 
                      similarity_threshold: float = 0.1) -> List[Dict[str, Any]]:
        """
        Perform fuzzy text search using PostgreSQL's pg_trgm extension.
        Good for catching typos and partial matches.
        """
        sql_query = text("""
            SELECT 
                m.id,
                m.conversation_id,
                m.role,
                m.content,
                m.created_at,
                m.metadata,
                c.title as conversation_title,
                similarity(m.content, :query) as similarity
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE similarity(m.content, :query) > :threshold
            ORDER BY similarity DESC, m.created_at DESC
            LIMIT :limit
        """)
        
        params = {
            'query': query,
            'threshold': similarity_threshold,
            'limit': limit
        }
        
        result = self.session.execute(sql_query, params)
        messages = []
        
        for row in result:
            # Format timestamp for legacy compatibility
            timestamp_str = row.created_at.strftime("%Y-%m-%d %H:%M:%S")
            
            # Build document content in legacy format
            if row.role == 'user':
                document_content = f"**You said** *(on {timestamp_str})*:\n\n{row.content}"
            elif row.role == 'assistant':
                document_content = f"**Assistant said** *(on {timestamp_str})*:\n\n{row.content}"
            elif row.role == 'system':
                document_content = f"**System** *(on {timestamp_str})*:\n\n{row.content}"
            else:
                document_content = f"**{row.role.capitalize()}** *(on {timestamp_str})*:\n\n{row.content}"
            
            messages.append({
                'id': str(row.conversation_id),  # Use conversation ID for API compatibility
                'document': document_content,
                'metadata': {
                    'title': row.conversation_title,
                    'source': 'postgres',
                    'message_count': 1,  # Single message
                    'earliest_ts': row.created_at.isoformat(),
                    'latest_ts': row.created_at.isoformat(),
                    'conversation_id': str(row.conversation_id),
                    'message_id': str(row.id),
                    'role': row.role,
                    'similarity': float(row.similarity)
                }
            })
        
        return messages
    
    def get_messages_without_embeddings(self, limit: int = 100) -> List[Message]:
        """Get messages that don't have embeddings yet."""
        return self.session.query(Message)\
            .outerjoin(MessageEmbedding)\
            .filter(MessageEmbedding.message_id.is_(None))\
            .order_by(Message.created_at)\
            .limit(limit)\
            .all()
    
    def get_messages_with_stale_embeddings(self, limit: int = 100) -> List[Message]:
        """Get messages whose embeddings are stale (message version > embedding update time)."""
        sql_query = text("""
            SELECT m.*
            FROM messages m
            JOIN message_embeddings e ON m.id = e.message_id
            WHERE m.updated_at > e.updated_at
            ORDER BY m.updated_at DESC
            LIMIT :limit
        """)
        
        result = self.session.execute(sql_query, {'limit': limit})
        message_ids = [row.id for row in result]
        
        if not message_ids:
            return []
        
        return self.session.query(Message)\
            .filter(Message.id.in_(message_ids))\
            .all()
    
    def get_by_role(self, role: str, limit: int = 100) -> List[Message]:
        """Get messages by role (user, assistant, system)."""
        return self.session.query(Message)\
            .filter(Message.role == role)\
            .order_by(desc(Message.created_at))\
            .limit(limit)\
            .all()
    
    def get_recent_activity(self, hours: int = 24) -> List[Message]:
        """Get recent messages for activity tracking."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return self.session.query(Message)\
            .filter(Message.created_at >= cutoff_time)\
            .order_by(desc(Message.created_at))\
            .all()
    
    def get_message_stats(self) -> Dict[str, Any]:
        """Get message statistics."""
        total_messages = self.count()
        
        # Count by role
        role_counts = dict(
            self.session.query(Message.role, func.count(Message.id))
            .group_by(Message.role)
            .all()
        )
        
        # Count embedded messages
        embedded_count = self.session.query(func.count(MessageEmbedding.message_id)).scalar() or 0
        
        # Recent activity (last 24 hours)
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_messages = self.session.query(func.count(Message.id))\
            .filter(Message.created_at >= recent_cutoff)\
            .scalar() or 0
        
        return {
            'total_messages': total_messages,
            'role_distribution': role_counts,
            'embedded_messages': embedded_count,
            'embedding_coverage_percent': round((embedded_count / total_messages) * 100, 2) if total_messages > 0 else 0,
            'recent_messages_24h': recent_messages
        }
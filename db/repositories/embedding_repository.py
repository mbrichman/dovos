"""
Repository for message embedding operations and vector similarity search.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from uuid import UUID
from sqlalchemy import desc, func, text
from sqlalchemy.orm import Session, joinedload
import numpy as np

from db.models.models import MessageEmbedding, Message, Conversation
from db.repositories.base_repository import BaseRepository


class EmbeddingRepository(BaseRepository[MessageEmbedding]):
    """Repository for message embedding operations and vector search."""
    
    def __init__(self, session: Session):
        super().__init__(session, MessageEmbedding)
        self.model_class = MessageEmbedding
    
    def create_or_update(self, message_id: UUID, embedding: List[float], 
                        model: str) -> MessageEmbedding:
        """Create or update an embedding for a message."""
        existing = self.session.query(MessageEmbedding)\
            .filter(MessageEmbedding.message_id == message_id)\
            .first()
        
        if existing:
            # Update existing embedding
            existing.embedding = embedding
            existing.model = model
            existing.updated_at = datetime.utcnow()
            self.session.flush()
            return existing
        else:
            # Create new embedding
            new_embedding = MessageEmbedding(
                message_id=message_id,
                embedding=embedding,
                model=model
            )
            self.session.add(new_embedding)
            self.session.flush()
            return new_embedding
    
    def get_by_message_id(self, message_id: UUID) -> Optional[MessageEmbedding]:
        """Get embedding by message ID."""
        return self.session.query(MessageEmbedding)\
            .filter(MessageEmbedding.message_id == message_id)\
            .first()
    
    def delete_by_message_id(self, message_id: UUID) -> bool:
        """Delete embedding by message ID."""
        embedding = self.get_by_message_id(message_id)
        if embedding:
            self.session.delete(embedding)
            self.session.flush()
            return True
        return False
    
    def search_similar(self, query_embedding: List[float], limit: int = 10, 
                      distance_threshold: float = 1.0,
                      conversation_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search using PostgreSQL's vector extension.
        Returns results in a format compatible with the legacy search API.
        """
        # Build the similarity search query
        # Using cosine distance (1 - cosine similarity)
        # Convert list to string format for PostgreSQL vector type
        query_vector_str = '[' + ','.join(map(str, query_embedding)) + ']'
        
        # Use string formatting instead of parameters for vector values
        if conversation_id:
            where_clause = f"e.embedding <=> '{query_vector_str}'::vector < :threshold AND m.conversation_id = :conversation_id"
            params = {
                'threshold': distance_threshold,
                'conversation_id': conversation_id,
                'limit': limit
            }
        else:
            where_clause = f"e.embedding <=> '{query_vector_str}'::vector < :threshold"
            params = {
                'threshold': distance_threshold,
                'limit': limit
            }
        
        sql_query = text(f"""
            SELECT 
                m.id as message_id,
                m.conversation_id,
                m.role,
                m.content,
                m.created_at,
                m.metadata as message_metadata,
                c.title as conversation_title,
                e.embedding <=> '{query_vector_str}'::vector as distance,
                1 - (e.embedding <=> '{query_vector_str}'::vector) as similarity
            FROM message_embeddings e
            JOIN messages m ON e.message_id = m.id
            JOIN conversations c ON m.conversation_id = c.id
            WHERE {where_clause}
            ORDER BY e.embedding <=> '{query_vector_str}'::vector ASC
            LIMIT :limit
        """)
        
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
                    'message_id': str(row.message_id),
                    'role': row.role,
                    'distance': float(row.distance),
                    'similarity': float(row.similarity)
                }
            })
        
        return messages
    
    def search_hybrid(self, query_embedding: List[float], text_query: str,
                     limit: int = 10, vector_weight: float = 0.7, 
                     text_weight: float = 0.3) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector similarity and full-text search.
        Results are ranked using a weighted combination of both scores.
        """
        # Convert list to string format for PostgreSQL vector type
        query_vector_str = '[' + ','.join(map(str, query_embedding)) + ']'
        
        sql_query = text(f"""
            WITH vector_results AS (
                SELECT 
                    m.id as message_id,
                    m.conversation_id,
                    m.role,
                    m.content,
                    m.created_at,
                    c.title as conversation_title,
                    (1 - (e.embedding <=> '{query_vector_str}'::vector)) as vector_score
                FROM message_embeddings e
                JOIN messages m ON e.message_id = m.id
                JOIN conversations c ON m.conversation_id = c.id
                WHERE e.embedding <=> '{query_vector_str}'::vector < 1.0
            ),
            text_results AS (
                SELECT 
                    m.id as message_id,
                    m.conversation_id,
                    m.role,
                    m.content,
                    m.created_at,
                    c.title as conversation_title,
                    ts_rank(m.message_search, plainto_tsquery('english', :text_query)) as text_score
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE m.message_search @@ plainto_tsquery('english', :text_query)
            ),
            combined_results AS (
                SELECT 
                    COALESCE(v.message_id, t.message_id) as message_id,
                    COALESCE(v.conversation_id, t.conversation_id) as conversation_id,
                    COALESCE(v.role, t.role) as role,
                    COALESCE(v.content, t.content) as content,
                    COALESCE(v.created_at, t.created_at) as created_at,
                    COALESCE(v.conversation_title, t.conversation_title) as conversation_title,
                    COALESCE(v.vector_score, 0) as vector_score,
                    COALESCE(t.text_score, 0) as text_score,
                    (:vector_weight * COALESCE(v.vector_score, 0) + :text_weight * COALESCE(t.text_score, 0)) as combined_score
                FROM vector_results v
                FULL OUTER JOIN text_results t ON v.message_id = t.message_id
            )
            SELECT * FROM combined_results
            ORDER BY combined_score DESC, created_at DESC
            LIMIT :limit
        """)
        
        params = {
            'text_query': text_query,
            'vector_weight': vector_weight,
            'text_weight': text_weight,
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
                    'message_id': str(row.message_id),
                    'role': row.role,
                    'vector_score': float(row.vector_score),
                    'text_score': float(row.text_score),
                    'combined_score': float(row.combined_score)
                }
            })
        
        return messages
    
    def get_coverage_stats(self) -> Dict[str, Any]:
        """Get embedding coverage statistics."""
        # Use the view we created in schema.sql
        sql_query = text("""
            SELECT * FROM embedding_coverage
        """)
        
        result = self.session.execute(sql_query).first()
        
        if result:
            return {
                'total_messages': result.total_messages,
                'embedded_messages': result.embedded_messages,
                'coverage_percent': float(result.coverage_percent),
                'stale_embeddings': result.stale_embeddings
            }
        else:
            return {
                'total_messages': 0,
                'embedded_messages': 0,
                'coverage_percent': 0.0,
                'stale_embeddings': 0
            }
    
    def get_embeddings_by_model(self, model: str, limit: int = 100) -> List[MessageEmbedding]:
        """Get embeddings created with a specific model."""
        return self.session.query(MessageEmbedding)\
            .filter(MessageEmbedding.model == model)\
            .order_by(desc(MessageEmbedding.updated_at))\
            .limit(limit)\
            .all()
    
    def delete_embeddings_by_model(self, model: str) -> int:
        """Delete all embeddings created with a specific model. Returns count deleted."""
        count = self.session.query(MessageEmbedding)\
            .filter(MessageEmbedding.model == model)\
            .count()
        
        self.session.query(MessageEmbedding)\
            .filter(MessageEmbedding.model == model)\
            .delete()
        
        self.session.flush()
        return count
    
    def get_model_stats(self) -> Dict[str, int]:
        """Get statistics grouped by embedding model."""
        result = self.session.query(
            MessageEmbedding.model,
            func.count(MessageEmbedding.message_id)
        ).group_by(MessageEmbedding.model).all()
        
        return dict(result)
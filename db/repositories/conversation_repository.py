"""
Repository for conversation operations.
"""

from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import desc, func, text
from sqlalchemy.orm import Session, selectinload

from db.models.models import Conversation, Message
from db.repositories.base_repository import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for conversation operations."""
    
    def __init__(self, session: Session):
        super().__init__(session, Conversation)
    
    def get_with_messages(self, conversation_id: UUID) -> Optional[Conversation]:
        """Get a conversation with all its messages loaded."""
        return self.session.query(Conversation)\
            .options(selectinload(Conversation.messages))\
            .filter(Conversation.id == conversation_id)\
            .first()
    
    def get_all_with_summary(self, limit: Optional[int] = None, offset: int = 0) -> List[dict]:
        """
        Get all conversations with summary information including message counts,
        date ranges, and preview content.
        
        Returns a list of dictionaries with conversation metadata similar to the
        legacy ChromaDB format for API compatibility.
        """
        # Use the view we created in schema.sql for efficient summaries
        query = text("""
            SELECT 
                c.id,
                c.title,
                c.created_at,
                c.updated_at,
                cs.message_count,
                cs.earliest_message_at,
                cs.latest_message_at,
                cs.preview
            FROM conversations c
            LEFT JOIN conversation_summaries cs ON c.id = cs.id
            ORDER BY c.updated_at DESC
            LIMIT :limit OFFSET :offset
        """)
        
        params = {
            'limit': limit or 10000,  # Large default for compatibility
            'offset': offset
        }
        
        result = self.session.execute(query, params)
        conversations = []
        
        for row in result:
            # Create a document-like structure for compatibility
            document_content = self._build_document_content(row.id, row.title, row.preview)
            
            conversations.append({
                'id': str(row.id),
                'document': document_content,
                'metadata': {
                    'title': row.title,
                    'source': 'postgres',
                    'message_count': row.message_count or 0,
                    'earliest_ts': row.earliest_message_at.isoformat() if row.earliest_message_at else None,
                    'latest_ts': row.latest_message_at.isoformat() if row.latest_message_at else None,
                    'conversation_id': str(row.id)
                }
            })
        
        return conversations
    
    def _build_document_content(self, conversation_id: UUID, title: str, preview: Optional[str]) -> str:
        """
        Build document content for a conversation. 
        This provides a preview that matches the legacy format.
        """
        if preview:
            return f"**{title}**\n\n{preview}"
        else:
            return f"**{title}**\n\nNo messages yet."
    
    def get_full_document_by_id(self, conversation_id: UUID) -> Optional[dict]:
        """
        Get a conversation as a full document with all messages formatted
        in the legacy style for API compatibility.
        """
        conversation = self.session.query(Conversation)\
            .options(selectinload(Conversation.messages))\
            .filter(Conversation.id == conversation_id)\
            .first()
        
        if not conversation:
            return None
        
        # Sort messages by creation time
        messages = sorted(conversation.messages, key=lambda m: m.created_at)
        
        # Build document content in legacy format
        document_lines = []
        
        for message in messages:
            timestamp_str = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            
            if message.role == 'user':
                document_lines.append(f"**You said** *(on {timestamp_str})*:\n\n{message.content}")
            elif message.role == 'assistant':
                document_lines.append(f"**Assistant said** *(on {timestamp_str})*:\n\n{message.content}")
            elif message.role == 'system':
                document_lines.append(f"**System** *(on {timestamp_str})*:\n\n{message.content}")
        
        document_content = "\n\n".join(document_lines)
        
        # Calculate date range
        earliest_ts = min(m.created_at for m in messages) if messages else conversation.created_at
        latest_ts = max(m.created_at for m in messages) if messages else conversation.updated_at
        
        return {
            'id': str(conversation.id),
            'document': document_content,
            'metadata': {
                'title': conversation.title,
                'source': 'postgres',
                'message_count': len(messages),
                'earliest_ts': earliest_ts.isoformat(),
                'latest_ts': latest_ts.isoformat(),
                'conversation_id': str(conversation.id)
            }
        }
    
    def search_by_title(self, title_query: str, limit: int = 10) -> List[Conversation]:
        """Search conversations by title using ILIKE."""
        return self.session.query(Conversation)\
            .filter(Conversation.title.ilike(f"%{title_query}%"))\
            .order_by(desc(Conversation.updated_at))\
            .limit(limit)\
            .all()
    
    def get_recent(self, days: int = 30, limit: int = 50) -> List[Conversation]:
        """Get conversations from the last N days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self.session.query(Conversation)\
            .filter(Conversation.updated_at >= cutoff_date)\
            .order_by(desc(Conversation.updated_at))\
            .limit(limit)\
            .all()
    
    def get_stats(self) -> dict:
        """Get conversation statistics."""
        total_conversations = self.count()
        
        # Get message count across all conversations
        total_messages = self.session.query(func.count(Message.id)).scalar() or 0
        
        # Get recent activity (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_conversations = self.session.query(func.count(Conversation.id))\
            .filter(Conversation.updated_at >= thirty_days_ago)\
            .scalar() or 0
        
        return {
            'total_conversations': total_conversations,
            'total_messages': total_messages,
            'recent_conversations': recent_conversations,
            'avg_messages_per_conversation': round(total_messages / total_conversations, 2) if total_conversations > 0 else 0
        }
"""
Repository for conversation operations.
"""

from typing import List, Optional, Tuple
from datetime import datetime, timedelta, timezone
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
            ORDER BY COALESCE(cs.latest_message_at, c.updated_at) DESC
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
        
        # Sort messages by creation time, then sequence (from metadata), then id
        # This ensures deterministic ordering even with identical timestamps
        def message_sort_key(m):
            # Extract sequence from metadata if available, otherwise use 0
            sequence = 0
            if m.message_metadata and isinstance(m.message_metadata, dict):
                try:
                    sequence = int(m.message_metadata.get('sequence', 0))
                except (ValueError, TypeError):
                    sequence = 0
            return (m.created_at, sequence, m.id)
        
        messages = sorted(conversation.messages, key=message_sort_key)
        
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
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
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
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent_conversations = self.session.query(func.count(Conversation.id))\
            .filter(Conversation.updated_at >= thirty_days_ago)\
            .scalar() or 0

        return {
            'total_conversations': total_conversations,
            'total_messages': total_messages,
            'recent_conversations': recent_conversations,
            'avg_messages_per_conversation': round(total_messages / total_conversations, 2) if total_conversations > 0 else 0
        }

    def get_timeline_histogram(self, bucket_count: int = 10) -> List[dict]:
        """Get conversation creation timeline as histogram buckets with source breakdown.

        Args:
            bucket_count: Number of time buckets to create

        Returns:
            List of dicts with 'date' and source counts
        """
        # Get earliest and latest conversation dates
        date_range = self.session.query(
            func.min(Conversation.created_at).label('earliest'),
            func.max(Conversation.created_at).label('latest')
        ).first()

        if not date_range.earliest or not date_range.latest:
            return []

        earliest = date_range.earliest
        latest = date_range.latest

        # Calculate time span and bucket size
        time_span = (latest - earliest).total_seconds()

        # Determine appropriate bucket size based on time span
        days_span = time_span / 86400

        if days_span <= 30:
            # Daily buckets for <= 30 days
            trunc_format = 'day'
        elif days_span <= 180:
            # Weekly buckets for <= 6 months
            trunc_format = 'week'
        elif days_span <= 730:
            # Monthly buckets for <= 2 years
            trunc_format = 'month'
        else:
            # Quarterly buckets for > 2 years
            trunc_format = 'month'  # PostgreSQL doesn't have quarter trunc, we'll group by month

        # Query conversations grouped by date buckets AND source
        # We need to join with messages to get the source from message metadata
        query = text(f"""
            WITH first_messages AS (
                SELECT
                    conversation_id,
                    metadata->>'source' as source,
                    ROW_NUMBER() OVER (PARTITION BY conversation_id ORDER BY created_at ASC) as rn
                FROM messages
            ),
            conversation_sources AS (
                SELECT
                    c.id,
                    c.created_at,
                    COALESCE(LOWER(fm.source), 'unknown') as source
                FROM conversations c
                LEFT JOIN first_messages fm ON c.id = fm.conversation_id AND fm.rn = 1
                WHERE c.created_at IS NOT NULL
            )
            SELECT
                DATE_TRUNC('{trunc_format}', created_at) as bucket_date,
                source,
                COUNT(*) as count
            FROM conversation_sources
            GROUP BY bucket_date, source
            ORDER BY bucket_date, source
        """)

        try:
            result = self.session.execute(query)

            # Organize data by date bucket
            buckets_map = {}
            for row in result:
                date_key = row.bucket_date.date().isoformat()
                if date_key not in buckets_map:
                    buckets_map[date_key] = {'date': date_key}

                # Normalize source names
                source = row.source if row.source else 'unknown'
                if source and isinstance(source, str):
                    source_lower = source.lower()
                    if 'claude' in source_lower:
                        source = 'claude'
                    elif 'chatgpt' in source_lower or 'gpt' in source_lower:
                        source = 'chatgpt'
                    elif 'openwebui' in source_lower or 'open-webui' in source_lower:
                        source = 'openwebui'
                    elif 'json' in source_lower:
                        source = 'json'
                    elif 'docx' in source_lower:
                        source = 'docx'
                    else:
                        source = 'unknown'
                else:
                    source = 'unknown'

                # Add to bucket, summing if same source appears multiple times
                if source in buckets_map[date_key]:
                    buckets_map[date_key][source] += int(row.count)
                else:
                    buckets_map[date_key][source] = int(row.count)

            # Convert to list and sort by date
            buckets = sorted(buckets_map.values(), key=lambda x: x['date'])

            return buckets
        except Exception as e:
            # Log error and return empty list
            import logging
            logging.error(f"Error getting timeline histogram: {e}")
            return []
    
    def delete_conversation_with_cascade(self, conversation_id: UUID) -> bool:
        """Delete a conversation and all its associated data (messages and embeddings).
        
        Returns True if deleted, False if not found.
        """
        conversation = self.get_by_id(conversation_id)
        if not conversation:
            return False
        
        # PostgreSQL will handle cascade deletion of messages and embeddings
        # due to foreign key constraints defined in the schema
        self.session.delete(conversation)
        self.session.flush()
        return True

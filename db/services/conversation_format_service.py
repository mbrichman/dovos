"""ConversationFormatService - Formats conversation data for different views

This service extracts formatting logic from ConversationController, following
the Single Responsibility Principle. It handles:
- List view formatting
- Detail view formatting  
- Search results formatting
- PostgreSQL-specific formatting
- Message and metadata operations
"""

import re
import markdown
from datetime import datetime
from typing import List, Dict, Any, Optional
from models.conversation_view_model import (
    extract_preview_content,
    parse_messages_from_document
)


class ConversationFormatService:
    """Service for formatting conversation data for different views"""
    
    def format_conversation_list(self, conversations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format conversations for list view
        
        Args:
            conversations: List of conversation dictionaries with fields:
                - id: Conversation ID
                - title: Conversation title
                - preview: Preview text
                - source: Source (claude, chatgpt, etc.)
                - created_at: Created datetime (optional)
                - updated_at: Updated datetime (optional)
                - message_count: Number of messages (optional)
        
        Returns:
            List of formatted conversations with structure:
                - id: Conversation ID
                - meta: Dict with title, source, earliest_ts, latest_ts, message_count
                - preview: Preview text
        """
        if not conversations:
            return []
        
        formatted = []
        for conv in conversations:
            formatted_conv = {
                'id': conv.get('id', ''),
                'meta': {
                    'title': conv.get('title') or 'Untitled Conversation',
                    'source': conv.get('source') or 'unknown',
                    'earliest_ts': self._format_timestamp(conv.get('created_at')) or '',
                    'latest_ts': self._format_timestamp(conv.get('updated_at')) or '',
                    'message_count': conv.get('message_count') or 0,
                    'relevance_display': 'N/A'
                },
                'preview': conv.get('preview') or ''
            }
            formatted.append(formatted_conv)
        
        return formatted
    
    def format_conversation_view(self, document: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Format a single conversation for detail view
        
        Args:
            document: Raw conversation document text
            metadata: Conversation metadata dict with fields:
                - title: Conversation title
                - source: Source (claude, chatgpt, etc.)
                - earliest_ts: Earliest timestamp
                - message_count: Number of messages
        
        Returns:
            Dict with keys:
                - conversation: Dict with 'meta' and 'document' keys
                - messages: List of parsed message dicts
                - assistant_name: Name of the assistant (Claude, ChatGPT, AI)
        """
        # Parse messages from document
        messages = self._parse_messages(document, metadata.get('source', ''))
        
        # Determine assistant name
        assistant_name = self._determine_assistant_name(
            document, 
            metadata.get('source', '').lower()
        )
        
        # Build conversation object
        conversation = {
            'meta': metadata,
            'document': document
        }
        
        return {
            'conversation': conversation,
            'messages': messages,
            'assistant_name': assistant_name
        }
    
    def format_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format search results for display
        
        Args:
            results: List of search result dicts with fields:
                - id: Result ID
                - title: Result title
                - content: Result content/preview
                - metadata: Result metadata dict
                - score: Relevance score (optional)
        
        Returns:
            List of formatted results with structure:
                - id: Result ID
                - meta: Dict with title, source, earliest_ts, relevance_score, relevance_display
                - preview: Preview text
        """
        if not results:
            return []
        
        formatted = []
        for result in results:
            metadata = result.get('metadata', {})
            score = result.get('score')
            
            formatted_result = {
                'id': result.get('id', ''),
                'meta': {
                    'title': result.get('title', 'Untitled'),
                    'source': metadata.get('source', 'unknown'),
                    'earliest_ts': metadata.get('earliest_ts', ''),
                    'latest_ts': metadata.get('latest_ts', ''),
                    'message_count': metadata.get('message_count', 0),
                    'relevance_score': score,
                    'relevance_display': f'{score:.3f}' if score is not None else 'N/A'
                },
                'preview': result.get('content', '')
            }
            formatted.append(formatted_result)
        
        return formatted
    
    # ===== Helper methods =====
    
    def _extract_preview(self, document: str, max_length: int = 200) -> str:
        """Extract clean preview text from document
        
        Args:
            document: Raw document text
            max_length: Maximum preview length
        
        Returns:
            Cleaned preview text, truncated to max_length
        """
        return extract_preview_content(document, max_length)
    
    def _parse_messages(self, document: str, source: str) -> List[Dict[str, Any]]:
        """Parse document into individual messages
        
        Args:
            document: Raw document text
            source: Source type (claude, chatgpt, etc.)
        
        Returns:
            List of message dicts with 'role', 'content', 'timestamp' keys
        """
        return parse_messages_from_document(document)
    
    def _determine_assistant_name(self, document: Optional[str], source: str) -> str:
        """Determine assistant name from source or document content
        
        Args:
            document: Raw document text (optional, can be None or empty)
            source: Source type (claude, chatgpt, etc.)
        
        Returns:
            Assistant name: 'Claude', 'ChatGPT', or 'AI'
        """
        source_lower = source.lower() if source else ''
        
        if source_lower == 'claude':
            return 'Claude'
        elif source_lower == 'chatgpt':
            return 'ChatGPT'
        else:
            # Try to detect from document content if available
            if document:
                if '**Claude said**' in document or '**Claude**:' in document:
                    return 'Claude'
                elif '**ChatGPT said**' in document or '**ChatGPT**:' in document:
                    return 'ChatGPT'
            return 'AI'
    
    def _format_timestamp(self, dt: Optional[datetime]) -> Optional[str]:
        """Format datetime to string
        
        Args:
            dt: Datetime object or None
        
        Returns:
            Formatted timestamp string or None
        """
        if dt is None:
            return None
        
        if isinstance(dt, datetime):
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        
        return None
    
    # ===== PostgreSQL-specific formatting methods =====
    
    def format_postgres_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format PostgreSQL search results for legacy UI
        
        Args:
            results: List of search result dicts with fields:
                - content: Result content/preview
                - title: Result title (optional)
                - date: Result date (optional)
                - metadata: Result metadata dict (optional)
                - source: Source at top level (optional)
        
        Returns:
            List of formatted items with structure:
                - id: Result ID
                - preview: Preview text
                - meta: Dict with title, source, timestamps, relevance_display
        """
        items = []
        for result in results:
            metadata = result.get('metadata', {})
            
            # Extract and normalize source
            source = metadata.get('source') or result.get('source') or 'unknown'
            if source and isinstance(source, str):
                source_lower = source.lower()
                if 'claude' in source_lower:
                    source = 'claude'
                elif 'chatgpt' in source_lower or 'gpt' in source_lower:
                    source = 'chatgpt'
            
            item = {
                'id': metadata.get('conversation_id', metadata.get('id', 'unknown')),
                'preview': result.get('content', ''),
                'meta': {
                    'title': result.get('title', metadata.get('title', 'Untitled')),
                    'source': source,
                    'earliest_ts': result.get('date', metadata.get('earliest_ts', '')),
                    'latest_ts': metadata.get('latest_ts', result.get('date', '')),
                    'relevance_display': 'N/A'
                }
            }
            items.append(item)
        
        return items
    
    def format_postgres_list_results(self, conversations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format paginated conversation results for list view
        
        Args:
            conversations: List of conversation dicts with fields:
                - id: Conversation ID
                - title: Conversation title
                - preview: Preview text
                - source: Source type
                - latest_ts: Latest timestamp (optional)
        
        Returns:
            List of formatted items with structure:
                - id: Conversation ID
                - preview: Preview text
                - meta: Dict with title, source, timestamps, relevance_display
        """
        items = []
        for conv in conversations:
            # Normalize source value
            source = conv.get('source', 'unknown')
            if source:
                source = str(source).strip().lower()
            else:
                source = 'unknown'
            
            # Handle empty string after stripping
            if not source:
                source = 'unknown'
            
            item = {
                'id': conv['id'],
                'preview': conv['preview'],
                'meta': {
                    'title': conv['title'],
                    'source': source,
                    'earliest_ts': conv.get('latest_ts', ''),
                    'latest_ts': conv.get('latest_ts', ''),
                    'relevance_display': 'N/A'
                }
            }
            items.append(item)
        return items
    
    def calculate_source_breakdown(self, all_conversations: Dict[str, Any]) -> Dict[str, int]:
        """Count conversations by source
        
        Args:
            all_conversations: Dict with 'metadatas' key containing list of metadata dicts
        
        Returns:
            Dict mapping source names to counts
        """
        source_counts = {}
        
        if not all_conversations or not all_conversations.get('metadatas'):
            return source_counts
        
        for metadata in all_conversations.get('metadatas', []):
            # Get source, preferring original_source
            source = metadata.get('original_source', metadata.get('source', 'unknown')).lower()
            
            # Map postgres -> imported
            if source == 'postgres':
                source = 'imported'
            
            if source not in source_counts:
                source_counts[source] = 0
            source_counts[source] += 1
        
        return source_counts
    
    # ===== Message and metadata operations =====
    
    def extract_source_from_messages(self, db_messages: List[Any]) -> str:
        """Extract source from message metadata
        
        Args:
            db_messages: List of message objects with message_metadata attribute
        
        Returns:
            Source string (defaults to 'unknown' if not found)
        """
        if db_messages and db_messages[0].message_metadata:
            return db_messages[0].message_metadata.get('source', 'unknown')
        return 'unknown'
    
    def format_db_messages_for_view(self, db_messages: List[Any]) -> List[Dict[str, Any]]:
        """Format database messages for view template
        
        Args:
            db_messages: List of message objects from database with fields:
                - role: Message role (user/assistant)
                - content: Message content (markdown)
                - created_at: Created timestamp (optional)
                - message_metadata: Message metadata dict (optional)
        
        Returns:
            List of formatted message dicts with fields:
                - role: Message role
                - content: HTML-rendered content
                - timestamp: Formatted timestamp string
                - attachments: List of attachments (if present)
        """
        messages = []
        for msg in db_messages:
            # Convert markdown content to HTML
            # Note: Using fenced_code without codehilite to preserve language markers for Prism.js
            html_content = markdown.markdown(
                msg.content,
                extensions=["extra", "tables", "fenced_code", "nl2br"]
            )
            
            msg_dict = {
                'role': msg.role,
                'content': html_content,
                'timestamp': msg.created_at.strftime('%Y-%m-%d %H:%M:%S') if msg.created_at else None
            }
            
            # Extract attachments from metadata if present
            if msg.message_metadata and msg.message_metadata.get('attachments'):
                msg_dict['attachments'] = msg.message_metadata['attachments']
            
            messages.append(msg_dict)
        
        return messages

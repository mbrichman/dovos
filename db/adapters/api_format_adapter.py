"""
API Format Adapter for PostgreSQL Backend

This adapter translates PostgreSQL data into ChromaDB-compatible API response formats.
It maintains backward compatibility with existing API clients that expect ChromaDB-style
responses (documents, metadatas, ids format) while using PostgreSQL internally.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import text

from db.services.search_service import SearchService, SearchConfig
from db.services.message_service import MessageService
from db.repositories.unit_of_work import get_unit_of_work

logger = logging.getLogger(__name__)


class APIFormatAdapter:
    """
    Adapter that translates PostgreSQL data into ChromaDB-compatible API formats.
    
    This maintains backward compatibility with existing API clients while using
    the PostgreSQL backend with SearchService, MessageService, and repository patterns.
    """
    
    def __init__(self):
        self.search_service = SearchService()
        self.message_service = MessageService()
    
    # ===== CONVERSATION METHODS =====
    
    def get_conversations_summary(self, limit: int = 9999, offset: int = 0, 
                                  source_filter: str = 'all', date_filter: str = 'all',
                                  sort_order: str = 'newest') -> Dict[str, Any]:
        """
        Get conversations with summary data only (optimized for list view).
        Uses the conversation_summaries view instead of loading all messages.
        
        This is much faster than get_all_conversations() for displaying lists.
        
        Args:
            limit: Max number of results
            offset: Number of results to skip
            source_filter: Filter by source (all, chatgpt, claude, docx)
            date_filter: Filter by date (all, today, week, month, year)
            sort_order: Sort order (newest, oldest, alphabetical)
        """
        with get_unit_of_work() as uow:
            # Build dynamic WHERE and ORDER BY clauses
            where_clauses = []
            params = {'limit': limit, 'offset': offset}
            
            # Source filter
            if source_filter != 'all':
                where_clauses.append("""
                    (SELECT m.metadata->>'source' 
                     FROM messages m 
                     WHERE m.conversation_id = c.id 
                     ORDER BY m.created_at LIMIT 1) = :source
                """)
                params['source'] = source_filter
            
            # Date filter
            if date_filter != 'all':
                date_map = {
                    'today': "COALESCE(cs.latest_message_at, c.updated_at) >= CURRENT_DATE",
                    'week': "COALESCE(cs.latest_message_at, c.updated_at) >= CURRENT_DATE - INTERVAL '7 days'",
                    'month': "COALESCE(cs.latest_message_at, c.updated_at) >= CURRENT_DATE - INTERVAL '30 days'",
                    'year': "COALESCE(cs.latest_message_at, c.updated_at) >= CURRENT_DATE - INTERVAL '365 days'"
                }
                if date_filter in date_map:
                    where_clauses.append(date_map[date_filter])
            
            # Sort order
            order_map = {
                'newest': 'COALESCE(cs.latest_message_at, c.updated_at) DESC',
                'oldest': 'COALESCE(cs.earliest_message_at, c.created_at) ASC',
                'alphabetical': 'c.title ASC'
            }
            order_by = order_map.get(sort_order, order_map['newest'])
            
            # Build WHERE clause
            where_sql = ' AND ' + ' AND '.join(where_clauses) if where_clauses else ''
            
            # Use raw SQL to query the conversation_summaries view
            query = text(f"""
                SELECT 
                    c.id,
                    c.title,
                    c.created_at,
                    c.updated_at,
                    cs.message_count,
                    cs.earliest_message_at,
                    cs.latest_message_at,
                    cs.preview,
                    -- Get source from first message metadata
                    (SELECT m.metadata->>'source' 
                     FROM messages m 
                     WHERE m.conversation_id = c.id 
                     ORDER BY m.created_at LIMIT 1) as source
                FROM conversations c
                LEFT JOIN conversation_summaries cs ON c.id = cs.id
                WHERE 1=1 {where_sql}
                ORDER BY {order_by}
                LIMIT :limit OFFSET :offset
            """)
            
            result = uow.session.execute(query, params)
            
            documents = []
            metadatas = []
            ids = []
            
            for row in result:
                # Use preview instead of building full document
                # Don't include title in preview since it's shown separately in UI
                preview = row.preview if row.preview else "No messages yet."
                document = preview
                
                metadata = {
                    "id": str(row.id),
                    "title": row.title,
                    "source": row.source or "unknown",
                    "message_count": row.message_count or 0,
                    "earliest_ts": row.earliest_message_at.isoformat() if row.earliest_message_at else row.created_at.isoformat(),
                    "latest_ts": row.latest_message_at.isoformat() if row.latest_message_at else row.updated_at.isoformat(),
                    "is_chunk": False,
                    "conversation_id": str(row.id)
                }
                
                documents.append(document)
                metadatas.append(metadata)
                ids.append(str(row.id))
            
            return {
                "documents": documents,
                "metadatas": metadatas,
                "ids": ids
            }
    
    def get_all_conversations(self, include: List[str] = None, limit: int = 9999) -> Dict[str, Any]:
        """
        Get all conversations in ChromaDB-compatible format.
        
        Returns:
            Dict with 'documents', 'metadatas', 'ids' arrays (ChromaDB format)
        """
        include = include or ["documents", "metadatas", "ids"]
        
        with get_unit_of_work() as uow:
            # Get all conversations with their messages
            conversations = uow.conversations.get_all(limit=limit)
            
            documents = []
            metadatas = []
            ids = []
            
            for conv in conversations:
                # Get messages for this conversation
                messages = uow.messages.get_by_conversation(conv.id)
                
                # Build the document content (concatenated messages)
                document_parts = []
                message_count = len(messages)
                earliest_ts = None
                latest_ts = None
                
                # Extract source from first message's metadata if available
                source = "unknown"
                if messages and messages[0].message_metadata:
                    source = messages[0].message_metadata.get('source', 'unknown')
                
                for msg in messages:
                    # Format timestamp
                    timestamp_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Format message based on role and source
                    if msg.role == 'user':
                        document_parts.append(f"**You said** *(on {timestamp_str})*:\n\n{msg.content}")
                    elif msg.role == 'assistant':
                        # Use actual source name if available (ChatGPT, Claude, OpenWebUI, etc.)
                        if source.lower() == 'chatgpt':
                            document_parts.append(f"**ChatGPT said** *(on {timestamp_str})*:\n\n{msg.content}")
                        elif source.lower() == 'claude':
                            document_parts.append(f"**Claude said** *(on {timestamp_str})*:\n\n{msg.content}")
                        elif source.lower() == 'openwebui':
                            document_parts.append(f"**OpenWebUI said** *(on {timestamp_str})*:\n\n{msg.content}")
                        else:
                            document_parts.append(f"**Assistant said** *(on {timestamp_str})*:\n\n{msg.content}")
                    elif msg.role == 'system':
                        document_parts.append(f"**System** *(on {timestamp_str})*:\n\n{msg.content}")
                    else:
                        document_parts.append(f"**{msg.role.capitalize()}** *(on {timestamp_str})*:\n\n{msg.content}")
                    
                    # Track timestamps
                    if earliest_ts is None or msg.created_at < earliest_ts:
                        earliest_ts = msg.created_at
                    if latest_ts is None or msg.created_at > latest_ts:
                        latest_ts = msg.created_at
                
                # Build complete document
                document = "\n\n---\n\n".join(document_parts)
                
                # Build metadata in legacy format
                metadata = {
                    "id": str(conv.id),
                    "title": conv.title,
                    "source": source,  # Use actual source from import
                    "message_count": message_count,
                    "earliest_ts": earliest_ts.isoformat() if earliest_ts else conv.created_at.isoformat(),
                    "latest_ts": latest_ts.isoformat() if latest_ts else conv.updated_at.isoformat(),
                    "is_chunk": False,
                    "conversation_id": str(conv.id)
                }
                
                documents.append(document)
                metadatas.append(metadata)
                ids.append(str(conv.id))
        
        result = {}
        if "documents" in include:
            result["documents"] = documents
        if "metadatas" in include:
            result["metadatas"] = metadatas  
        if "ids" in include:
            result["ids"] = ids
            
        return result
    
    def get_conversation_by_id(self, doc_id: str) -> Dict[str, Any]:
        """Get a single conversation by ID in legacy format."""
        try:
            conv_uuid = UUID(doc_id)
        except ValueError:
            # Handle legacy ID formats like "chat-0", "docx-0"
            return self._handle_legacy_id_format(doc_id)
        
        with get_unit_of_work() as uow:
            conversation = uow.conversations.get_by_id(conv_uuid)
            if not conversation:
                return {"documents": [], "metadatas": [], "ids": []}
            
            # Get messages for this conversation
            messages = uow.messages.get_by_conversation(conv_uuid)
            
            # Build document content
            document_parts = []
            message_count = len(messages)
            earliest_ts = None
            latest_ts = None
            
            # Extract source from first message's metadata if available
            source = "unknown"
            if messages and messages[0].message_metadata:
                source = messages[0].message_metadata.get('source', 'unknown')
            
            for msg in messages:
                timestamp_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                
                if msg.role == 'user':
                    document_parts.append(f"**You said** *(on {timestamp_str})*:\n\n{msg.content}")
                elif msg.role == 'assistant':
                    # Use actual source name if available (ChatGPT, Claude, OpenWebUI, etc.)
                    if source.lower() == 'chatgpt':
                        document_parts.append(f"**ChatGPT said** *(on {timestamp_str})*:\n\n{msg.content}")
                    elif source.lower() == 'claude':
                        document_parts.append(f"**Claude said** *(on {timestamp_str})*:\n\n{msg.content}")
                    elif source.lower() == 'openwebui':
                        document_parts.append(f"**OpenWebUI said** *(on {timestamp_str})*:\n\n{msg.content}")
                    else:
                        document_parts.append(f"**Assistant said** *(on {timestamp_str})*:\n\n{msg.content}")
                elif msg.role == 'system':
                    document_parts.append(f"**System** *(on {timestamp_str})*:\n\n{msg.content}")
                else:
                    document_parts.append(f"**{msg.role.capitalize()}** *(on {timestamp_str})*:\n\n{msg.content}")
                
                if earliest_ts is None or msg.created_at < earliest_ts:
                    earliest_ts = msg.created_at
                if latest_ts is None or msg.created_at > latest_ts:
                    latest_ts = msg.created_at
            
            document = "\n\n---\n\n".join(document_parts)
            
            # Extract source from first message's metadata if available
            source = "unknown"
            if messages and messages[0].message_metadata:
                source = messages[0].message_metadata.get('source', 'unknown')
            
            metadata = {
                "id": str(conversation.id),
                "title": conversation.title,
                "source": source,  # Use actual source from import
                "message_count": message_count,
                "earliest_ts": earliest_ts.isoformat() if earliest_ts else conversation.created_at.isoformat(),
                "latest_ts": latest_ts.isoformat() if latest_ts else conversation.updated_at.isoformat(),
                "is_chunk": False,
                "conversation_id": str(conversation.id)
            }
            
            return {
                "documents": [document],
                "metadatas": [metadata],
                "ids": [str(conversation.id)]
            }
    
    def _handle_legacy_id_format(self, doc_id: str) -> Dict[str, Any]:
        """Handle legacy ID formats like 'chat-0', 'docx-0'."""
        if not doc_id.startswith(("chat-", "docx-")):
            return {"documents": [], "metadatas": [], "ids": []}
        
        try:
            idx = int(doc_id.split("-")[1])
        except (ValueError, IndexError):
            return {"documents": [], "metadatas": [], "ids": []}
        
        # Get all conversations and select by index
        all_conversations = self.get_all_conversations(include=["documents", "metadatas", "ids"])
        
        if (all_conversations.get("documents") and 
            idx < len(all_conversations["documents"])):
            
            return {
                "documents": [all_conversations["documents"][idx]],
                "metadatas": [all_conversations["metadatas"][idx]],
                "ids": [all_conversations["ids"][idx]]
            }
        
        return {"documents": [], "metadatas": [], "ids": []}
    
    # ===== SEARCH METHODS =====
    
    def search_conversations(self, 
                           query_text: str,
                           n_results: int = 10,
                           date_range: Optional[Tuple[datetime, datetime]] = None,
                           keyword_search: bool = False,
                           search_type: str = "auto") -> Dict[str, Any]:
        """
        Search conversations using the new SearchService but return legacy format.
        
        Args:
            query_text: Search query
            n_results: Number of results to return
            date_range: Optional date range filter
            keyword_search: Legacy parameter for backward compatibility
            search_type: "auto", "fts", "semantic", or "hybrid"
            
        Returns:
            Dict in legacy ChromaDB format with documents, metadatas, distances
        """
        # Map search types to SearchService methods
        # Handle both "fts" and "keyword" for backward compatibility
        if search_type in ("fts", "keyword") or keyword_search:
            results = self.search_service.search_fts_only(query_text, limit=n_results)
        elif search_type == "semantic":
            results = self.search_service.search_vector_only(query_text, limit=n_results)
        elif search_type == "hybrid":
            results = self.search_service.search(query_text, limit=n_results)
        else:  # auto
            # Auto mode: try hybrid first, fallback to FTS if no embeddings
            stats = self.search_service.get_search_stats()
            if stats["hybrid_search_available"]:
                results = self.search_service.search(query_text, limit=n_results)
            else:
                results = self.search_service.search_fts_only(query_text, limit=n_results)
        
        # Apply date range filter if specified
        if date_range and results:
            start_date, end_date = date_range
            filtered_results = []
            
            for result in results:
                try:
                    result_date = datetime.fromisoformat(result.created_at.replace("Z", "+00:00"))
                    if start_date <= result_date <= end_date:
                        filtered_results.append(result)
                except:
                    # If date parsing fails, include the result
                    filtered_results.append(result)
            
            results = filtered_results
        
        # Convert to legacy format
        if not results:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        
        # Group results by conversation for legacy compatibility
        conversation_map = {}
        for result in results:
            conv_id = result.conversation_id
            if conv_id not in conversation_map:
                conversation_map[conv_id] = []
            conversation_map[conv_id].append(result)
        
        documents = []
        metadatas = []
        distances = []
        
        for conv_id, conv_results in conversation_map.items():
            # Take the best result from this conversation
            best_result = max(conv_results, key=lambda x: x.combined_score)
            legacy_result = best_result.to_legacy_format()
            
            documents.append(legacy_result['document'])
            metadatas.append(legacy_result['metadata'])
            
            # Convert similarity/score to distance (lower is better)
            if best_result.similarity is not None:
                distance = 1.0 - best_result.similarity
            elif best_result.combined_score is not None:
                distance = 1.0 - min(1.0, best_result.combined_score)
            else:
                distance = 0.5  # Default middle distance
            
            distances.append(distance)
        
        return {
            "documents": [documents],
            "metadatas": [metadatas], 
            "distances": [distances]
        }
    
    def search(self, 
               query_text: str,
               n_results: int = 10,
               keyword_search: bool = False) -> Dict[str, Any]:
        """Legacy search method for backward compatibility."""
        search_type = "fts" if keyword_search else "auto"
        return self.search_conversations(
            query_text=query_text,
            n_results=n_results,
            keyword_search=keyword_search,
            search_type=search_type
        )
    
    # ===== STATS AND HEALTH METHODS =====
    
    def get_count(self) -> int:
        """Get total number of conversations."""
        with get_unit_of_work() as uow:
            return uow.conversations.count()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics in legacy format."""
        # Get conversation count (not message count)
        conversation_count = self.get_count()
        
        # Map to legacy format
        return {
            "status": "healthy",
            "collection_name": "chat_history",  # Legacy collection name
            "document_count": conversation_count,
            "embedding_model": "all-MiniLM-L6-v2"
        }
    
    def get_health(self) -> Dict[str, Any]:
        """Get health status for /api/rag/health endpoint."""
        return self.get_stats()
    
    # ===== MANAGEMENT METHODS =====
    
    def clear_database(self) -> Dict[str, Any]:
        """Clear the entire database."""
        try:
            with get_unit_of_work() as uow:
                # Count first, then delete
                conversations_count = uow.session.execute(
                    text("SELECT COUNT(*) FROM conversations")
                ).scalar()
                
                jobs_count = uow.session.execute(
                    text("SELECT COUNT(*) FROM jobs")
                ).scalar()
                
                # Delete all data (conversations cascade to messages and embeddings)
                uow.session.execute(text("DELETE FROM conversations"))
                
                # Clean up orphaned jobs
                uow.session.execute(text("DELETE FROM jobs"))
                
                deleted_conversations = conversations_count
                deleted_jobs = jobs_count
                
            return {
                "status": "success",
                "message": f"Database cleared successfully. Deleted {deleted_conversations} conversations and {deleted_jobs} jobs."
            }
            
        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            return {
                "status": "error", 
                "message": f"Failed to clear database: {str(e)}"
            }
    
    # ===== RAG QUERY METHOD =====
    
    def rag_query(self, 
                  query: str,
                  n_results: int = 5,
                  search_type: str = "semantic") -> Dict[str, Any]:
        """
        RAG query endpoint compatible with OpenWebUI integration.
        
        Returns results in the format expected by OpenWebUI.
        """
        try:
            # Use SearchService based on search_type
            if search_type == "semantic":
                results = self.search_service.search_vector_only(query, limit=n_results)
            elif search_type == "keyword":
                results = self.search_service.search_fts_only(query, limit=n_results)
            else:
                # Default to hybrid
                results = self.search_service.search(query, limit=n_results)
            
            # Format for OpenWebUI
            formatted_results = []
            for i, result in enumerate(results):
                # Extract a preview of the content
                preview = result.content[:500] + "..." if len(result.content) > 500 else result.content
                
                # Calculate relevance score
                if result.similarity is not None:
                    relevance = result.similarity
                    distance = 1.0 - result.similarity
                elif result.combined_score is not None:
                    relevance = min(1.0, result.combined_score)
                    distance = 1.0 - relevance
                else:
                    relevance = 0.5
                    distance = 0.5
                
                formatted_results.append({
                    "id": result.conversation_id,
                    "title": result.conversation_title,
                    "content": result.content,
                    "preview": preview,
                    "source": "postgres",
                    "distance": distance,
                    "relevance": relevance,
                    "metadata": {
                        "id": result.conversation_id,
                        "title": result.conversation_title,
                        "source": "postgres",
                        "earliest_ts": result.created_at,
                        "latest_ts": result.created_at,
                        "message_count": 1,
                        "conversation_id": result.conversation_id,
                        "message_id": result.message_id,
                        "role": result.role
                    }
                })
            
            return {
                "query": query,
                "search_type": search_type,
                "results": formatted_results
            }
            
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            raise
    
    # ===== EXPORT METHODS =====
    
    def export_to_openwebui(self, doc_id: str) -> Dict[str, Any]:
        """Export conversation to OpenWebUI format."""
        import requests
        import config
        from uuid import UUID
        
        # Import the converter functions
        from scripts.utils.claude_to_openwebui_converter import convert_conversation
        
        try:
            # Try to get raw messages from database
            try:
                conv_uuid = UUID(doc_id)
                with get_unit_of_work() as uow:
                    conversation = uow.conversations.get_by_id(conv_uuid)
                    if not conversation:
                        return {
                            "success": False,
                            "error": "Conversation not found"
                        }
                    
                    # Get raw messages from database and convert to dicts while in session
                    db_messages = uow.messages.get_by_conversation(conv_uuid)
                    messages = []
                    for msg in db_messages:
                        messages.append({
                            "role": msg.role,
                            "content": msg.content
                        })
                    
                    metadata = {
                        "title": conversation.title,
                        "earliest_ts": conversation.created_at.isoformat() if conversation.created_at else "",
                        "latest_ts": conversation.updated_at.isoformat() if conversation.updated_at else ""
                    }
            except (ValueError, TypeError):
                # Fallback to legacy ID format or legacy method
                doc_result = self.get_conversation_by_id(doc_id)
                if not doc_result or not doc_result.get("documents"):
                    return {
                        "success": False,
                        "error": "Conversation not found"
                    }
                
                # Parse the conversation into messages
                document = doc_result["documents"][0]
                metadata = doc_result["metadatas"][0] if doc_result.get("metadatas") else {}
                messages = self._parse_conversation_messages(document, metadata)
            
            # Create chat_messages in the format expected by the converter
            chat_messages = []
            for msg in messages:
                # Handle both dict and object formats
                role = msg.get("role") if isinstance(msg, dict) else msg.role
                content = msg.get("content") if isinstance(msg, dict) else msg.content
                
                chat_msg = {
                    "sender": "human" if role == "user" else "assistant" if role == "assistant" else role,
                    "text": content,
                    "created_at": metadata.get("earliest_ts", "")
                }
                chat_messages.append(chat_msg)
            
            # Build conversation object
            claude_conv = {
                "name": metadata.get("title", "Untitled Conversation"),
                "created_at": metadata.get("earliest_ts", ""),
                "updated_at": metadata.get("latest_ts") or metadata.get("earliest_ts", ""),
                "chat_messages": chat_messages
            }
            
            # Convert to OpenWebUI format
            try:
                openwebui_conv = convert_conversation(claude_conv)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Conversion failed: {str(e)}"
                }
            
            # Send to OpenWebUI server using config values
            headers = {
                "Authorization": f"Bearer {config.OPENWEBUI_API_KEY}",
                "Content-Type": "application/json"
            }
            
            try:
                # OpenWebUI's chat creation endpoint
                response = requests.post(
                    f"{config.OPENWEBUI_URL}/api/v1/chats/new",
                    headers=headers,
                    json=openwebui_conv,
                    timeout=30
                )
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "message": "Conversation exported to OpenWebUI successfully"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"OpenWebUI API error: {response.status_code}",
                        "detail": response.text
                    }
                    
            except requests.exceptions.RequestException as e:
                return {
                    "success": False,
                    "error": f"Failed to connect to OpenWebUI: {str(e)}"
                }
        
        except Exception as e:
            logger.error(f"Export to OpenWebUI failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_conversation_messages(self, document: str, metadata: Dict) -> List[Dict]:
        """Parse conversation document into messages."""
        messages = []
        
        # Split by message separators (both formats use ** for role markers)
        lines = document.split("\n")
        current_role = None
        current_content = []
        
        for line in lines:
            if "**" in line and "said**" in line.lower():
                # This is a role marker line
                if current_content and current_role:
                    messages.append({
                        "role": current_role,
                        "content": "\n".join(current_content).strip()
                    })
                    current_content = []
                
                # Extract role
                if "You said" in line or "user" in line.lower():
                    current_role = "user"
                elif "ChatGPT said" in line or "Claude said" in line or "assistant" in line.lower():
                    current_role = "assistant"
                else:
                    current_role = "system"
            elif current_role and line.strip():  # Only add non-empty lines
                current_content.append(line)
        
        # Add final message
        if current_content and current_role:
            messages.append({
                "role": current_role,
                "content": "\n".join(current_content).strip()
            })
        
        return messages
    
    # ===== SETTINGS METHODS =====
    
    def get_all_settings(self) -> Dict[str, str]:
        """Get all settings from database."""
        try:
            with get_unit_of_work() as uow:
                return uow.settings.get_all_as_dict()
        except Exception as e:
            logger.error(f"Failed to get settings: {e}")
            return {}
    
    def get_setting(self, key: str) -> Optional[str]:
        """Get a single setting by key."""
        try:
            with get_unit_of_work() as uow:
                return uow.settings.get_value(key)
        except Exception as e:
            logger.error(f"Failed to get setting {key}: {e}")
            return None
    
    def set_setting(self, key: str, value: str) -> bool:
        """Save or update a setting."""
        try:
            with get_unit_of_work() as uow:
                uow.settings.create_or_update(key, value)
            return True
        except Exception as e:
            logger.error(f"Failed to set setting {key}: {e}")
            return False


# Global adapter instance
_adapter = None

def get_api_format_adapter() -> APIFormatAdapter:
    """Get the global API format adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = APIFormatAdapter()
    return _adapter

# Backward compatibility alias
def get_legacy_adapter() -> APIFormatAdapter:
    """Backward compatibility alias for get_api_format_adapter()."""
    return get_api_format_adapter()

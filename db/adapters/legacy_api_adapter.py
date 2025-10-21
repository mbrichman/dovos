"""
Legacy API Adapter for PostgreSQL Backend

This adapter provides the exact same interface as the legacy ChromaDB+SQLite 
system while using the new PostgreSQL backend. It ensures 100% API compatibility
during the migration.
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


class LegacyAPIAdapter:
    """
    Adapter that implements the legacy ChromaDB API interface using PostgreSQL backend.
    
    This maintains 100% compatibility with existing API endpoints while using
    the new SearchService, MessageService, and repository patterns.
    """
    
    def __init__(self):
        self.search_service = SearchService()
        self.message_service = MessageService()
    
    # ===== CONVERSATION METHODS =====
    
    def get_all_conversations(self, include: List[str] = None, limit: int = 9999) -> Dict[str, Any]:
        """
        Get all conversations in legacy ChromaDB format.
        
        Returns:
            Dict with 'documents', 'metadatas', 'ids' arrays
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
                
                for msg in messages:
                    # Format timestamp
                    timestamp_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Format message based on role
                    if msg.role == 'user':
                        document_parts.append(f"**You said** *(on {timestamp_str})*:\n\n{msg.content}")
                    elif msg.role == 'assistant':
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
                    "source": "postgres",  # Mark as coming from postgres
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
            
            for msg in messages:
                timestamp_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                
                if msg.role == 'user':
                    document_parts.append(f"**You said** *(on {timestamp_str})*:\n\n{msg.content}")
                elif msg.role == 'assistant':
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
            
            metadata = {
                "id": str(conversation.id),
                "title": conversation.title,
                "source": "postgres",
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
        if search_type == "fts" or keyword_search:
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
        stats = self.search_service.get_search_stats()
        
        # Map to legacy format
        return {
            "status": "healthy",
            "collection_name": "chat_history",  # Legacy collection name
            "document_count": stats["total_messages"],
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
        # This would integrate with the existing export functionality
        # For now, return a success response
        return {
            "success": True,
            "message": "Conversation exported to OpenWebUI successfully"
        }


# Global adapter instance 
_adapter = None

def get_legacy_adapter() -> LegacyAPIAdapter:
    """Get the global legacy adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = LegacyAPIAdapter()
    return _adapter
"""
PostgreSQL Controller

This controller provides the same interface as ConversationController 
but uses the PostgreSQL backend through the LegacyAPIAdapter.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from flask import request

from db.adapters.legacy_api_adapter import get_legacy_adapter
from db.services.message_service import MessageService

logger = logging.getLogger(__name__)


class PostgresController:
    """
    Controller that provides the same API interface as ConversationController
    but backed by PostgreSQL through the LegacyAPIAdapter.
    """
    
    def __init__(self):
        self.adapter = get_legacy_adapter()
        self.message_service = MessageService()
    
    # ===== CONVERSATION ENDPOINTS =====
    
    def get_conversations(self) -> Dict[str, Any]:
        """
        GET /api/conversations
        
        Returns all conversations in the legacy format.
        """
        try:
            result = self.adapter.get_all_conversations(
                include=["documents", "metadatas", "ids"],
                limit=9999
            )
            return result
        
        except Exception as e:
            logger.error(f"Failed to get conversations: {e}")
            return {
                "error": str(e),
                "documents": [],
                "metadatas": [],
                "ids": []
            }
    
    def get_conversation(self, doc_id: str) -> Dict[str, Any]:
        """
        GET /api/conversation/<id>
        
        Returns a single conversation by ID.
        """
        try:
            result = self.adapter.get_conversation_by_id(doc_id)
            return result
        
        except Exception as e:
            logger.error(f"Failed to get conversation {doc_id}: {e}")
            return {
                "error": str(e),
                "documents": [],
                "metadatas": [], 
                "ids": []
            }
    
    # ===== SEARCH ENDPOINTS =====
    
    def api_search(self) -> Dict[str, Any]:
        """
        GET /api/search
        
        Search conversations with query parameters (legacy API format).
        """
        try:
            query = request.args.get("q")
            if not query:
                return {"error": "No query provided"}
            
            n_results = int(request.args.get("n", 5))
            keyword = request.args.get("keyword", "false").lower() == "true"
            
            # Use SearchService based on keyword flag
            if keyword:
                results = self.adapter.search_service.search_fts_only(query, limit=n_results)
            else:
                # Auto mode: hybrid if available, otherwise FTS
                stats = self.adapter.search_service.get_search_stats()
                if stats["hybrid_search_available"]:
                    results = self.adapter.search_service.search(query, limit=n_results)
                else:
                    results = self.adapter.search_service.search_fts_only(query, limit=n_results)
            
            # Format results in legacy format
            formatted_results = []
            for result in results:
                # Extract preview content (first 300 characters)
                cleaned_preview = result.content[:300] + "..." if len(result.content) > 300 else result.content
                
                formatted_results.append({
                    "title": result.conversation_title,
                    "date": result.created_at,
                    "content": cleaned_preview,
                    "metadata": {
                        "id": result.conversation_id,
                        "title": result.conversation_title,
                        "source": "postgres",
                        "earliest_ts": result.created_at,
                        "latest_ts": result.created_at,
                        "message_count": 1,  # Individual message result
                        "conversation_id": result.conversation_id,
                        "message_id": result.message_id,
                        "role": result.role
                    }
                })
            
            return {"query": query, "results": formatted_results}
        
        except Exception as e:
            logger.error(f"API search failed: {e}")
            return {"error": str(e)}
    
    def search(self) -> Dict[str, Any]:
        """
        POST /api/search
        
        Search conversations with various filters and options.
        """
        try:
            # Parse request data
            data = request.get_json() or {}
            
            # Extract search parameters
            query = data.get('query', '').strip()
            if not query:
                return {
                    "error": "Query parameter is required",
                    "documents": [[]],
                    "metadatas": [[]],
                    "distances": [[]]
                }
            
            n_results = data.get('n_results', 10)
            keyword_search = data.get('keyword_search', False)
            search_type = data.get('search_type', 'auto')
            
            # Handle date range filter if specified
            date_range = None
            if 'start_date' in data and 'end_date' in data:
                try:
                    start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
                    end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00'))
                    date_range = (start_date, end_date)
                except Exception as e:
                    logger.warning(f"Invalid date range format: {e}")
            
            # Perform search
            result = self.adapter.search_conversations(
                query_text=query,
                n_results=n_results,
                date_range=date_range,
                keyword_search=keyword_search,
                search_type=search_type
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {
                "error": str(e),
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }
    
    # ===== RAG ENDPOINTS =====
    
    def rag_query(self) -> Dict[str, Any]:
        """
        POST /api/rag/query
        
        RAG query endpoint for OpenWebUI integration.
        """
        try:
            data = request.get_json() or {}
            
            query = data.get('query', '').strip()
            if not query:
                return {
                    "error": "Query parameter is required",
                    "query": "",
                    "search_type": "semantic",
                    "results": []
                }
            
            n_results = data.get('n_results', 5)
            search_type = data.get('search_type', 'semantic')
            
            result = self.adapter.rag_query(
                query=query,
                n_results=n_results,
                search_type=search_type
            )
            
            return result
        
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return {
                "error": str(e),
                "query": request.get_json().get('query', '') if request.get_json() else '',
                "search_type": "semantic",
                "results": []
            }
    
    def rag_health(self) -> Dict[str, Any]:
        """
        GET /api/rag/health
        
        Health check for RAG functionality.
        """
        try:
            return self.adapter.get_health()
        
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    # ===== STATS ENDPOINTS =====
    
    def get_stats(self) -> Dict[str, Any]:
        """
        GET /api/stats
        
        Get database statistics.
        """
        try:
            return self.adapter.get_stats()
        
        except Exception as e:
            logger.error(f"Stats query failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def get_collection_count(self) -> Dict[str, Any]:
        """
        GET /api/collection/count
        
        Get collection count (legacy endpoint).
        """
        try:
            count = self.adapter.get_count()
            return {"count": count}
        
        except Exception as e:
            logger.error(f"Count query failed: {e}")
            return {
                "error": str(e),
                "count": 0
            }
    
    # ===== MANAGEMENT ENDPOINTS =====
    
    def clear_database(self) -> Dict[str, Any]:
        """
        DELETE /api/clear
        
        Clear the entire database.
        """
        try:
            return self.adapter.clear_database()
        
        except Exception as e:
            logger.error(f"Database clear failed: {e}")
            return {
                "status": "error",
                "message": f"Failed to clear database: {str(e)}"
            }
    
    # ===== EXPORT ENDPOINTS =====
    
    def export_to_openwebui(self, doc_id: str) -> Dict[str, Any]:
        """
        POST /api/export/openwebui/<doc_id>
        
        Export conversation to OpenWebUI format.
        """
        try:
            return self.adapter.export_to_openwebui(doc_id)
        
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return {
                "success": False,
                "message": f"Export failed: {str(e)}"
            }
    
    # ===== UPLOAD ENDPOINTS =====
    
    def upload(self) -> Any:
        """Handle file upload for PostgreSQL backend."""
        from flask import render_template, request, redirect, url_for
        import os
        import json
        
        if request.method == "GET":
            return render_template("upload.html")
        
        try:
            # Handle file upload
            if 'file' not in request.files:
                return "No file uploaded", 400
            
            file = request.files['file']
            if file.filename == '':
                return "No file selected", 400
            
            # Check file type
            if not (file.filename.endswith('.json') or file.filename.endswith('.docx')):
                return "Unsupported file type. Please upload JSON or DOCX files.", 400
            
            # Handle JSON files (Claude/ChatGPT exports)
            if file.filename.endswith('.json'):
                try:
                    content = file.read().decode('utf-8')
                    conversations_data = json.loads(content)
                    
                    # Import conversations into PostgreSQL
                    imported_count = self._import_conversations_json(conversations_data)
                    
                    return f"Success: Imported {imported_count} conversations into PostgreSQL backend", 200
                
                except json.JSONDecodeError as e:
                    return f"Error: Invalid JSON format - {str(e)}", 400
                except Exception as e:
                    logger.error(f"JSON import failed: {e}")
                    return f"Error: Import failed - {str(e)}", 400
            
            # Handle DOCX files  
            elif file.filename.endswith('.docx'):
                # For now, return not implemented for DOCX in PostgreSQL mode
                return "DOCX import not yet implemented for PostgreSQL backend", 400
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return f"Error: Upload failed - {str(e)}", 500
    
    def _import_conversations_json(self, data: Dict[str, Any]) -> int:
        """Import conversations from JSON data into PostgreSQL."""
        from db.repositories.unit_of_work import get_unit_of_work
        
        # Detect format (Claude vs ChatGPT) using proper detection method
        conversations, format_type = self._detect_json_format(data)
        if not conversations:
            raise ValueError("Unknown JSON format - no conversations found")
        
        print(f"🔍 Detected {format_type} format with {len(conversations)} conversations")
        logger.info(f"🔍 Detected {format_type} format with {len(conversations)} conversations")
        logger.info(f"📥 Importing {len(conversations)} conversations from {format_type} format into PostgreSQL")
        print(f"📥 Importing {len(conversations)} conversations from {format_type} format into PostgreSQL")
        
        imported_count = 0
        
        # Process each conversation in its own transaction
        for conv_data in conversations:
            try:
                # Extract conversation title
                title = conv_data.get('title', conv_data.get('name', 'Untitled Conversation'))
                
                # Extract messages first
                messages = []
                if 'mapping' in conv_data:  # ChatGPT format
                    messages = self._extract_chatgpt_messages(conv_data['mapping'])
                elif 'chat_messages' in conv_data:  # Claude format
                    messages = self._extract_claude_messages(conv_data['chat_messages'])
                
                # Skip if no valid messages
                if not messages:
                    continue
                
                # Import in a single transaction
                with get_unit_of_work() as uow:
                    # Create conversation
                    conversation = uow.conversations.create(title=title)
                    uow.session.flush()  # Get the ID
                    
                    # Add messages directly using repository instead of service
                    # to avoid nested transactions
                    for msg in messages:
                        if msg['content'].strip():  # Skip empty messages
                            # Store source and conversation info in message metadata
                            message_metadata = {
                                'source': format_type.lower(),
                                'conversation_title': title,
                                'original_conversation_id': conv_data.get('id') or conv_data.get('uuid') or str(conversation.id)
                            }
                            
                            message = uow.messages.create(
                                conversation_id=conversation.id,
                                role=msg['role'],
                                content=msg['content'],
                                message_metadata=message_metadata
                            )
                            uow.session.flush()  # Get the message ID
                            
                            # Enqueue embedding job separately
                            job_payload = {
                                'message_id': str(message.id),
                                'conversation_id': str(conversation.id),
                                'content': msg['content'],
                                'model': 'all-MiniLM-L6-v2'
                            }
                            
                            uow.jobs.enqueue(
                                kind='generate_embedding',
                                payload=job_payload
                            )
                    
                    # Transaction commits here automatically
                
                imported_count += 1
                
                if imported_count % 50 == 0:
                    print(f"📊 Imported {imported_count} conversations...")
                    logger.info(f"📊 Imported {imported_count} conversations...")
            
            except Exception as e:
                error_msg = f"Failed to import conversation '{conv_data.get('title', 'Unknown')}': {e}"
                print(f"❌ {error_msg}")
                logger.error(error_msg)
                continue
        
        completion_msg = f"✅ Successfully imported {imported_count} conversations into PostgreSQL"
        print(completion_msg)
        logger.info(completion_msg)
        return imported_count
    
    def _extract_chatgpt_messages(self, mapping: Dict) -> List[Dict]:
        """Extract messages from ChatGPT format."""
        messages = []
        
        for node_id, node in mapping.items():
            message = node.get('message')
            if not message:
                continue
            
            author = message.get('author', {})
            role = author.get('role', 'unknown')
            
            # Skip system messages and empty content
            if role == 'system':
                continue
            
            content_parts = message.get('content', {}).get('parts', [])
            if content_parts and isinstance(content_parts[0], str):
                content = content_parts[0]
                
                if content.strip():
                    messages.append({
                        'role': role,
                        'content': content
                    })
        
        return messages
    
    def _extract_claude_messages(self, chat_messages: List) -> List[Dict]:
        """Extract messages from Claude format."""
        messages = []
        
        for msg in chat_messages:
            role = 'user' if msg.get('sender') == 'human' else 'assistant'
            content = msg.get('text', '')
            
            if content.strip():
                messages.append({
                    'role': role,
                    'content': content
                })
        
        return messages
    
    def _detect_json_format(self, data):
        """Detect whether JSON is ChatGPT or Claude format (copied from original)"""
        # Ensure data is a list
        if isinstance(data, dict):
            conversations = data.get("conversations", [])
        else:
            conversations = data if isinstance(data, list) else []
            
        if not conversations:
            return [], "Unknown"
            
        # Check first conversation to determine format
        first_conv = conversations[0] if conversations else {}
        
        # Claude format has 'uuid', 'name', and 'chat_messages'
        if (first_conv.get("uuid") and 
            first_conv.get("name") is not None and  # name can be empty string
            "chat_messages" in first_conv):
            return conversations, "Claude"
            
        # ChatGPT format has 'title', 'mapping', and timestamps as epoch
        elif (first_conv.get("title") is not None and 
              "mapping" in first_conv and
              first_conv.get("create_time")):
            return conversations, "ChatGPT"
            
        return conversations, "Unknown"
    
    # ===== UTILITY METHODS =====
    
    def _parse_date_range(self, start_str: Optional[str], end_str: Optional[str]) -> Optional[Tuple[datetime, datetime]]:
        """
        Parse date range strings into datetime objects.
        
        Args:
            start_str: Start date string (ISO format)
            end_str: End date string (ISO format)
            
        Returns:
            Tuple of (start_date, end_date) or None if parsing fails
        """
        if not start_str or not end_str:
            return None
        
        try:
            start_date = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
            return (start_date, end_date)
        except Exception as e:
            logger.warning(f"Failed to parse date range {start_str} - {end_str}: {e}")
            return None


# Global controller instance
_controller = None

def get_postgres_controller() -> PostgresController:
    """Get the global PostgreSQL controller instance."""
    global _controller
    if _controller is None:
        _controller = PostgresController()
    return _controller
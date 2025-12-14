"""
PostgreSQL Controller

This controller provides Flask route handlers that use PostgreSQL backend
through the APIFormatAdapter for ChromaDB-compatible response formatting.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from flask import request

from db.adapters.api_format_adapter import get_api_format_adapter
from db.services.message_service import MessageService
from db.services.import_service import ConversationImportService
from db.importers import detect_format
from db.importers.registry import FORMAT_REGISTRY

logger = logging.getLogger(__name__)


class PostgresController:
    """
    Controller that provides Flask route handlers using PostgreSQL backend
    with ChromaDB-compatible response formatting via APIFormatAdapter.
    """
    
    def __init__(self):
        self.adapter = get_api_format_adapter()
        self.message_service = MessageService()
        self.import_service = ConversationImportService()
    
    # ===== CONVERSATION ENDPOINTS =====
    
    def get_conversations(self) -> Dict[str, Any]:
        """
        GET /api/conversations
        
        Returns all conversations in the legacy format (optimized with summaries).
        """
        try:
            # Use optimized summary method instead of loading all messages
            result = self.adapter.get_conversations_summary(limit=9999)
            return result
        
        except Exception as e:
            logger.error(f"Failed to get conversations: {e}")
            return {
                "error": str(e),
                "documents": [],
                "metadatas": [],
                "ids": []
            }
    
    def get_conversations_paginated(self) -> Dict[str, Any]:
        """
        GET /api/conversations/list?page=1&limit=30&source=chatgpt&date=month&sort=newest
        
        Returns paginated conversations for lazy loading with filters.
        """
        try:
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 30))
            offset = (page - 1) * limit
            
            # Get filter parameters
            source_filter = request.args.get('source', 'all')
            date_filter = request.args.get('date', 'all')
            sort_order = request.args.get('sort', 'newest')
            
            # Get conversations with filters applied
            result = self.adapter.get_conversations_summary(
                limit=limit + 1, 
                offset=offset,
                source_filter=source_filter,
                date_filter=date_filter,
                sort_order=sort_order
            )
            
            # Check if there are more items
            has_more = len(result['documents']) > limit
            
            # Trim to actual limit
            if has_more:
                result['documents'] = result['documents'][:limit]
                result['metadatas'] = result['metadatas'][:limit]
                result['ids'] = result['ids'][:limit]
            
            return {
                'conversations': [
                    {
                        'id': result['ids'][i],
                        'title': result['metadatas'][i].get('title', 'Untitled'),
                        'source': result['metadatas'][i].get('source', 'unknown'),
                        'preview': result['documents'][i],
                        'latest_ts': result['metadatas'][i].get('latest_ts', ''),
                        'message_count': result['metadatas'][i].get('message_count', 0)
                    }
                    for i in range(len(result['documents']))
                ],
                'page': page,
                'limit': limit,
                'has_more': has_more
            }
        
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
            
            # Get search type from parameters (new way) or keyword flag (legacy way)
            search_type = request.args.get("search_type", "auto")
            keyword = request.args.get("keyword", "false").lower() == "true"
            
            # Use SearchService based on search type
            if search_type in ("fts", "keyword") or keyword:
                results = self.adapter.search_service.search_fts_only(query, limit=n_results)
            elif search_type == "semantic":
                results = self.adapter.search_service.search_vector_only(query, limit=n_results)
            elif search_type == "hybrid":
                results = self.adapter.search_service.search(query, limit=n_results)
            else:  # auto
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
                
                # Get the actual source for this conversation
                source = self._get_conversation_source(result.conversation_id)
                
                formatted_results.append({
                    "title": result.conversation_title,
                    "date": result.created_at,
                    "content": cleaned_preview,
                    "metadata": {
                        "id": result.conversation_id,
                        "title": result.conversation_title,
                        "source": source,
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
    
    def _get_conversation_source(self, conversation_id: str) -> str:
        """
        Get the source (ChatGPT, Claude, etc.) for a conversation.
        Looks up the first message's metadata to find the original source.
        """
        try:
            from uuid import UUID
            from db.repositories.unit_of_work import get_unit_of_work
            
            conv_uuid = UUID(conversation_id)
            with get_unit_of_work() as uow:
                messages = uow.messages.get_by_conversation(conv_uuid)
                if messages and messages[0].message_metadata:
                    source = messages[0].message_metadata.get('source', 'unknown')
                    # Normalize to expected values
                    if source and isinstance(source, str):
                        source_lower = source.lower()
                        if 'claude' in source_lower:
                            return 'claude'
                        elif 'chatgpt' in source_lower or 'gpt' in source_lower:
                            return 'chatgpt'
                        elif 'openwebui' in source_lower or 'open-webui' in source_lower:
                            return 'openwebui'
                    return source
            return 'unknown'
        except Exception as e:
            logger.error(f"Failed to get source for conversation {conversation_id}: {e}")
            return 'unknown'
    
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
    
    def delete_conversation(self, doc_id: str) -> Dict[str, Any]:
        """
        DELETE /api/conversation/<doc_id>
        
        Delete a conversation and all its associated data (messages and embeddings).
        """
        try:
            from uuid import UUID
            from db.repositories.unit_of_work import get_unit_of_work
            
            # Parse UUID
            try:
                conv_uuid = UUID(doc_id)
            except ValueError:
                return {
                    "success": False,
                    "message": "Invalid conversation ID format"
                }
            
            # Delete conversation with cascade
            with get_unit_of_work() as uow:
                deleted = uow.conversations.delete_conversation_with_cascade(conv_uuid)
                
                if deleted:
                    uow.commit()
                    logger.info(f"Successfully deleted conversation {doc_id}")
                    return {
                        "success": True,
                        "message": "Conversation deleted successfully"
                    }
                else:
                    return {
                        "success": False,
                        "message": "Conversation not found"
                    }
        
        except Exception as e:
            logger.error(f"Conversation deletion failed: {e}")
            return {
                "success": False,
                "message": f"Failed to delete conversation: {str(e)}"
            }
    
    # ===== EXPORT ENDPOINTS =====
    
    def export_conversation(self, doc_id: str) -> Any:
        """
        GET /export/<doc_id>
        
        Export conversation as markdown file.
        """
        from flask import Response
        from datetime import datetime
        from uuid import UUID
        from db.repositories.unit_of_work import get_unit_of_work
        
        try:
            # Try to parse as UUID for PostgreSQL
            try:
                conv_uuid = UUID(doc_id)
                with get_unit_of_work() as uow:
                    conversation = uow.conversations.get_by_id(conv_uuid)
                    if not conversation:
                        return "Conversation not found", 404
                    
                    # Get all messages for the conversation
                    messages = uow.messages.get_by_conversation(conv_uuid)
                    if not messages:
                        return "No messages found in conversation", 404
                    
                    # Build markdown content
                    title = conversation.title or "Untitled Conversation"
                    markdown_content = f"# {title}\n\n"
                    
                    # Add date if available
                    if conversation.created_at:
                        date_str = conversation.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        markdown_content += f"Date: {date_str}\n\n"
                    
                    # Add messages
                    for msg in messages:
                        role = msg.role.upper()
                        content = msg.content
                        
                        markdown_content += f"**{role}:**\n\n{content}\n\n---\n\n"
                    
                    # Create filename
                    safe_title = title.replace(" ", "_").replace("/", "_")
                    filename = f"{safe_title}.md"
                    
                    # Create response with markdown file
                    response = Response(markdown_content, mimetype="text/markdown")
                    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
                    
                    return response
                    
            except (ValueError, TypeError):
                # If not a UUID, try fallback to legacy format
                return "Invalid conversation ID format", 400
        
        except Exception as e:
            logger.error(f"Export markdown failed: {e}")
            return f"Export failed: {str(e)}", 500
    
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
        import tempfile
        
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
                    
                    # Delegate to import service
                    import_result = self.import_service.import_json_data(conversations_data)
                    
                    # Return user-friendly success message
                    if import_result.imported_count > 0:
                        msg = f"✅ Successfully imported {import_result.imported_count} conversations from {import_result.format_detected} format"
                        if import_result.skipped_duplicates > 0:
                            msg += f" (skipped {import_result.skipped_duplicates} duplicates)"
                        return msg, 200
                    elif import_result.skipped_duplicates > 0:
                        return f"ℹ️ All {import_result.skipped_duplicates} conversations were already imported", 200
                    else:
                        return "⚠️ No conversations were imported", 400
                
                except json.JSONDecodeError as e:
                    return f"Error: Invalid JSON format - {str(e)}", 400
                except ValueError as e:
                    # User-friendly error from import service
                    return f"Error: {str(e)}", 400
                except Exception as e:
                    logger.error(f"JSON import failed: {e}")
                    return f"Error: Import failed - {str(e)}", 400
            
            # Handle DOCX files  
            elif file.filename.endswith('.docx'):
                try:
                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_file:
                        file.save(temp_file.name)
                        temp_path = temp_file.name
                    
                    try:
                        # Delegate to import service
                        import_result = self.import_service.import_docx_file(temp_path, file.filename)
                        
                        # Return user-friendly success message
                        if import_result.imported_count > 0:
                            return f"✅ Successfully imported Word document with {import_result.imported_count} conversation(s)", 200
                        else:
                            return "⚠️ No conversations were imported from Word document", 400
                    finally:
                        # Clean up temp file
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                
                except ValueError as e:
                    logger.error(f"DOCX import failed: {e}")
                    return f"Error: {str(e)}", 400
                except Exception as e:
                    logger.error(f"DOCX import failed: {e}")
                    return f"Error: DOCX import failed - {str(e)}", 400
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return f"Error: Upload failed - {str(e)}", 500
    
    def _import_conversations_json(self, data: Dict[str, Any]) -> str:
        """DEPRECATED: Import conversations from JSON data. Use ConversationImportService instead.
        
        This method is kept for backward compatibility. New code should use:
        result = self.import_service.import_json_data(data)
        """
        try:
            result = self.import_service.import_json_data(data)
            # Convert result to legacy string format
            return f"Success: {result}"
        except ValueError as e:
            raise
        except Exception as e:
            return f"Error: {str(e)}"
    
    
    def _detect_json_format(self, data):
        """DEPRECATED: Detect JSON format. Use ConversationImportService instead.
        
        This method is kept for backward compatibility.
        Delegates to the registry detect_format function.
        """
        return detect_format(data)
    
    def _import_docx_file(self, file_path: str, filename: str) -> str:
        """DEPRECATED: Import DOCX file. Use ConversationImportService instead.
        
        This method is kept for backward compatibility. New code should use:
        result = self.import_service.import_docx_file(file_path, filename)
        """
        try:
            result = self.import_service.import_docx_file(file_path, filename)
            # Convert result to legacy string format
            return f"Successfully imported with {result.imported_count} conversations"
        except ValueError as e:
            raise
        except Exception as e:
            raise ValueError(f"Failed to import Word document: {str(e)}")
    
    # ===== SETTINGS ENDPOINTS =====
    
    def get_settings_page(self) -> Any:
        """
        GET /settings
        
        Render the settings page with current settings.
        """
        from flask import render_template
        try:
            # Fetch all settings from database
            settings = self.adapter.get_all_settings()
            print(f"DEBUG: Settings loaded: {settings}")
            logger.info(f"Settings loaded: {settings}")
            return render_template('settings.html', settings=settings)
        except Exception as e:
            logger.error(f"Failed to load settings page: {e}")
            import traceback
            traceback.print_exc()
            return render_template('settings.html', settings={})
    
    def handle_settings(self, request_obj) -> Dict[str, Any]:
        """
        POST /api/settings - Save settings
        GET /api/settings - Retrieve settings
        """
        try:
            from flask import request as flask_request
            
            if flask_request.method == 'POST':
                data = request_obj.get_json() or {}
                
                # Save settings
                for key, value in data.items():
                    if value:  # Only save non-empty values
                        self.adapter.set_setting(key, value)
                
                return {
                    "success": True,
                    "message": "Settings saved successfully"
                }
            else:
                # GET request - return current settings
                settings = self.adapter.get_all_settings()
                return {
                    "success": True,
                    "settings": settings
                }
        
        except Exception as e:
            logger.error(f"Settings operation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
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


# ===== ATTACHMENT EXTRACTION UTILITIES =====

def extract_claude_attachments(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract attachments from a Claude message.
    
    Claude exports have two types of attachments:
    - attachments[]: Files with extracted_content (text files, code, etc.)
    - files[]: File references without content (images, etc.)
    
    Args:
        message: Claude message dict with 'attachments' and 'files' fields
        
    Returns:
        List of normalized attachment dicts
    """
    attachments = []
    
    # Process attachments with extracted content
    for attachment in message.get('attachments', []):
        file_name = attachment.get('file_name', 'unknown')
        file_type = attachment.get('file_type', '')
        
        # Determine if it's an image based on file extension or type
        is_image = (
            file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')) or
            'image' in file_type.lower()
        )
        
        attachments.append({
            'type': 'image' if is_image else 'file',
            'file_name': file_name,
            'file_size': attachment.get('file_size'),
            'file_type': file_type,
            'extracted_content': attachment.get('extracted_content'),
            'available': bool(attachment.get('extracted_content')),
            'metadata': {}
        })
    
    # Process file references (usually images without content)
    for file_ref in message.get('files', []):
        file_name = file_ref.get('file_name', 'unknown')
        
        # Determine type from extension
        is_image = file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'))
        
        attachments.append({
            'type': 'image' if is_image else 'file',
            'file_name': file_name,
            'file_size': None,
            'file_type': None,
            'extracted_content': None,
            'available': False,  # Files without extracted_content are not available
            'metadata': {}
        })
    
    return attachments


def extract_chatgpt_attachments(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract attachments/artifacts from a ChatGPT message.
    
    ChatGPT exports have various content types and metadata that represent attachments:
    - content.content_type: 'code', 'thoughts', 'reasoning_recap', 'multimodal_text'
    - content.parts[]: Can contain image_asset_pointer, audio_transcription, etc.
    - metadata.attachments[]: File metadata
    - metadata.content_references[]: Web citations
    
    Args:
        message: ChatGPT message dict
        
    Returns:
        List of normalized attachment dicts
    """
    attachments = []
    content = message.get('content', {})
    metadata = message.get('metadata', {})
    
    # Handle code content type
    if isinstance(content, dict) and content.get('content_type') == 'code':
        attachments.append({
            'type': 'code',
            'language': content.get('language', 'unknown'),
            'extracted_content': content.get('text', ''),
            'available': True,
            'file_name': f"code.{content.get('language', 'txt')}",
            'metadata': {}
        })
    
    # Handle thoughts/reasoning content type
    elif isinstance(content, dict) and content.get('content_type') == 'thoughts':
        thoughts_data = content.get('thoughts', [])
        if thoughts_data:
            attachments.append({
                'type': 'reasoning',
                'reasoning_type': 'thoughts',
                'thoughts': thoughts_data,
                'available': True,
                'file_name': 'reasoning.txt',
                'metadata': {}
            })
    
    # Handle reasoning_recap content type
    elif isinstance(content, dict) and content.get('content_type') == 'reasoning_recap':
        attachments.append({
            'type': 'reasoning',
            'reasoning_type': 'recap',
            'recap_content': content.get('content', ''),
            'available': True,
            'file_name': 'reasoning_recap.txt',
            'metadata': {}
        })
    
    # Handle multimodal_text content type
    elif isinstance(content, dict) and content.get('content_type') == 'multimodal_text':
        parts = content.get('parts', [])
        
        for part in parts:
            if not isinstance(part, dict):
                continue
            
            part_type = part.get('content_type')
            
            # Image asset pointer
            if part_type == 'image_asset_pointer':
                # Try to get actual filename from metadata.attachments
                file_name = 'image.png'
                file_size = part.get('size_bytes')
                file_type = 'image/png'
                
                # Look for matching attachment in metadata
                for meta_attachment in metadata.get('attachments', []):
                    if meta_attachment.get('id') in part.get('asset_pointer', ''):
                        file_name = meta_attachment.get('name', file_name)
                        file_size = meta_attachment.get('size', file_size)
                        file_type = meta_attachment.get('mime_type', file_type)
                        break
                
                attachments.append({
                    'type': 'image',
                    'file_name': file_name,
                    'file_size': file_size,
                    'file_type': file_type,
                    'asset_pointer': part.get('asset_pointer'),
                    'width': part.get('width'),
                    'height': part.get('height'),
                    'available': False,  # Asset not in export
                    'metadata': {}
                })
            
            # Audio transcription
            elif part_type == 'audio_transcription':
                attachments.append({
                    'type': 'audio',
                    'transcription': part.get('text', ''),
                    'direction': part.get('direction'),
                    'available': True,
                    'file_name': 'audio_transcription.txt',
                    'metadata': {}
                })
            
            # Audio asset pointer
            elif part_type == 'audio_asset_pointer':
                attachments.append({
                    'type': 'audio',
                    'asset_pointer': part.get('asset_pointer'),
                    'available': False,
                    'file_name': 'audio.mp3',
                    'metadata': {}
                })
    
    # Handle content_references (web citations)
    content_refs = metadata.get('content_references', [])
    if content_refs:
        citations = []
        for ref in content_refs:
            if ref.get('type') == 'grouped_webpages':
                for item in ref.get('items', []):
                    citations.append({
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'snippet': item.get('snippet', '')
                    })
        
        if citations:
            attachments.append({
                'type': 'citation',
                'citations': citations,
                'available': True,
                'file_name': 'citations.json',
                'metadata': {}
            })
    
    return attachments


def extract_openwebui_attachments(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract attachments from an OpenWebUI message.
    
    OpenWebUI messages can have a 'files' array with file metadata.
    Files may include images (as data URLs), documents, and other attachments.
    
    Args:
        message: OpenWebUI message dict with optional 'files' field
        
    Returns:
        List of normalized attachment dicts
    """
    attachments = []
    
    # Process files array if present
    files = message.get('files', [])
    if not files:
        return attachments
    
    for file_data in files:
        if not isinstance(file_data, dict):
            continue
        
        file_name = file_data.get('name') or file_data.get('filename')
        file_type = file_data.get('type') or file_data.get('mime_type', '')
        
        # Determine if it's an image based on file type or data URL
        url = file_data.get('url', '')
        is_image = 'image' in file_type.lower() or (url and url.startswith('data:image/'))
        
        # If filename is None, infer from file type
        if not file_name:
            if is_image:
                # Try to get extension from data URL or default to jpg
                if url.startswith('data:image/'):
                    mime = url.split(';')[0].split('/')[-1]  # e.g., 'jpeg', 'png'
                    file_name = f'image.{mime}'
                else:
                    file_name = 'image.jpg'
            else:
                file_name = 'attachment'
        
        # Also check filename extension for image detection
        if file_name and file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg')):
            is_image = True
        
        # Check if content is available
        # OpenWebUI stores images as data URLs in 'url' field
        content = file_data.get('content') or file_data.get('data')
        
        # Data URLs contain base64-encoded image data that we can render
        has_data_url = url and url.startswith('data:')
        has_content = bool(content)
        
        # For images with data URLs, store the data URL for rendering
        if is_image and has_data_url:
            attachments.append({
                'type': 'image',
                'file_name': file_name,
                'file_size': file_data.get('size'),
                'file_type': file_type,
                'extracted_content': url,  # Store data URL for image rendering
                'available': True,  # Image is available for display
                'metadata': {
                    'data_url': url,
                    'collection_name': file_data.get('collection_name')
                }
            })
        else:
            # For non-images or files without data URLs
            attachments.append({
                'type': 'image' if is_image else 'file',
                'file_name': file_name,
                'file_size': file_data.get('size'),
                'file_type': file_type,
                'extracted_content': content,
                'available': has_content,
                'metadata': {
                    'url': url if not has_data_url else None,
                    'collection_name': file_data.get('collection_name')
                }
            })
    
    return attachments


def normalize_attachment(attachment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize an attachment dict to ensure all required fields are present.
    
    Args:
        attachment: Raw attachment dict
        
    Returns:
        Normalized attachment dict with all required fields
    """
    normalized = {
        'type': attachment.get('type', 'file'),
        'file_name': attachment.get('file_name', 'unknown'),
        'file_size': attachment.get('file_size'),
        'file_type': attachment.get('file_type'),
        'extracted_content': attachment.get('extracted_content'),
        'available': attachment.get('available', False),
        'metadata': attachment.get('metadata', {})
    }
    
    # Copy any additional fields (language, transcription, citations, etc.)
    for key, value in attachment.items():
        if key not in normalized:
            normalized[key] = value
    
    return normalized


# Global controller instance
_controller = None

def get_postgres_controller() -> PostgresController:
    """Get the global PostgreSQL controller instance."""
    global _controller
    if _controller is None:
        _controller = PostgresController()
    return _controller

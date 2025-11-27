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

logger = logging.getLogger(__name__)


class PostgresController:
    """
    Controller that provides Flask route handlers using PostgreSQL backend
    with ChromaDB-compatible response formatting via APIFormatAdapter.
    """
    
    def __init__(self):
        self.adapter = get_api_format_adapter()
        self.message_service = MessageService()
    
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
                    import_result = self._import_conversations_json(conversations_data)
                    
                    return import_result, 200
                
                except json.JSONDecodeError as e:
                    return f"Error: Invalid JSON format - {str(e)}", 400
                except Exception as e:
                    logger.error(f"JSON import failed: {e}")
                    return f"Error: Import failed - {str(e)}", 400
            
            # Handle DOCX files  
            elif file.filename.endswith('.docx'):
                try:
                    import tempfile
                    import os
                    
                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_file:
                        file.save(temp_file.name)
                        temp_path = temp_file.name
                    
                    try:
                        # Import the DOCX file
                        import_result = self._import_docx_file(temp_path, file.filename)
                        return import_result, 200
                    finally:
                        # Clean up temp file
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                
                except Exception as e:
                    logger.error(f"DOCX import failed: {e}")
                    return f"Error: DOCX import failed - {str(e)}", 400
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return f"Error: Upload failed - {str(e)}", 500
    
    def _import_conversations_json(self, data: Dict[str, Any]) -> str:
        """Import conversations from JSON data into PostgreSQL. Returns message string."""
        from db.repositories.unit_of_work import get_unit_of_work
        import hashlib
        
        # Detect format (Claude vs ChatGPT) using proper detection method
        conversations, format_type = self._detect_json_format(data)
        if not conversations:
            raise ValueError("Unknown JSON format - no conversations found")
        
        print(f"🔍 Detected {format_type} format with {len(conversations)} conversations")
        logger.info(f"🔍 Detected {format_type} format with {len(conversations)} conversations")
        logger.info(f"📥 Importing {len(conversations)} conversations from {format_type} format into PostgreSQL")
        print(f"📥 Importing {len(conversations)} conversations from {format_type} format into PostgreSQL")
        
        # Build map of existing conversations for duplicate detection
        existing_conv_map = {}  # Map conversation_id -> (content_hash, db_id)
        with get_unit_of_work() as uow:
            existing_conversations = uow.conversations.get_all()
            for conv in existing_conversations:
                messages = uow.messages.get_by_conversation(conv.id)
                # Concatenate all message content for duplicate detection
                full_content = "\n\n".join(msg.content for msg in messages if msg.content)
                content_hash = hashlib.sha256(full_content.encode()).hexdigest()
                
                # Store by original conversation ID if available in metadata
                if messages and messages[0].message_metadata:
                    original_id = messages[0].message_metadata.get('original_conversation_id')
                    if original_id:
                        existing_conv_map[original_id] = (content_hash, conv.id)
        
        print(f"Found {len(existing_conv_map)} existing conversations for duplicate checking")
        
        imported_count = 0
        skipped_duplicates = 0
        
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
                elif 'chat' in conv_data and 'history' in conv_data.get('chat', {}) and 'messages' in conv_data['chat']['history']:  # OpenWebUI format
                    messages = self._extract_openwebui_messages(conv_data['chat']['history']['messages'])
                
                # Skip if no valid messages
                if not messages:
                    continue
                
                # Check for duplicates using conversation ID
                conv_id = conv_data.get('id') or conv_data.get('uuid')
                full_content = "\n\n".join(msg['content'] for msg in messages if msg['content'].strip())
                content_hash = hashlib.sha256(full_content.encode()).hexdigest()
                
                if conv_id and conv_id in existing_conv_map:
                    existing_hash, existing_db_id = existing_conv_map[conv_id]
                    if content_hash == existing_hash:
                        # Content is identical, skip this duplicate
                        skipped_duplicates += 1
                        logger.info(f"Skipping duplicate conversation: {title}")
                        continue
                    else:
                        # Content changed - for now we skip (update logic would go here)
                        skipped_duplicates += 1
                        logger.info(f"Conversation exists with different content: {title} - skipping")
                        continue
                
                # Calculate earliest and latest timestamps from messages
                timestamps = [msg.get('created_at') for msg in messages if msg.get('created_at')]
                earliest_ts = min(timestamps) if timestamps else None
                latest_ts = max(timestamps) if timestamps else None
                
                # If no message-level timestamps, fall back to conversation-level timestamps
                # ChatGPT exports strip message timestamps, Claude uses ISO format, OpenWebUI uses Unix epoch
                if not earliest_ts:
                    if format_type.lower() == 'chatgpt':
                        earliest_ts = conv_data.get('create_time')
                    elif format_type.lower() == 'claude':
                        earliest_ts = conv_data.get('created_at')
                    elif format_type.lower() == 'openwebui':
                        earliest_ts = conv_data.get('created_at')
                if not latest_ts:
                    if format_type.lower() == 'chatgpt':
                        latest_ts = conv_data.get('update_time') or conv_data.get('create_time')
                    elif format_type.lower() == 'claude':
                        latest_ts = conv_data.get('updated_at') or conv_data.get('created_at')
                    elif format_type.lower() == 'openwebui':
                        latest_ts = conv_data.get('updated_at') or conv_data.get('created_at')
                
                # Import in a single transaction
                with get_unit_of_work() as uow:
                    # Create conversation with original timestamps if available
                    conv_kwargs = {'title': title}
                    
                    # Set original timestamps if available
                    # ChatGPT/OpenWebUI use Unix epoch (numeric), Claude uses ISO format (string)
                    if earliest_ts:
                        try:
                            if isinstance(earliest_ts, datetime):
                                # Already a datetime object (from OpenWebUI extraction)
                                conv_kwargs['created_at'] = earliest_ts
                            elif isinstance(earliest_ts, (int, float)):
                                # ChatGPT/OpenWebUI format: Unix epoch
                                conv_kwargs['created_at'] = datetime.fromtimestamp(earliest_ts, tz=timezone.utc)
                            elif isinstance(earliest_ts, str):
                                # Claude format: ISO string
                                conv_kwargs['created_at'] = datetime.fromisoformat(earliest_ts.replace('Z', '+00:00'))
                        except (ValueError, TypeError, OSError):
                            pass  # Use default if conversion fails
                    if latest_ts:
                        try:
                            if isinstance(latest_ts, datetime):
                                # Already a datetime object (from OpenWebUI extraction)
                                conv_kwargs['updated_at'] = latest_ts
                            elif isinstance(latest_ts, (int, float)):
                                # ChatGPT/OpenWebUI format: Unix epoch
                                conv_kwargs['updated_at'] = datetime.fromtimestamp(latest_ts, tz=timezone.utc)
                            elif isinstance(latest_ts, str):
                                # Claude format: ISO string
                                conv_kwargs['updated_at'] = datetime.fromisoformat(latest_ts.replace('Z', '+00:00'))
                        except (ValueError, TypeError, OSError):
                            pass  # Use default if conversion fails
                    
                    conversation = uow.conversations.create(**conv_kwargs)
                    uow.session.flush()  # Get the ID
                    
                    # Add messages directly using repository instead of service
                    # to avoid nested transactions
                    for msg in messages:
                        if msg['content'].strip():  # Skip empty messages
                            # Store source and conversation info in message metadata
                            message_metadata = {
                                'source': format_type.lower(),
                                'conversation_title': title,
                                'original_conversation_id': conv_id or str(conversation.id)
                            }
                            
                            # Add OpenWebUI-specific metadata
                            if format_type.lower() == 'openwebui':
                                openwebui_meta = {
                                    'archived': conv_data.get('archived', False),
                                    'pinned': conv_data.get('pinned', False),
                                    'folder_id': conv_data.get('folder_id'),
                                    'share_id': conv_data.get('share_id'),
                                    'user_id': conv_data.get('user_id')
                                }
                                # Add model if present in the message
                                if msg.get('model'):
                                    openwebui_meta['model'] = msg['model']
                                message_metadata['openwebui'] = {k: v for k, v in openwebui_meta.items() if v is not None}
                            
                            # Build kwargs for message creation, including timestamp if available
                            msg_kwargs = {
                                'conversation_id': conversation.id,
                                'role': msg['role'],
                                'content': msg['content'],
                                'message_metadata': message_metadata
                            }
                            
                            # Add original message timestamp if available
                            # ChatGPT/OpenWebUI use Unix epoch (numeric), Claude uses ISO format (string)
                            msg_ts = msg.get('created_at')
                            # Fall back to conversation timestamp if message timestamp is unavailable
                            if not msg_ts:
                                if format_type.lower() == 'chatgpt':
                                    msg_ts = conv_data.get('create_time')
                                elif format_type.lower() == 'claude':
                                    msg_ts = conv_data.get('created_at')
                                elif format_type.lower() == 'openwebui':
                                    msg_ts = conv_data.get('created_at')
                            
                            if msg_ts:
                                try:
                                    if isinstance(msg_ts, datetime):
                                        # Already a datetime object (from OpenWebUI extraction)
                                        msg_kwargs['created_at'] = msg_ts
                                    elif isinstance(msg_ts, (int, float)):
                                        # ChatGPT/OpenWebUI format: Unix epoch
                                        msg_kwargs['created_at'] = datetime.fromtimestamp(msg_ts, tz=timezone.utc)
                                    elif isinstance(msg_ts, str):
                                        # Claude format: ISO string
                                        msg_kwargs['created_at'] = datetime.fromisoformat(msg_ts.replace('Z', '+00:00'))
                                except (ValueError, TypeError, OSError):
                                    pass
                            
                            message = uow.messages.create(**msg_kwargs)
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
        
        if imported_count == 0:
            if skipped_duplicates > 0:
                message = f"All {skipped_duplicates} conversations already indexed (no new content)"
            else:
                message = "No valid conversations found to index"
            print(f"ℹ️ {message}")
            logger.info(message)
            return f"Success: {message}"
        
        completion_msg = f"✅ Successfully imported {imported_count} conversations into PostgreSQL"
        if skipped_duplicates > 0:
            completion_msg += f" (skipped {skipped_duplicates} duplicates)"
        print(completion_msg)
        logger.info(completion_msg)
        return f"Success: {completion_msg}"
    
    def _extract_chatgpt_messages(self, mapping: Dict) -> List[Dict]:
        """Extract messages from ChatGPT format, preserving timestamps."""
        messages = []
        
        # Sort messages by create_time to maintain order, or by message id as fallback
        ordered_nodes = sorted(mapping.items(), key=lambda x: x[1].get('create_time', 0))
        
        for node_id, node in ordered_nodes:
            message = node.get('message')
            if not message:
                continue
            
            author = message.get('author', {})
            role = author.get('role', 'unknown')
            
            # Skip non-conversation roles (system, tool, function, etc.)
            # Only keep user and assistant messages
            if role not in ('user', 'assistant'):
                continue
            
            content_parts = message.get('content', {}).get('parts', [])
            if content_parts and isinstance(content_parts[0], str):
                content = content_parts[0]
                
                if content.strip():
                    # Try to get timestamp from message, then from node
                    created_at = message.get('create_time') or node.get('create_time')
                    messages.append({
                        'role': role,
                        'content': content,
                        'created_at': created_at  # Unix epoch timestamp or None
                    })
        
        return messages
    
    def _extract_claude_messages(self, chat_messages: List) -> List[Dict]:
        """Extract messages from Claude format, preserving timestamps."""
        messages = []
        
        for msg in chat_messages:
            role = 'user' if msg.get('sender') == 'human' else 'assistant'
            content = msg.get('text', '')
            
            if content.strip():
                msg_dict = {
                    'role': role,
                    'content': content
                }
                
                # Preserve the original timestamp from Claude (ISO format string)
                created_at = msg.get('created_at')
                if created_at:
                    msg_dict['created_at'] = created_at
                
                messages.append(msg_dict)
        
        return messages
    
    def _epoch_to_dt(self, ts):
        """Helper to convert epoch timestamp to datetime, handling ms vs s vs ns."""
        try:
            ts = int(ts)
            # Detect nanoseconds (> 10^12)
            if ts > 10**12:
                ts = ts / 10**9
            # Detect milliseconds (> 10^11)
            elif ts > 10**11:
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception as e:
            logger.warning(f"Failed to convert timestamp {ts}: {e}, using current time")
            return datetime.now(tz=timezone.utc)
    
    def _extract_openwebui_messages(self, messages_dict: Dict) -> List[Dict]:
        """Extract and flatten messages from OpenWebUI format chronologically.
        
        OpenWebUI stores messages as a dict keyed by message ID with parent-child
        relationships. This flattens them into a chronological list.
        """
        import json
        
        if not isinstance(messages_dict, dict) or not messages_dict:
            return []

        nodes = []
        for mid, m in messages_dict.items():
            if not isinstance(m, dict):
                continue
                
            role = (m.get("role") or "").lower().strip() or "user"
            content = m.get("content")
            
            # Handle content that might be a dict
            if isinstance(content, dict):
                content = content.get("text") or content.get("content") or json.dumps(content, ensure_ascii=False)
            elif content is None:
                content = ""
            
            # Get timestamp
            ts = m.get("timestamp") or m.get("created_at")
            created_at = self._epoch_to_dt(ts) if ts is not None else datetime.now(tz=timezone.utc)

            # Extract model information
            model = m.get("model")  # assistant messages
            if not model:
                models = m.get("models")  # user messages
                if isinstance(models, list) and models:
                    model = models[0]
                elif isinstance(models, str):
                    model = models

            nodes.append({
                "id": mid,
                "parentId": m.get("parentId"),
                "childrenIds": m.get("childrenIds") or [],
                "role": role if role in {"user", "assistant", "system", "tool"} else "user",
                "content": content,
                "created_at": created_at,
                "model": model
            })

        # Flatten: sort by created_at ascending; tie-break by parent presence (roots first), then id
        nodes.sort(key=lambda n: (n["created_at"], 0 if not n.get("parentId") else 1, str(n["id"])))

        # Convert to DovOS import format (list of messages)
        flat = []
        for n in nodes:
            if not n["content"] or not n["content"].strip():
                continue
            
            msg_dict = {
                "role": n["role"],
                "content": n["content"],
                "created_at": n["created_at"]
            }
            
            # Only add model if present
            if n.get("model"):
                msg_dict["model"] = n["model"]
            
            flat.append(msg_dict)
        
        return flat
    
    def _detect_json_format(self, data):
        """Detect whether JSON is ChatGPT, Claude, or OpenWebUI format"""
        # Ensure data is a list
        if isinstance(data, dict):
            conversations = data.get("conversations", [])
        else:
            conversations = data if isinstance(data, list) else []
            
        if not conversations:
            return [], "Unknown"
            
        # Check first conversation to determine format
        first_conv = conversations[0] if conversations else {}
        
        # OpenWebUI format has 'chat' with 'history.messages' as a dict
        chat = first_conv.get("chat", {}) if isinstance(first_conv, dict) else {}
        hist = chat.get("history", {}) if isinstance(chat, dict) else {}
        msgs = hist.get("messages")
        
        if isinstance(msgs, dict) and msgs:
            # Further sanity check: any message has keys id/role/content/timestamp
            try:
                any_msg = next(iter(msgs.values()))
                if isinstance(any_msg, dict) and "role" in any_msg and "content" in any_msg and "timestamp" in any_msg:
                    return conversations, "OpenWebUI"
            except (StopIteration, TypeError):
                pass
        
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
    
    def _import_docx_file(self, file_path: str, filename: str) -> str:
        """Import a Word document conversation into PostgreSQL. Returns message string."""
        from db.repositories.unit_of_work import get_unit_of_work
        from utils.docx_parser import parse_docx_file
        from datetime import datetime
        import os
        
        try:
            # Parse the DOCX file, passing original filename for title extraction
            messages, timestamps, title = parse_docx_file(file_path, original_filename=filename)
            
            if not messages:
                raise ValueError("No messages found in Word document")
            
            logger.info(f"📄 Importing Word document: {title} with {len(messages)} messages")
            print(f"📄 Importing Word document: {title} with {len(messages)} messages")
            
            # Determine timestamps
            if timestamps:
                earliest_ts = datetime.fromisoformat(min(timestamps))
                latest_ts = datetime.fromisoformat(max(timestamps))
            else:
                # Use file creation time as fallback
                file_create_time = datetime.fromtimestamp(os.path.getctime(file_path))
                earliest_ts = file_create_time
                latest_ts = file_create_time
            
            # Create conversation and messages in database
            with get_unit_of_work() as uow:
                # Create conversation
                conversation = uow.conversations.create(
                    title=title,
                    created_at=earliest_ts,
                    updated_at=latest_ts
                )
                
                # Create messages with sequence tracking
                for idx, msg_data in enumerate(messages):
                    # Store source, filename, and sequence in metadata
                    metadata = {
                        'source': 'docx',
                        'filename': filename,
                        'original_conversation_id': None,  # DOCX files don't have IDs
                        'sequence': idx  # Track message order within conversation
                    }
                    
                    uow.messages.create(
                        conversation_id=conversation.id,
                        role=msg_data['role'],
                        content=msg_data['content'],
                        message_metadata=metadata,
                        created_at=earliest_ts  # Use conversation timestamp for all messages
                    )
                
                uow.commit()
                
                logger.info(f"✅ Successfully imported Word document: {title}")
                print(f"✅ Successfully imported Word document: {title}")
                
                return f"Successfully imported '{title}' with {len(messages)} messages"
        
        except Exception as e:
            logger.error(f"DOCX import failed: {e}")
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


# Global controller instance
_controller = None

def get_postgres_controller() -> PostgresController:
    """Get the global PostgreSQL controller instance."""
    global _controller
    if _controller is None:
        _controller = PostgresController()
    return _controller
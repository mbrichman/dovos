from flask import render_template, request, Response, redirect, url_for, jsonify
import os
from datetime import datetime

from forms import SearchForm
from models.search_model import SearchModel
from models.conversation_view_model import ConversationViewModel, extract_preview_content


class ConversationController:
    """Controller for handling conversation-related routes"""
    
    def __init__(self):
        self.search_model = SearchModel()
        self.view_model = ConversationViewModel()
    
    def index(self):
        """Redirect to conversations view"""
        # If there's a search query, pass it to conversations
        if request.args.get("q"):
            return redirect(url_for("conversations", **request.args))
        elif request.method == "POST":
            # Handle POST form submission by redirecting to GET
            search_form = SearchForm()
            if search_form.validate_on_submit():
                return redirect(url_for("conversations", q=search_form.query.data))
        
        # Otherwise just redirect to conversations
        return redirect(url_for("conversations"))
    
    def conversations(self, page=1):
        """Display all documents in a list with filtering, pagination, and search"""
        # Items per page
        per_page = 20

        # Initialize search form
        search_form = SearchForm()
        search_triggered = False
        query = None

        # Check if search was triggered (either by form submission or URL parameter)
        if request.method == "POST":
            # Handle traditional form submission (POST)
            if search_form.validate_on_submit():
                query = search_form.query.data
                search_triggered = True
        elif request.method == "GET" and request.args.get("q"):
            # Handle URL parameter (GET)
            query = request.args.get("q")
            # Populate the form with the query from URL
            search_form.query.data = query
            search_triggered = True

        # Get filter parameters from URL
        source_filter = request.args.get("source", "all")
        date_filter = request.args.get("date", "all")
        sort_order = request.args.get("sort", "newest")

        # Handle search if triggered
        if search_triggered and query:
            # Perform search instead of getting all documents
            n_results = 50  # Get more results for search
            keyword_search = False
            date_range = None

            # Get search parameters
            search_type = "auto"  # Default
            
            # Use form values if available (POST method)
            if request.method == "POST" and hasattr(search_form, "results_count"):
                n_results = search_form.results_count.data or 50

            if request.method == "POST" and hasattr(search_form, "search_type"):
                search_type = search_form.search_type.data or "auto"
                keyword_search = search_form.search_type.data == "keyword"  # Keep for backward compatibility
            elif request.args.get("search_type"):
                search_type = request.args.get("search_type", "auto")

            if (
                request.method == "POST"
                and hasattr(search_form, "date_from")
                and hasattr(search_form, "date_to")
            ):
                if search_form.date_from.data and search_form.date_to.data:
                    date_range = (search_form.date_from.data, search_form.date_to.data)

            # Perform search with new search type
            search_method_names = {
                "auto": "Auto (Smart)",
                "fts": "Keyword (Fast)",
                "semantic": "Semantic (AI)",
                "hybrid": "Hybrid (Both)"
            }
            search_method = search_method_names.get(search_type, "Auto")
            print(f"DEBUG: Performing {search_method} search for: '{query}'")
            
            search_results = self.search_model.search_conversations(
                query_text=query,
                n_results=n_results,
                date_range=date_range,
                keyword_search=keyword_search,  # Keep for backward compatibility
                search_type=search_type
            )
            
            print(f"DEBUG: {search_method} search returned {len(search_results.get('documents', [[]])[0])} results")

            # Format search results for display
            items = self.view_model.format_search_results(search_results)

        else:
            # Get ALL documents directly, including their IDs (original behavior)
            try:
                # ChromaDB should return the IDs automatically with documents and metadatas
                all_docs = self.search_model.get_all_conversations(include=["documents", "metadatas"], limit=9999)
            except Exception as e:
                print(f"Error getting documents: {e}")
                all_docs = self.search_model.get_all_conversations(include=["documents", "metadatas"], limit=9999)

            if not all_docs or not all_docs.get("documents"):
                print("DEBUG: No documents found in the database")
                return render_template("conversations.html", conversations=None, search_form=search_form)

            print(f"DEBUG: Found {len(all_docs['documents'])} total documents")

            # Format conversations for list display
            items = self.view_model.format_conversations_list(
                all_docs, source_filter, date_filter, sort_order)

        # Calculate pagination
        total_items = len(items)
        page_count = (total_items + per_page - 1) // per_page  # Ceiling division

        # Make sure page is in valid range
        page = max(1, min(page, page_count)) if page_count > 0 else 1

        # Get items for current page
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, total_items)
        page_items = items[start_idx:end_idx]

        return render_template(
            "conversations.html",
            conversations=page_items,
            current_page=page,
            page_count=page_count,
            total_items=total_items,
            source_filter=source_filter,
            date_filter=date_filter,
            sort_order=sort_order,
            search_form=search_form,
            search_triggered=search_triggered,
            query=query,
        )
    
    def view_conversation(self, doc_id):
        """View a single conversation"""
        # Get document by ID
        doc_result = self.search_model.get_conversation_by_id(doc_id)

        # If that didn't work, try the old fallback methods
        if not doc_result or not doc_result.get("documents"):
            # If doc_id is in the format "chat-X" or "docx-X", this might be an old-style lookup
            if doc_id.startswith(("chat-", "docx-")):
                try:
                    idx = int(doc_id.split("-")[1])
                    # Get all documents and find the one with the matching index
                    all_docs_fallback = self.search_model.get_all_conversations(
                        include=["documents", "metadatas"], limit=9999
                    )

                    if (
                        all_docs_fallback
                        and all_docs_fallback.get("documents")
                        and idx < len(all_docs_fallback["documents"])
                    ):
                        # Create a filtered result with only the matching document
                        doc_result = {
                            "documents": [all_docs_fallback["documents"][idx]],
                            "metadatas": [
                                all_docs_fallback["metadatas"][idx]
                                if idx < len(all_docs_fallback.get("metadatas", []))
                                else {}
                            ],
                            "ids": [doc_id]
                        }
                    else:
                        # Document not found
                        return "Conversation not found", 404
                except (ValueError, IndexError):
                    # Invalid format
                    return "Conversation not found", 404
            else:
                # Document not found
                return "Conversation not found", 404

        document = doc_result["documents"][0]
        metadata = doc_result["metadatas"][0] if doc_result.get("metadatas") else {}

        # Format the conversation for detailed view
        conversation, messages, assistant_name = self.view_model.format_conversation_view(document, metadata)

        return render_template("view.html", conversation=conversation, messages=messages, assistant_name=assistant_name, doc_id=doc_id)
    
    def export_conversation(self, doc_id):
        """Export a conversation as markdown"""
        # Get document by ID
        doc_result = self.search_model.get_conversation_by_id(doc_id)

        # If that doesn't work, the ID might be stored in other fields or be a generated ID like 'chat-0' or 'docx-0'
        if not doc_result or not doc_result.get("documents") or not doc_result["documents"]:
            # If doc_id is in the format "chat-X" or "docx-X", extract the index
            if doc_id.startswith(("chat-", "docx-")):
                try:
                    idx = int(doc_id.split("-")[1])
                    # Get all documents and find the one with the matching index
                    all_docs = self.search_model.get_all_conversations(
                        include=["documents", "metadatas"], limit=9999
                    )

                    if (
                        all_docs
                        and all_docs.get("documents")
                        and idx < len(all_docs["documents"])
                    ):
                        # Create a filtered result with only the matching document
                        doc_result = {
                            "documents": [all_docs["documents"][idx]],
                            "metadatas": [
                                all_docs["metadatas"][idx]
                                if idx < len(all_docs.get("metadatas", []))
                                else {}
                            ],
                        }
                    else:
                        # Document not found
                        return "Conversation not found", 404
                except (ValueError, IndexError):
                    # Invalid format
                    return "Conversation not found", 404
            else:
                # Document not found
                return "Conversation not found", 404

        document = doc_result["documents"][0]
        metadata = doc_result["metadatas"][0] if doc_result.get("metadatas") else {}

        # Create filename
        title = metadata.get("title", "conversation").replace(" ", "_")
        filename = f"{title}.md"

        # Add headers to the markdown
        markdown_content = f"# {metadata.get('title', 'Conversation')}\n\n"

        if metadata.get("earliest_ts"):
            try:
                date_obj = datetime.fromisoformat(metadata["earliest_ts"])
                date_str = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                markdown_content += f"Date: {date_str}\n\n"
            except:
                pass

        markdown_content += document

        # Create response with markdown file
        response = Response(markdown_content, mimetype="text/markdown")
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"

        return response
    
    def export_to_openwebui(self, doc_id):
        """Export a conversation to OpenWebUI format and send it to the server"""
        import requests
        import json
        import config
        
        # Import the converter functions
        from claude_to_openwebui_converter import convert_conversation, parse_timestamp
        
        # Get document by ID
        doc_result = self.search_model.get_conversation_by_id(doc_id)
        
        # Handle fallback for old-style IDs
        if not doc_result or not doc_result.get("documents"):
            if doc_id.startswith(("chat-", "docx-")):
                try:
                    idx = int(doc_id.split("-")[1])
                    all_docs = self.search_model.get_all_conversations(
                        include=["documents", "metadatas"], limit=9999
                    )
                    
                    if (
                        all_docs
                        and all_docs.get("documents")
                        and idx < len(all_docs["documents"])
                    ):
                        doc_result = {
                            "documents": [all_docs["documents"][idx]],
                            "metadatas": [
                                all_docs["metadatas"][idx]
                                if idx < len(all_docs.get("metadatas", []))
                                else {}
                            ],
                        }
                    else:
                        return jsonify({"error": "Conversation not found"}), 404
                except (ValueError, IndexError):
                    return jsonify({"error": "Invalid conversation ID"}), 404
            else:
                return jsonify({"error": "Conversation not found"}), 404
        
        document = doc_result["documents"][0]
        metadata = doc_result["metadatas"][0] if doc_result.get("metadatas") else {}
        
        # Parse the conversation into messages
        messages = self._parse_conversation_messages(document, metadata)
        
        # Build a conversation structure compatible with the converter
        source = metadata.get("source", "").lower()
        
        # Create chat_messages in the format expected by the converter
        chat_messages = []
        for msg in messages:
            chat_msg = {
                "sender": msg["role"],
                "text": msg["content"],
                "created_at": msg.get("timestamp") or metadata.get("earliest_ts", "")
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
            return jsonify({"error": f"Conversion failed: {str(e)}"}), 500
        
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
                return jsonify({
                    "success": True,
                    "message": "Conversation exported to OpenWebUI successfully"
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": f"OpenWebUI API error: {response.status_code}",
                    "detail": response.text
                }), response.status_code
                
        except requests.exceptions.RequestException as e:
            return jsonify({
                "success": False,
                "error": f"Failed to connect to OpenWebUI: {str(e)}"
            }), 500
    
    def stats(self):
        """Display statistics about conversations"""
        # Get statistics from the model
        stats_data = self.search_model.get_statistics()
        return render_template("stats.html", stats=stats_data)
    
    def api_stats(self):
        """API endpoint for statistics in JSON format"""
        try:
            # Get statistics from the model
            stats_data = self.search_model.get_statistics()
            
            # Format for API response matching the contract
            return jsonify({
                "status": "healthy",
                "collection_name": stats_data.get("collection_name", "chat_history"),
                "document_count": stats_data.get("document_count", 0),
                "embedding_model": stats_data.get("embedding_model", "all-MiniLM-L6-v2")
            })
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # ===== PostgreSQL Adapter Methods =====
    
    def index_with_postgres_adapter(self, postgres_controller):
        """Index page using PostgreSQL backend"""
        # Reuse same logic but with postgres adapter for search
        if request.args.get("q"):
            return redirect(url_for("conversations", **request.args))
        elif request.method == "POST":
            search_form = SearchForm()
            if search_form.validate_on_submit():
                return redirect(url_for("conversations", q=search_form.query.data))
        
        return redirect(url_for("conversations"))
    
    def conversations_with_postgres_adapter(self, page, postgres_controller):
        """Display conversations using PostgreSQL backend with legacy UI"""
        per_page = 20
        search_form = SearchForm()
        search_triggered = False
        query = None

        # Handle search
        if request.method == "POST":
            if search_form.validate_on_submit():
                query = search_form.query.data
                search_triggered = True
        elif request.method == "GET" and request.args.get("q"):
            query = request.args.get("q")
            search_form.query.data = query
            search_triggered = True

        # Get filter parameters
        source_filter = request.args.get("source", "all")
        date_filter = request.args.get("date", "all")
        sort_order = request.args.get("sort", "newest")

        if search_triggered and query:
            # Use PostgreSQL search
            try:
                from werkzeug.datastructures import ImmutableMultiDict
                
                # Save original args
                original_args = request.args
                
                # Create new args with search query
                new_args = dict(original_args)
                new_args['q'] = query
                new_args['n'] = '20'  # Number of results
                
                # Temporarily replace request.args
                request.args = ImmutableMultiDict(new_args)
                
                # Get search results from postgres controller
                search_results = postgres_controller.api_search()
                
                # Restore original args
                request.args = original_args
                
                # Format results for legacy UI
                items = self._format_postgres_search_results(search_results.get('results', []))
                
            except Exception as e:
                print(f"Error in PostgreSQL search: {e}")
                items = []
        else:
            # Get all conversations from PostgreSQL
            try:
                all_docs = postgres_controller.get_conversations()
                items = self._format_postgres_conversations_list(
                    all_docs, source_filter, date_filter, sort_order
                )
            except Exception as e:
                print(f"Error getting PostgreSQL conversations: {e}")
                items = []

        # Pagination
        total_items = len(items)
        page_count = (total_items + per_page - 1) // per_page if total_items > 0 else 1
        page = max(1, min(page, page_count)) if page_count > 0 else 1
        
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, total_items)
        page_items = items[start_idx:end_idx]

        return render_template(
            "conversations.html",
            conversations=page_items,
            current_page=page,
            page_count=page_count,
            total_items=total_items,
            source_filter=source_filter,
            date_filter=date_filter,
            sort_order=sort_order,
            search_form=search_form,
            search_triggered=search_triggered,
            query=query,
        )
    
    def view_conversation_with_postgres_adapter(self, doc_id, postgres_controller):
        """View a single conversation using PostgreSQL backend"""
        try:
            # Get conversation from PostgreSQL
            doc_result = postgres_controller.get_conversation(doc_id)
            
            if not doc_result or not doc_result.get("documents"):
                return "Conversation not found", 404
            
            document = doc_result["documents"][0]
            metadata = doc_result["metadatas"][0] if doc_result.get("metadatas") else {}
            
            # Format the conversation for detailed view
            conversation, messages, assistant_name = self.view_model.format_conversation_view(document, metadata)
            
            return render_template("view.html", conversation=conversation, messages=messages, assistant_name=assistant_name, doc_id=doc_id)
            
        except Exception as e:
            print(f"Error viewing PostgreSQL conversation: {e}")
            return "Conversation not found", 404
    
    def _format_postgres_search_results(self, results):
        """Format PostgreSQL search results for legacy UI"""
        items = []
        for result in results:
            metadata = result.get('metadata', {})
            
            item = {
                'id': metadata.get('conversation_id', metadata.get('id', 'unknown')),
                'preview': result.get('content', ''),
                'meta': {
                    'title': result.get('title', metadata.get('title', 'Untitled')),
                    'source': metadata.get('source', 'postgres'),
                    'earliest_ts': result.get('date', metadata.get('earliest_ts', '')),
                    'latest_ts': metadata.get('latest_ts', ''),
                    'relevance_display': 'N/A'
                }
            }
            items.append(item)
        
        return items
    
    def _format_postgres_conversations_list(self, all_docs, source_filter, date_filter, sort_order):
        """Format PostgreSQL conversations for legacy UI list view"""
        if not all_docs or not all_docs.get('documents'):
            return []
        
        items = []
        documents = all_docs.get('documents', [])
        metadatas = all_docs.get('metadatas', [])
        ids = all_docs.get('ids', [])
        
        for i, document in enumerate(documents):
            metadata = metadatas[i] if i < len(metadatas) else {}
            doc_id = ids[i] if i < len(ids) else f'doc-{i}'
            
            # Extract preview (first 300 chars)
            preview = document[:300] + "..." if len(document) > 300 else document
            
            item = {
                'id': doc_id,
                'preview': preview,
                'meta': {
                    'title': metadata.get('title', 'Untitled Conversation'),
                    'source': metadata.get('source', 'postgres'),
                    'earliest_ts': metadata.get('earliest_ts', ''),
                    'latest_ts': metadata.get('latest_ts', ''),
                    'relevance_display': 'N/A'
                }
            }
            items.append(item)
        
        # Apply filters (simplified - you could implement more sophisticated filtering)
        filtered_items = []
        for item in items:
            # Source filter
            if source_filter != 'all':
                item_source = item['meta']['source'].lower()
                if source_filter.lower() not in item_source:
                    continue
            
            filtered_items.append(item)
        
        # Sort items
        if sort_order == 'newest':
            filtered_items.sort(key=lambda x: x['meta'].get('earliest_ts', ''), reverse=True)
        elif sort_order == 'oldest':
            filtered_items.sort(key=lambda x: x['meta'].get('earliest_ts', ''), reverse=False)
        # 'original' keeps the original order
        
        return filtered_items
    
    def clear_database(self):
        """Clear the entire database"""
        try:
            # Get the conversation model from search model
            self.search_model.conversation_model.delete_collection()
            return {"status": "success", "message": "Database cleared successfully"}, 200
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500
    
    def api_conversations(self):
        """API endpoint for paginated conversations list"""
        try:
            # Get pagination parameters
            try:
                page = int(request.args.get('page', 1))
                if page <= 0:
                    page = 1
            except (ValueError, TypeError):
                page = 1
                
            try:
                limit = int(request.args.get('limit', 50))
                if limit <= 0:
                    limit = 50
                limit = min(100, limit)  # Cap at 100
            except (ValueError, TypeError):
                limit = 50
            
            # Get all conversations
            all_docs = self.search_model.get_all_conversations(include=["documents", "metadatas"], limit=9999)
            
            if not all_docs or not all_docs.get("documents"):
                return jsonify({
                    "conversations": [],
                    "pagination": {
                        "page": page,
                        "limit": limit,
                        "total": 0,
                        "has_next": False,
                        "has_prev": False
                    }
                })
            
            # Transform conversations data for API response
            conversations = []
            for i, (doc, meta) in enumerate(zip(all_docs["documents"], all_docs.get("metadatas", []))):
                conversation = {
                    "id": meta.get("id", f"conv-{i}"),
                    "title": meta.get("title", "Untitled Conversation"),
                    "preview": extract_preview_content(doc, max_length=200) if doc else "",
                    "date": meta.get("earliest_ts", ""),
                    "source": meta.get("source", "unknown")
                }
                conversations.append(conversation)
            
            # Calculate pagination
            total = len(conversations)
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            page_conversations = conversations[start_idx:end_idx]
            
            return jsonify({
                "conversations": page_conversations,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "has_next": end_idx < total,
                    "has_prev": page > 1
                }
            })
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    def api_conversation(self, conversation_id):
        """Get a single conversation by ID in JSON format for the frontend MessageView"""
        try:
            # Get the conversation data
            doc_result = self.search_model.get_conversation_by_id(conversation_id)
            
            if not doc_result or not doc_result.get("documents"):
                return jsonify({"error": "Conversation not found"}), 404
            
            document = doc_result["documents"][0]
            metadata = doc_result["metadatas"][0] if doc_result.get("metadatas") else {}
            
            # Parse the conversation content into individual messages
            messages = self._parse_conversation_messages(document, metadata)
            
            # Determine assistant name based on source and document content
            assistant_name = self._determine_assistant_name(document, metadata)
            
            # Format response for MessageView component
            conversation_data = {
                "id": conversation_id,
                "title": metadata.get("title", "Untitled Conversation"),
                "source": metadata.get("source", "unknown"),
                "date": metadata.get("earliest_ts") or metadata.get("date"),
                "assistant_name": assistant_name,
                "messages": messages
            }
            
            return jsonify(conversation_data)
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    def _parse_conversation_messages(self, document, metadata):
        """Parse conversation content into individual messages"""
        messages = []
        source = metadata.get("source", "").lower()
        
        
        # Different patterns based on source
        if source == "chatgpt":
            # ChatGPT format: **You said** and **ChatGPT said**
            parts = document.split("**You said**")
            
            for i, part in enumerate(parts[1:], 1):  # Skip first empty part
                if "**ChatGPT said**" in part:
                    user_content, ai_content = part.split("**ChatGPT said**", 1)
                    
                    # Extract timestamp if present
                    user_timestamp = self._extract_timestamp(user_content)
                    ai_timestamp = self._extract_timestamp(ai_content)
                    
                    # Clean content
                    user_msg = self._clean_message_content(user_content)
                    ai_msg = self._clean_message_content(ai_content)
                    
                    if user_msg.strip():
                        messages.append({
                            "id": f"user-{i}",
                            "role": "user", 
                            "content": user_msg,
                            "timestamp": user_timestamp
                        })
                    
                    if ai_msg.strip():
                        messages.append({
                            "id": f"assistant-{i}",
                            "role": "assistant",
                            "content": ai_msg,
                            "timestamp": ai_timestamp
                        })
        
        elif source == "claude":
            # Claude format: **You said** and **Claude said**
            parts = document.split("**You said**")
            
            for i, part in enumerate(parts[1:], 1):
                if "**Claude said**" in part:
                    user_content, ai_content = part.split("**Claude said**", 1)
                    
                    user_timestamp = self._extract_timestamp(user_content)
                    ai_timestamp = self._extract_timestamp(ai_content)
                    
                    user_msg = self._clean_message_content(user_content)
                    ai_msg = self._clean_message_content(ai_content)
                    
                    if user_msg.strip():
                        messages.append({
                            "id": f"user-{i}",
                            "role": "user",
                            "content": user_msg,
                            "timestamp": user_timestamp
                        })
                    
                    if ai_msg.strip():
                        messages.append({
                            "id": f"assistant-{i}", 
                            "role": "assistant",
                            "content": ai_msg,
                            "timestamp": ai_timestamp
                        })
        
        else:
            # Generic format - try to split on common patterns
            if "**You said**" in document and "**AI said**" in document:
                parts = document.split("**You said**")
                for i, part in enumerate(parts[1:], 1):
                    if "**AI said**" in part:
                        user_content, ai_content = part.split("**AI said**", 1)
                        
                        user_msg = self._clean_message_content(user_content)
                        ai_msg = self._clean_message_content(ai_content)
                        
                        if user_msg.strip():
                            messages.append({
                                "id": f"user-{i}",
                                "role": "user",
                                "content": user_msg,
                                "timestamp": None
                            })
                        
                        if ai_msg.strip():
                            messages.append({
                                "id": f"assistant-{i}",
                                "role": "assistant", 
                                "content": ai_msg,
                                "timestamp": None
                            })
        
        return messages
    
    def _determine_assistant_name(self, document, metadata):
        """Determine the assistant name based on source and document content"""
        source = metadata.get("source", "").lower()
        
        if source == "claude":
            return "Claude"
        elif source == "chatgpt":
            return "ChatGPT"
        else:
            # Try to detect from document content
            if "**Claude said**" in document or "**Claude**:" in document:
                return "Claude"
            elif "**ChatGPT said**" in document or "**ChatGPT**:" in document:
                return "ChatGPT"
            else:
                # Default fallback for generic AI responses
                return "AI"
    
    def _extract_timestamp(self, content):
        """Extract timestamp from message content"""
        import re
        # Look for patterns like *(on 2025-04-05 02:20:02)*:
        timestamp_match = re.search(r'\*\(on ([\d\-\s:]+)\)\*', content)
        if timestamp_match:
            return timestamp_match.group(1)
        return None
    
    def _clean_message_content(self, content):
        """Clean message content by removing timestamps and formatting"""
        import re
        # Remove timestamp patterns
        content = re.sub(r'\*\(on [\d\-\s:]+\)\*', '', content)
        # Remove leading/trailing whitespace and newlines
        content = content.strip()
        # Remove leading colon and whitespace
        if content.startswith(':'):
            content = content[1:].strip()
        return content


class UploadController:
    """Controller for handling upload-related routes"""
    
    def __init__(self):
        self.search_model = SearchModel()
    
    def upload(self):
        if request.method == "POST":
            if "file" not in request.files:
                return "No file part", 400

            file = request.files["file"]
            if file.filename == "":
                return "No selected file", 400

            if file and file.filename.endswith(".json"):
                # Save file to temp location
                temp_path = "temp_upload.json"
                file.save(temp_path)

                # Index the file
                success, message = self.search_model.conversation_model.index_json(temp_path)

                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

                if success:
                    return f"Success: {message}", 200
                else:
                    return f"Error: {message}", 400

            elif file and file.filename.endswith(".docx"):
                # Save file to temp location
                temp_path = "temp_upload.docx"
                file.save(temp_path)

                # Make a temp directory for the file
                temp_dir = "temp_docx_dir"
                os.makedirs(temp_dir, exist_ok=True)
                os.rename(temp_path, os.path.join(temp_dir, file.filename))

                # Index the file
                success, message = self.search_model.conversation_model.index_docx(temp_dir)

                # Clean up temp files
                if os.path.exists(os.path.join(temp_dir, file.filename)):
                    os.remove(os.path.join(temp_dir, file.filename))
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)

                if success:
                    return f"Success: {message}", 200
                else:
                    return f"Error: {message}", 400

            else:
                return "Unsupported file type", 400

        return render_template("upload.html")
    
    def api_search(self):
        query = request.args.get("q")
        if not query:
            return {"error": "No query provided"}, 400

        n_results = int(request.args.get("n", 5))
        keyword = request.args.get("keyword", "false").lower() == "true"

        raw_results = self.search_model.search_conversations(
            query_text=query, n_results=n_results, keyword_search=keyword
        )

        results = []
        if raw_results["documents"][0]:
            for doc, meta in zip(raw_results["documents"][0], raw_results["metadatas"][0]):
                # Use cleaned preview content instead of raw document
                cleaned_preview = extract_preview_content(doc, max_length=300)
                
                results.append(
                    {
                        "title": meta.get("title", "Untitled"),
                        "date": meta.get("earliest_ts", "Unknown"),
                        "content": cleaned_preview,
                        "metadata": meta,
                    }
                )

        return {"query": query, "results": results}

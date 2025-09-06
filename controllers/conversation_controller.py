from flask import render_template, request, Response, redirect, url_for, jsonify
import os
from datetime import datetime

from forms import SearchForm
from models.search_model import SearchModel
from models.conversation_view_model import ConversationViewModel


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

        return render_template("view.html", conversation=conversation, messages=messages, assistant_name=assistant_name)
    
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
    
    def stats(self):
        """Display statistics about conversations"""
        # Get statistics from the model
        stats_data = self.search_model.get_statistics()
        return render_template("stats.html", stats=stats_data)
    
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
                    "preview": doc[:200] + ("..." if len(doc) > 200 else "") if doc else "",
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
                results.append(
                    {
                        "title": meta.get("title", "Untitled"),
                        "date": meta.get("earliest_ts", "Unknown"),
                        "content": doc,
                        "metadata": meta,
                    }
                )

        return {"query": query, "results": results}

import os
import re
from datetime import datetime, timedelta

from flask import render_template, request, Response
import markdown

from forms import SearchForm
from utils import highlight_concepts


def clean_message_content(content):
    """Clean artifacts and special tokens from message content"""
    if not content:
        return content
    
    # Remove common ChatGPT artifacts and tokens
    artifacts_to_remove = [
        r'citeturn\d+search\d+',  # citeturn0search3, etc.
        r'cite\d*',               # cite0, cite1, etc. and standalone 'cite'
        r'search\d+',             # search0, search1, etc.
        r'turn\d+',               # turn0, turn1, etc.
        r'\bcite\b',              # standalone 'cite' word
        r'\【\d+:\d+†[^】]*\】',   # Citation format like 【1:2†source】
        r'\【\d+†[^】]*\】',       # Citation format like 【1†source】
        r'\[\d+:\d+\]',           # Reference format like [1:2]
        r'\[\d+\]',               # Reference format like [1]
    ]
    
    cleaned_content = content
    for pattern in artifacts_to_remove:
        cleaned_content = re.sub(pattern, '', cleaned_content, flags=re.IGNORECASE)
    
    # Clean up extra whitespace
    cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
    cleaned_content = cleaned_content.strip()
    
    return cleaned_content


def parse_messages_from_document(document):
    """Parse a document into individual messages with role, content, and timestamp"""
    messages = []
    
    lines = document.split("\n")
    current_role = None
    current_content = []
    current_timestamp = None

    for line in lines:
        # Check for message headers with timestamps
        user_match = re.search(r"\*\*You said\*\* \*\(on ([^)]+)\)\*:", line)
        assistant_match = re.search(r"\*\*ChatGPT said\*\* \*\(on ([^)]+)\)\*:", line)
        system_match = re.search(r"\*([^*]+)\* \*\(on ([^)]+)\)\*:", line)

        if user_match:
            # Save previous message if any
            if current_role:
                # Clean and join content
                raw_content = "\n".join(current_content)
                cleaned_content = clean_message_content(raw_content)
                messages.append(
                    {
                        "role": current_role,
                        "content": markdown.markdown(
                            cleaned_content, extensions=["extra"]
                        ),
                        "timestamp": current_timestamp,
                    }
                )

            # Start new user message
            current_role = "user"
            current_content = []
            current_timestamp = user_match.group(1)

        elif assistant_match:
            # Save previous message if any
            if current_role:
                # Clean and join content
                raw_content = "\n".join(current_content)
                cleaned_content = clean_message_content(raw_content)
                messages.append(
                    {
                        "role": current_role,
                        "content": markdown.markdown(
                            cleaned_content, extensions=["extra"]
                        ),
                        "timestamp": current_timestamp,
                    }
                )

            # Start new assistant message
            current_role = "assistant"
            current_content = []
            current_timestamp = assistant_match.group(1)

        elif system_match:
            # Save previous message if any
            if current_role:
                # Clean and join content
                raw_content = "\n".join(current_content)
                cleaned_content = clean_message_content(raw_content)
                messages.append(
                    {
                        "role": current_role,
                        "content": markdown.markdown(
                            cleaned_content, extensions=["extra"]
                        ),
                        "timestamp": current_timestamp,
                    }
                )

            # Start new system message
            current_role = "system"
            current_content = []
            current_timestamp = system_match.group(2)

        elif current_role:
            # Add line to current message
            current_content.append(line)

    # Don't forget the last message
    if current_role:
        # Clean and join content
        raw_content = "\n".join(current_content)
        cleaned_content = clean_message_content(raw_content)
        messages.append(
            {
                "role": current_role,
                "content": markdown.markdown(
                    cleaned_content, extensions=["extra"]
                ),
                "timestamp": current_timestamp,
            }
        )

    return messages


def init_routes(app, archive):
    """Initialize all Flask routes"""

    @app.route("/", methods=["GET", "POST"])
    def index():
        search_form = SearchForm()
        search_triggered = False
        results = []
        stats = {}

        # Get DB stats
        doc_count = archive.get_count()
        stats["doc_count"] = doc_count

        # Check if search was triggered (either by form submission or URL parameter)
        query = None

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

        # Perform search if triggered
        if search_triggered and query:
            # Default values for optional parameters
            n_results = 5
            keyword_search = False
            date_range = None

            # Use form values if available (POST method) or defaults (GET method with URL params)
            if request.method == "POST" and hasattr(search_form, "results_count"):
                n_results = search_form.results_count.data or 5

            if request.method == "POST" and hasattr(search_form, "search_type"):
                keyword_search = search_form.search_type.data == "keyword"

            if (
                request.method == "POST"
                and hasattr(search_form, "date_from")
                and hasattr(search_form, "date_to")
            ):
                if search_form.date_from.data and search_form.date_to.data:
                    date_range = (search_form.date_from.data, search_form.date_to.data)

            # Perform search
            raw_results = archive.search(
                query_text=query,
                n_results=n_results,
                date_range=date_range,
                keyword_search=keyword_search,
            )

            # Process results
            if raw_results["documents"][0]:
                for doc, meta in zip(
                    raw_results["documents"][0], raw_results["metadatas"][0]
                ):
                    # Parse document into individual messages
                    messages = parse_messages_from_document(doc)

                    # Get dates from metadata
                    date_str = meta.get("earliest_ts", "Unknown date")
                    if date_str != "Unknown date":
                        try:
                            date_obj = datetime.fromisoformat(date_str)
                            date_str = date_obj.strftime("%Y-%m-%d %H:%M")
                        except:
                            pass

                    results.append(
                        {
                            "title": meta.get("title", "Untitled"),
                            "date": date_str,
                            "messages": messages,
                            "meta": meta,
                        }
                    )

        return render_template(
            "index.html",
            search_form=search_form,
            search_triggered=search_triggered,
            results=results,
            stats=stats,
            request=request,  # Pass request object to template
        )

    @app.route("/upload", methods=["GET", "POST"])
    def upload():
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
                success, message = archive.index_json(temp_path)

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
                success, message = archive.index_docx(temp_dir)

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

    @app.route("/api/search", methods=["GET"])
    def api_search():
        query = request.args.get("q")
        if not query:
            return {"error": "No query provided"}, 400

        n_results = int(request.args.get("n", 5))
        keyword = request.args.get("keyword", "false").lower() == "true"

        raw_results = archive.search(
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

    @app.route("/stats")
    def stats():
        # Get basic stats
        doc_count = archive.get_count()

        # Get all metadata to analyze
        all_meta = archive.get_documents(include=["metadatas"], limit=9999)["metadatas"]

        # Count by source
        sources = {}
        for meta in all_meta:
            source = meta.get("source", "unknown")
            sources[source] = sources.get(source, 0) + 1

        # Get date range
        dates = [meta.get("earliest_ts") for meta in all_meta if meta.get("earliest_ts")]
        date_range = None
        if dates:
            dates.sort()
            date_range = {"earliest": dates[0], "latest": dates[-1]}

        # Count by chunks
        chunked = sum(1 for meta in all_meta if meta.get("is_chunk", False))

        stats_data = {
            "total": doc_count,
            "sources": sources,
            "date_range": date_range,
            "chunked": chunked,
            "full": doc_count - chunked,
        }

        return render_template("stats.html", stats=stats_data)

    @app.route("/conversations")
    @app.route("/conversations/<int:page>")
    def conversations(page=1):
        """Display all documents in a list with filtering and pagination"""
        # Items per page
        per_page = 20

        # Get filter parameters from URL
        source_filter = request.args.get("source", "all")
        date_filter = request.args.get("date", "all")
        sort_order = request.args.get("sort", "newest")

        # Get ALL documents directly, but only include valid parameters
        all_docs = archive.get_documents(include=["documents", "metadatas"], limit=9999)

        if not all_docs or not all_docs.get("documents"):
            print("DEBUG: No documents found in the database")
            return render_template("conversations.html", conversations=None)

        print(f"DEBUG: Found {len(all_docs['documents'])} total documents")

        # Get all items - with minimal processing and filtering
        items = []

        for idx, doc in enumerate(all_docs["documents"]):
            # Get metadata for this document
            meta = (
                all_docs["metadatas"][idx]
                if idx < len(all_docs.get("metadatas", []))
                else {}
            )

            # IDs are returned automatically with the query
            doc_id = (
                all_docs["ids"][idx]
                if "ids" in all_docs and idx < len(all_docs["ids"])
                else f"doc-{idx}"
            )

            # Skip empty documents
            if not doc or not doc.strip():
                continue

            # Basic preview
            preview = doc[:500] + "..." if len(doc) > 500 else doc
            preview_html = markdown.markdown(preview, extensions=["extra"])

            # Get a title - with fallbacks
            title = meta.get("title", "")
            if not title:
                # Try to extract a title from the first line of content
                first_line = doc.split("\n")[0] if doc else ""
                if (
                    first_line and len(first_line) < 100
                ):  # Only use as title if reasonably short
                    title = first_line.strip("# ")
                else:
                    title = f"Conversation {idx+1}"

            # Get a date for sorting
            date_obj = None

            # Try standard metadata fields
            for date_field in [
                "update_time",
                "create_time",
                "latest_ts",
                "earliest_ts",
                "modified",
                "created",
            ]:
                if meta.get(date_field) and not date_obj:
                    try:
                        date_value = meta[date_field]
                        # Handle epoch timestamps (floating point seconds)
                        if isinstance(date_value, (float, int)):
                            date_obj = datetime.fromtimestamp(date_value)
                            break
                        # Handle ISO format strings
                        elif isinstance(date_value, str):
                            date_obj = datetime.fromisoformat(date_value)
                            break
                    except (ValueError, TypeError):
                        pass

            # Try to extract any date from the document content
            if not date_obj:
                date_patterns = [
                    r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}",  # ISO format or space-separated
                    r"\d{4}-\d{2}-\d{2}",  # Just date
                    r"\d{2}/\d{2}/\d{4}",  # MM/DD/YYYY
                    r"\w+ \d{1,2}, \d{4}",  # Month Day, Year
                ]

                for pattern in date_patterns:
                    matches = re.findall(pattern, doc)
                    if matches:
                        try:
                            date_str = matches[0]
                            # Try different date formats
                            for fmt in (
                                "%Y-%m-%d %H:%M:%S",
                                "%Y-%m-%dT%H:%M:%S",
                                "%Y-%m-%d",
                                "%m/%d/%Y",
                                "%B %d, %Y",
                            ):
                                try:
                                    date_obj = datetime.strptime(date_str, fmt)
                                    break
                                except ValueError:
                                    continue
                            if date_obj:
                                break
                        except:
                            pass

            # Last resort: use creation time of metadata if available
            if not date_obj:
                # Use current time as absolute last resort
                date_obj = datetime.now()

            # Store original index in metadata for ordering
            meta["original_index"] = idx

            # Add to items list
            items.append(
                {
                    "id": doc_id,
                    "meta": {
                        "title": title,
                        "source": meta.get("source", "unknown"),
                        "earliest_ts": meta.get("earliest_ts", ""),
                        "message_count": meta.get("message_count", 0),
                        "original_index": meta.get("original_index", idx),
                    },
                    "date_obj": date_obj,
                    "preview": preview_html,
                }
            )

        print(f"DEBUG: Processed {len(items)} valid items for display")

        # Apply source filter
        if source_filter != "all":
            items = [item for item in items if item["meta"].get("source") == source_filter]

        # Apply date filter
        if date_filter != "all":
            now = datetime.now()
            if date_filter == "today":
                items = [item for item in items if item["date_obj"].date() == now.date()]
            elif date_filter == "week":
                week_ago = now - timedelta(days=7)
                items = [item for item in items if item["date_obj"] >= week_ago]
            elif date_filter == "month":
                month_ago = now - timedelta(days=30)
                items = [item for item in items if item["date_obj"] >= month_ago]
            elif date_filter == "year":
                year_ago = now - timedelta(days=365)
                items = [item for item in items if item["date_obj"] >= year_ago]

        # Apply sort order
        if sort_order == "newest":
            # Sort by date (newest first)
            items.sort(key=lambda x: x["date_obj"], reverse=True)
        elif sort_order == "oldest":
            # Sort by date (oldest first)
            items.sort(key=lambda x: x["date_obj"])
        elif sort_order == "original":
            # Sort by original order
            items.sort(key=lambda x: x["meta"].get("original_index", float("inf")))

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
        )

    @app.route("/view/<doc_id>")
    def view_conversation(doc_id):
        """View a single conversation"""
        # Get document by ID using the where filter
        # Since we can't use the 'ids' parameter directly, we need to use 'where' with a field that contains the ID

        # First, try to get the document with the ID in the 'id' field
        doc_result = archive.get_documents(
            where={"id": doc_id}, include=["documents", "metadatas"]
        )

        # If that doesn't work, the ID might be stored in other fields or be a generated ID like 'chat-0'
        if not doc_result or not doc_result.get("documents") or not doc_result["documents"]:
            # If doc_id is in the format "chat-X", extract the index
            if doc_id.startswith("chat-"):
                try:
                    idx = int(doc_id.split("-")[1])
                    # Get all documents and find the one with the matching index
                    all_docs = archive.get_documents(
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
                            "ids": [
                                all_docs["ids"][idx]
                                if "ids" in all_docs and idx < len(all_docs["ids"])
                                else doc_id
                            ],
                        }
                    else:
                        # Document not found
                        return "Conversation not found", 404
                except (ValueError, IndexError):
                    # Invalid chat-X format
                    return "Conversation not found", 404
            else:
                # Try other possible ID fields
                where_conditions = [{"conversation_id": doc_id}, {"original_index": doc_id}]

                for condition in where_conditions:
                    doc_result = archive.get_documents(
                        where=condition, include=["documents", "metadatas"]
                    )
                    if (
                        doc_result
                        and doc_result.get("documents")
                        and doc_result["documents"]
                    ):
                        break

                # If still not found
                if (
                    not doc_result
                    or not doc_result.get("documents")
                    or not doc_result["documents"]
                ):
                    return "Conversation not found", 404

        document = doc_result["documents"][0]
        metadata = doc_result["metadatas"][0] if doc_result.get("metadatas") else {}

        # Parse the document to extract messages
        messages = []

        # Simple parsing of markdown format with "You said" and "ChatGPT said" headers
        # This is a basic implementation - might need adjustment based on actual format
        lines = document.split("\n")
        current_role = None
        current_content = []
        current_timestamp = None

        for line in lines:
            # Check for message headers with timestamps
            user_match = re.search(r"\*\*You said\*\* \*\(on ([^)]+)\)\*:", line)
            assistant_match = re.search(r"\*\*ChatGPT said\*\* \*\(on ([^)]+)\)\*:", line)
            system_match = re.search(r"\*([^*]+)\* \*\(on ([^)]+)\)\*:", line)

            if user_match:
                # Save previous message if any
                if current_role:
                    messages.append(
                        {
                            "role": current_role,
                            "content": markdown.markdown(
                                "\n".join(current_content), extensions=["extra"]
                            ),
                            "timestamp": current_timestamp,
                        }
                    )

                # Start new user message
                current_role = "user"
                current_content = []
                current_timestamp = user_match.group(1)

            elif assistant_match:
                # Save previous message if any
                if current_role:
                    messages.append(
                        {
                            "role": current_role,
                            "content": markdown.markdown(
                                "\n".join(current_content), extensions=["extra"]
                            ),
                            "timestamp": current_timestamp,
                        }
                    )

                # Start new assistant message
                current_role = "assistant"
                current_content = []
                current_timestamp = assistant_match.group(1)

            elif system_match:
                # Save previous message if any
                if current_role:
                    messages.append(
                        {
                            "role": current_role,
                            "content": markdown.markdown(
                                "\n".join(current_content), extensions=["extra"]
                            ),
                            "timestamp": current_timestamp,
                        }
                    )

                # Start new system message
                current_role = "system"
                current_content = []
                current_timestamp = system_match.group(2)

            elif current_role:
                # Add line to current message
                current_content.append(line)

        # Don't forget the last message
        if current_role:
            messages.append(
                {
                    "role": current_role,
                    "content": markdown.markdown(
                        "\n".join(current_content), extensions=["extra"]
                    ),
                    "timestamp": current_timestamp,
                }
            )

        # Create conversation object
        conversation = {"id": doc_id, "meta": metadata, "document": document}

        return render_template("view.html", conversation=conversation, messages=messages)

    @app.route("/export/<doc_id>")
    def export_conversation(doc_id):
        """Export a conversation as markdown"""
        # Get document by ID using the where filter
        # First, try to get the document with the ID in the 'id' field
        doc_result = archive.get_documents(
            where={"id": doc_id}, include=["documents", "metadatas"]
        )

        # If that doesn't work, the ID might be stored in other fields or be a generated ID like 'chat-0'
        if not doc_result or not doc_result.get("documents") or not doc_result["documents"]:
            # If doc_id is in the format "chat-X", extract the index
            if doc_id.startswith("chat-"):
                try:
                    idx = int(doc_id.split("-")[1])
                    # Get all documents and find the one with the matching index
                    all_docs = archive.get_documents(
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
                    # Invalid chat-X format
                    return "Conversation not found", 404
            else:
                # Try other possible ID fields
                where_conditions = [{"conversation_id": doc_id}, {"original_index": doc_id}]

                for condition in where_conditions:
                    doc_result = archive.get_documents(
                        where=condition, include=["documents", "metadatas"]
                    )
                    if (
                        doc_result
                        and doc_result.get("documents")
                        and doc_result["documents"]
                    ):
                        break

                # If still not found
                if (
                    not doc_result
                    or not doc_result.get("documents")
                    or not doc_result["documents"]
                ):
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

    @app.route("/clear_db", methods=["POST"])
    def clear_database():
        """Clear the entire database"""
        try:
            archive.delete_collection()
            return {"status": "success", "message": "Database cleared successfully"}, 200
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500
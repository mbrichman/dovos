import re
from datetime import datetime, timedelta
import markdown

from models import BaseModel


def clean_message_content(content):
    """Clean artifacts and special tokens from message content while preserving markdown"""
    if not content or not isinstance(content, str):
        return content
    
    # Remove ChatGPT private use area Unicode characters (formatting markers)
    cleaned = re.sub(r'[\ue000-\uf8ff]', '', content)
    
    # Remove ChatGPT plugin/tool artifacts
    cleaned = re.sub(r'businesses_map\{[^}]*\}', '', cleaned)
    cleaned = re.sub(r'businesses_map(?=\s|$)', '', cleaned)
    cleaned = re.sub(r'[a-zA-Z_]+_map\{[^}]*\}', '', cleaned)
    cleaned = re.sub(r'\{"name":"[^}]*","location":"[^}]*","description":"[^}]*","[^}]*"\}', '', cleaned)
    cleaned = re.sub(r'"cite":"turn\d+search\d+"', '', cleaned)
    
    # Remove common ChatGPT citation artifacts
    cleaned = re.sub(r'citeturn\d+search\d+', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\【\d+:\d+†[^】]*\】', '', cleaned)   # Citation format like 【1:2†source】
    cleaned = re.sub(r'\【\d+†[^】]*\】', '', cleaned)       # Citation format like 【1†source】
    cleaned = re.sub(r'\[\d+:\d+\]', '', cleaned)           # Reference format like [1:2]
    cleaned = re.sub(r'\[\d+\]', '', cleaned)               # Reference format like [1]
    
    # Clean up excessive whitespace but preserve markdown structure
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)     # Multiple spaces/tabs to single space
    cleaned = re.sub(r'\n[ \t]+', '\n', cleaned)  # Remove spaces at start of lines
    cleaned = re.sub(r'[ \t]+\n', '\n', cleaned)  # Remove spaces at end of lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)  # Limit consecutive newlines to 2
    
    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()
    
    return cleaned


def parse_messages_from_document(document):
    """Parse a document into individual messages with role, content, and timestamp"""
    messages = []
    
    lines = document.split("\n")
    current_role = None
    current_content = []
    current_timestamp = None

    for line in lines:
        # Check for message headers with timestamps (JSON format) or without (DOCX format)
        user_match = re.search(r"\*\*You said\*\* \*\(on ([^)]+)\)\*:", line) or re.search(r"\*\*You\*\*:", line)
        assistant_match = (
            re.search(r"\*\*(ChatGPT|Claude) said\*\* \*\(on ([^)]+)\)\*:", line) or 
            re.search(r"\*\*(ChatGPT|Claude)\*\*:", line)
        )
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
                            cleaned_content, extensions=["extra", "tables"]
                        ),
                        "timestamp": current_timestamp,
                    }
                )

            # Start new user message
            current_role = "user"
            current_content = []
            # Extract timestamp if it exists (JSON format has it, DOCX format doesn't)
            if hasattr(user_match, 'group') and user_match.lastindex and user_match.lastindex >= 1:
                try:
                    current_timestamp = user_match.group(1)
                except (AttributeError, IndexError):
                    current_timestamp = None
            else:
                current_timestamp = None

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
                            cleaned_content, extensions=["extra", "tables"]
                        ),
                        "timestamp": current_timestamp,
                    }
                )

            # Start new assistant message
            current_role = "assistant"
            current_content = []
            # Extract timestamp if it exists (JSON format has it, DOCX format doesn't)
            if hasattr(assistant_match, 'group') and assistant_match.lastindex and assistant_match.lastindex >= 2:
                try:
                    current_timestamp = assistant_match.group(2)  # Timestamp is now group 2 due to (ChatGPT|Claude) being group 1
                except (AttributeError, IndexError):
                    current_timestamp = None
            else:
                current_timestamp = None

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
                            cleaned_content, extensions=["extra", "tables"]
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
                    cleaned_content, extensions=["extra", "tables"]
                ),
                "timestamp": current_timestamp,
            }
        )

    return messages


class ConversationViewModel(BaseModel):
    """Model for handling conversation presentation logic"""
    
    def __init__(self):
        self.initialize()
    
    def initialize(self):
        """Initialize the view model"""
        pass
    
    def format_conversations_list(self, conversations_data, source_filter="all", date_filter="all", sort_order="newest"):
        """Format conversations for list display"""
        # Get all items - with minimal processing and filtering
        items = []

        for idx, doc in enumerate(conversations_data["documents"]):
            # Get metadata for this document
            meta = (
                conversations_data["metadatas"][idx]
                if idx < len(conversations_data.get("metadatas", []))
                else {}
            )

            # IDs are returned automatically with the query
            doc_id = (
                conversations_data["ids"][idx]
                if "ids" in conversations_data and idx < len(conversations_data["ids"])
                else f"doc-{idx}"
            )

            # Skip empty documents
            if not doc or not doc.strip():
                continue

            # Basic preview
            preview = doc[:500] + "..." if len(doc) > 500 else doc
            preview_html = markdown.markdown(preview, extensions=["extra", "tables"])

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
                            date_obj = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                            # Convert to timezone-naive for consistent sorting
                            if date_obj.tzinfo is not None:
                                date_obj = date_obj.replace(tzinfo=None)
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
                # Use a very old date as fallback so undated conversations don't interfere with date filters
                date_obj = datetime(1970, 1, 1)

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

        # Apply filters
        items = self._filter_by_source(items, source_filter)
        items = self._filter_by_date(items, date_filter)

        # Apply sorting
        items = self._apply_sorting(items, sort_order)
        
        return items
    
    def format_search_results(self, search_results):
        """Format search results for display"""
        # Convert search results to items format
        items = []
        if search_results["documents"][0]:
            # Get distances if available (for relevance scoring)
            distances = search_results.get("distances", [[]])[0]
            
            for i, (doc, meta) in enumerate(zip(
                search_results["documents"][0], search_results["metadatas"][0]
            )):
                # Get relevance score (distance - lower is better)
                relevance_score = distances[i] if i < len(distances) else None
                
                # Get conversation ID for the view link
                conv_id = (
                    meta.get("id") or 
                    meta.get("conversation_id") or
                    f"unknown-{len(items)}"
                )
                
                # Get title
                title = meta.get("title", "Untitled")
                
                # Get dates from metadata
                date_obj = None
                date_str = meta.get("earliest_ts", "Unknown date")
                if date_str != "Unknown date":
                    try:
                        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        if date_obj.tzinfo is not None:
                            date_obj = date_obj.replace(tzinfo=None)
                    except:
                        date_obj = datetime(1970, 1, 1)
                else:
                    date_obj = datetime(1970, 1, 1)

                # Basic preview
                preview = doc[:500] + "..." if len(doc) > 500 else doc
                preview_html = markdown.markdown(preview, extensions=["extra", "tables"])

                items.append({
                    "id": conv_id,
                    "meta": {
                        "title": title,
                        "source": meta.get("source", "unknown"),
                        "earliest_ts": meta.get("earliest_ts", ""),
                        "message_count": meta.get("message_count", 0),
                        "relevance_score": relevance_score,
                        "relevance_display": f"{relevance_score:.3f}" if relevance_score is not None else "N/A",
                    },
                    "date_obj": date_obj,
                    "preview": preview_html,
                })
        
        return items
    
    def format_conversation_view(self, document, metadata):
        """Format a single conversation for detailed view"""
        # Parse the document to extract messages
        messages = parse_messages_from_document(document)

        # Determine assistant name based on source
        assistant_name = "Claude" if metadata.get("source") == "claude" else "ChatGPT"
        
        # Create conversation object
        conversation = {"meta": metadata, "document": document}
        
        return conversation, messages, assistant_name
    
    # Filter functions
    def _filter_by_source(self, items, source_filter):
        """Filter conversations by source type"""
        if source_filter == "all":
            return items
        
        filtered = [item for item in items if item["meta"].get("source") == source_filter]
        return filtered

    def _filter_by_date(self, items, date_filter):
        """Filter conversations by date range"""
        if date_filter == "all":
            return items
        
        now = datetime.now()
        today = now.date()
        
        if date_filter == "today":
            filtered = [item for item in items if item["date_obj"].date() == today]
            return filtered
            
        elif date_filter == "week":
            week_ago = now - timedelta(days=7)
            filtered = [item for item in items if item["date_obj"] >= week_ago]
            return filtered
            
        elif date_filter == "month":
            month_ago = now - timedelta(days=30)
            filtered = [item for item in items if item["date_obj"] >= month_ago]
            return filtered
            
        elif date_filter == "year":
            year_ago = now - timedelta(days=365)
            filtered = [item for item in items if item["date_obj"] >= year_ago]
            return filtered
        
        # Unknown date filter, return all items
        return items

    def _apply_sorting(self, items, sort_order):
        """Apply sorting to conversation items"""
        if sort_order == "newest":
            return sorted(items, key=lambda x: x["date_obj"], reverse=True)
        elif sort_order == "oldest":
            return sorted(items, key=lambda x: x["date_obj"])
        elif sort_order == "original":
            return sorted(items, key=lambda x: x["meta"].get("original_index", 0))
        else:
            # Default to newest first
            return sorted(items, key=lambda x: x["date_obj"], reverse=True)

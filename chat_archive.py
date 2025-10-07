import json
import os
import re
from datetime import datetime
from pathlib import Path

from sentence_transformers import SentenceTransformer
import chromadb
from docx import Document

from config import COLLECTION_NAME, PERSIST_DIR, DEFAULT_EMBEDDING_MODEL
from utils import expand_query_with_stems


def clean_text_content(text):
    """Clean text content by removing non-printable characters and ChatGPT artifacts while preserving markdown"""
    if not text or not isinstance(text, str):
        return text
    
    # Remove ChatGPT private use area Unicode characters (formatting markers)
    cleaned = re.sub(r'[\ue000-\uf8ff]', '', text)
    
    # Remove ChatGPT plugin/tool artifacts
    cleaned = re.sub(r'businesses_map\{[^}]*\}', '', cleaned)
    cleaned = re.sub(r'businesses_map(?=\s|$)', '', cleaned)
    cleaned = re.sub(r'[a-zA-Z_]+_map\{[^}]*\}', '', cleaned)
    cleaned = re.sub(r'\{"name":"[^}]*","location":"[^}]*","description":"[^}]*","[^}]*"\}', '', cleaned)
    cleaned = re.sub(r'"cite":"turn\d+search\d+"', '', cleaned)
    
    # Clean up excessive whitespace but preserve markdown structure
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)     # Multiple spaces/tabs to single space
    cleaned = re.sub(r'\n[ \t]+', '\n', cleaned)  # Remove spaces at start of lines
    cleaned = re.sub(r'[ \t]+\n', '\n', cleaned)  # Remove spaces at end of lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)  # Limit consecutive newlines to 2
    
    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()
    
    return cleaned


class ChatArchive:
    def __init__(self):
        self.embedder = None
        self.chroma_client = None
        self.collection = None
        self._initialize()

    def _initialize(self):
        """Initialize embedding model and database connection"""
        # Initialize chromadb client
        self.chroma_client = chromadb.PersistentClient(path=PERSIST_DIR)

        # Initialize collection
        self.collection = self.chroma_client.get_or_create_collection(
            COLLECTION_NAME,
            metadata={
                "description": "ChatGPT conversation history with timestamp indexing"
            },
        )

    def load_embedder(self):
        """Load the embedding model (done lazily to save resources)"""
        if self.embedder is None:
            print("Loading embedding model...")
            self.embedder = SentenceTransformer(DEFAULT_EMBEDDING_MODEL)
        return self.embedder

    def get_count(self):
        """Get the number of documents in the collection"""
        return self.collection.count()

    def delete_collection(self):
        """Delete the collection"""
        self.chroma_client.delete_collection(COLLECTION_NAME)
        # Reinitialize
        self.collection = self.chroma_client.create_collection(COLLECTION_NAME)

    def add_documents(self, documents, embeddings, metadatas, ids):
        """Add documents to the collection"""
        self.collection.add(
            documents=documents, embeddings=embeddings, metadatas=metadatas, ids=ids
        )

    def query(self, query_embeddings, n_results=5, where=None, include_distances=False):
        """Query the collection"""
        include_list = ["documents", "metadatas"]
        if include_distances:
            include_list.append("distances")
            
        if where:
            return self.collection.query(
                query_embeddings=query_embeddings, n_results=n_results, where=where, include=include_list
            )
        else:
            return self.collection.query(
                query_embeddings=query_embeddings, n_results=n_results, include=include_list
            )

    def get_documents(self, where=None, include=None, limit=None):
        """Get documents from the collection"""
        kwargs = {}
        if where:
            kwargs["where"] = where
        if include:
            kwargs["include"] = include
        if limit:
            kwargs["limit"] = limit

        return self.collection.get(**kwargs)

    def search(self, query_text, n_results=5, date_range=None, keyword_search=False):
        """Unified search interface"""
        # Load embedder if needed
        embedder = self.load_embedder()

        # Handle date filtering
        date_filter = None
        if date_range:
            start_date, end_date = date_range
            if start_date and end_date:
                date_filter = {
                    "$and": [
                        {"earliest_ts": {"$gte": start_date}},
                        {"latest_ts": {"$lte": end_date}},
                    ]
                }

        if keyword_search:
            # Use improved keyword search with stemming
            return self._keyword_search_with_stemming(query_text, n_results, date_filter)
        else:
            # Vector search
            embedding = embedder.encode([query_text])[0]

            # Perform the query with date filter if specified
            return self.query(
                query_embeddings=[embedding.tolist()],
                n_results=n_results,
                where=date_filter,
                include_distances=True,
            )

    def _keyword_search_with_stemming(self, query_text, n_results, date_filter):
        """
        Improved keyword search using stemming and query expansion
        """
        # Get expanded query terms with stemming
        expanded_terms = expand_query_with_stems(query_text)
        
        # Get all documents for filtering
        all_docs = self.get_documents(
            where=date_filter, include=["documents", "metadatas"], limit=9999
        )
        
        if not all_docs or not all_docs.get("documents"):
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        
        # Score documents based on term matches
        matches = []
        
        for idx, doc in enumerate(all_docs["documents"]):
            doc_lower = doc.lower()
            score = 0
            term_matches = 0
            
            # Score based on term frequency and importance
            for term in expanded_terms:
                term_lower = term.lower()
                if term_lower in doc_lower:
                    # Count occurrences
                    occurrences = doc_lower.count(term_lower)
                    
                    # Weight different types of matches
                    if term in query_text.lower():
                        # Original query terms get higher weight
                        score += occurrences * 2
                    else:
                        # Expanded terms get lower weight
                        score += occurrences * 1
                    
                    term_matches += 1
            
            # Only include documents that have at least one term match
            if term_matches > 0:
                # Bonus for matching more distinct terms
                score += term_matches * 5
                
                # Add title matching bonus
                title = all_docs["metadatas"][idx].get("title", "").lower()
                for term in expanded_terms:
                    if term.lower() in title:
                        score += 10  # Title matches are important
                
                matches.append({
                    "doc": doc,
                    "metadata": all_docs["metadatas"][idx],
                    "score": score,
                    "term_matches": term_matches
                })
        
        # Sort by score (higher = better for keyword search)
        matches.sort(key=lambda x: x["score"], reverse=True)
        
        # Take top n_results
        top_matches = matches[:n_results]
        
        if not top_matches:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        
        # Format results similar to vector search
        documents = [m["doc"] for m in top_matches]
        metadatas = [m["metadata"] for m in top_matches]
        # Convert keyword scores to distance-like scores (invert so lower is better)
        max_score = max(m["score"] for m in top_matches) if top_matches else 1
        distances = [1.0 - (m["score"] / max_score) for m in top_matches]
        
        return {"documents": [documents], "metadatas": [metadatas], "distances": [distances]}

    def index_json(self, json_path, chunk_size=0):
        """Index conversations from a JSON export (supports ChatGPT and Claude formats)"""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print("Invalid JSON file")
            return False, "Invalid JSON file"
        except FileNotFoundError:
            print(f"File '{json_path}' not found")
            return False, f"File '{json_path}' not found"

        # Load embedder
        embedder = self.load_embedder()

        # Detect format and get conversations
        conversations, file_format = self._detect_json_format(data)
        print(f"Detected {file_format} format with {len(conversations)} conversations")

        if len(conversations) == 0:
            return False, "No conversations found in the JSON file"

        # Get existing conversation IDs to avoid duplicates (only same format)
        existing_docs = self.get_documents(include=["metadatas"], limit=9999)
        existing_conv_ids = set()
        for meta in existing_docs.get("metadatas", []):
            # Only check for duplicates within the same source format
            if meta.get("source") == file_format.lower():
                conv_id = meta.get("conversation_id") or meta.get("id")
                if conv_id:
                    existing_conv_ids.add(conv_id)
        
        print(f"Found {len(existing_conv_ids)} existing {file_format} conversation IDs")

        documents, metadatas, ids = [], [], []
        skipped_duplicates = 0
        processed_count = 0

        for idx, conv in enumerate(conversations):
            if file_format == "ChatGPT":
                processed_conv = self._process_chatgpt_conversation(conv, idx)
            elif file_format == "Claude":
                processed_conv = self._process_claude_conversation(conv, idx)
            else:
                print(f"Unknown format, skipping conversation {idx}")
                continue
                
            if not processed_conv:
                continue
                
            messages, timestamps, title = processed_conv

            # Check for duplicates using conversation ID
            conv_id = conv.get("id") or conv.get("uuid")
            if conv_id and conv_id in existing_conv_ids:
                skipped_duplicates += 1
                continue

            # Skip empty conversations
            if not messages or not any(msg.strip() for msg in messages):
                print(f"Skipping empty conversation {idx}: {title}")
                continue

            # Calculate earliest and latest timestamps
            valid_timestamps = [ts for ts in timestamps if ts]
            earliest_ts = min(valid_timestamps) if valid_timestamps else None
            latest_ts = max(valid_timestamps) if valid_timestamps else None

            # Convert timestamps to ISO format for better filtering
            if file_format == "ChatGPT":
                # ChatGPT timestamps are Unix epoch seconds
                earliest_ts_iso = (
                    datetime.fromtimestamp(earliest_ts).isoformat() if earliest_ts else None
                )
                latest_ts_iso = (
                    datetime.fromtimestamp(latest_ts).isoformat() if latest_ts else None
                )
            elif file_format == "Claude":
                # Claude timestamps are already ISO strings
                earliest_ts_iso = earliest_ts
                latest_ts_iso = latest_ts

            full_text = "\n\n".join(messages)

            # Skip empty conversations
            if not full_text.strip():
                continue

            # Handle chunking if enabled
            if chunk_size > 0 and len(messages) > chunk_size:
                chunks = [
                    messages[i : i + chunk_size]
                    for i in range(0, len(messages), chunk_size)
                ]

                for chunk_idx, chunk in enumerate(chunks):
                    chunk_text = "\n\n".join(chunk)
                    chunk_title = f"{title} (Part {chunk_idx+1}/{len(chunks)})"

                    documents.append(chunk_text)

                    # Create a metadata dict with no None values
                    metadata_dict = {
                        "title": chunk_title,
                        "source": file_format.lower(),
                        "message_count": len(chunk),
                        "is_chunk": True,
                        "chunk_index": chunk_idx,
                        "total_chunks": len(chunks),
                    }

                    # Only add fields that aren't None
                    conv_id = conv.get("id") or conv.get("uuid")
                    if conv_id:
                        metadata_dict["id"] = f"{conv_id}-{chunk_idx}"
                        metadata_dict["conversation_id"] = conv_id
                    if earliest_ts_iso:
                        metadata_dict["earliest_ts"] = earliest_ts_iso
                    if latest_ts_iso:
                        metadata_dict["latest_ts"] = latest_ts_iso

                    metadatas.append(metadata_dict)
                    ids.append(f"{file_format.lower()}-chat-{idx}-chunk-{chunk_idx}")
            else:
                documents.append(full_text)

                # Create a metadata dict with no None values
                metadata_dict = {
                    "title": title,
                    "source": file_format.lower(),
                    "message_count": len(messages),
                    "is_chunk": False,
                }

                # Only add fields that aren't None
                conv_id = conv.get("id") or conv.get("uuid")
                if conv_id:
                    metadata_dict["id"] = conv_id
                if earliest_ts_iso:
                    metadata_dict["earliest_ts"] = earliest_ts_iso
                if latest_ts_iso:
                    metadata_dict["latest_ts"] = latest_ts_iso

                metadatas.append(metadata_dict)
                ids.append(f"{file_format.lower()}-chat-{idx}")

        if not documents:
            if skipped_duplicates > 0:
                return True, f"All {skipped_duplicates} conversations already indexed (no new content)"
            else:
                return False, "No valid conversations found to index"

        # Process in batches to avoid memory issues with large datasets
        batch_size = 100
        total_indexed = 0

        for i in range(0, len(documents), batch_size):
            end = min(i + batch_size, len(documents))

            batch_docs = documents[i:end]
            batch_metas = metadatas[i:end]
            batch_ids = ids[i:end]

            embeddings = embedder.encode(batch_docs, show_progress_bar=False)

            try:
                self.add_documents(
                    documents=batch_docs,
                    embeddings=embeddings.tolist(),
                    metadatas=batch_metas,
                    ids=batch_ids,
                )
                total_indexed += len(batch_docs)
                print(f"Indexed batch {i//batch_size + 1}: {len(batch_docs)} documents")
            except Exception as e:
                print(f"Error indexing batch {i//batch_size + 1}: {e}")
                # Continue with remaining batches rather than failing completely
                continue

        message = f"Successfully indexed {total_indexed} documents"
        if skipped_duplicates > 0:
            message += f" (skipped {skipped_duplicates} duplicates)"
        
        return True, message

    def _detect_json_format(self, data):
        """Detect whether JSON is ChatGPT or Claude format"""
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
        
    def _process_chatgpt_conversation(self, conv, idx):
        """Process a ChatGPT format conversation"""
        messages = []
        message_map = conv.get("mapping", {})
        ordered = sorted(
            message_map.values(), key=lambda m: m.get("create_time", 0)
        )

        # Store all timestamps for more comprehensive filtering
        timestamps = []

        for msg in ordered:
            message = msg.get("message")
            if not message:
                continue

            role = message.get("author", {}).get("role", "unknown")
            parts = message.get("content", {}).get("parts", [])
            content = clean_text_content(" ".join([p for p in parts if isinstance(p, str)]))
            if not content:
                continue

            ts = message.get("create_time", None)
            if ts:
                timestamps.append(ts)
            dt_str = (
                datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                if ts
                else "unknown time"
            )

            if role == "user":
                messages.append(f"**You said** *(on {dt_str})*:\n\n{content}")
            elif role == "assistant":
                messages.append(f"**ChatGPT said** *(on {dt_str})*:\n\n{content}")
            else:
                messages.append(
                    f"*{role.capitalize()}* *(on {dt_str})*:\n\n{content}"
                )
                
        title = conv.get("title", f"Chat {idx}")
        return (messages, timestamps, title) if messages else None
        
    def _process_claude_conversation(self, conv, idx):
        """Process a Claude format conversation"""
        messages = []
        chat_messages = conv.get("chat_messages", [])
        
        # Store all timestamps for more comprehensive filtering
        timestamps = []
        
        for msg in chat_messages:
            role = msg.get("sender", "unknown")
            content = clean_text_content(msg.get("text", ""))
            
            if not content:
                continue
                
            # Parse timestamp from ISO string
            ts_str = msg.get("created_at")
            ts_parsed = None
            dt_str = "unknown time"
            
            if ts_str:
                try:
                    # Parse ISO timestamp
                    ts_parsed = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    timestamps.append(ts_str)  # Store original ISO string
                    dt_str = ts_parsed.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, AttributeError):
                    pass
                    
            if role == "human":
                messages.append(f"**You said** *(on {dt_str})*:\n\n{content}")
            elif role == "assistant":
                messages.append(f"**Claude said** *(on {dt_str})*:\n\n{content}")
            else:
                messages.append(
                    f"*{role.capitalize()}* *(on {dt_str})*:\n\n{content}"
                )
                
        title = conv.get("name", f"Claude Chat {idx}")
        return (messages, timestamps, title) if messages else None

    def index_docx(self, doc_folder):
        """Index Word documents containing chat conversations"""
        # Load the embedder
        embedder = self.load_embedder()

        documents, metadatas, ids = [], [], []

        def extract_timestamp(text):
            """Try to extract timestamps from text using regex"""
            # Look for common date formats
            date_patterns = [
                r"(\d{4}-\d{2}-\d{2})",  # YYYY-MM-DD
                r"(\d{2}/\d{2}/\d{4})",  # MM/DD/YYYY
                r"(\w+ \d{1,2}, \d{4})",  # Month DD, YYYY
            ]

            for pattern in date_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    try:
                        # Try different formats
                        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"):
                            try:
                                dt = datetime.strptime(matches[0], fmt)
                                return dt.isoformat()
                            except ValueError:
                                continue
                    except Exception:
                        pass
            return None

        def format_paragraphs(doc):
            lines = []
            timestamps = []
            current_role = None
            current_content = []

            for p in doc.paragraphs:
                text = p.text.strip()
                # Clean up non-breaking spaces and other Unicode issues
                text = text.replace('\xa0', ' ').replace('\u00a0', ' ')
                text = re.sub(r'\s+', ' ', text).strip()
                
                if not text:
                    if current_role and current_content:
                        formatted_content = "\n".join(current_content)
                        lines.append(f"**{current_role}**:\n\n{formatted_content}\n")
                        current_content = []
                    continue

                # Extract potential timestamp
                ts = extract_timestamp(text)
                if ts:
                    timestamps.append(ts)

                # Check if this is a role indicator - handle various formats
                role_match = re.match(
                    r"^(You|ChatGPT|User|Assistant|System)(\s+said)?:?\s*$",
                    text,
                    re.IGNORECASE,
                )
                if role_match:
                    # Save previous content if any
                    if current_role and current_content:
                        formatted_content = "\n".join(current_content)
                        lines.append(f"**{current_role}**:\n\n{formatted_content}\n")

                    # Normalize the role name
                    raw_role = role_match.group(1)
                    if raw_role.lower() == 'chatgpt':
                        current_role = 'ChatGPT'
                    elif raw_role.lower() == 'you':
                        current_role = 'You'
                    else:
                        current_role = raw_role.capitalize()
                    current_content = []
                else:
                    # Add to current content
                    if current_role:
                        # Apply additional cleaning to content text
                        cleaned_text = clean_text_content(text)
                        if cleaned_text:  # Only add non-empty content
                            current_content.append(cleaned_text)
                    else:
                        cleaned_text = clean_text_content(text)
                        if cleaned_text:
                            lines.append(cleaned_text)

            # Don't forget the last block
            if current_role and current_content:
                formatted_content = "\n".join(current_content)
                lines.append(f"**{current_role}**:\n\n{formatted_content}\n")

            return "\n".join(lines), timestamps

        # Check if folder exists
        if not os.path.isdir(doc_folder):
            return False, f"Folder '{doc_folder}' not found"

        docx_files = [
            f
            for f in os.listdir(doc_folder)
            if f.endswith(".docx")
            and not f.startswith("~$")
            and os.path.isfile(os.path.join(doc_folder, f))
        ]

        if not docx_files:
            return False, f"No .docx files found in '{doc_folder}'"

        print(f"Found {len(docx_files)} Word documents")

        for idx, filename in enumerate(docx_files):
            full_path = os.path.join(doc_folder, filename)
            try:
                doc = Document(full_path)
                full_text, timestamps = format_paragraphs(doc)

                if not full_text.strip():
                    continue

                # Get file creation time as fallback timestamp
                file_create_time = datetime.fromtimestamp(
                    os.path.getctime(full_path)
                ).isoformat()

                # Use extracted timestamps if available, otherwise use file timestamps
                earliest_ts = min(timestamps) if timestamps else file_create_time
                latest_ts = max(timestamps) if timestamps else file_create_time

                documents.append(full_text)

                # Create metadata with no None values
                metadata_dict = {
                    "title": filename,
                    "source": "docx",
                    "file_path": full_path,
                }

                # Only add timestamps if they exist
                if earliest_ts:
                    metadata_dict["earliest_ts"] = earliest_ts
                if latest_ts:
                    metadata_dict["latest_ts"] = latest_ts

                metadatas.append(metadata_dict)
                ids.append(f"docx-{idx}")

            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")

        if not documents:
            return False, "No valid documents found to index"

        print(f"Embedding {len(documents)} documents")

        # Process in batches
        batch_size = 100
        total_indexed = 0

        for i in range(0, len(documents), batch_size):
            end = min(i + batch_size, len(documents))

            batch_docs = documents[i:end]
            batch_metas = metadatas[i:end]
            batch_ids = ids[i:end]

            embeddings = embedder.encode(batch_docs, show_progress_bar=False)

            self.add_documents(
                documents=batch_docs,
                embeddings=embeddings.tolist(),
                metadatas=batch_metas,
                ids=batch_ids,
            )

            total_indexed += len(batch_docs)

        return True, f"Successfully indexed {total_indexed} documents"
import json
import os
import re
from datetime import datetime
from pathlib import Path

from sentence_transformers import SentenceTransformer
import chromadb
from docx import Document

from config import COLLECTION_NAME, PERSIST_DIR, DEFAULT_EMBEDDING_MODEL


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

    def query(self, query_embeddings, n_results=5, where=None):
        """Query the collection"""
        if where:
            return self.collection.query(
                query_embeddings=query_embeddings, n_results=n_results, where=where
            )
        else:
            return self.collection.query(
                query_embeddings=query_embeddings, n_results=n_results
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
            # Get all docs matching date filter if specified
            where_filter = date_filter if date_filter else None
            all_docs = self.get_documents(
                where=where_filter, include=["documents", "metadatas"], limit=9999
            )
            terms = (
                query_text.replace("AND", "&&")
                .replace("OR", "||")
                .replace("NOT", "!!")
                .split()
            )
            matches = []

            def match(doc):
                text = doc.lower()
                expr = ""
                for term in terms:
                    if term == "&&":
                        expr += " and "
                    elif term == "||":
                        expr += " or "
                    elif term == "!!":
                        expr += " not "
                    else:
                        expr += f"'{term.lower()}' in text"
                try:
                    return eval(expr)
                except Exception:
                    return False

            for idx, doc in enumerate(all_docs["documents"]):
                if match(doc):
                    matches.append((doc, all_docs["metadatas"][idx]))

            # Format results like a query response
            if not matches:
                return {"documents": [[]], "metadatas": [[]]}

            documents = [m[0] for m in matches[:n_results]]
            metadatas = [m[1] for m in matches[:n_results]]

            return {"documents": [documents], "metadatas": [metadatas]}
        else:
            # Vector search
            embedding = embedder.encode([query_text])[0]

            # Perform the query with date filter if specified
            return self.query(
                query_embeddings=[embedding.tolist()],
                n_results=n_results,
                where=date_filter,
            )

    def index_json(self, json_path, chunk_size=0):
        """Index ChatGPT conversations from a JSON export"""
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

        conversations = (
            data if isinstance(data, list) else data.get("conversations", [])
        )
        print(f"Found {len(conversations)} conversations in the JSON file")

        if len(conversations) == 0:
            return False, "No conversations found in the JSON file"

        documents, metadatas, ids = [], [], []

        for idx, conv in enumerate(conversations):
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
                content = " ".join([p for p in parts if isinstance(p, str)]).strip()
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

            # Calculate earliest and latest timestamps
            valid_timestamps = [ts for ts in timestamps if ts]
            earliest_ts = min(valid_timestamps) if valid_timestamps else None
            latest_ts = max(valid_timestamps) if valid_timestamps else None

            # Convert timestamps to ISO format for better filtering
            earliest_ts_iso = (
                datetime.fromtimestamp(earliest_ts).isoformat() if earliest_ts else None
            )
            latest_ts_iso = (
                datetime.fromtimestamp(latest_ts).isoformat() if latest_ts else None
            )

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
                    chunk_title = f"{conv.get('title', f'Chat {idx}')} (Part {chunk_idx+1}/{len(chunks)})"

                    documents.append(chunk_text)

                    # Create a metadata dict with no None values
                    metadata_dict = {
                        "title": chunk_title,
                        "source": "json",
                        "message_count": len(chunk),
                        "is_chunk": True,
                        "chunk_index": chunk_idx,
                        "total_chunks": len(chunks),
                    }

                    # Only add fields that aren't None
                    if conv.get("id"):
                        metadata_dict["id"] = f"{conv.get('id')}-{chunk_idx}"
                        metadata_dict["conversation_id"] = conv.get("id")
                    if earliest_ts_iso:
                        metadata_dict["earliest_ts"] = earliest_ts_iso
                    if latest_ts_iso:
                        metadata_dict["latest_ts"] = latest_ts_iso

                    metadatas.append(metadata_dict)
                    ids.append(f"chat-{idx}-chunk-{chunk_idx}")
            else:
                documents.append(full_text)

                # Create a metadata dict with no None values
                metadata_dict = {
                    "title": conv.get("title", f"Chat {idx}"),
                    "source": "json",
                    "message_count": len(messages),
                    "is_chunk": False,
                }

                # Only add fields that aren't None
                if conv.get("id"):
                    metadata_dict["id"] = conv.get("id")
                if earliest_ts_iso:
                    metadata_dict["earliest_ts"] = earliest_ts_iso
                if latest_ts_iso:
                    metadata_dict["latest_ts"] = latest_ts_iso

                metadatas.append(metadata_dict)
                ids.append(f"chat-{idx}")

        if not documents:
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

            self.add_documents(
                documents=batch_docs,
                embeddings=embeddings.tolist(),
                metadatas=batch_metas,
                ids=batch_ids,
            )

            total_indexed += len(batch_docs)

        return True, f"Successfully indexed {total_indexed} documents"

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

                # Check if this is a role indicator
                role_match = re.match(
                    r"^(You|ChatGPT|User|Assistant|System)(\s+said)?:?$",
                    text,
                    re.IGNORECASE,
                )
                if role_match:
                    # Save previous content if any
                    if current_role and current_content:
                        formatted_content = "\n".join(current_content)
                        lines.append(f"**{current_role}**:\n\n{formatted_content}\n")

                    current_role = role_match.group(1)
                    current_content = []
                else:
                    # Add to current content
                    if current_role:
                        current_content.append(text)
                    else:
                        lines.append(text)

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
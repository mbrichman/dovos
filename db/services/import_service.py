"""
Service for importing conversations from various file formats.

Handles:
- Format detection (ChatGPT, Claude, OpenWebUI, DOCX)
- JSON and DOCX file parsing
- Duplicate detection using content hashing
- Batch import with transaction management
- Metadata extraction and normalization
- Job enqueueing for embeddings

This service abstracts away all the complex import logic, allowing
controllers and other components to trigger imports programmatically.
"""

import logging
import hashlib
import os
import tempfile
from typing import Dict, List, Any, Tuple
from datetime import datetime, timezone

from db.models.import_result import ImportResult
from db.repositories.unit_of_work import get_unit_of_work
from db.importers.registry import detect_format, FORMAT_REGISTRY, EXTRACTOR_METADATA
from db.importers.errors import (
    FormatDetectionError,
    ImporterNotAvailableError,
    ExtractionError,
    get_user_friendly_error_message
)
from utils.license import check_feature_license

logger = logging.getLogger(__name__)


class ConversationImportService:
    """Service for importing conversations from various file formats."""
    
    def __init__(self):
        """Initialize the import service."""
        pass
    
    def import_json_data(self, data: Dict[str, Any]) -> ImportResult:
        """
        Import conversations from JSON data.
        
        Args:
            data: JSON data containing conversations
            
        Returns:
            ImportResult with import statistics and messages
            
        Raises:
            ValueError: If format is unknown or import fails
        """
        result = ImportResult()
        
        try:
            # Detect format (Claude vs ChatGPT) using proper detection method
            conversations, format_type = self._detect_format(data)
            result.format_detected = format_type
            
            # Check if format was detected
            if format_type == "Unknown":
                available_formats = list(FORMAT_REGISTRY.keys())
                error = FormatDetectionError(available_formats=available_formats)
                user_msg = get_user_friendly_error_message(error, available_formats)
                raise ValueError(user_msg)
            
            if not conversations:
                available_formats = list(FORMAT_REGISTRY.keys())
                error = FormatDetectionError(available_formats=available_formats)
                user_msg = get_user_friendly_error_message(error, available_formats)
                raise ValueError(user_msg)
            
            # Validate that extractor is available for the detected format
            format_key = format_type.lower() if format_type != "OpenWebUI" else "openwebui"
            if format_key not in FORMAT_REGISTRY:
                available_formats = list(FORMAT_REGISTRY.keys())
                error = ImporterNotAvailableError(
                    format_name=format_type,
                    available_formats=available_formats
                )
                user_msg = get_user_friendly_error_message(error, available_formats)
                raise ValueError(user_msg)

            # Check license requirements for this format
            metadata = EXTRACTOR_METADATA.get(format_key, {})
            capabilities = metadata.get('capabilities', {})
            requires_license = capabilities.get('requires_license', False)

            has_access, license_error = check_feature_license(format_type, requires_license)
            if not has_access:
                raise ValueError(license_error)

            result.messages.append(f"🔍 Detected {format_type} format with {len(conversations)} conversations")
            result.messages.append(f"📥 Importing {len(conversations)} conversations from {format_type} format")
            logger.info(f"🔍 Detected {format_type} format with {len(conversations)} conversations")
            logger.info(f"📥 Importing {len(conversations)} conversations from {format_type} format")
            
            # Build map of existing conversations for duplicate detection
            existing_conv_map = self._build_existing_conversations_map()
            result.messages.append(f"Found {len(existing_conv_map)} existing conversations for duplicate checking")
            
            # Process each conversation
            for conv_data in conversations:
                try:
                    self._import_single_conversation(
                        conv_data, format_type, existing_conv_map, result
                    )
                except Exception as e:
                    error_msg = f"Failed to import conversation '{conv_data.get('title', 'Unknown')}': {e}"
                    result.errors.append(error_msg)
                    result.failed_count += 1
                    logger.error(error_msg)
            
            # Generate summary message
            if result.imported_count == 0:
                if result.skipped_duplicates > 0:
                    result.messages.append(f"All {result.skipped_duplicates} conversations already indexed")
                else:
                    result.messages.append("No valid conversations found to import")
            else:
                summary = f"✅ Successfully imported {result.imported_count} conversations"
                if result.skipped_duplicates > 0:
                    summary += f" (skipped {result.skipped_duplicates} duplicates)"
                if result.failed_count > 0:
                    summary += f" ({result.failed_count} failed)"
                result.messages.append(summary)
                logger.info(summary)
            
            return result
        
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"JSON import failed: {e}")
            result.errors.append(f"Import failed: {str(e)}")
            raise ValueError(f"Failed to import conversations: {str(e)}")
    
    def import_docx_file(self, file_path: str, filename: str) -> ImportResult:
        """
        Import conversations from a DOCX file.
        
        Args:
            file_path: Path to the DOCX file
            filename: Original filename for metadata
            
        Returns:
            ImportResult with import statistics
            
        Raises:
            ValueError: If import fails
        """
        result = ImportResult()
        result.format_detected = "DOCX"
        
        try:
            # Extract messages using registry extractor
            if 'docx' not in FORMAT_REGISTRY:
                raise ValueError("DOCX import not available")

            # Check license requirements for DOCX format
            metadata = EXTRACTOR_METADATA.get('docx', {})
            capabilities = metadata.get('capabilities', {})
            requires_license = capabilities.get('requires_license', False)

            has_access, license_error = check_feature_license('DOCX', requires_license)
            if not has_access:
                raise ValueError(license_error)

            messages, title, timestamps = FORMAT_REGISTRY['docx'](file_path, filename)
            
            if not messages:
                raise ValueError("No messages found in Word document")
            
            logger.info(f"📄 Importing Word document: {title} with {len(messages)} messages")
            result.messages.append(f"📄 Importing Word document: {title} with {len(messages)} messages")
            
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
            
            result.imported_count = 1
            result.messages.append(f"✅ Successfully imported Word document: {title}")
            logger.info(f"✅ Successfully imported Word document: {title}")
            
            return result
        
        except Exception as e:
            logger.error(f"DOCX import failed: {e}")
            result.errors.append(f"Failed to import Word document: {str(e)}")
            raise ValueError(f"Failed to import Word document: {str(e)}")
    
    def _detect_format(self, data: Any) -> Tuple[List[Dict], str]:
        """
        Detect the format of imported data.
        
        Args:
            data: Raw import data
            
        Returns:
            Tuple of (conversations_list, format_string)
        """
        return detect_format(data)
    
    def _build_existing_conversations_map(self) -> Dict[str, Tuple[str, str, datetime]]:
        """
        Build a map of existing conversations for duplicate/update detection.

        Returns:
            Dict mapping source_id -> (content_hash, db_id, source_updated_at)
        """
        existing_conv_map = {}

        with get_unit_of_work() as uow:
            existing_conversations = uow.conversations.get_all()
            for conv in existing_conversations:
                messages = uow.messages.get_by_conversation(conv.id)
                # Concatenate all message content for duplicate detection
                full_content = "\n\n".join(msg.content for msg in messages if msg.content)
                content_hash = hashlib.sha256(full_content.encode()).hexdigest()

                # Use source_id from conversation if available (new approach)
                if conv.source_id:
                    existing_conv_map[conv.source_id] = (content_hash, conv.id, conv.source_updated_at)
                # Fall back to original_conversation_id from message metadata (legacy approach)
                elif messages and messages[0].message_metadata:
                    original_id = messages[0].message_metadata.get('original_conversation_id')
                    if original_id:
                        existing_conv_map[original_id] = (content_hash, conv.id, None)

        return existing_conv_map
    
    def _import_single_conversation(
        self,
        conv_data: Dict[str, Any],
        format_type: str,
        existing_conv_map: Dict[str, Tuple[str, str, datetime]],
        result: ImportResult
    ) -> None:
        """
        Import a single conversation from converted data.
        
        Args:
            conv_data: Conversation data
            format_type: Detected format type
            existing_conv_map: Map of existing conversations for duplicate detection
            result: ImportResult object to update with counts
            
        Raises:
            Exceptions are caught and recorded in result
        """
        # Extract conversation title
        title = conv_data.get('title', conv_data.get('name', 'Untitled Conversation'))
        
        # Extract messages first
        messages = []
        try:
            if 'mapping' in conv_data:  # ChatGPT format
                if 'chatgpt' in FORMAT_REGISTRY:
                    messages = FORMAT_REGISTRY['chatgpt'](conv_data['mapping'])
            elif 'chat_messages' in conv_data:  # Claude format
                if 'claude' in FORMAT_REGISTRY:
                    messages = FORMAT_REGISTRY['claude'](conv_data['chat_messages'])
            elif 'chat' in conv_data and 'history' in conv_data.get('chat', {}) and 'messages' in conv_data['chat']['history']:  # OpenWebUI format
                if 'openwebui' in FORMAT_REGISTRY:
                    messages = FORMAT_REGISTRY['openwebui'](conv_data['chat']['history']['messages'])
        except (KeyError, TypeError, ValueError) as e:
            available_formats = list(FORMAT_REGISTRY.keys())
            error = ExtractionError(
                format_name=format_type,
                original_error=e
            )
            user_msg = get_user_friendly_error_message(error, available_formats)
            logger.error(f"Failed to extract messages from {format_type}: {e}")
            raise ValueError(user_msg)
        
        # Skip if no valid messages
        if not messages:
            return
        
        # Check for duplicates/updates using conversation ID
        conv_id = conv_data.get('id') or conv_data.get('uuid')
        full_content = "\n\n".join(msg['content'] for msg in messages if msg['content'].strip())
        content_hash = hashlib.sha256(full_content.encode()).hexdigest()

        if conv_id and conv_id in existing_conv_map:
            existing_hash, existing_db_id, existing_source_updated_at = existing_conv_map[conv_id]
            if content_hash == existing_hash:
                # Content is identical, skip this duplicate
                result.skipped_duplicates += 1
                logger.info(f"Skipping duplicate conversation: {title}")
                return
            else:
                # Content changed - check if we should update
                source_updated_at = self._extract_source_updated_at(conv_data, format_type)

                if self._should_update(existing_source_updated_at, source_updated_at):
                    # Update the existing conversation with new messages
                    messages_added = self._update_existing_conversation(
                        existing_db_id, conv_data, format_type, messages, source_updated_at
                    )
                    result.updated_count += 1
                    result.messages_added += messages_added
                    logger.info(f"Updated conversation '{title}' with {messages_added} new messages")
                    return
                else:
                    result.skipped_duplicates += 1
                    logger.info(f"Conversation exists with different content: {title} - skipping (no newer timestamp)")
                    return
        
        # Calculate earliest and latest timestamps from messages
        timestamps = [msg.get('created_at') for msg in messages if msg.get('created_at')]
        earliest_ts = min(timestamps) if timestamps else None
        latest_ts = max(timestamps) if timestamps else None
        
        # If no message-level timestamps, fall back to conversation-level timestamps
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
            # Create conversation with original timestamps and source tracking
            conv_kwargs = {'title': title}

            # Add source tracking fields
            if conv_id:
                conv_kwargs['source_id'] = conv_id
                conv_kwargs['source_type'] = format_type.lower()
                source_updated_at = self._extract_source_updated_at(conv_data, format_type)
                if source_updated_at:
                    conv_kwargs['source_updated_at'] = source_updated_at
            
            # Set original timestamps if available
            # ChatGPT/OpenWebUI use Unix epoch (numeric), Claude uses ISO format (string)
            if earliest_ts:
                try:
                    if isinstance(earliest_ts, datetime):
                        conv_kwargs['created_at'] = earliest_ts
                    elif isinstance(earliest_ts, (int, float)):
                        conv_kwargs['created_at'] = datetime.fromtimestamp(earliest_ts, tz=timezone.utc)
                    elif isinstance(earliest_ts, str):
                        conv_kwargs['created_at'] = datetime.fromisoformat(earliest_ts.replace('Z', '+00:00'))
                except (ValueError, TypeError, OSError):
                    pass  # Use default if conversion fails
            
            if latest_ts:
                try:
                    if isinstance(latest_ts, datetime):
                        conv_kwargs['updated_at'] = latest_ts
                    elif isinstance(latest_ts, (int, float)):
                        conv_kwargs['updated_at'] = datetime.fromtimestamp(latest_ts, tz=timezone.utc)
                    elif isinstance(latest_ts, str):
                        conv_kwargs['updated_at'] = datetime.fromisoformat(latest_ts.replace('Z', '+00:00'))
                except (ValueError, TypeError, OSError):
                    pass  # Use default if conversion fails
            
            conversation = uow.conversations.create(**conv_kwargs)
            uow.session.flush()  # Get the ID
            
            # Add messages directly using repository instead of service
            # to avoid nested transactions
            for idx, msg in enumerate(messages):
                if msg['content'].strip():  # Skip empty messages
                    # Store source and conversation info in message metadata
                    message_metadata = {
                        'source': format_type.lower(),
                        'conversation_title': title,
                        'original_conversation_id': conv_id or str(conversation.id),
                        'sequence': msg.get('sequence', idx)  # Preserve sequence if available
                    }
                    
                    # Preserve attachments if present in the message
                    if msg.get('attachments'):
                        message_metadata['attachments'] = msg['attachments']
                    
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
                                msg_kwargs['created_at'] = msg_ts
                            elif isinstance(msg_ts, (int, float)):
                                msg_kwargs['created_at'] = datetime.fromtimestamp(msg_ts, tz=timezone.utc)
                            elif isinstance(msg_ts, str):
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
        
        result.imported_count += 1

        if result.imported_count % 50 == 0:
            logger.info(f"Imported {result.imported_count} conversations...")

    def _extract_source_updated_at(self, conv_data: Dict[str, Any], format_type: str) -> datetime:
        """
        Extract the source updated_at timestamp from conversation data.

        Args:
            conv_data: Conversation data
            format_type: Detected format type

        Returns:
            datetime object or None if not available
        """
        ts = None

        if format_type.lower() == 'chatgpt':
            ts = conv_data.get('update_time') or conv_data.get('create_time')
        elif format_type.lower() == 'claude':
            ts = conv_data.get('updated_at') or conv_data.get('created_at')
        elif format_type.lower() == 'openwebui':
            ts = conv_data.get('updated_at') or conv_data.get('created_at')

        if ts is None:
            return None

        try:
            if isinstance(ts, datetime):
                return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            elif isinstance(ts, (int, float)):
                # Detect nanoseconds (> 10^12)
                if ts > 10**12:
                    ts = ts / 10**9
                # Detect milliseconds (> 10^11)
                elif ts > 10**11:
                    ts = ts / 1000.0
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            elif isinstance(ts, str):
                return datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except (ValueError, TypeError, OSError):
            pass

        return None

    def _should_update(self, existing_updated_at: datetime, new_updated_at: datetime) -> bool:
        """
        Determine if an existing conversation should be updated.

        Args:
            existing_updated_at: The existing source_updated_at timestamp (may be None)
            new_updated_at: The new source updated_at timestamp (may be None)

        Returns:
            True if the conversation should be updated
        """
        # If we don't have the new timestamp, don't update
        if new_updated_at is None:
            return False

        # If we don't have an existing timestamp, update (assume it's newer)
        if existing_updated_at is None:
            return True

        # Update if the new timestamp is newer
        return new_updated_at > existing_updated_at

    def _update_existing_conversation(
        self,
        conversation_id,
        conv_data: Dict[str, Any],
        format_type: str,
        messages: List[Dict],
        source_updated_at: datetime
    ) -> int:
        """
        Update an existing conversation with new messages.

        Args:
            conversation_id: The existing conversation's UUID
            conv_data: Conversation data
            format_type: Detected format type
            messages: Extracted messages
            source_updated_at: The source's updated_at timestamp

        Returns:
            Number of messages added
        """
        messages_added = 0

        with get_unit_of_work() as uow:
            # Get existing messages for comparison
            existing_messages = uow.messages.get_by_conversation(conversation_id)
            existing_content_hashes = {
                hashlib.sha256(f"{m.role}:{m.content}".encode()).hexdigest()[:16]
                for m in existing_messages
            }

            # Get max sequence for appending
            max_sequence = uow.messages.get_max_sequence(conversation_id)

            # Process new messages
            for idx, msg in enumerate(messages):
                content = msg.get('content', '').strip()
                if not content:
                    continue

                # Check if message already exists by content hash
                content_hash = hashlib.sha256(f"{msg['role']}:{content}".encode()).hexdigest()[:16]
                if content_hash in existing_content_hashes:
                    continue

                # New message, add it
                max_sequence += 1
                message_metadata = {
                    'source': format_type.lower(),
                    'sequence': max_sequence
                }

                # Determine message timestamp
                msg_ts = msg.get('created_at')
                msg_kwargs = {
                    'conversation_id': conversation_id,
                    'role': msg['role'],
                    'content': content,
                    'message_metadata': message_metadata
                }

                if msg_ts:
                    try:
                        if isinstance(msg_ts, datetime):
                            msg_kwargs['created_at'] = msg_ts
                        elif isinstance(msg_ts, (int, float)):
                            msg_kwargs['created_at'] = datetime.fromtimestamp(msg_ts, tz=timezone.utc)
                        elif isinstance(msg_ts, str):
                            msg_kwargs['created_at'] = datetime.fromisoformat(msg_ts.replace('Z', '+00:00'))
                    except (ValueError, TypeError, OSError):
                        pass

                message = uow.messages.create(**msg_kwargs)
                uow.session.flush()

                # Enqueue embedding job
                uow.jobs.enqueue(
                    kind='generate_embedding',
                    payload={
                        'message_id': str(message.id),
                        'conversation_id': str(conversation_id),
                        'content': content,
                        'model': 'all-MiniLM-L6-v2'
                    }
                )

                messages_added += 1
                existing_content_hashes.add(content_hash)

            # Update source tracking timestamp
            if source_updated_at:
                uow.conversations.update_source_tracking(conversation_id, source_updated_at)

            uow.commit()

        return messages_added

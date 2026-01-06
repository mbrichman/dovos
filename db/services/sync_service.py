"""
Service for synchronizing conversations from external sources.

Handles:
- OpenWebUI API synchronization (pull-based)
- Change detection via source_updated_at comparison
- Message upsert with ordering preservation
- Background sync execution
"""

import logging
import hashlib
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from uuid import UUID
from enum import Enum

from db.repositories.unit_of_work import get_unit_of_work
from db.services.openwebui_client import (
    OpenWebUIClient,
    OpenWebUIChat,
    OpenWebUIClientError,
    OpenWebUIAuthError
)
from db.importers.openwebui import extract_messages

logger = logging.getLogger(__name__)


class SyncSource(Enum):
    """Supported sync sources."""
    OPENWEBUI = "openwebui"
    CLAUDE = "claude"
    CHATGPT = "chatgpt"


@dataclass
class SyncResult:
    """Result of a sync operation."""
    imported_count: int = 0           # New conversations added
    updated_count: int = 0            # Existing conversations updated
    skipped_count: int = 0            # Unchanged conversations skipped
    failed_count: int = 0             # Failed operations
    messages_added: int = 0           # New messages added to existing convs
    messages: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    success: bool = True


class ConversationSyncService:
    """Service for synchronizing conversations from external sources."""

    # Class-level lock and status for background sync
    _sync_lock = threading.Lock()
    _sync_status = {
        'running': False,
        'progress': None,
        'started_at': None,
        'error': None
    }

    def __init__(self):
        """Initialize the sync service."""
        self._openwebui_client = None

    @classmethod
    def is_sync_running(cls) -> bool:
        """Check if a sync is currently running."""
        return cls._sync_status['running']

    @classmethod
    def get_sync_progress(cls) -> Dict[str, Any]:
        """Get current sync progress."""
        return dict(cls._sync_status)

    def start_background_sync(self) -> Dict[str, Any]:
        """
        Start a background sync if one isn't already running.

        Returns:
            Dict with status (started, already_running, or error)
        """
        with self._sync_lock:
            if self._sync_status['running']:
                return {
                    'status': 'already_running',
                    'started_at': self._sync_status['started_at'],
                    'progress': self._sync_status['progress']
                }

            # Validate configuration before starting
            try:
                self._get_openwebui_client()
            except ValueError as e:
                return {
                    'status': 'error',
                    'error': str(e)
                }

            # Mark as running
            self._sync_status['running'] = True
            self._sync_status['started_at'] = datetime.now(timezone.utc).isoformat()
            self._sync_status['progress'] = 'Starting...'
            self._sync_status['error'] = None

        # Start background thread
        thread = threading.Thread(target=self._run_background_sync, daemon=True)
        thread.start()

        return {
            'status': 'started',
            'started_at': self._sync_status['started_at']
        }

    def _run_background_sync(self) -> None:
        """Run the sync in background thread."""
        try:
            result = self.sync_from_openwebui()
            with self._sync_lock:
                if result.success:
                    self._sync_status['progress'] = f"Complete: {result.imported_count} imported, {result.updated_count} updated, {result.skipped_count} skipped"
                else:
                    self._sync_status['error'] = result.errors[0] if result.errors else 'Unknown error'
                    self._sync_status['progress'] = 'Failed'
        except Exception as e:
            logger.error(f"Background sync failed: {e}")
            with self._sync_lock:
                self._sync_status['error'] = str(e)
                self._sync_status['progress'] = 'Failed'
        finally:
            with self._sync_lock:
                self._sync_status['running'] = False

    def _update_sync_timestamp(self) -> None:
        """Update the last sync timestamp in settings."""
        with get_unit_of_work() as uow:
            uow.settings.create_or_update(
                'last_openwebui_sync',
                datetime.now(timezone.utc).isoformat(),
                description='Last OpenWebUI sync timestamp',
                category='sync'
            )
            uow.commit()

    def _get_openwebui_client(self) -> OpenWebUIClient:
        """Get or create the OpenWebUI client with current settings."""
        with get_unit_of_work() as uow:
            url = uow.settings.get_value('openwebui_url')
            api_key = uow.settings.get_value('openwebui_api_key')

        if not url or not api_key:
            raise ValueError("OpenWebUI URL and API key must be configured in settings")

        return OpenWebUIClient(base_url=url, api_key=api_key)

    def sync_from_openwebui(self) -> SyncResult:
        """
        Sync conversations from OpenWebUI API.

        Returns:
            SyncResult with counts of imported, updated, skipped, and failed conversations
        """
        result = SyncResult()

        try:
            client = self._get_openwebui_client()
        except ValueError as e:
            result.success = False
            result.errors.append(str(e))
            return result

        try:
            # Test connection first
            client.test_connection()
        except OpenWebUIAuthError as e:
            result.success = False
            result.errors.append(f"Authentication failed: {e}")
            return result
        except OpenWebUIClientError as e:
            result.success = False
            result.errors.append(f"Connection failed: {e}")
            return result

        # Build map of existing OpenWebUI conversations
        with get_unit_of_work() as uow:
            existing_map = uow.conversations.get_source_tracking_map(SyncSource.OPENWEBUI.value)

        result.messages.append(f"Found {len(existing_map)} existing OpenWebUI conversations")
        logger.info(f"Starting OpenWebUI sync, found {len(existing_map)} existing conversations")

        # Iterate through all OpenWebUI conversations
        processed_count = 0
        try:
            for chat_summary in client.iter_all_chats():
                try:
                    self._sync_single_chat(client, chat_summary, existing_map, result)
                except Exception as e:
                    result.failed_count += 1
                    error_msg = f"Failed to sync chat '{chat_summary.title}': {e}"
                    result.errors.append(error_msg)
                    logger.error(error_msg)

                processed_count += 1
                # Save progress every 50 chats to prevent losing work on timeout
                if processed_count % 50 == 0:
                    self._update_sync_timestamp()
                    progress_msg = f"Processed {processed_count} chats ({result.imported_count} new, {result.updated_count} updated, {result.skipped_count} unchanged)"
                    with self._sync_lock:
                        self._sync_status['progress'] = progress_msg
                    logger.info(progress_msg)

        except OpenWebUIClientError as e:
            result.success = False
            result.errors.append(f"Error fetching chats: {e}")
            # Still save timestamp for partial progress
            self._update_sync_timestamp()
            return result

        # Update last sync timestamp
        self._update_sync_timestamp()

        # Generate summary
        summary = f"Sync complete: {result.imported_count} imported, {result.updated_count} updated, {result.skipped_count} skipped"
        if result.failed_count > 0:
            summary += f", {result.failed_count} failed"
        if result.messages_added > 0:
            summary += f" ({result.messages_added} new messages added)"
        result.messages.append(summary)
        logger.info(summary)

        return result

    def _sync_single_chat(
        self,
        client: OpenWebUIClient,
        chat_summary: OpenWebUIChat,
        existing_map: Dict[str, Tuple[UUID, Optional[datetime]]],
        result: SyncResult
    ) -> None:
        """
        Sync a single chat from OpenWebUI.

        Args:
            client: The OpenWebUI client
            chat_summary: Summary of the chat (without messages)
            existing_map: Map of source_id -> (conversation_id, source_updated_at)
            result: SyncResult to update with counts
        """
        source_id = chat_summary.id

        # Check if conversation exists
        if source_id in existing_map:
            existing_id, existing_updated_at = existing_map[source_id]

            # Compare timestamps to detect changes
            if existing_updated_at and chat_summary.updated_at <= existing_updated_at:
                # No changes, skip
                result.skipped_count += 1
                return

            # Conversation has updates, fetch full chat and upsert messages
            full_chat = client.get_chat(source_id)
            messages_added = self._upsert_messages(
                existing_id,
                full_chat,
                SyncSource.OPENWEBUI
            )

            # Update source tracking
            with get_unit_of_work() as uow:
                uow.conversations.update_source_tracking(existing_id, chat_summary.updated_at)
                # Also update the conversation's title if changed
                conv = uow.conversations.get_by_id(existing_id)
                if conv and conv.title != chat_summary.title:
                    conv.title = chat_summary.title
                uow.commit()

            result.updated_count += 1
            result.messages_added += messages_added

            # Sync topics for updated conversation
            self._sync_topics(client, source_id, existing_id)

            logger.info(f"Updated conversation '{chat_summary.title}' with {messages_added} new messages")
        else:
            # New conversation, fetch full chat and create
            full_chat = client.get_chat(source_id)
            new_conv_id = self._create_conversation(full_chat, SyncSource.OPENWEBUI)

            # Sync topics for new conversation
            self._sync_topics(client, source_id, new_conv_id)

            result.imported_count += 1
            logger.info(f"Imported new conversation '{chat_summary.title}'")

    def _create_conversation(
        self,
        chat: OpenWebUIChat,
        source_type: SyncSource
    ) -> UUID:
        """
        Create a new conversation with source tracking.

        Args:
            chat: The full chat data from OpenWebUI
            source_type: The source system

        Returns:
            The new conversation's UUID
        """
        # Extract messages using the existing OpenWebUI importer
        messages_dict = {}
        if chat.messages:
            for msg in chat.messages:
                messages_dict[msg.get('id', str(len(messages_dict)))] = msg

        extracted_messages = extract_messages(messages_dict)

        if not extracted_messages:
            logger.warning(f"No messages extracted for chat '{chat.title}'")

        with get_unit_of_work() as uow:
            # Create conversation with source tracking
            conversation = uow.conversations.create(
                title=chat.title,
                created_at=chat.created_at,
                updated_at=chat.updated_at,
                source_id=chat.id,
                source_type=source_type.value,
                source_updated_at=chat.updated_at
            )
            uow.session.flush()

            # Create messages
            for idx, msg in enumerate(extracted_messages):
                if not msg.get('content', '').strip():
                    continue

                # Get the source message ID from the original data
                source_msg_id = None
                if chat.messages and idx < len(chat.messages):
                    source_msg_id = chat.messages[idx].get('id')

                metadata = {
                    'source': source_type.value,
                    'sequence': msg.get('sequence', idx)
                }

                message = uow.messages.create(
                    conversation_id=conversation.id,
                    role=msg['role'],
                    content=msg['content'],
                    message_metadata=metadata,
                    created_at=msg.get('created_at', chat.created_at),
                    source_message_id=source_msg_id
                )
                uow.session.flush()

                # Enqueue embedding job
                uow.jobs.enqueue(
                    kind='generate_embedding',
                    payload={
                        'message_id': str(message.id),
                        'conversation_id': str(conversation.id),
                        'content': msg['content'],
                        'model': 'all-MiniLM-L6-v2'
                    }
                )

            uow.commit()
            return conversation.id

    def _upsert_messages(
        self,
        conversation_id: UUID,
        chat: OpenWebUIChat,
        source_type: SyncSource
    ) -> int:
        """
        Upsert messages into an existing conversation.

        Args:
            conversation_id: The conversation to update
            chat: The full chat data from OpenWebUI
            source_type: The source system

        Returns:
            Number of new messages added
        """
        # Extract messages using the existing OpenWebUI importer
        messages_dict = {}
        if chat.messages:
            for msg in chat.messages:
                messages_dict[msg.get('id', str(len(messages_dict)))] = msg

        extracted_messages = extract_messages(messages_dict)
        messages_added = 0

        with get_unit_of_work() as uow:
            # Get existing message source IDs
            existing_source_ids = uow.messages.get_source_message_ids(conversation_id)

            # Get existing messages for content hash comparison
            existing_messages = uow.messages.get_by_conversation(conversation_id)
            existing_content_hashes = {
                self._compute_message_hash(m.content, m.role)
                for m in existing_messages
            }

            # Get max sequence for appending
            max_sequence = uow.messages.get_max_sequence(conversation_id)

            for idx, msg in enumerate(extracted_messages):
                content = msg.get('content', '').strip()
                if not content:
                    continue

                # Get the source message ID
                source_msg_id = None
                if chat.messages and idx < len(chat.messages):
                    source_msg_id = chat.messages[idx].get('id')

                # Check if message already exists
                if source_msg_id and source_msg_id in existing_source_ids:
                    # Already exists by source ID, skip
                    continue

                # Check by content hash
                content_hash = self._compute_message_hash(content, msg['role'])
                if content_hash in existing_content_hashes:
                    # Already exists by content, skip
                    continue

                # New message, add it
                max_sequence += 1
                metadata = {
                    'source': source_type.value,
                    'sequence': max_sequence
                }

                message = uow.messages.create(
                    conversation_id=conversation_id,
                    role=msg['role'],
                    content=content,
                    message_metadata=metadata,
                    created_at=msg.get('created_at', datetime.now(timezone.utc)),
                    source_message_id=source_msg_id
                )
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
                if source_msg_id:
                    existing_source_ids.add(source_msg_id)

            uow.commit()

        return messages_added

    def _compute_message_hash(self, content: str, role: str) -> str:
        """Compute a hash for message deduplication."""
        combined = f"{role}:{content}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _sync_topics(
        self,
        client: OpenWebUIClient,
        source_id: str,
        conversation_id: UUID
    ) -> int:
        """
        Sync topics (tags) from OpenWebUI for a conversation.

        Args:
            client: The OpenWebUI client
            source_id: The OpenWebUI chat ID
            conversation_id: The local conversation UUID

        Returns:
            Number of topics synced
        """
        try:
            topic_names = client.get_chat_topics(source_id)
            if not topic_names:
                return 0

            with get_unit_of_work() as uow:
                uow.topics.set_conversation_topics(conversation_id, topic_names)
                uow.commit()

            logger.debug(f"Synced {len(topic_names)} topics for conversation {conversation_id}")
            return len(topic_names)

        except Exception as e:
            logger.warning(f"Failed to sync topics for {source_id}: {e}")
            return 0

    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get current sync status and statistics.

        Returns:
            Dict with last sync time and conversation counts by source
        """
        with get_unit_of_work() as uow:
            last_sync = uow.settings.get_value('last_openwebui_sync')

            # Count conversations by source type
            source_counts = {}
            for source in SyncSource:
                convs = uow.conversations.get_all_by_source_type(source.value)
                source_counts[source.value] = len(convs)

            # Get total conversation count
            total = uow.conversations.count()

        return {
            'last_openwebui_sync': last_sync,
            'conversations_by_source': source_counts,
            'total_conversations': total,
            'openwebui_configured': self._is_openwebui_configured()
        }

    def _is_openwebui_configured(self) -> bool:
        """Check if OpenWebUI is configured."""
        with get_unit_of_work() as uow:
            url = uow.settings.get_value('openwebui_url')
            api_key = uow.settings.get_value('openwebui_api_key')
            return bool(url and api_key)

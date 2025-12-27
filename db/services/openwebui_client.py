"""
HTTP client for OpenWebUI API.

Provides methods for fetching conversations from OpenWebUI for synchronization.

Endpoints used:
- GET /api/v1/chats/list - Paginated conversation list
- GET /api/v1/chats/{id} - Full conversation with messages
"""

import logging
import requests
import urllib3
from typing import Dict, List, Any, Optional, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Disable SSL verification warnings (OpenWebUI often uses self-signed certs)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


@dataclass
class OpenWebUIChat:
    """Represents an OpenWebUI conversation."""
    id: str
    title: str
    updated_at: datetime
    created_at: datetime
    user_id: Optional[str] = None
    archived: bool = False
    pinned: bool = False
    folder_id: Optional[str] = None
    share_id: Optional[str] = None
    messages: Optional[List[Dict]] = field(default=None)  # Only populated when fetched individually


class OpenWebUIClientError(Exception):
    """Base exception for OpenWebUI client errors."""
    pass


class OpenWebUIAuthError(OpenWebUIClientError):
    """Authentication failed."""
    pass


class OpenWebUINotFoundError(OpenWebUIClientError):
    """Resource not found."""
    pass


class OpenWebUIClient:
    """HTTP client for OpenWebUI API."""

    def __init__(self, base_url: str, api_key: str, verify_ssl: bool = False, timeout: int = 30):
        """
        Initialize the OpenWebUI client.

        Args:
            base_url: Base URL of the OpenWebUI instance (e.g., 'https://oi.dovrichman.site')
            api_key: API key or bearer token for authentication
            verify_ssl: Whether to verify SSL certificates (default: False for self-signed)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

    def list_chats(self, page: int = 1) -> List[OpenWebUIChat]:
        """
        Get paginated list of conversations.

        Args:
            page: Page number (1-based) for pagination

        Returns:
            List of OpenWebUIChat objects (without messages)

        Note:
            OpenWebUI API uses page-based pagination, not skip/offset.
            Each page returns ~60 chats (server-controlled page size).
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/chats/list",
                params={'page': page},
                verify=self.verify_ssl,
                timeout=self.timeout
            )

            if response.status_code == 401:
                raise OpenWebUIAuthError("Authentication failed. Check your API key.")
            elif response.status_code == 403:
                raise OpenWebUIAuthError("Access forbidden. Check your permissions.")

            response.raise_for_status()

            chats = []
            for chat_data in response.json():
                chats.append(self._parse_chat_summary(chat_data))

            return chats

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list chats from OpenWebUI: {e}")
            raise OpenWebUIClientError(f"Failed to list chats: {e}") from e

    def get_chat(self, chat_id: str) -> OpenWebUIChat:
        """
        Get full conversation with messages.

        Args:
            chat_id: The chat ID to fetch

        Returns:
            OpenWebUIChat object with messages populated
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/chats/{chat_id}",
                verify=self.verify_ssl,
                timeout=self.timeout
            )

            if response.status_code == 401:
                raise OpenWebUIAuthError("Authentication failed. Check your API key.")
            elif response.status_code == 404:
                raise OpenWebUINotFoundError(f"Chat {chat_id} not found")

            response.raise_for_status()

            return self._parse_chat_full(response.json())

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get chat {chat_id} from OpenWebUI: {e}")
            raise OpenWebUIClientError(f"Failed to get chat: {e}") from e

    def list_all_chats_from_db(self) -> List[OpenWebUIChat]:
        """
        Get ALL conversations including those in folders.

        Uses the /api/v1/chats/all/db endpoint which returns all chats
        regardless of folder membership.

        Returns:
            List of all OpenWebUIChat objects (without messages)
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/chats/all/db",
                verify=self.verify_ssl,
                timeout=self.timeout * 2  # Longer timeout for full fetch
            )

            if response.status_code == 401:
                raise OpenWebUIAuthError("Authentication failed. Check your API key.")
            elif response.status_code == 403:
                raise OpenWebUIAuthError("Access forbidden. Check your permissions.")

            response.raise_for_status()

            chats = []
            for chat_data in response.json():
                chats.append(self._parse_chat_summary(chat_data))

            logger.info(f"Fetched {len(chats)} chats from OpenWebUI (including folders)")
            return chats

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list all chats from OpenWebUI: {e}")
            raise OpenWebUIClientError(f"Failed to list all chats: {e}") from e

    def iter_all_chats(self) -> Iterator[OpenWebUIChat]:
        """
        Iterate through all conversations including those in folders.

        Uses the /api/v1/chats/all/db endpoint to ensure ALL conversations
        are included, not just those outside of folders.

        Yields:
            OpenWebUIChat objects (without messages)
        """
        try:
            # Try the all/db endpoint first (includes folders)
            all_chats = self.list_all_chats_from_db()
            yield from all_chats
        except OpenWebUIClientError as e:
            # Fall back to paginated list if all/db fails
            logger.warning(f"all/db endpoint failed, falling back to pagination: {e}")
            yield from self._iter_chats_paginated()

    def _iter_chats_paginated(self) -> Iterator[OpenWebUIChat]:
        """
        Iterate through conversations using pagination (legacy fallback).

        Note: This may miss conversations in folders.

        Yields:
            OpenWebUIChat objects (without messages)
        """
        page = 1
        prev_count = None
        while True:
            batch = self.list_chats(page=page)
            if not batch:
                break

            yield from batch

            # Stop if this page returned fewer than expected (last page)
            # Or if we got the same count as last time with no new chats
            if prev_count is not None and len(batch) < prev_count:
                break

            prev_count = len(batch)
            page += 1

    def test_connection(self) -> bool:
        """
        Test the connection to OpenWebUI.

        Returns:
            True if connection is successful, raises exception otherwise
        """
        try:
            # Try to list the first page to verify connection
            self.list_chats(page=1)
            return True
        except OpenWebUIClientError:
            raise

    def _parse_chat_summary(self, data: Dict[str, Any]) -> OpenWebUIChat:
        """Parse chat list item (without messages)."""
        return OpenWebUIChat(
            id=data.get('id', ''),
            title=data.get('title', 'Untitled'),
            updated_at=self._parse_timestamp(data.get('updated_at')),
            created_at=self._parse_timestamp(data.get('created_at')),
            user_id=data.get('user_id'),
            archived=data.get('archived', False),
            pinned=data.get('pinned', False),
            folder_id=data.get('folder_id'),
            share_id=data.get('share_id'),
            messages=None
        )

    def _parse_chat_full(self, data: Dict[str, Any]) -> OpenWebUIChat:
        """Parse full chat with messages."""
        chat = self._parse_chat_summary(data)

        # Extract messages from the nested chat.history.messages structure
        messages = []
        chat_content = data.get('chat', {})
        history = chat_content.get('history', {})
        messages_dict = history.get('messages', {})

        if isinstance(messages_dict, dict):
            # OpenWebUI stores messages as a dict keyed by message ID
            for msg_id, msg_data in messages_dict.items():
                if msg_data and isinstance(msg_data, dict):
                    messages.append({
                        'id': msg_id,
                        'role': msg_data.get('role', 'user'),
                        'content': self._extract_content(msg_data.get('content')),
                        'timestamp': msg_data.get('timestamp'),
                        'created_at': msg_data.get('created_at'),
                        'model': msg_data.get('model'),
                        'parentId': msg_data.get('parentId')
                    })

        chat.messages = messages
        return chat

    def _extract_content(self, content: Any) -> str:
        """Extract text content from various formats."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            return content.get('text') or content.get('content') or str(content)
        return str(content)

    def _parse_timestamp(self, ts: Any) -> datetime:
        """
        Parse timestamp from various formats.

        Supports:
        - Unix epoch (seconds, milliseconds, nanoseconds)
        - ISO format strings
        """
        if ts is None:
            return datetime.now(tz=timezone.utc)

        try:
            if isinstance(ts, (int, float)):
                # Detect nanoseconds (> 10^12)
                if ts > 10**12:
                    ts = ts / 10**9
                # Detect milliseconds (> 10^11)
                elif ts > 10**11:
                    ts = ts / 1000.0
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            elif isinstance(ts, str):
                return datetime.fromisoformat(ts.replace('Z', '+00:00'))
            elif isinstance(ts, datetime):
                return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError, OSError) as e:
            logger.warning(f"Failed to parse timestamp {ts}: {e}")

        return datetime.now(tz=timezone.utc)

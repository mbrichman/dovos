"""
Unit tests for sync API endpoints in PostgresController.

Tests the controller methods for OpenWebUI sync functionality.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from controllers.postgres_controller import PostgresController
from db.services.sync_service import SyncResult


@pytest.fixture
def controller():
    """Create a PostgresController instance for testing."""
    with patch('controllers.postgres_controller.get_api_format_adapter'):
        with patch('controllers.postgres_controller.MessageService'):
            with patch('controllers.postgres_controller.ConversationImportService'):
                return PostgresController()


class TestTriggerOpenwebuiSync:
    """Tests for trigger_openwebui_sync endpoint (background sync)."""

    @patch('db.services.sync_service.ConversationSyncService')
    def test_sync_started(self, mock_sync_class, controller):
        """Test sync starts successfully in background."""
        mock_sync = MagicMock()
        mock_sync.start_background_sync.return_value = {
            'status': 'started',
            'started_at': '2024-01-15T10:30:00Z'
        }
        mock_sync_class.return_value = mock_sync

        result = controller.trigger_openwebui_sync()

        assert result['success'] is True
        assert result['message'] == 'Sync started in background'
        assert result['started_at'] == '2024-01-15T10:30:00Z'

    @patch('db.services.sync_service.ConversationSyncService')
    def test_sync_already_running(self, mock_sync_class, controller):
        """Test response when sync is already running."""
        mock_sync = MagicMock()
        mock_sync.start_background_sync.return_value = {
            'status': 'already_running',
            'started_at': '2024-01-15T10:30:00Z',
            'progress': 'Processed 500 chats...'
        }
        mock_sync_class.return_value = mock_sync

        result = controller.trigger_openwebui_sync()

        assert result['success'] is True
        assert result['message'] == 'Sync already in progress'
        assert result['progress'] == 'Processed 500 chats...'

    @patch('db.services.sync_service.ConversationSyncService')
    def test_sync_config_error(self, mock_sync_class, controller):
        """Test response when OpenWebUI not configured."""
        mock_sync = MagicMock()
        mock_sync.start_background_sync.return_value = {
            'status': 'error',
            'error': 'OpenWebUI URL and API key must be configured'
        }
        mock_sync_class.return_value = mock_sync

        result = controller.trigger_openwebui_sync()

        assert result['success'] is False
        assert 'must be configured' in result['error']

    @patch('db.services.sync_service.ConversationSyncService')
    def test_sync_exception_handling(self, mock_sync_class, controller):
        """Test sync handles unexpected exceptions."""
        mock_sync = MagicMock()
        mock_sync.start_background_sync.side_effect = Exception("Network error")
        mock_sync_class.return_value = mock_sync

        result = controller.trigger_openwebui_sync()

        assert result['success'] is False
        assert "Network error" in result['error']


class TestGetSyncStatus:
    """Tests for get_sync_status endpoint."""

    @patch('db.services.sync_service.ConversationSyncService')
    def test_status_configured(self, mock_sync_class, controller):
        """Test status when OpenWebUI is configured."""
        mock_sync = MagicMock()
        mock_sync.get_sync_status.return_value = {
            'last_openwebui_sync': '2024-01-15T10:30:00Z',
            'conversations_by_source': {
                'openwebui': 50,
                'claude': 100,
                'chatgpt': 75
            },
            'total_conversations': 225,
            'openwebui_configured': True
        }
        mock_sync.get_sync_progress.return_value = {
            'running': False,
            'progress': None,
            'started_at': None,
            'error': None
        }
        mock_sync_class.return_value = mock_sync

        result = controller.get_sync_status()

        assert result['last_openwebui_sync'] == '2024-01-15T10:30:00Z'
        assert result['openwebui_configured'] is True
        assert result['total_conversations'] == 225
        assert result['conversations_by_source']['openwebui'] == 50
        assert result['sync_running'] is False

    @patch('db.services.sync_service.ConversationSyncService')
    def test_status_sync_running(self, mock_sync_class, controller):
        """Test status when sync is running."""
        mock_sync = MagicMock()
        mock_sync.get_sync_status.return_value = {
            'last_openwebui_sync': '2024-01-15T10:30:00Z',
            'conversations_by_source': {'openwebui': 50},
            'total_conversations': 50,
            'openwebui_configured': True
        }
        mock_sync.get_sync_progress.return_value = {
            'running': True,
            'progress': 'Processed 100 chats (5 new, 2 updated, 93 unchanged)',
            'started_at': '2024-01-15T11:00:00Z',
            'error': None
        }
        mock_sync_class.return_value = mock_sync

        result = controller.get_sync_status()

        assert result['sync_running'] is True
        assert result['sync_progress'] == 'Processed 100 chats (5 new, 2 updated, 93 unchanged)'
        assert result['sync_started_at'] == '2024-01-15T11:00:00Z'

    @patch('db.services.sync_service.ConversationSyncService')
    def test_status_with_error(self, mock_sync_class, controller):
        """Test status shows last error."""
        mock_sync = MagicMock()
        mock_sync.get_sync_status.return_value = {
            'last_openwebui_sync': None,
            'conversations_by_source': {},
            'total_conversations': 0,
            'openwebui_configured': True
        }
        mock_sync.get_sync_progress.return_value = {
            'running': False,
            'progress': 'Failed',
            'started_at': None,
            'error': 'Connection refused'
        }
        mock_sync_class.return_value = mock_sync

        result = controller.get_sync_status()

        assert result['sync_running'] is False
        assert result['sync_error'] == 'Connection refused'

    @patch('db.services.sync_service.ConversationSyncService')
    def test_status_not_configured(self, mock_sync_class, controller):
        """Test status when OpenWebUI is not configured."""
        mock_sync = MagicMock()
        mock_sync.get_sync_status.return_value = {
            'last_openwebui_sync': None,
            'conversations_by_source': {},
            'total_conversations': 0,
            'openwebui_configured': False
        }
        mock_sync.get_sync_progress.return_value = {
            'running': False,
            'progress': None,
            'started_at': None,
            'error': None
        }
        mock_sync_class.return_value = mock_sync

        result = controller.get_sync_status()

        assert result['last_openwebui_sync'] is None
        assert result['openwebui_configured'] is False
        assert result['sync_running'] is False

    @patch('db.services.sync_service.ConversationSyncService')
    def test_status_exception_handling(self, mock_sync_class, controller):
        """Test status handles exceptions gracefully."""
        mock_sync = MagicMock()
        mock_sync.get_sync_status.side_effect = Exception("Database error")
        mock_sync_class.return_value = mock_sync

        result = controller.get_sync_status()

        assert 'error' in result
        assert "Database error" in result['error']
        assert result['sync_running'] is False


class TestSyncEndpointIntegration:
    """Integration tests for sync endpoints."""

    def test_controller_has_sync_methods(self, controller):
        """Test controller has required sync methods."""
        assert hasattr(controller, 'trigger_openwebui_sync')
        assert hasattr(controller, 'get_sync_status')
        assert callable(controller.trigger_openwebui_sync)
        assert callable(controller.get_sync_status)

    @patch('db.services.sync_service.ConversationSyncService')
    def test_sync_response_format(self, mock_sync_class, controller):
        """Test sync response has all expected fields."""
        mock_sync = MagicMock()
        mock_sync.start_background_sync.return_value = {
            'status': 'started',
            'started_at': '2024-01-15T10:30:00Z'
        }
        mock_sync_class.return_value = mock_sync

        result = controller.trigger_openwebui_sync()

        assert 'success' in result
        assert 'message' in result

    @patch('db.services.sync_service.ConversationSyncService')
    def test_status_response_format(self, mock_sync_class, controller):
        """Test status response has all expected fields."""
        mock_sync = MagicMock()
        mock_sync.get_sync_status.return_value = {
            'last_openwebui_sync': None,
            'conversations_by_source': {},
            'total_conversations': 0,
            'openwebui_configured': False
        }
        mock_sync.get_sync_progress.return_value = {
            'running': False,
            'progress': None,
            'started_at': None,
            'error': None
        }
        mock_sync_class.return_value = mock_sync

        result = controller.get_sync_status()

        assert 'last_openwebui_sync' in result
        assert 'conversations_by_source' in result
        assert 'total_conversations' in result
        assert 'openwebui_configured' in result
        assert 'sync_running' in result

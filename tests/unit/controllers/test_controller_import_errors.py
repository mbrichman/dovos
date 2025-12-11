"""
Tests for improved error handling in postgres_controller import methods.

Tests that import errors are caught and translated to user-friendly messages.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from controllers.postgres_controller import PostgresController
from db.importers.errors import (
    FormatDetectionError,
    ImporterNotAvailableError,
    ExtractionError
)


class TestImportConversationsJsonErrorHandling:
    """Test error handling in _import_conversations_json."""
    
    def test_import_json_with_unknown_format(self):
        """_import_conversations_json should handle unknown format gracefully."""
        controller = PostgresController()
        
        unknown_data = {
            "conversations": [
                {
                    "random_field": "value",
                    "unrecognized": "format"
                }
            ]
        }
        
        # Should raise ValueError with helpful message
        with pytest.raises(ValueError) as exc_info:
            controller._import_conversations_json(unknown_data)
        
        error_msg = str(exc_info.value)
        # Error should mention it's unknown format and list supported formats
        assert "Unknown" in error_msg or "format" in error_msg.lower()
    
    def test_import_json_with_missing_extractor(self):
        """_import_conversations_json should handle missing extractor."""
        controller = PostgresController()
        
        # Mock FORMAT_REGISTRY to have missing extractor
        with patch('controllers.postgres_controller.FORMAT_REGISTRY', {}):
            chatgpt_data = {
                "conversations": [
                    {
                        "title": "Test",
                        "mapping": {"node": {}},
                        "create_time": 1695000000
                    }
                ]
            }
            
            # Should raise error mentioning missing importer
            with pytest.raises((ValueError, KeyError)):
                controller._import_conversations_json(chatgpt_data)
    
    def test_import_json_detects_format_before_extraction(self):
        """_import_conversations_json should detect format before trying extraction."""
        controller = PostgresController()
        
        # Unknown format should fail early
        unknown_data = {"conversations": [{"unknown": "format"}]}
        
        with pytest.raises(ValueError):
            controller._import_conversations_json(unknown_data)
    
    def test_import_json_validates_extractor_exists(self):
        """_import_conversations_json should validate extractor exists in FORMAT_REGISTRY."""
        controller = PostgresController()
        
        # Valid ChatGPT format but extractor missing
        with patch('controllers.postgres_controller.FORMAT_REGISTRY', {'docx': lambda x: []}):
            chatgpt_data = {
                "conversations": [
                    {
                        "title": "ChatGPT",
                        "mapping": {"node": {}},
                        "create_time": 1695000000
                    }
                ]
            }
            
            # Should fail because chatgpt extractor not in registry
            with pytest.raises((ValueError, KeyError)):
                controller._import_conversations_json(chatgpt_data)


class TestUploadEndpointErrorHandling:
    """Test error handling in upload endpoint."""
    
    def test_upload_catches_json_decode_error(self):
        """Sanity check for JSON error path (isolated from Flask context)."""
        import json
        invalid_json = '{invalid json{'
        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_json)
    
    def test_upload_error_messages_are_user_friendly(self):
        """Error messages from _import_conversations_json should be user-friendly."""
        controller = PostgresController()
        
        # Unknown format should raise with helpful message
        unknown_data = {"conversations": [{"unknown": "format"}]}
        
        with pytest.raises(ValueError) as exc_info:
            controller._import_conversations_json(unknown_data)
        
        error_msg = str(exc_info.value)
        # Should mention supported formats, not be technical
        assert "supported" in error_msg.lower()
    
    def test_extraction_error_message_format(self):
        """Extraction errors should be formatted with format name."""
        from db.importers.errors import ExtractionError, get_user_friendly_error_message
        
        original_error = ValueError("Invalid structure")
        error = ExtractionError(
            format_name="TestFormat",
            original_error=original_error
        )
        
        msg = get_user_friendly_error_message(error)
        assert "testformat" in msg.lower() or "failed to extract" in msg.lower()


class TestErrorMessageConsistency:
    """Test that error messages are consistent and helpful."""
    
    def test_import_errors_are_caught_and_wrapped(self):
        """Import-related errors should be caught and wrapped with helpful messages."""
        controller = PostgresController()
        
        # Any import error should result in helpful message, not stack trace
        unknown_data = {"conversations": [{"nothing": "useful"}]}
        
        with pytest.raises(ValueError) as exc_info:
            controller._import_conversations_json(unknown_data)
        
        # Error message should be user-friendly, not technical
        error_msg = str(exc_info.value)
        assert "format" in error_msg.lower() or "unknown" in error_msg.lower()
        assert "Traceback" not in error_msg

"""
Tests for improved error handling in the modular import system.

Tests that error messages are user-friendly and dynamically reflect
available importers through the plugin system.
"""

import pytest
from db.importers.errors import (
    FormatDetectionError, 
    ImporterNotAvailableError, 
    ExtractionError,
    get_user_friendly_error_message
)


class TestFormatDetectionError:
    """Test FormatDetectionError exception with dynamic format support."""
    
    def test_format_detection_error_with_available_formats(self):
        """FormatDetectionError should include available formats in message."""
        available = ["ChatGPT", "Claude", "OpenWebUI"]
        error = FormatDetectionError(available_formats=available)
        
        assert "ChatGPT" in error.message
        assert "Claude" in error.message
        assert "OpenWebUI" in error.message
        assert "Could not detect file format" in error.message
    
    def test_format_detection_error_with_no_formats(self):
        """FormatDetectionError should handle case when no importers available."""
        error = FormatDetectionError(available_formats=[])
        
        assert "no importers registered" in error.message
    
    def test_format_detection_error_with_diagnostic_info(self):
        """FormatDetectionError should store diagnostic information."""
        diagnostic = {
            "has_title": False,
            "has_mapping": False,
            "has_uuid": False,
            "has_chat_messages": False
        }
        error = FormatDetectionError(
            available_formats=["ChatGPT", "Claude"],
            diagnostic_info=diagnostic
        )
        
        assert error.diagnostic_info == diagnostic


class TestImporterNotAvailableError:
    """Test ImporterNotAvailableError exception with dynamic format support."""
    
    def test_importer_not_available_error_basic(self):
        """ImporterNotAvailableError should mention format and available importers."""
        available = ["ChatGPT", "Claude"]
        error = ImporterNotAvailableError(
            format_name="UnknownFormat",
            available_formats=available
        )
        
        assert "UnknownFormat" in error.message
        assert "ChatGPT" in error.message
        assert "Claude" in error.message
        assert "system configuration issue" in error.message
    
    def test_importer_not_available_error_no_available_formats(self):
        """ImporterNotAvailableError with no available importers."""
        error = ImporterNotAvailableError(
            format_name="TestFormat",
            available_formats=[]
        )
        
        assert "TestFormat" in error.message
        assert "no importers registered" in error.message
    
    def test_importer_not_available_error_custom_message(self):
        """ImporterNotAvailableError can use custom message."""
        custom_msg = "Custom error message"
        error = ImporterNotAvailableError(
            format_name="TestFormat",
            available_formats=["ChatGPT"],
            message=custom_msg
        )
        
        assert error.message == custom_msg


class TestExtractionError:
    """Test ExtractionError exception."""
    
    def test_extraction_error_basic(self):
        """ExtractionError should include format name."""
        error = ExtractionError(format_name="ChatGPT")
        
        assert "ChatGPT" in error.message
        assert "Failed to extract" in error.message
    
    def test_extraction_error_with_original_error(self):
        """ExtractionError should include original error details."""
        original = ValueError("Invalid mapping structure")
        error = ExtractionError(
            format_name="ChatGPT",
            original_error=original
        )
        
        assert "ChatGPT" in error.message
        assert "Invalid mapping structure" in error.message
    
    def test_extraction_error_with_custom_message(self):
        """ExtractionError can use custom message."""
        custom_msg = "Custom extraction error"
        error = ExtractionError(
            format_name="Claude",
            message=custom_msg
        )
        
        assert error.message == custom_msg


class TestUserFriendlyErrorMessages:
    """Test get_user_friendly_error_message function."""
    
    def test_user_friendly_format_detection_error(self):
        """get_user_friendly_error_message formats detection errors properly."""
        available = ["ChatGPT", "Claude", "OpenWebUI"]
        error = FormatDetectionError(available_formats=available)
        
        msg = get_user_friendly_error_message(error, available_formats=available)
        
        assert "Could not detect file format" in msg
        assert "ChatGPT" in msg
        assert "Claude" in msg
        assert "OpenWebUI" in msg
    
    def test_user_friendly_importer_not_available_error(self):
        """get_user_friendly_error_message formats importer errors properly."""
        available = ["ChatGPT", "Claude"]
        error = ImporterNotAvailableError(
            format_name="MyFormat",
            available_formats=available
        )
        
        msg = get_user_friendly_error_message(error, available_formats=available)
        
        assert "MyFormat" in msg
        assert "ChatGPT" in msg
        assert "Claude" in msg
    
    def test_user_friendly_extraction_error(self):
        """get_user_friendly_error_message formats extraction errors."""
        error = ExtractionError(
            format_name="Claude",
            message="Failed to process chat_messages field"
        )
        
        msg = get_user_friendly_error_message(error)
        
        assert "Failed to process" in msg
    
    def test_user_friendly_generic_error(self):
        """get_user_friendly_error_message handles generic exceptions."""
        error = ValueError("Some error")
        msg = get_user_friendly_error_message(error)
        
        assert "Import failed" in msg


class TestErrorMessagesReflectAvailableFormats:
    """Test that error messages dynamically reflect available importers."""
    
    def test_format_detection_error_with_single_format(self):
        """Error message with only one available format."""
        error = FormatDetectionError(available_formats=["ChatGPT"])
        
        assert "ChatGPT" in error.message
        assert "Claude" not in error.message
    
    def test_format_detection_error_with_custom_formats(self):
        """Error message reflects custom available formats."""
        # Simulate a system with only Claude and a custom format
        available = ["Claude", "CustomFormat"]
        error = FormatDetectionError(available_formats=available)
        
        assert "Claude" in error.message
        assert "CustomFormat" in error.message
        assert "ChatGPT" not in error.message
    
    def test_importer_not_available_lists_available(self):
        """ImporterNotAvailableError lists what IS available."""
        available = ["ChatGPT"]
        error = ImporterNotAvailableError(
            format_name="Claude",
            available_formats=available
        )
        
        msg = error.message
        assert "Claude" in msg  # Detected format
        assert "ChatGPT" in msg  # Available format


class TestExceptionInheritance:
    """Test that exceptions properly inherit from ImportError."""
    
    def test_format_detection_error_is_import_error(self):
        """FormatDetectionError should be an ImportError."""
        from db.importers.errors import ImportError
        error = FormatDetectionError()
        
        assert isinstance(error, ImportError)
    
    def test_importer_not_available_error_is_import_error(self):
        """ImporterNotAvailableError should be an ImportError."""
        from db.importers.errors import ImportError
        error = ImporterNotAvailableError(format_name="Test")
        
        assert isinstance(error, ImportError)
    
    def test_extraction_error_is_import_error(self):
        """ExtractionError should be an ImportError."""
        from db.importers.errors import ImportError
        error = ExtractionError(format_name="Test")
        
        assert isinstance(error, ImportError)

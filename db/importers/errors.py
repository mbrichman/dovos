"""
Custom exceptions for the modular import system.

Provides structured error types for format detection failures,
missing importers, and extraction errors. All error messages dynamically
reflect the actually available importers.
"""


class ImportError(Exception):
    """Base exception for import-related errors."""
    pass


class FormatDetectionError(ImportError):
    """
    Raised when a file format cannot be reliably detected.
    
    Attributes:
        message: User-friendly error message (dynamically constructed)
        detected_as: What the detector thought it might be (or None)
        diagnostic_info: Dict with details about what was/wasn't found
        available_formats: List of format names that ARE available
    """
    
    def __init__(self, message: str = None, detected_as: str = None, 
                 diagnostic_info: dict = None, available_formats: list = None):
        self.detected_as = detected_as
        self.diagnostic_info = diagnostic_info or {}
        self.available_formats = available_formats or []
        
        if message is None:
            formats_str = ", ".join(self.available_formats) if self.available_formats else "no importers registered"
            message = (
                f"Could not detect file format. "
                f"Supported formats: {formats_str}. "
                f"Please ensure your file is a valid export from one of these sources."
            )
        
        self.message = message
        super().__init__(message)


class ImporterNotAvailableError(ImportError):
    """
    Raised when a format is detected but no importer is available.
    
    This indicates a system configuration issue - the format was recognized
    but the corresponding extractor is not registered in FORMAT_REGISTRY.
    
    Attributes:
        format_name: The format that was detected
        message: User-friendly error message
        available_formats: List of formats that ARE available
    """
    
    def __init__(self, format_name: str, available_formats: list = None, message: str = None):
        self.format_name = format_name
        self.available_formats = available_formats or []
        
        if message is None:
            formats_str = ", ".join(self.available_formats) if self.available_formats else "no importers registered"
            message = (
                f"Format '{format_name}' was detected in your file, but the importer is not available. "
                f"This is a system configuration issue. "
                f"Available importers: {formats_str}"
            )
        
        self.message = message
        super().__init__(message)


class ExtractionError(ImportError):
    """
    Raised when message extraction from a detected format fails.
    
    Attributes:
        format_name: The format being extracted from
        message: User-friendly error message
        original_error: The underlying exception (for logging/debugging)
    """
    
    def __init__(self, format_name: str, message: str = None, original_error: Exception = None):
        self.format_name = format_name
        self.original_error = original_error
        
        if message is None:
            message = f"Failed to extract messages from {format_name} format"
            if original_error:
                message += f": {str(original_error)}"
        
        self.message = message
        super().__init__(message)


def get_user_friendly_error_message(error: Exception, available_formats: list = None) -> str:
    """
    Convert an import error to a user-friendly message for display in the UI.
    
    Args:
        error: An exception from the import system
        available_formats: List of currently available importer formats
        
    Returns:
        A user-friendly error message suitable for displaying in the import dialog
    """
    available_formats = available_formats or []
    
    if isinstance(error, FormatDetectionError):
        if error.message:
            return error.message
        # Fallback message if no message was set
        formats_str = ", ".join(available_formats) if available_formats else "no importers registered"
        return (
            f"Could not detect file format. "
            f"Supported formats: {formats_str}. "
            f"Please ensure your file is a valid export."
        )
    
    elif isinstance(error, ImporterNotAvailableError):
        if error.message:
            return error.message
        # Fallback message
        formats_str = ", ".join(available_formats) if available_formats else "no importers registered"
        return (
            f"Format '{error.format_name}' detected but importer not available. "
            f"Available importers: {formats_str}"
        )
    
    elif isinstance(error, ExtractionError):
        return error.message
    
    else:
        # Generic fallback for non-import errors
        return f"Import failed: {str(error)}"

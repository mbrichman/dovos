"""
DOCX format message extractor.

Provides a wrapper around utils.docx_parser that normalizes output
to match the extractor interface used by other formats.
"""

import sys
import os
from typing import List, Dict, Tuple, Any

# Add project root to path for utils import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.docx_parser import parse_docx_file


def extract_messages_from_file(file_path: str, filename: str, **kwargs) -> Tuple[List[Dict], str, List[str]]:
    """
    Extract messages from a DOCX (Word document) file.
    
    This is a wrapper around utils.docx_parser that provides a consistent
    interface for extracting messages from Word documents.
    
    Args:
        file_path: Path to the DOCX file
        filename: Original filename (used for title extraction)
        **kwargs: Additional options (for extensibility)
        
    Returns:
        Tuple of (messages_list, title, timestamps)
        where:
        - messages_list: List of dicts with 'role' and 'content' keys
        - title: Extracted or derived conversation title
        - timestamps: List of ISO format timestamp strings (may be empty)
    """
    # Call the DOCX parser which returns (messages, timestamps, title)
    messages, timestamps, title = parse_docx_file(file_path, original_filename=filename)
    
    # Return in consistent format: (messages, title, timestamps)
    return messages, title, timestamps

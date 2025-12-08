"""
Import system with pluggable format extractors.

This module provides a registry-based system for detecting and extracting
different chat export formats (ChatGPT, Claude, OpenWebUI, etc.).
"""

from db.importers.registry import detect_format, FORMAT_REGISTRY

__all__ = ["detect_format", "FORMAT_REGISTRY"]

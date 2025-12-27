"""
Metadata schema and utilities for extractors.

Defines the structure and defaults for extractor metadata.
"""

from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class ExtractorMetadata:
    """Metadata for a message extractor."""
    
    # Basic information
    name: str  # Human-readable name (e.g., "ChatGPT")
    version: str  # Semantic version (e.g., "1.0.0")
    description: str  # What this extractor handles
    author: str  # Maintainer name
    
    # Format information
    supported_extensions: List[str] = field(default_factory=lambda: [])  # e.g., [".json"]
    
    # Capabilities
    capabilities: Dict[str, Any] = field(default_factory=dict)  # Feature flags
    
    # Format specification
    format_spec: Dict[str, Any] = field(default_factory=dict)  # Expected input format
    
    # Breaking changes history
    breaking_changes: List[Dict[str, str]] = field(default_factory=list)  # Version history
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author,
            'supported_extensions': self.supported_extensions,
            'capabilities': self.capabilities,
            'format_spec': self.format_spec,
            'breaking_changes': self.breaking_changes,
        }


# Default metadata for built-in extractors
DEFAULT_METADATA: Dict[str, ExtractorMetadata] = {
    'chatgpt': ExtractorMetadata(
        name='ChatGPT',
        version='1.0.0',
        description='ChatGPT format message extractor. Extracts messages from ChatGPT\'s node-based mapping structure.',
        author='DovOS Contributors',
        supported_extensions=['.json'],
        capabilities={'auto_detect': True, 'streaming': False},
        format_spec={
            'description': 'ChatGPT JSON export format',
            'input_type': 'dict',
            'structure': 'Conversation dict with "mapping" key containing node_id -> node_data',
            'required_fields': ['mapping'],
            'example_field': 'mapping is a dict where each node contains "message" with "author" and "content"',
        },
        breaking_changes=[],
    ),
    'docx': ExtractorMetadata(
        name='DOCX',
        version='1.0.0',
        description='DOCX format message extractor. Extracts messages from Word documents.',
        author='DovOS Contributors',
        supported_extensions=['.docx'],
        capabilities={'auto_detect': False, 'streaming': False},
        format_spec={
            'description': 'Microsoft Word DOCX format',
            'input_type': 'file',
            'structure': 'Word document with message exchanges',
        },
        breaking_changes=[],
    ),
    'claude': ExtractorMetadata(
        name='Claude',
        version='1.0.0',
        description='Claude format message extractor. Extracts messages from Claude\'s chat_messages list format.',
        author='DovOS Contributors',
        supported_extensions=['.json'],
        capabilities={'auto_detect': True, 'streaming': False},
        format_spec={
            'description': 'Claude JSON export format',
            'input_type': 'list',
            'structure': 'List of chat_messages where each message has sender and text',
            'required_fields': ['sender', 'text'],
            'sender_mapping': 'human -> user, others -> assistant',
        },
        breaking_changes=[],
    ),
    'openwebui': ExtractorMetadata(
        name='OpenWebUI',
        version='1.0.0',
        description='OpenWebUI format message extractor. Extracts and flattens messages from OpenWebUI\'s tree-structured dict format.',
        author='DovOS Contributors',
        supported_extensions=['.json'],
        capabilities={'auto_detect': True, 'streaming': False, 'tree_flattening': True},
        format_spec={
            'description': 'OpenWebUI JSON export format',
            'input_type': 'dict',
            'structure': 'Dict with message_id -> message_data mapping, messages have role, content, timestamp',
            'required_fields': ['role', 'content'],
            'timestamp_handling': 'Handles nanoseconds, milliseconds, and seconds',
        },
        breaking_changes=[],
    ),
}

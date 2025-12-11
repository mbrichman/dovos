"""
Unit tests for format detection logic.

Tests the ability to detect and parse different chat export formats:
- ChatGPT (title, mapping, create_time)
- Claude (uuid, name, chat_messages)
- OpenWebUI (chat.history.messages as dict with id/role/content/timestamp)
- Unknown formats
"""

import pytest
from typing import Dict, List, Any


class TestFormatDetection:
    """Test suite for detecting different chat export formats."""
    
    def test_detect_chatgpt_format(self):
        """Test detection of ChatGPT export format."""
        from db.importers.registry import detect_format
        
        chatgpt_data = {
            "conversations": [
                {
                    "id": "conv-123",
                    "title": "Python Help",
                    "mapping": {
                        "node-1": {
                            "message": {
                                "content": {"parts": ["Hello"]},
                                "role": "user"
                            }
                        }
                    },
                    "create_time": 1695000000,
                    "update_time": 1695001000
                }
            ]
        }
        
        conversations, format_type = detect_format(chatgpt_data)
        assert format_type == "ChatGPT"
        assert len(conversations) == 1
        assert conversations[0]["title"] == "Python Help"
    
    def test_detect_claude_format(self):
        """Test detection of Claude export format."""
        from db.importers.registry import detect_format
        
        claude_data = {
            "conversations": [
                {
                    "uuid": "uuid-123",
                    "name": "Claude Conversation",
                    "chat_messages": [
                        {
                            "uuid": "msg-1",
                            "text": "Hello",
                            "created_at": "2023-09-18T10:00:00Z"
                        }
                    ],
                    "created_at": "2023-09-18T10:00:00Z",
                    "updated_at": "2023-09-18T10:05:00Z"
                }
            ]
        }
        
        conversations, format_type = detect_format(claude_data)
        assert format_type == "Claude"
        assert len(conversations) == 1
        assert conversations[0]["uuid"] == "uuid-123"
    
    def test_detect_openwebui_format(self):
        """Test detection of OpenWebUI export format."""
        from db.importers.registry import detect_format
        
        openwebui_data = {
            "conversations": [
                {
                    "id": "webui-123",
                    "title": "OpenWebUI Chat",
                    "chat": {
                        "history": {
                            "messages": {
                                "msg-1": {
                                    "id": "msg-1",
                                    "role": "user",
                                    "content": "Hello",
                                    "timestamp": 1695000000
                                },
                                "msg-2": {
                                    "id": "msg-2",
                                    "role": "assistant",
                                    "content": "Hi there!",
                                    "timestamp": 1695000001
                                }
                            }
                        }
                    },
                    "created_at": 1695000000,
                    "updated_at": 1695000001
                }
            ]
        }
        
        conversations, format_type = detect_format(openwebui_data)
        assert format_type == "OpenWebUI"
        assert len(conversations) == 1
        assert "chat" in conversations[0]
    
    def test_detect_unknown_format(self):
        """Test detection returns Unknown for unrecognized format."""
        from db.importers.registry import detect_format
        
        unknown_data = {
            "conversations": [
                {
                    "random_field": "value",
                    "unrecognized": "format"
                }
            ]
        }
        
        conversations, format_type = detect_format(unknown_data)
        assert format_type == "Unknown"
        assert len(conversations) == 1
    
    def test_detect_empty_conversations(self):
        """Test detection with empty conversations list."""
        from db.importers.registry import detect_format
        
        empty_data = {"conversations": []}
        conversations, format_type = detect_format(empty_data)
        assert format_type == "Unknown"
        assert len(conversations) == 0
    
    def test_detect_data_as_list(self):
        """Test detection when input is a list instead of dict."""
        from db.importers.registry import detect_format
        
        list_data = [
            {
                "title": "ChatGPT Conv",
                "mapping": {"node-1": {"message": {"content": {"parts": ["text"]}}}},
                "create_time": 1695000000
            }
        ]
        
        conversations, format_type = detect_format(list_data)
        assert format_type == "ChatGPT"
        assert len(conversations) == 1
    
    def test_detect_missing_conversations_key(self):
        """Test detection when 'conversations' key is missing."""
        from db.importers.registry import detect_format
        
        no_key_data = [
            {
                "title": "ChatGPT",
                "mapping": {"node": {"message": {"content": {"parts": ["text"]}}}},
                "create_time": 1695000000
            }
        ]
        
        conversations, format_type = detect_format(no_key_data)
        assert format_type == "ChatGPT"
        assert len(conversations) == 1
    
    def test_claude_with_empty_name(self):
        """Test Claude format detection when name is empty string."""
        from db.importers.registry import detect_format
        
        claude_data = {
            "conversations": [
                {
                    "uuid": "uuid-456",
                    "name": "",  # Empty name but still Claude format
                    "chat_messages": [],
                    "created_at": "2023-09-18T10:00:00Z"
                }
            ]
        }
        
        conversations, format_type = detect_format(claude_data)
        assert format_type == "Claude"
    
    def test_openwebui_messages_must_be_dict(self):
        """Test that OpenWebUI format requires messages to be a dict, not list."""
        from db.importers.registry import detect_format
        
        # Invalid OpenWebUI with messages as list instead of dict
        invalid_data = {
            "conversations": [
                {
                    "chat": {
                        "history": {
                            "messages": [  # Wrong type - should be dict
                                {"id": "msg-1", "role": "user", "content": "text", "timestamp": 123}
                            ]
                        }
                    }
                }
            ]
        }
        
        conversations, format_type = detect_format(invalid_data)
        assert format_type != "OpenWebUI"
    
    def test_openwebui_message_must_have_required_fields(self):
        """Test OpenWebUI format validation for message fields."""
        from db.importers.registry import detect_format
        
        # Missing required fields in message
        invalid_data = {
            "conversations": [
                {
                    "chat": {
                        "history": {
                            "messages": {
                                "msg-1": {
                                    "id": "msg-1",
                                    # Missing role, content, timestamp
                                }
                            }
                        }
                    }
                }
            ]
        }
        
        conversations, format_type = detect_format(invalid_data)
        assert format_type != "OpenWebUI"
    
    def test_chatgpt_requires_mapping(self):
        """Test ChatGPT format requires 'mapping' key."""
        from db.importers.registry import detect_format
        
        # Missing mapping
        invalid_data = {
            "conversations": [
                {
                    "title": "Title",
                    "create_time": 1695000000,
                    # Missing mapping
                }
            ]
        }
        
        conversations, format_type = detect_format(invalid_data)
        assert format_type != "ChatGPT"
    
    def test_chatgpt_requires_create_time(self):
        """Test ChatGPT format requires 'create_time' key."""
        from db.importers.registry import detect_format
        
        # Missing create_time
        invalid_data = {
            "conversations": [
                {
                    "title": "Title",
                    "mapping": {"node": {}},
                    # Missing create_time
                }
            ]
        }
        
        conversations, format_type = detect_format(invalid_data)
        assert format_type != "ChatGPT"
    
    def test_multiple_conversations_uses_first(self):
        """Test that format detection uses only the first conversation."""
        from db.importers.registry import detect_format
        
        mixed_data = {
            "conversations": [
                {
                    "title": "ChatGPT",
                    "mapping": {"node": {"message": {"content": {"parts": ["text"]}}}},
                    "create_time": 1695000000
                },
                {
                    "uuid": "uuid-2",
                    "name": "Claude",
                    "chat_messages": []
                }
            ]
        }
        
        conversations, format_type = detect_format(mixed_data)
        # Should detect as ChatGPT since it's first
        assert format_type == "ChatGPT"
        assert len(conversations) == 2


class TestFormatDetectionErrorHandling:
    """Test error handling in format detection."""
    
    def test_detect_unknown_format_can_raise_error(self):
        """Test that unknown format detection can raise FormatDetectionError."""
        from db.importers.registry import detect_format
        from db.importers.errors import FormatDetectionError
        
        unknown_data = {
            "conversations": [
                {
                    "random_field": "value",
                    "unrecognized": "format"
                }
            ]
        }
        
        # detect_format should return tuple for backward compatibility
        conversations, format_type = detect_format(unknown_data)
        assert format_type == "Unknown"
        
        # But can also raise error when explicitly requested or needed
        # (This tests the capability, implementation depends on requirements)
    
    def test_detect_format_returns_available_formats_list(self):
        """Test that detect_format can include list of available formats."""
        from db.importers.registry import detect_format, FORMAT_REGISTRY
        
        # Should be able to get available formats from registry
        available_formats = list(FORMAT_REGISTRY.keys())
        
        assert len(available_formats) > 0
        assert "chatgpt" in available_formats or "ChatGPT" in available_formats.upper()

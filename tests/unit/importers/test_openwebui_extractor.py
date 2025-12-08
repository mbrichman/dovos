"""
Unit tests for OpenWebUI message extraction.

Tests the extraction and flattening of messages from OpenWebUI's tree-structured format.
"""

import pytest
from typing import Dict, List, Any
from datetime import datetime, timezone


class TestOpenWebUIExtractor:
    """Test suite for OpenWebUI message extraction."""
    
    def test_extract_basic_messages(self):
        """Test extraction of basic user/assistant message pairs."""
        from db.importers.openwebui import extract_messages
        
        messages_dict = {
            "msg-1": {
                "id": "msg-1",
                "role": "user",
                "content": "Hello",
                "timestamp": 1695000000,
                "models": ["gpt-4"]
            },
            "msg-2": {
                "id": "msg-2",
                "role": "assistant",
                "content": "Hi there",
                "timestamp": 1695000001,
                "model": "gpt-4"
            }
        }
        
        messages = extract_messages(messages_dict)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hi there"
    
    def test_extract_preserves_timestamps(self):
        """Test that Unix epoch timestamps are converted to datetime objects."""
        from db.importers.openwebui import extract_messages
        
        ts1 = 1695000000
        ts2 = 1695000001
        
        messages_dict = {
            "msg-1": {
                "role": "user",
                "content": "Message 1",
                "timestamp": ts1
            },
            "msg-2": {
                "role": "assistant",
                "content": "Message 2",
                "timestamp": ts2
            }
        }
        
        messages = extract_messages(messages_dict)
        # Should be datetime objects
        assert isinstance(messages[0]["created_at"], datetime)
        assert isinstance(messages[1]["created_at"], datetime)
    
    def test_extract_normalizes_role_case(self):
        """Test that roles are normalized to lowercase."""
        from db.importers.openwebui import extract_messages
        
        messages_dict = {
            "msg-1": {
                "role": "USER",
                "content": "User message"
            },
            "msg-2": {
                "role": "Assistant",
                "content": "Assistant message"
            }
        }
        
        messages = extract_messages(messages_dict)
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
    
    def test_extract_skips_empty_messages(self):
        """Test that empty messages are skipped."""
        from db.importers.openwebui import extract_messages
        
        messages_dict = {
            "msg-1": {
                "role": "user",
                "content": "Valid message"
            },
            "msg-2": {
                "role": "assistant",
                "content": ""
            },
            "msg-3": {
                "role": "user",
                "content": "   "
            }
        }
        
        messages = extract_messages(messages_dict)
        assert len(messages) == 1
        assert messages[0]["content"] == "Valid message"
    
    def test_extract_handles_dict_content(self):
        """Test handling of content that's a dict instead of string."""
        from db.importers.openwebui import extract_messages
        
        messages_dict = {
            "msg-1": {
                "role": "user",
                "content": {"text": "Message in dict"}
            },
            "msg-2": {
                "role": "assistant",
                "content": {"content": "Alternative dict key"}
            }
        }
        
        messages = extract_messages(messages_dict)
        assert len(messages) == 2
        assert "Message in dict" in messages[0]["content"]
        assert "Alternative dict key" in messages[1]["content"]
    
    def test_extract_handles_none_content(self):
        """Test handling of None content."""
        from db.importers.openwebui import extract_messages
        
        messages_dict = {
            "msg-1": {
                "role": "user",
                "content": "Valid"
            },
            "msg-2": {
                "role": "assistant",
                "content": None
            }
        }
        
        messages = extract_messages(messages_dict)
        assert len(messages) == 1
    
    def test_extract_preserves_model_from_assistant(self):
        """Test that model field is preserved from assistant messages."""
        from db.importers.openwebui import extract_messages
        
        messages_dict = {
            "msg-1": {
                "role": "user",
                "content": "Question",
                "models": ["gpt-4", "gpt-3.5"]
            },
            "msg-2": {
                "role": "assistant",
                "content": "Answer",
                "model": "gpt-4"
            }
        }
        
        messages = extract_messages(messages_dict)
        assert messages[0]["model"] == "gpt-4"  # First from models list
        assert messages[1]["model"] == "gpt-4"
    
    def test_extract_skips_none_dict_entries(self):
        """Test handling of None entries in messages dict."""
        from db.importers.openwebui import extract_messages
        
        messages_dict = {
            "msg-1": {
                "role": "user",
                "content": "Valid"
            },
            "msg-2": None
        }
        
        messages = extract_messages(messages_dict)
        assert len(messages) == 1
    
    def test_extract_empty_dict(self):
        """Test extraction from empty dict."""
        from db.importers.openwebui import extract_messages
        
        messages = extract_messages({})
        assert messages == []
    
    def test_extract_none_input(self):
        """Test handling of None input."""
        from db.importers.openwebui import extract_messages
        
        messages = extract_messages(None)
        assert messages == []
    
    def test_extract_sorts_by_timestamp(self):
        """Test that messages are sorted chronologically by timestamp."""
        from db.importers.openwebui import extract_messages
        
        messages_dict = {
            "msg-3": {
                "role": "user",
                "content": "Third",
                "timestamp": 1695000003
            },
            "msg-1": {
                "role": "user",
                "content": "First",
                "timestamp": 1695000001
            },
            "msg-2": {
                "role": "assistant",
                "content": "Second",
                "timestamp": 1695000002
            }
        }
        
        messages = extract_messages(messages_dict)
        assert len(messages) == 3
        assert messages[0]["content"] == "First"
        assert messages[1]["content"] == "Second"
        assert messages[2]["content"] == "Third"
    
    def test_extract_handles_millisecond_timestamps(self):
        """Test handling of timestamps in milliseconds."""
        from db.importers.openwebui import extract_messages
        
        # Millisecond timestamp (will be converted to seconds)
        messages_dict = {
            "msg-1": {
                "role": "user",
                "content": "Message",
                "timestamp": 1695000000000  # Milliseconds
            }
        }
        
        messages = extract_messages(messages_dict)
        assert len(messages) == 1
        assert isinstance(messages[0]["created_at"], datetime)
    
    def test_extract_handles_missing_role(self):
        """Test handling of messages with missing role."""
        from db.importers.openwebui import extract_messages
        
        messages_dict = {
            "msg-1": {
                "content": "No role"
            },
            "msg-2": {
                "role": "user",
                "content": "Valid"
            }
        }
        
        messages = extract_messages(messages_dict)
        # Message without role should default to 'user'
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
    
    def test_extract_preserves_sequence(self):
        """Test that insertion order sequence is preserved."""
        from db.importers.openwebui import extract_messages
        
        messages_dict = {
            "msg-1": {
                "role": "user",
                "content": "First"
            },
            "msg-2": {
                "role": "assistant",
                "content": "Second"
            },
            "msg-3": {
                "role": "user",
                "content": "Third"
            }
        }
        
        messages = extract_messages(messages_dict)
        assert len(messages) == 3
        # Check that sequence is preserved
        for msg in messages:
            assert "sequence" in msg
    
    def test_extract_signature_matches_interface(self):
        """Test that extract_messages has correct signature."""
        from db.importers.openwebui import extract_messages
        import inspect
        
        sig = inspect.signature(extract_messages)
        params = list(sig.parameters.keys())
        
        # Should have conversation_data as first parameter
        assert params[0] == "conversation_data"
        # Should accept **kwargs for extensibility
        assert "kwargs" in params or any(
            p for p in sig.parameters.values() if p.kind == inspect.Parameter.VAR_KEYWORD
        )
    
    def test_extract_handles_whitespace_only_role(self):
        """Test handling of whitespace-only role values."""
        from db.importers.openwebui import extract_messages
        
        messages_dict = {
            "msg-1": {
                "role": "   ",
                "content": "Message"
            }
        }
        
        messages = extract_messages(messages_dict)
        assert len(messages) == 1
        # Whitespace-only role should default to 'user'
        assert messages[0]["role"] == "user"
    
    def test_extract_invalid_timestamp_uses_now(self):
        """Test that invalid timestamps use current time."""
        from db.importers.openwebui import extract_messages
        
        messages_dict = {
            "msg-1": {
                "role": "user",
                "content": "Message",
                "timestamp": "invalid"
            }
        }
        
        messages = extract_messages(messages_dict)
        assert len(messages) == 1
        # Should have a datetime (either converted or defaulted)
        assert isinstance(messages[0]["created_at"], datetime)

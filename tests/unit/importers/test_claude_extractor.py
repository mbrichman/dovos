"""
Unit tests for Claude message extraction.

Tests the extraction of messages from Claude's chat_messages format.
"""

import pytest
from typing import Dict, List, Any


class TestClaudeExtractor:
    """Test suite for Claude message extraction."""
    
    def test_extract_basic_messages(self):
        """Test extraction of basic human/assistant message pairs."""
        from db.importers.claude import extract_messages
        
        chat_messages = [
            {
                "uuid": "msg-1",
                "sender": "human",
                "text": "Hello Claude",
                "created_at": "2023-09-18T10:00:00Z"
            },
            {
                "uuid": "msg-2",
                "sender": "assistant",
                "text": "Hi there! How can I help?",
                "created_at": "2023-09-18T10:00:01Z"
            }
        ]
        
        messages = extract_messages(chat_messages)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello Claude"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hi there! How can I help?"
    
    def test_extract_maps_human_to_user(self):
        """Test that sender='human' maps to role='user'."""
        from db.importers.claude import extract_messages
        
        chat_messages = [
            {
                "sender": "human",
                "text": "User message"
            }
        ]
        
        messages = extract_messages(chat_messages)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
    
    def test_extract_maps_other_senders_to_assistant(self):
        """Test that non-human senders map to assistant."""
        from db.importers.claude import extract_messages
        
        chat_messages = [
            {
                "sender": "assistant",
                "text": "Assistant message"
            },
            {
                "sender": "claude",
                "text": "Claude message"
            },
            {
                "sender": "system",
                "text": "System message"
            }
        ]
        
        messages = extract_messages(chat_messages)
        assert len(messages) == 3
        # All should be assistant role
        assert all(msg["role"] == "assistant" for msg in messages)
    
    def test_extract_preserves_timestamps(self):
        """Test that ISO format timestamps are preserved."""
        from db.importers.claude import extract_messages
        
        ts1 = "2023-09-18T10:00:00Z"
        ts2 = "2023-09-18T10:00:01Z"
        
        chat_messages = [
            {
                "sender": "human",
                "text": "Message 1",
                "created_at": ts1
            },
            {
                "sender": "assistant",
                "text": "Message 2",
                "created_at": ts2
            }
        ]
        
        messages = extract_messages(chat_messages)
        assert messages[0]["created_at"] == ts1
        assert messages[1]["created_at"] == ts2
    
    def test_extract_skips_empty_messages(self):
        """Test that empty messages are skipped."""
        from db.importers.claude import extract_messages
        
        chat_messages = [
            {
                "sender": "human",
                "text": "Valid message"
            },
            {
                "sender": "assistant",
                "text": ""
            },
            {
                "sender": "human",
                "text": "   "
            },
            {
                "sender": "assistant",
                "text": "Another valid message"
            }
        ]
        
        messages = extract_messages(chat_messages)
        assert len(messages) == 2
        assert messages[0]["content"] == "Valid message"
        assert messages[1]["content"] == "Another valid message"
    
    def test_extract_handles_missing_text_field(self):
        """Test handling of messages without text field."""
        from db.importers.claude import extract_messages
        
        chat_messages = [
            {
                "sender": "human",
                "text": "Valid"
            },
            {
                "sender": "assistant"
                # No text field
            }
        ]
        
        messages = extract_messages(chat_messages)
        assert len(messages) == 1
        assert messages[0]["content"] == "Valid"
    
    def test_extract_skips_messages_without_sender(self):
        """Test that messages without sender are skipped."""
        from db.importers.claude import extract_messages
        
        chat_messages = [
            {
                "sender": "human",
                "text": "Message 1"
            },
            {
                "text": "No sender"
            },
            {
                "sender": "assistant",
                "text": "Message 2"
            }
        ]
        
        messages = extract_messages(chat_messages)
        assert len(messages) == 2
    
    def test_extract_empty_list(self):
        """Test extraction from empty list."""
        from db.importers.claude import extract_messages
        
        messages = extract_messages([])
        assert messages == []
    
    def test_extract_none_input(self):
        """Test handling of None input."""
        from db.importers.claude import extract_messages
        
        messages = extract_messages(None)
        assert messages == []
    
    def test_extract_with_none_messages(self):
        """Test handling of None message values."""
        from db.importers.claude import extract_messages
        
        chat_messages = [
            {
                "sender": "human",
                "text": "Valid"
            },
            None,
            {
                "sender": "assistant",
                "text": "Another"
            }
        ]
        
        messages = extract_messages(chat_messages)
        assert len(messages) == 2
    
    def test_extract_timestamps_optional(self):
        """Test that timestamps are optional."""
        from db.importers.claude import extract_messages
        
        chat_messages = [
            {
                "sender": "human",
                "text": "Message without timestamp"
            },
            {
                "sender": "assistant",
                "text": "Message with timestamp",
                "created_at": "2023-09-18T10:00:00Z"
            }
        ]
        
        messages = extract_messages(chat_messages)
        assert len(messages) == 2
        assert "created_at" not in messages[0]
        assert messages[1]["created_at"] == "2023-09-18T10:00:00Z"
    
    def test_extract_preserves_message_order(self):
        """Test that message order is preserved."""
        from db.importers.claude import extract_messages
        
        chat_messages = [
            {"sender": "human", "text": "First"},
            {"sender": "assistant", "text": "Second"},
            {"sender": "human", "text": "Third"},
            {"sender": "assistant", "text": "Fourth"}
        ]
        
        messages = extract_messages(chat_messages)
        assert len(messages) == 4
        assert messages[0]["content"] == "First"
        assert messages[1]["content"] == "Second"
        assert messages[2]["content"] == "Third"
        assert messages[3]["content"] == "Fourth"
    
    def test_extract_signature_matches_interface(self):
        """Test that extract_messages has correct signature."""
        from db.importers.claude import extract_messages
        import inspect
        
        sig = inspect.signature(extract_messages)
        params = list(sig.parameters.keys())
        
        # Should have conversation_data as first parameter
        assert params[0] == "conversation_data"
        # Should accept **kwargs for extensibility
        assert "kwargs" in params or any(
            p for p in sig.parameters.values() if p.kind == inspect.Parameter.VAR_KEYWORD
        )
    
    def test_extract_handles_dict_input(self):
        """Test handling when input is a dict instead of list."""
        from db.importers.claude import extract_messages
        
        # Should handle gracefully (Claude's actual data structure is a list)
        messages = extract_messages({"chat_messages": []})
        assert messages == []
    
    def test_extract_whitespace_stripping(self):
        """Test that whitespace-only messages are stripped."""
        from db.importers.claude import extract_messages
        
        chat_messages = [
            {"sender": "human", "text": "   \n\t  "},
            {"sender": "assistant", "text": " Valid "}
        ]
        
        messages = extract_messages(chat_messages)
        assert len(messages) == 1
        # Whitespace should be preserved in valid content
        assert messages[0]["content"] == " Valid "

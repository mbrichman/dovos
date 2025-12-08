"""
Unit tests for ChatGPT message extraction.

Tests the extraction of messages from ChatGPT's node-based mapping structure.
"""

import pytest
from typing import Dict, List, Any


class TestChatGPTExtractor:
    """Test suite for ChatGPT message extraction."""
    
    def test_extract_basic_messages(self):
        """Test extraction of basic user/assistant message pairs."""
        from db.importers.chatgpt import extract_messages
        
        mapping = {
            "node-1": {
                "id": "node-1",
                "create_time": 1695000000,
                "message": {
                    "id": "msg-1",
                    "create_time": 1695000000,
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Hello there"]}
                }
            },
            "node-2": {
                "id": "node-2",
                "create_time": 1695000001,
                "message": {
                    "id": "msg-2",
                    "create_time": 1695000001,
                    "author": {"role": "assistant"},
                    "content": {"content_type": "text", "parts": ["Hi! How can I help?"]}
                }
            }
        }
        
        messages = extract_messages(mapping)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello there"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hi! How can I help?"
    
    def test_extract_preserves_timestamps(self):
        """Test that timestamps are preserved from messages."""
        from db.importers.chatgpt import extract_messages
        
        ts1 = 1695000000
        ts2 = 1695000100
        
        mapping = {
            "node-1": {
                "create_time": ts1,
                "message": {
                    "create_time": ts1,
                    "author": {"role": "user"},
                    "content": {"parts": ["Message 1"]}
                }
            },
            "node-2": {
                "create_time": ts2,
                "message": {
                    "create_time": ts2,
                    "author": {"role": "assistant"},
                    "content": {"parts": ["Message 2"]}
                }
            }
        }
        
        messages = extract_messages(mapping)
        assert messages[0]["created_at"] == ts1
        assert messages[1]["created_at"] == ts2
    
    def test_extract_filters_non_conversation_roles(self):
        """Test that non-user/assistant roles are filtered out."""
        from db.importers.chatgpt import extract_messages
        
        mapping = {
            "node-1": {
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["User message"]}
                }
            },
            "node-2": {
                "message": {
                    "author": {"role": "system"},
                    "content": {"parts": ["System message"]}
                }
            },
            "node-3": {
                "message": {
                    "author": {"role": "assistant"},
                    "content": {"parts": ["Assistant message"]}
                }
            },
            "node-4": {
                "message": {
                    "author": {"role": "function"},
                    "content": {"parts": ["Function message"]}
                }
            }
        }
        
        messages = extract_messages(mapping)
        # Should only have user and assistant messages
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
    
    def test_extract_skips_empty_messages(self):
        """Test that empty messages are skipped."""
        from db.importers.chatgpt import extract_messages
        
        mapping = {
            "node-1": {
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["Valid message"]}
                }
            },
            "node-2": {
                "message": {
                    "author": {"role": "assistant"},
                    "content": {"parts": [""]}  # Empty
                }
            },
            "node-3": {
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["   "]}  # Whitespace only
                }
            }
        }
        
        messages = extract_messages(mapping)
        assert len(messages) == 1
        assert messages[0]["content"] == "Valid message"
    
    def test_extract_skips_nodes_without_message(self):
        """Test that nodes without message field are skipped."""
        from db.importers.chatgpt import extract_messages
        
        mapping = {
            "node-1": {
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["Message 1"]}
                }
            },
            "node-2": {
                # No message field
                "id": "node-2"
            },
            "node-3": {
                "message": {
                    "author": {"role": "assistant"},
                    "content": {"parts": ["Message 3"]}
                }
            }
        }
        
        messages = extract_messages(mapping)
        assert len(messages) == 2
    
    def test_extract_handles_missing_author_role(self):
        """Test handling of missing author role defaults gracefully."""
        from db.importers.chatgpt import extract_messages
        
        mapping = {
            "node-1": {
                "message": {
                    "author": {},  # No role
                    "content": {"parts": ["Test"]}
                }
            }
        }
        
        messages = extract_messages(mapping)
        # Should handle gracefully - might skip or use default
        # Based on implementation, this should be skipped since 'unknown' is not user/assistant
        assert len(messages) == 0
    
    def test_extract_orders_by_timestamp(self):
        """Test that messages are ordered by create_time."""
        from db.importers.chatgpt import extract_messages
        
        mapping = {
            "node-3": {
                "create_time": 1695000003,
                "message": {
                    "create_time": 1695000003,
                    "author": {"role": "user"},
                    "content": {"parts": ["Third"]}
                }
            },
            "node-1": {
                "create_time": 1695000001,
                "message": {
                    "create_time": 1695000001,
                    "author": {"role": "user"},
                    "content": {"parts": ["First"]}
                }
            },
            "node-2": {
                "create_time": 1695000002,
                "message": {
                    "create_time": 1695000002,
                    "author": {"role": "assistant"},
                    "content": {"parts": ["Second"]}
                }
            }
        }
        
        messages = extract_messages(mapping)
        assert len(messages) == 3
        assert messages[0]["content"] == "First"
        assert messages[1]["content"] == "Second"
        assert messages[2]["content"] == "Third"
    
    def test_extract_falls_back_to_node_timestamp(self):
        """Test fallback to node timestamp when message timestamp missing."""
        from db.importers.chatgpt import extract_messages
        
        node_time = 1695000000
        
        mapping = {
            "node-1": {
                "create_time": node_time,
                "message": {
                    # No create_time in message
                    "author": {"role": "user"},
                    "content": {"parts": ["Test"]}
                }
            }
        }
        
        messages = extract_messages(mapping)
        assert len(messages) == 1
        assert messages[0]["created_at"] == node_time
    
    def test_extract_empty_mapping(self):
        """Test extraction from empty mapping."""
        from db.importers.chatgpt import extract_messages
        
        messages = extract_messages({})
        assert messages == []
    
    def test_extract_mapping_with_none_message(self):
        """Test handling of None message values."""
        from db.importers.chatgpt import extract_messages
        
        mapping = {
            "node-1": {
                "message": None
            },
            "node-2": {
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["Valid"]}
                }
            }
        }
        
        messages = extract_messages(mapping)
        assert len(messages) == 1
    
    def test_extract_multipart_content_uses_first_part(self):
        """Test that only first part of multipart content is used."""
        from db.importers.chatgpt import extract_messages
        
        mapping = {
            "node-1": {
                "message": {
                    "author": {"role": "user"},
                    "content": {
                        "parts": [
                            "First part",
                            "Second part",
                            "Third part"
                        ]
                    }
                }
            }
        }
        
        messages = extract_messages(mapping)
        assert len(messages) == 1
        assert messages[0]["content"] == "First part"
    
    def test_extract_handles_missing_content_field(self):
        """Test handling of messages with missing content field."""
        from db.importers.chatgpt import extract_messages
        
        mapping = {
            "node-1": {
                "message": {
                    "author": {"role": "user"}
                    # No content field
                }
            },
            "node-2": {
                "message": {
                    "author": {"role": "assistant"},
                    "content": {"parts": ["Valid"]}
                }
            }
        }
        
        messages = extract_messages(mapping)
        assert len(messages) == 1
        assert messages[0]["content"] == "Valid"
    
    def test_extract_handles_missing_parts_field(self):
        """Test handling of content without parts field."""
        from db.importers.chatgpt import extract_messages
        
        mapping = {
            "node-1": {
                "message": {
                    "author": {"role": "user"},
                    "content": {}  # No parts field
                }
            }
        }
        
        messages = extract_messages(mapping)
        assert len(messages) == 0
    
    def test_extract_signature_matches_interface(self):
        """Test that extract_messages has correct signature."""
        from db.importers.chatgpt import extract_messages
        import inspect
        
        sig = inspect.signature(extract_messages)
        params = list(sig.parameters.keys())
        
        # Should have mapping as first parameter
        assert params[0] == "conversation_data"
        # Should accept **kwargs for extensibility
        assert "kwargs" in params or any(
            p for p in sig.parameters.values() if p.kind == inspect.Parameter.VAR_KEYWORD
        )

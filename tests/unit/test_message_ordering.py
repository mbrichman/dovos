"""
Tests for message ordering, especially with identical timestamps.

This ensures messages with the same created_at timestamp are ordered
deterministically using the sequence number from metadata.
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from dotenv import load_dotenv

load_dotenv()

from db.repositories.unit_of_work import get_unit_of_work
from db.models.models import Message, Conversation


class TestMessageOrdering:
    """Test message ordering with identical and different timestamps."""
    
    def test_messages_with_identical_timestamps_maintain_sequence_order(self):
        """
        When multiple messages have identical timestamps, they should be ordered
        by their sequence number from metadata, not randomly by UUID.
        """
        with get_unit_of_work() as uow:
            # Create a test conversation
            conversation = uow.conversations.create(title="Test Ordering - Identical TS")
            uow.session.flush()
            
            # Create timestamp that all messages will share
            shared_ts = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
            
            # Create messages with identical timestamps but different sequences
            messages_data = [
                {"role": "user", "content": "Message 0 - user", "sequence": 0},
                {"role": "assistant", "content": "Message 1 - assistant", "sequence": 1},
                {"role": "user", "content": "Message 2 - user", "sequence": 2},
                {"role": "assistant", "content": "Message 3 - assistant", "sequence": 3},
            ]
            
            created_messages = []
            for msg_data in messages_data:
                msg = uow.messages.create(
                    conversation_id=conversation.id,
                    role=msg_data["role"],
                    content=msg_data["content"],
                    created_at=shared_ts,
                    message_metadata={
                        "source": "test",
                        "sequence": msg_data["sequence"]
                    }
                )
                created_messages.append(msg)
            
            uow.session.flush()
            
            # Retrieve messages using get_by_conversation (which should sort by sequence)
            retrieved = uow.messages.get_by_conversation(conversation.id)
            
            # Verify order matches the sequence numbers, not random UUID order
            assert len(retrieved) == 4
            for i, msg in enumerate(retrieved):
                assert msg.content == f"Message {i} - {'user' if i % 2 == 0 else 'assistant'}"
                assert msg.role == ("user" if i % 2 == 0 else "assistant")
                # Verify sequence is in metadata
                assert msg.message_metadata["sequence"] == i
    
    def test_messages_with_different_timestamps_ordered_chronologically(self):
        """
        Messages with different timestamps should be ordered chronologically,
        regardless of insertion order.
        """
        with get_unit_of_work() as uow:
            # Create a test conversation
            conversation = uow.conversations.create(title="Test Ordering - Different TS")
            uow.session.flush()
            
            # Create messages with different timestamps in non-chronological order
            messages_data = [
                {"role": "user", "content": "Third message", "ts_offset": 30, "sequence": 2},
                {"role": "assistant", "content": "First message", "ts_offset": 0, "sequence": 0},
                {"role": "user", "content": "Second message", "ts_offset": 10, "sequence": 1},
                {"role": "assistant", "content": "Fourth message", "ts_offset": 60, "sequence": 3},
            ]
            
            base_ts = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
            created_messages = []
            
            for msg_data in messages_data:
                ts = datetime.fromtimestamp(
                    base_ts.timestamp() + msg_data["ts_offset"],
                    tz=timezone.utc
                )
                msg = uow.messages.create(
                    conversation_id=conversation.id,
                    role=msg_data["role"],
                    content=msg_data["content"],
                    created_at=ts,
                    message_metadata={
                        "source": "test",
                        "sequence": msg_data["sequence"]
                    }
                )
                created_messages.append(msg)
            
            uow.session.flush()
            
            # Retrieve messages - should be ordered chronologically
            retrieved = uow.messages.get_by_conversation(conversation.id)
            
            # Verify chronological order
            assert len(retrieved) == 4
            assert retrieved[0].content == "First message"
            assert retrieved[1].content == "Second message"
            assert retrieved[2].content == "Third message"
            assert retrieved[3].content == "Fourth message"
    
    def test_mixed_timestamps_and_sequences(self):
        """
        When some messages share timestamps and others don't,
        ordering should be: timestamp first, then sequence within same timestamp.
        """
        with get_unit_of_work() as uow:
            # Create a test conversation
            conversation = uow.conversations.create(title="Test Ordering - Mixed")
            uow.session.flush()
            
            ts1 = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
            ts2 = datetime(2025, 1, 15, 10, 30, 10, tzinfo=timezone.utc)
            
            # Group 1: ts1 with sequences 0, 1
            # Group 2: ts2 with sequences 0, 1
            messages_data = [
                # First timestamp group (created first)
                {"content": "TS1-Seq0", "ts": ts1, "sequence": 0},
                {"content": "TS1-Seq1", "ts": ts1, "sequence": 1},
                # Second timestamp group (created second)
                {"content": "TS2-Seq0", "ts": ts2, "sequence": 0},
                {"content": "TS2-Seq1", "ts": ts2, "sequence": 1},
            ]
            
            for i, msg_data in enumerate(messages_data):
                uow.messages.create(
                    conversation_id=conversation.id,
                    role="user" if i % 2 == 0 else "assistant",
                    content=msg_data["content"],
                    created_at=msg_data["ts"],
                    message_metadata={
                        "source": "test",
                        "sequence": msg_data["sequence"]
                    }
                )
            
            uow.session.flush()
            
            # Retrieve messages
            retrieved = uow.messages.get_by_conversation(conversation.id)
            
            # Verify order: all TS1 messages first, then all TS2 messages
            # Within each timestamp group, ordered by sequence
            assert len(retrieved) == 4
            assert retrieved[0].content == "TS1-Seq0"
            assert retrieved[1].content == "TS1-Seq1"
            assert retrieved[2].content == "TS2-Seq0"
            assert retrieved[3].content == "TS2-Seq1"
    
    def test_messages_without_sequence_fall_back_to_id(self):
        """
        Messages without sequence in metadata should still be ordered deterministically
        (by id as fallback).
        """
        with get_unit_of_work() as uow:
            # Create a test conversation
            conversation = uow.conversations.create(title="Test Ordering - No Sequence")
            uow.session.flush()
            
            # Create messages without sequence metadata
            shared_ts = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
            
            msg_ids = []
            for i in range(3):
                msg = uow.messages.create(
                    conversation_id=conversation.id,
                    role="user",
                    content=f"Message {i}",
                    created_at=shared_ts,
                    message_metadata={"source": "test"}  # No sequence
                )
                msg_ids.append(msg.id)
            
            uow.session.flush()
            
            # Retrieve messages - should be ordered by ID
            retrieved = uow.messages.get_by_conversation(conversation.id)
            
            # Verify they're in a deterministic order (by id)
            assert len(retrieved) == 3
            retrieved_ids = [m.id for m in retrieved]
            assert retrieved_ids == sorted(msg_ids)


class TestOpenWebUIMessageExtraction:
    """Test OpenWebUI message extraction and ordering."""
    
    def test_extract_openwebui_preserves_file_order(self):
        """
        When extracting OpenWebUI messages, the sequence numbers should match
        the insertion order from the JSON file.
        """
        from db.importers.registry import FORMAT_REGISTRY
        
        # Create test OpenWebUI messages dict (preserves insertion order in Python 3.7+)
        messages_dict = {
            "msg1": {
                "id": "msg1",
                "role": "user",
                "content": "First message",
                "timestamp": 1000,
                "parentId": None,
                "childrenIds": ["msg2"]
            },
            "msg2": {
                "id": "msg2",
                "role": "assistant",
                "content": "Second message",
                "timestamp": 1000,
                "parentId": "msg1",
                "childrenIds": ["msg3"]
            },
            "msg3": {
                "id": "msg3",
                "role": "user",
                "content": "Third message",
                "timestamp": 2000,
                "parentId": "msg2",
                "childrenIds": []
            },
        }
        
        # Use registry extractor
        extracted = FORMAT_REGISTRY['openwebui'](messages_dict)
        
        # Verify messages are extracted with sequences
        assert len(extracted) == 3
        assert extracted[0]["content"] == "First message"
        assert extracted[0]["sequence"] == 0
        assert extracted[1]["content"] == "Second message"
        assert extracted[1]["sequence"] == 1
        assert extracted[2]["content"] == "Third message"
        assert extracted[2]["sequence"] == 2
    
    def test_extract_openwebui_sorts_by_timestamp_then_sequence(self):
        """
        Extracted messages should be sorted by (timestamp, sequence)
        to handle identical timestamps correctly.
        """
        from db.importers.registry import FORMAT_REGISTRY
        
        # Create messages with identical timestamp
        messages_dict = {
            "msg3": {
                "id": "msg3",
                "role": "user",
                "content": "Third (inserted last, ts=100)",
                "timestamp": 100,
                "parentId": None
            },
            "msg1": {
                "id": "msg1",
                "role": "user",
                "content": "First (inserted first, ts=100)",
                "timestamp": 100,
                "parentId": None
            },
            "msg2": {
                "id": "msg2",
                "role": "assistant",
                "content": "Second (inserted middle, ts=100)",
                "timestamp": 100,
                "parentId": None
            },
        }
        
        # Use registry extractor
        extracted = FORMAT_REGISTRY['openwebui'](messages_dict)
        
        # Verify messages maintain insertion order despite identical timestamps
        assert len(extracted) == 3
        # The order should follow insertion order (sequence), not message ID
        assert extracted[0]["content"] == "Third (inserted last, ts=100)"
        assert extracted[0]["sequence"] == 0
        assert extracted[1]["content"] == "First (inserted first, ts=100)"
        assert extracted[1]["sequence"] == 1
        assert extracted[2]["content"] == "Second (inserted middle, ts=100)"
        assert extracted[2]["sequence"] == 2

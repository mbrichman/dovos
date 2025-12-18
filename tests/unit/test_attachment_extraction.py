"""
Unit tests for attachment extraction from LLM exports.

Tests the extraction and normalization of attachments from:
- Claude exports (attachments[] and files[])
- ChatGPT exports (multimodal_text, code, metadata.attachments)
- OpenWebUI exports (files[])
"""

import pytest
from typing import Dict, List


class TestClaudeAttachmentExtraction:
    """Test extraction of attachments from Claude export format."""
    
    def test_extract_text_attachment_with_content(self):
        """Test extraction of text file attachment with extracted_content."""
        # Arrange
        claude_message = {
            "uuid": "msg-123",
            "text": "Here's the file",
            "sender": "human",
            "attachments": [
                {
                    "file_name": "config.json",
                    "file_size": 1024,
                    "file_type": "application/json",
                    "extracted_content": '{"key": "value"}'
                }
            ],
            "files": []
        }
        
        # Act
        from controllers.postgres_controller import extract_claude_attachments
        attachments = extract_claude_attachments(claude_message)
        
        # Assert
        assert len(attachments) == 1
        assert attachments[0]["type"] == "file"
        assert attachments[0]["file_name"] == "config.json"
        assert attachments[0]["file_size"] == 1024
        assert attachments[0]["file_type"] == "application/json"
        assert attachments[0]["extracted_content"] == '{"key": "value"}'
        assert attachments[0]["available"] is True
    
    def test_extract_image_file_without_content(self):
        """Test extraction of image file reference (no extracted_content)."""
        # Arrange
        claude_message = {
            "uuid": "msg-456",
            "text": "Check this image",
            "sender": "human",
            "attachments": [],
            "files": [
                {
                    "file_name": "screenshot.png"
                }
            ]
        }
        
        # Act
        from controllers.postgres_controller import extract_claude_attachments
        attachments = extract_claude_attachments(claude_message)
        
        # Assert
        assert len(attachments) == 1
        assert attachments[0]["type"] == "image"
        assert attachments[0]["file_name"] == "screenshot.png"
        assert attachments[0]["available"] is False
        assert attachments[0].get("extracted_content") is None
    
    def test_extract_multiple_attachments(self):
        """Test extraction of multiple attachments in one message."""
        # Arrange
        claude_message = {
            "uuid": "msg-789",
            "text": "Files and images",
            "sender": "human",
            "attachments": [
                {
                    "file_name": "data.csv",
                    "file_size": 2048,
                    "file_type": "text/csv",
                    "extracted_content": "col1,col2\n1,2"
                }
            ],
            "files": [
                {
                    "file_name": "diagram.jpg"
                }
            ]
        }
        
        # Act
        from controllers.postgres_controller import extract_claude_attachments
        attachments = extract_claude_attachments(claude_message)
        
        # Assert
        assert len(attachments) == 2
        assert attachments[0]["file_name"] == "data.csv"
        assert attachments[0]["available"] is True
        assert attachments[1]["file_name"] == "diagram.jpg"
        assert attachments[1]["available"] is False
    
    def test_extract_no_attachments(self):
        """Test message with no attachments returns empty list."""
        # Arrange
        claude_message = {
            "uuid": "msg-000",
            "text": "Just text",
            "sender": "assistant",
            "attachments": [],
            "files": []
        }

        # Act
        from controllers.postgres_controller import extract_claude_attachments
        attachments = extract_claude_attachments(claude_message)

        # Assert
        assert attachments == []

    def test_extract_markdown_artifact(self):
        """Test extraction of markdown artifact from content array."""
        # Arrange
        claude_message = {
            "uuid": "msg-artifact-1",
            "text": "Here's the document",
            "sender": "assistant",
            "attachments": [],
            "files": [],
            "content": [
                {
                    "type": "text",
                    "text": "Here's the document"
                },
                {
                    "type": "tool_use",
                    "name": "artifacts",
                    "input": {
                        "id": "artifact-123",
                        "type": "text/markdown",
                        "title": "Project Overview",
                        "content": "# Project Overview\n\nThis is a test document.",
                        "language": None,
                        "md_citations": []
                    }
                }
            ]
        }

        # Act
        from controllers.postgres_controller import extract_claude_attachments
        attachments = extract_claude_attachments(claude_message)

        # Assert
        assert len(attachments) == 1
        assert attachments[0]["type"] == "artifact"
        assert attachments[0]["file_name"] == "Project_Overview.md"
        assert attachments[0]["file_type"] == "text/markdown"
        assert attachments[0]["extracted_content"] == "# Project Overview\n\nThis is a test document."
        assert attachments[0]["available"] is True
        assert attachments[0]["metadata"]["title"] == "Project Overview"
        assert attachments[0]["metadata"]["artifact_id"] == "artifact-123"

    def test_extract_python_artifact(self):
        """Test extraction of Python code artifact."""
        # Arrange
        claude_message = {
            "uuid": "msg-artifact-2",
            "text": "Here's the code",
            "sender": "assistant",
            "attachments": [],
            "files": [],
            "content": [
                {
                    "type": "tool_use",
                    "name": "artifacts",
                    "input": {
                        "id": "artifact-456",
                        "type": "application/python",
                        "title": "Hello World Script",
                        "content": "print('Hello, World!')",
                        "language": "python"
                    }
                }
            ]
        }

        # Act
        from controllers.postgres_controller import extract_claude_attachments
        attachments = extract_claude_attachments(claude_message)

        # Assert
        assert len(attachments) == 1
        assert attachments[0]["type"] == "artifact"
        assert attachments[0]["file_name"] == "Hello_World_Script.py"
        assert attachments[0]["metadata"]["language"] == "python"

    def test_extract_combined_files_and_artifacts(self):
        """Test extraction of both files and artifacts in same message."""
        # Arrange
        claude_message = {
            "uuid": "msg-combined",
            "text": "Image and document",
            "sender": "human",
            "attachments": [],
            "files": [
                {
                    "file_name": "screenshot.png"
                }
            ],
            "content": [
                {
                    "type": "tool_use",
                    "name": "artifacts",
                    "input": {
                        "id": "artifact-789",
                        "type": "text/html",
                        "title": "Report",
                        "content": "<html><body>Test</body></html>",
                        "language": None
                    }
                }
            ]
        }

        # Act
        from controllers.postgres_controller import extract_claude_attachments
        attachments = extract_claude_attachments(claude_message)

        # Assert
        assert len(attachments) == 2
        # First should be the file
        assert attachments[0]["type"] == "image"
        assert attachments[0]["file_name"] == "screenshot.png"
        # Second should be the artifact
        assert attachments[1]["type"] == "artifact"
        assert attachments[1]["file_name"] == "Report.html"

    def test_extract_thinking_block(self):
        """Test extraction of thinking block from content array."""
        # Arrange
        claude_message = {
            "uuid": "msg-thinking-1",
            "text": "Let me think about this",
            "sender": "assistant",
            "attachments": [],
            "files": [],
            "content": [
                {
                    "type": "text",
                    "text": "Let me think about this"
                },
                {
                    "type": "thinking",
                    "thinking": "I need to carefully consider the implications of this approach...",
                    "summaries": [
                        "Analyzing the problem",
                        "Considering alternatives"
                    ],
                    "cut_off": False
                }
            ]
        }

        # Act
        from controllers.postgres_controller import extract_claude_attachments
        attachments = extract_claude_attachments(claude_message)

        # Assert
        assert len(attachments) == 1
        assert attachments[0]["type"] == "thinking"
        assert attachments[0]["file_name"] == "Extended Reasoning"
        assert attachments[0]["file_type"] == "text/plain"
        assert attachments[0]["extracted_content"] == "I need to carefully consider the implications of this approach..."
        assert attachments[0]["available"] is True
        assert attachments[0]["metadata"]["summaries"] == ["Analyzing the problem", "Considering alternatives"]
        assert attachments[0]["metadata"]["cut_off"] is False

    def test_extract_voice_note(self):
        """Test extraction of voice note from content array."""
        # Arrange
        claude_message = {
            "uuid": "msg-voice-1",
            "text": "Here's what I recorded",
            "sender": "human",
            "attachments": [],
            "files": [],
            "content": [
                {
                    "type": "text",
                    "text": "Here's what I recorded"
                },
                {
                    "type": "voice_note",
                    "title": "Meeting Notes",
                    "text": "Discussion about project timeline\nKey deadlines identified\nAction items assigned"
                }
            ]
        }

        # Act
        from controllers.postgres_controller import extract_claude_attachments
        attachments = extract_claude_attachments(claude_message)

        # Assert
        assert len(attachments) == 1
        assert attachments[0]["type"] == "voice_note"
        assert attachments[0]["file_name"] == "Meeting Notes"
        assert attachments[0]["file_type"] == "audio/transcription"
        assert "Discussion about project timeline" in attachments[0]["extracted_content"]
        assert attachments[0]["available"] is True
        assert attachments[0]["metadata"]["title"] == "Meeting Notes"

    def test_extract_multiple_content_types(self):
        """Test extraction of artifact, thinking block, and voice note together."""
        # Arrange
        claude_message = {
            "uuid": "msg-multi",
            "text": "Here's everything",
            "sender": "assistant",
            "attachments": [],
            "files": [],
            "content": [
                {
                    "type": "voice_note",
                    "title": "User Request",
                    "text": "User wants a summary"
                },
                {
                    "type": "thinking",
                    "thinking": "Need to analyze the data first",
                    "summaries": [],
                    "cut_off": False
                },
                {
                    "type": "tool_use",
                    "name": "artifacts",
                    "input": {
                        "id": "art-1",
                        "type": "text/markdown",
                        "title": "Summary",
                        "content": "# Summary\n\nHere's the data analysis"
                    }
                }
            ]
        }

        # Act
        from controllers.postgres_controller import extract_claude_attachments
        attachments = extract_claude_attachments(claude_message)

        # Assert
        assert len(attachments) == 3
        assert attachments[0]["type"] == "voice_note"
        assert attachments[1]["type"] == "thinking"
        assert attachments[2]["type"] == "artifact"


class TestChatGPTAttachmentExtraction:
    """Test extraction of attachments from ChatGPT export format."""
    
    def test_extract_code_content_type(self):
        """Test extraction of code content type as attachment."""
        # Arrange
        chatgpt_message = {
            "id": "msg-abc",
            "content": {
                "content_type": "code",
                "language": "python",
                "text": "def hello():\n    print('world')"
            },
            "metadata": {}
        }
        
        # Act
        from controllers.postgres_controller import extract_chatgpt_attachments
        attachments = extract_chatgpt_attachments(chatgpt_message)
        
        # Assert
        assert len(attachments) == 1
        assert attachments[0]["type"] == "code"
        assert attachments[0]["language"] == "python"
        assert attachments[0]["extracted_content"] == "def hello():\n    print('world')"
        assert attachments[0]["available"] is True
    
    def test_extract_multimodal_image(self):
        """Test extraction of image from multimodal_text content."""
        # Arrange
        chatgpt_message = {
            "id": "msg-def",
            "content": {
                "content_type": "multimodal_text",
                "parts": [
                    {
                        "content_type": "image_asset_pointer",
                        "asset_pointer": "file-service://file-123",
                        "size_bytes": 401441,
                        "width": 1134,
                        "height": 1003
                    }
                ]
            },
            "metadata": {
                "attachments": [
                    {
                        "name": "screenshot.png",
                        "size": 401441,
                        "mime_type": "image/png",
                        "id": "file-123"
                    }
                ]
            }
        }
        
        # Act
        from controllers.postgres_controller import extract_chatgpt_attachments
        attachments = extract_chatgpt_attachments(chatgpt_message)
        
        # Assert
        assert len(attachments) == 1
        assert attachments[0]["type"] == "image"
        assert attachments[0]["file_name"] == "screenshot.png"
        assert attachments[0]["file_size"] == 401441
        assert attachments[0]["file_type"] == "image/png"
        assert attachments[0]["available"] is False
        assert attachments[0]["asset_pointer"] == "file-service://file-123"
    
    def test_extract_reasoning_thoughts(self):
        """Test extraction of o1/o3 reasoning as attachment."""
        # Arrange
        chatgpt_message = {
            "id": "msg-ghi",
            "content": {
                "content_type": "thoughts",
                "thoughts": [
                    {
                        "summary": "Thinking about the problem",
                        "content": "Let me analyze this step by step..."
                    }
                ]
            },
            "metadata": {}
        }
        
        # Act
        from controllers.postgres_controller import extract_chatgpt_attachments
        attachments = extract_chatgpt_attachments(chatgpt_message)
        
        # Assert
        assert len(attachments) == 1
        assert attachments[0]["type"] == "reasoning"
        assert attachments[0]["reasoning_type"] == "thoughts"
        assert attachments[0]["available"] is True
    
    def test_extract_audio_transcription(self):
        """Test extraction of audio transcription from multimodal content."""
        # Arrange
        chatgpt_message = {
            "id": "msg-jkl",
            "content": {
                "content_type": "multimodal_text",
                "parts": [
                    {
                        "content_type": "audio_transcription",
                        "text": "I need help with Spanish translation",
                        "direction": "in"
                    }
                ]
            },
            "metadata": {}
        }
        
        # Act
        from controllers.postgres_controller import extract_chatgpt_attachments
        attachments = extract_chatgpt_attachments(chatgpt_message)
        
        # Assert
        assert len(attachments) == 1
        assert attachments[0]["type"] == "audio"
        assert attachments[0]["transcription"] == "I need help with Spanish translation"
        assert attachments[0]["available"] is True
    
    def test_extract_content_references(self):
        """Test extraction of web citations from content_references."""
        # Arrange
        chatgpt_message = {
            "id": "msg-mno",
            "content": {
                "content_type": "text",
                "parts": ["Here's what I found"]
            },
            "metadata": {
                "content_references": [
                    {
                        "type": "grouped_webpages",
                        "items": [
                            {
                                "title": "Example Article",
                                "url": "https://example.com/article",
                                "snippet": "This is an example"
                            }
                        ]
                    }
                ]
            }
        }
        
        # Act
        from controllers.postgres_controller import extract_chatgpt_attachments
        attachments = extract_chatgpt_attachments(chatgpt_message)
        
        # Assert
        assert len(attachments) == 1
        assert attachments[0]["type"] == "citation"
        assert attachments[0]["citations"][0]["title"] == "Example Article"
        assert attachments[0]["citations"][0]["url"] == "https://example.com/article"
        assert attachments[0]["available"] is True


class TestAttachmentNormalization:
    """Test normalization of attachments to common format."""
    
    def test_normalize_preserves_required_fields(self):
        """Test that normalization preserves all required fields."""
        # Arrange
        raw_attachment = {
            "type": "file",
            "file_name": "test.txt",
            "file_size": 512,
            "file_type": "text/plain",
            "extracted_content": "Hello",
            "available": True
        }
        
        # Act
        from controllers.postgres_controller import normalize_attachment
        normalized = normalize_attachment(raw_attachment)
        
        # Assert
        assert normalized["type"] == "file"
        assert normalized["file_name"] == "test.txt"
        assert normalized["available"] is True
    
    def test_normalize_adds_default_values(self):
        """Test that normalization adds default values for missing fields."""
        # Arrange
        raw_attachment = {
            "type": "image",
            "file_name": "photo.jpg"
        }
        
        # Act
        from controllers.postgres_controller import normalize_attachment
        normalized = normalize_attachment(raw_attachment)
        
        # Assert
        assert "available" in normalized
        assert "file_size" in normalized
        assert "metadata" in normalized


class TestAttachmentIntegration:
    """Integration tests for attachment handling in full import flow."""
    
    @pytest.mark.integration
    def test_import_claude_conversation_preserves_attachments(self, postgres_controller):
        """Test that Claude import preserves attachment metadata."""
        # Arrange
        claude_export = [{
            "uuid": "test-conv-attach-integration",
            "name": "Test Conversation with Attachment",
            "created_at": "2024-01-15T10:00:00.000000Z",
            "updated_at": "2024-01-15T10:05:00.000000Z",
            "chat_messages": [
                {
                    "uuid": "msg-attach-1",
                    "text": "Here's a Python file",
                    "sender": "human",
                    "created_at": "2024-01-15T10:00:00.000000Z",
                    "attachments": [
                        {
                            "file_name": "code.py",
                            "file_size": 256,
                            "file_type": "text/x-python",
                            "extracted_content": "print('hello')"
                        }
                    ],
                    "files": [
                        {
                            "file_name": "image.png",
                            "file_size": 1024,
                            "file_type": "image/png"
                        }
                    ]
                },
                {
                    "uuid": "msg-attach-2",
                    "text": "Thanks!",
                    "sender": "assistant",
                    "created_at": "2024-01-15T10:01:00.000000Z"
                }
            ]
        }]
        
        # Act
        from db.repositories.unit_of_work import get_unit_of_work
        result = postgres_controller._import_conversations_json(claude_export)
        
        # Assert import succeeded
        assert "Success" in result
        
        # Verify attachments were stored in database
        with get_unit_of_work() as uow:
            # Find the conversation
            conversations = uow.conversations.get_all()
            test_conv = next((c for c in conversations if c.title == "Test Conversation with Attachment"), None)
            assert test_conv is not None, "Conversation not found in database"
            
            # Find the message with attachments
            messages = uow.messages.get_by_conversation(test_conv.id)
            user_msg = next((m for m in messages if m.role == "user"), None)
            assert user_msg is not None, "User message not found"
            
            # Verify attachments are in metadata
            assert "attachments" in user_msg.metadata
            attachments = user_msg.metadata["attachments"]
            assert len(attachments) == 2, f"Expected 2 attachments, got {len(attachments)}"
            
            # Verify file attachment
            file_att = next((a for a in attachments if a["type"] == "file"), None)
            assert file_att is not None, "File attachment not found"
            assert file_att["file_name"] == "code.py"
            assert file_att["extracted_content"] == "print('hello')"
            assert file_att["available"] is True
            
            # Verify image placeholder
            image_att = next((a for a in attachments if a["type"] == "image"), None)
            assert image_att is not None, "Image attachment not found"
            assert image_att["file_name"] == "image.png"
            assert image_att["available"] is False
    
    @pytest.mark.integration
    def test_import_chatgpt_conversation_preserves_reasoning_attachments(self, postgres_controller):
        """Test that ChatGPT import preserves reasoning traces as attachments."""
        # Arrange
        chatgpt_export = [{
            "title": "Test ChatGPT Reasoning",
            "create_time": 1705320000.0,
            "update_time": 1705320300.0,
            "mapping": {
                "node1": {
                    "id": "node1",
                    "message": {
                        "id": "msg1",
                        "author": {"role": "user"},
                        "create_time": 1705320000.0,
                        "content": {
                            "content_type": "text",
                            "parts": ["Solve this problem"]
                        }
                    },
                    "parent": None,
                    "children": ["node2"]
                },
                "node2": {
                    "id": "node2",
                    "message": {
                        "id": "msg2",
                        "author": {"role": "assistant"},
                        "create_time": 1705320100.0,
                        "content": {
                            "content_type": "thoughts",
                            "thoughts": [
                                {"thought": "Let me think about this"},
                                {"thought": "I need to consider X and Y"}
                            ]
                        },
                        "metadata": {}
                    },
                    "parent": "node1",
                    "children": ["node3"]
                },
                "node3": {
                    "id": "node3",
                    "message": {
                        "id": "msg3",
                        "author": {"role": "assistant"},
                        "create_time": 1705320200.0,
                        "content": {
                            "content_type": "reasoning_recap",
                            "content": "After analyzing the problem, here's my approach..."
                        },
                        "metadata": {}
                    },
                    "parent": "node2",
                    "children": []
                }
            }
        }]
        
        # Act
        from db.repositories.unit_of_work import get_unit_of_work
        result = postgres_controller._import_conversations_json(chatgpt_export)
        
        # Assert import succeeded
        assert "Success" in result
        
        # Verify reasoning attachments were stored
        with get_unit_of_work() as uow:
            # Find the conversation
            conversations = uow.conversations.get_all()
            test_conv = next((c for c in conversations if c.title == "Test ChatGPT Reasoning"), None)
            assert test_conv is not None, "Conversation not found in database"
            
            # Get all messages
            messages = uow.messages.get_by_conversation(test_conv.id)
            assert len(messages) == 3, f"Expected 3 messages, got {len(messages)}"
            
            # Find messages with reasoning attachments
            reasoning_messages = [m for m in messages if m.metadata.get("attachments")]
            assert len(reasoning_messages) == 2, f"Expected 2 messages with attachments, got {len(reasoning_messages)}"
            
            # Verify thoughts attachment
            thoughts_msg = next((m for m in reasoning_messages if m.content == "[Reasoning process]"), None)
            assert thoughts_msg is not None, "Thoughts message not found"
            thoughts_att = thoughts_msg.metadata["attachments"][0]
            assert thoughts_att["type"] == "reasoning"
            assert thoughts_att["reasoning_type"] == "thoughts"
            assert len(thoughts_att["thoughts"]) == 2
            assert thoughts_att["available"] is True
            
            # Verify reasoning recap attachment
            recap_msg = next((m for m in reasoning_messages if m.content == "[Reasoning summary]"), None)
            assert recap_msg is not None, "Reasoning recap message not found"
            recap_att = recap_msg.metadata["attachments"][0]
            assert recap_att["type"] == "reasoning"
            assert recap_att["reasoning_type"] == "recap"
            assert "After analyzing" in recap_att["recap_content"]
            assert recap_att["available"] is True

"""
Unit tests for DOCX message extraction.

Tests the extraction of messages from DOCX (Word document) format.
Since DOCX parsing is complex and delegated to utils/docx_parser,
we focus on testing the adapter/wrapper interface.
"""

import pytest
import tempfile
import os
from typing import Dict, List, Any
from datetime import datetime


class TestDocxExtractor:
    """Test suite for DOCX message extraction."""
    
    def test_extract_messages_returns_expected_format(self):
        """Test that extracted messages have the required fields."""
        from db.importers.docx import extract_messages_from_file
        from unittest.mock import patch, MagicMock
        
        # Mock the docx_parser output
        mock_messages = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there'}
        ]
        mock_timestamps = ['2024-01-01T10:00:00', '2024-01-01T10:01:00']
        mock_title = 'Test Conversation'
        
        with patch('db.importers.docx.parse_docx_file') as mock_parse:
            mock_parse.return_value = (mock_messages, mock_timestamps, mock_title)
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                messages, title, timestamps = extract_messages_from_file(tmp_path, 'test.docx')
                
                assert len(messages) == 2
                assert messages[0]['role'] == 'user'
                assert messages[0]['content'] == 'Hello'
                assert messages[1]['role'] == 'assistant'
                assert messages[1]['content'] == 'Hi there'
                assert title == 'Test Conversation'
                assert timestamps == mock_timestamps
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
    
    def test_extract_empty_messages(self):
        """Test handling of empty messages list."""
        from db.importers.docx import extract_messages_from_file
        from unittest.mock import patch
        
        with patch('db.importers.docx.parse_docx_file') as mock_parse:
            mock_parse.return_value = ([], [], 'Empty Document')
            
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                messages, title, timestamps = extract_messages_from_file(tmp_path, 'empty.docx')
                
                assert len(messages) == 0
                assert title == 'Empty Document'
                assert timestamps == []
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
    
    def test_extract_preserves_timestamps(self):
        """Test that timestamps are preserved from DOCX."""
        from db.importers.docx import extract_messages_from_file
        from unittest.mock import patch
        
        ts1 = '2024-01-01T10:00:00'
        ts2 = '2024-01-01T10:05:00'
        
        mock_messages = [
            {'role': 'user', 'content': 'Message 1'},
            {'role': 'assistant', 'content': 'Message 2'}
        ]
        mock_timestamps = [ts1, ts2]
        
        with patch('db.importers.docx.parse_docx_file') as mock_parse:
            mock_parse.return_value = (mock_messages, mock_timestamps, 'Test')
            
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                messages, title, timestamps = extract_messages_from_file(tmp_path, 'test.docx')
                
                assert timestamps == mock_timestamps
                assert len(timestamps) == 2
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
    
    def test_extract_handles_missing_timestamps(self):
        """Test handling when timestamps are missing."""
        from db.importers.docx import extract_messages_from_file
        from unittest.mock import patch
        
        mock_messages = [
            {'role': 'user', 'content': 'Message 1'},
            {'role': 'assistant', 'content': 'Message 2'}
        ]
        
        with patch('db.importers.docx.parse_docx_file') as mock_parse:
            mock_parse.return_value = (mock_messages, [], 'No Timestamps')
            
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                messages, title, timestamps = extract_messages_from_file(tmp_path, 'test.docx')
                
                assert len(messages) == 2
                assert timestamps == []
                assert title == 'No Timestamps'
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
    
    def test_extract_handles_various_roles(self):
        """Test that various role markers are preserved."""
        from db.importers.docx import extract_messages_from_file
        from unittest.mock import patch
        
        mock_messages = [
            {'role': 'user', 'content': 'You: Hello'},
            {'role': 'assistant', 'content': 'ChatGPT: Hi'},
            {'role': 'user', 'content': 'User: Another message'},
            {'role': 'assistant', 'content': 'Assistant: Response'}
        ]
        
        with patch('db.importers.docx.parse_docx_file') as mock_parse:
            mock_parse.return_value = (mock_messages, [], 'Multi-role')
            
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                messages, title, timestamps = extract_messages_from_file(tmp_path, 'test.docx')
                
                # Verify all messages extracted with their roles
                assert len(messages) == 4
                assert messages[0]['role'] == 'user'
                assert messages[1]['role'] == 'assistant'
                assert messages[2]['role'] == 'user'
                assert messages[3]['role'] == 'assistant'
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
    
    def test_extract_filename_passed_to_parser(self):
        """Test that filename is passed to the parser."""
        from db.importers.docx import extract_messages_from_file
        from unittest.mock import patch, call
        
        with patch('db.importers.docx.parse_docx_file') as mock_parse:
            mock_parse.return_value = ([], [], 'Title')
            
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                extract_messages_from_file(tmp_path, 'my_conversation.docx')
                
                # Verify parser was called with the filename for title extraction
                mock_parse.assert_called_once_with(tmp_path, original_filename='my_conversation.docx')
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
    
    def test_extract_signature_matches_interface(self):
        """Test that extract_messages_from_file has correct signature."""
        from db.importers.docx import extract_messages_from_file
        import inspect
        
        sig = inspect.signature(extract_messages_from_file)
        params = list(sig.parameters.keys())
        
        # Should have file_path and filename as parameters
        assert 'file_path' in params
        assert 'filename' in params
        # Should accept **kwargs for extensibility
        assert any(
            p for p in sig.parameters.values() if p.kind == inspect.Parameter.VAR_KEYWORD
        )
    
    def test_extract_with_long_conversation(self):
        """Test extraction with a longer conversation."""
        from db.importers.docx import extract_messages_from_file
        from unittest.mock import patch
        
        # Create a long conversation
        mock_messages = [
            {'role': 'user' if i % 2 == 0 else 'assistant', 'content': f'Message {i}'}
            for i in range(20)
        ]
        mock_timestamps = [f'2024-01-01T10:{i:02d}:00' for i in range(20)]
        
        with patch('db.importers.docx.parse_docx_file') as mock_parse:
            mock_parse.return_value = (mock_messages, mock_timestamps, 'Long Chat')
            
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                messages, title, timestamps = extract_messages_from_file(tmp_path, 'test.docx')
                
                assert len(messages) == 20
                assert len(timestamps) == 20
                assert title == 'Long Chat'
                
                # Verify alternation
                for i, msg in enumerate(messages):
                    expected_role = 'user' if i % 2 == 0 else 'assistant'
                    assert msg['role'] == expected_role
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

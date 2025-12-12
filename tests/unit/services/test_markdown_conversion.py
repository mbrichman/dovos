"""
Tests for markdown conversion in ConversationFormatService.

Verifies that language markers in fenced code blocks are preserved
for client-side syntax highlighting with Prism.js.
"""

import pytest
from db.services.conversation_format_service import ConversationFormatService


class MockMessage:
    """Mock message object for testing"""
    def __init__(self, role, content, created_at=None, message_metadata=None):
        self.role = role
        self.content = content
        self.created_at = created_at
        self.message_metadata = message_metadata or {}


class TestMarkdownConversion:
    """Test markdown to HTML conversion"""
    
    @pytest.fixture
    def format_service(self):
        """Fixture providing format service instance"""
        return ConversationFormatService()
    
    def test_preserves_python_language_marker(self, format_service):
        """Test that Python code blocks get language-python class"""
        mock_msg = MockMessage(
            role='assistant',
            content='Here is Python code:\n\n```python\ndef hello():\n    print("world")\n```'
        )
        
        formatted = format_service.format_db_messages_for_view([mock_msg])
        
        assert len(formatted) == 1
        html = formatted[0]['content']
        
        # Should have language-python class for Prism
        assert 'language-python' in html
        assert '<code class="language-python">' in html
        
    def test_preserves_ruby_language_marker(self, format_service):
        """Test that Ruby code blocks get language-ruby class"""
        mock_msg = MockMessage(
            role='assistant',
            content='Here is Ruby code:\n\n```ruby\nclass User\n  def hello\n    puts "world"\n  end\nend\n```'
        )
        
        formatted = format_service.format_db_messages_for_view([mock_msg])
        
        assert len(formatted) == 1
        html = formatted[0]['content']
        
        # Should have language-ruby class for Prism
        assert 'language-ruby' in html
        assert '<code class="language-ruby">' in html
        
    def test_preserves_javascript_language_marker(self, format_service):
        """Test that JavaScript code blocks get language-javascript class"""
        mock_msg = MockMessage(
            role='assistant',
            content='Here is JS:\n\n```javascript\nfunction hello() {\n  console.log("world");\n}\n```'
        )
        
        formatted = format_service.format_db_messages_for_view([mock_msg])
        
        assert len(formatted) == 1
        html = formatted[0]['content']
        
        assert 'language-javascript' in html
        assert '<code class="language-javascript">' in html
        
    def test_unmarked_code_blocks_have_no_language_class(self, format_service):
        """Test that code blocks without language markers have no language class"""
        mock_msg = MockMessage(
            role='assistant',
            content='Code without language:\n\n```\nsome code here\n```'
        )
        
        formatted = format_service.format_db_messages_for_view([mock_msg])
        
        assert len(formatted) == 1
        html = formatted[0]['content']
        
        # Should have <code> but no language- class
        assert '<code>' in html
        assert 'language-' not in html
        
    def test_no_codehilite_spans_in_output(self, format_service):
        """Test that codehilite extension is NOT being used"""
        mock_msg = MockMessage(
            role='assistant',
            content='```python\nclass Foo:\n    pass\n```'
        )
        
        formatted = format_service.format_db_messages_for_view([mock_msg])
        html = formatted[0]['content']
        
        # Should NOT have codehilite's span-based highlighting
        assert '<span class="k">' not in html  # codehilite uses this for keywords
        assert '<span class="nc">' not in html  # codehilite uses this for class names
        assert 'codehilite' not in html
        
    def test_multiple_language_blocks_in_one_message(self, format_service):
        """Test multiple code blocks with different languages"""
        mock_msg = MockMessage(
            role='assistant',
            content='''Here's Python:

```python
print("hello")
```

And here's Ruby:

```ruby
puts "hello"
```
'''
        )
        
        formatted = format_service.format_db_messages_for_view([mock_msg])
        html = formatted[0]['content']
        
        # Should have both language markers
        assert 'language-python' in html
        assert 'language-ruby' in html
        
    def test_preserves_attachments_in_metadata(self, format_service):
        """Test that attachments are preserved during formatting"""
        mock_msg = MockMessage(
            role='assistant',
            content='Here is code',
            message_metadata={
                'attachments': [
                    {'type': 'image', 'file_name': 'test.png', 'available': True}
                ]
            }
        )
        
        formatted = format_service.format_db_messages_for_view([mock_msg])
        
        assert 'attachments' in formatted[0]
        assert len(formatted[0]['attachments']) == 1
        assert formatted[0]['attachments'][0]['file_name'] == 'test.png'

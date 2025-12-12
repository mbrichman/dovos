"""
Claude format message extractor.

Extracts messages from Claude's chat_messages list format.
Claude stores conversations as a list of messages with sender and text fields.
"""

from typing import Dict, List, Any, Optional


def extract_messages(conversation_data: Optional[List], **kwargs) -> List[Dict]:
    """
    Extract messages from Claude format conversation data.
    
    Args:
        conversation_data: Claude conversation with list of chat_messages
                          Each message has: sender, text, created_at (optional), attachments, files
        **kwargs: Additional options (for extensibility)
        
    Returns:
        List of message dicts with keys:
        - role: 'user' or 'assistant' (human sender -> user, others -> assistant)
        - content: message text
        - created_at: ISO timestamp string (optional)
        - attachments: List of attachment dicts (if present)
    """
    # Handle None or non-list input
    if conversation_data is None or not isinstance(conversation_data, list):
        return []
    
    messages = []
    
    for msg_data in conversation_data:
        # Skip None entries
        if msg_data is None or not isinstance(msg_data, dict):
            continue
        
        # Extract sender - required field
        sender = msg_data.get('sender')
        if sender is None:
            continue
        
        # Extract text content - required field
        text = msg_data.get('text', '')
        
        # Skip empty or whitespace-only messages
        if not text or not text.strip():
            continue
        
        # Map sender to role: human -> user, everything else -> assistant
        role = 'user' if sender == 'human' else 'assistant'
        
        # Build message dict with required fields
        msg_dict = {
            'role': role,
            'content': text
        }
        
        # Preserve timestamp if available (ISO format string)
        created_at = msg_data.get('created_at')
        if created_at:
            msg_dict['created_at'] = created_at
        
        # Extract attachments if present
        from controllers.postgres_controller import extract_claude_attachments
        attachments = extract_claude_attachments(msg_data)
        if attachments:
            msg_dict['attachments'] = attachments
        
        messages.append(msg_dict)
    
    return messages

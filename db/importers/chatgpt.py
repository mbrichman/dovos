"""
ChatGPT format message extractor.

Extracts messages from ChatGPT's node-based mapping structure.
ChatGPT stores conversations as a dict of nodes keyed by node ID,
with parent-child relationships and message content.
"""

from typing import Dict, List, Any


def extract_messages(conversation_data: Dict, **kwargs) -> List[Dict]:
    """
    Extract messages from ChatGPT format conversation data.
    
    Args:
        conversation_data: ChatGPT conversation with 'mapping' field
                          mapping is a dict of node_id -> node_data
        **kwargs: Additional options (for extensibility)
        
    Returns:
        List of message dicts with keys:
        - role: 'user' or 'assistant'
        - content: message text
        - created_at: Unix epoch timestamp (optional)
    """
    mapping = conversation_data if isinstance(conversation_data, dict) else {}
    
    if not mapping:
        return []
    
    messages = []
    
    # Sort nodes by create_time to maintain chronological order
    # Fallback to node ID if no timestamp
    ordered_nodes = sorted(
        mapping.items(),
        key=lambda x: x[1].get('create_time', 0)
    )
    
    for node_id, node in ordered_nodes:
        message = node.get('message')
        if not message:
            continue
        
        # Extract role from author
        author = message.get('author', {})
        role = author.get('role', 'unknown')
        
        # Only keep user and assistant messages
        # Skip system, tool, function, and other roles
        if role not in ('user', 'assistant'):
            continue
        
        # Extract attachments first to check if this is a reasoning-only message
        from controllers.postgres_controller import extract_chatgpt_attachments
        attachments = extract_chatgpt_attachments(message)
        
        # Extract content from parts
        content_data = message.get('content', {})
        parts = content_data.get('parts', [])
        
        # Use first part if available
        content = None
        if parts and isinstance(parts, list) and isinstance(parts[0], str):
            content = parts[0]
        elif attachments:
            # Message has attachments but no text content (e.g., reasoning traces)
            # Use a placeholder so the attachments can be displayed
            content_type = content_data.get('content_type', '')
            if content_type == 'thoughts':
                content = '[Reasoning process]'
            elif content_type == 'reasoning_recap':
                content = '[Reasoning summary]'
            else:
                content = '[Attachment]'
        
        # Skip if no content and no attachments
        if not content or not content.strip():
            continue
        
        # Build message dict with required fields
        msg_dict = {
            'role': role,
            'content': content
        }
        
        # Preserve timestamp if available
        # Try message timestamp first, then node timestamp
        created_at = message.get('create_time') or node.get('create_time')
        if created_at is not None:
            msg_dict['created_at'] = created_at
        
        # Include attachments if present
        if attachments:
            msg_dict['attachments'] = attachments
        
        messages.append(msg_dict)
    
    return messages

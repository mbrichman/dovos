"""
Format detection and extractor registry.

Provides format detection for different chat export formats and a registry
system for pluggable format extractors.
"""

from typing import Tuple, Dict, List, Any


def detect_format(data: Dict[str, Any] | List[Dict]) -> Tuple[List[Dict], str]:
    """
    Detect the format of imported chat data.
    
    Args:
        data: Either a dict with 'conversations' key or a list of conversations
        
    Returns:
        Tuple of (conversations_list, format_type_string)
        Format types: 'ChatGPT', 'Claude', 'OpenWebUI', 'Unknown'
    
    Format signatures:
    - ChatGPT: has 'title', 'mapping', and 'create_time'
    - Claude: has 'uuid', 'name', and 'chat_messages'
    - OpenWebUI: has 'chat.history.messages' as dict with id/role/content/timestamp
    """
    # Ensure data is normalized to a list of conversations
    if isinstance(data, dict):
        conversations = data.get("conversations", [])
    else:
        conversations = data if isinstance(data, list) else []
    
    if not conversations:
        return [], "Unknown"
    
    # Check first conversation to determine format
    first_conv = conversations[0] if conversations else {}
    
    # Check for OpenWebUI format first (most specific structure)
    chat = first_conv.get("chat", {}) if isinstance(first_conv, dict) else {}
    hist = chat.get("history", {}) if isinstance(chat, dict) else {}
    msgs = hist.get("messages")
    
    if isinstance(msgs, dict) and msgs:
        # Validate that at least one message has required OpenWebUI fields
        try:
            any_msg = next(iter(msgs.values()))
            if isinstance(any_msg, dict) and "role" in any_msg and "content" in any_msg and "timestamp" in any_msg:
                return conversations, "OpenWebUI"
        except (StopIteration, TypeError):
            pass
    
    # Check for Claude format
    # Claude has uuid, name (can be empty string), and chat_messages
    if (first_conv.get("uuid") and 
        first_conv.get("name") is not None and  # name can be empty string
        "chat_messages" in first_conv):
        return conversations, "Claude"
    
    # Check for ChatGPT format
    # ChatGPT has title (can be None), mapping, and create_time
    elif (first_conv.get("title") is not None and 
          "mapping" in first_conv and
          first_conv.get("create_time")):
        return conversations, "ChatGPT"
    
    return conversations, "Unknown"


# Format registry - maps format names to extractor functions
# This will be populated by individual extractor modules
from db.importers.chatgpt import extract_messages as extract_chatgpt_messages
from db.importers.claude import extract_messages as extract_claude_messages
from db.importers.openwebui import extract_messages as extract_openwebui_messages
from db.importers.docx import extract_messages_from_file as extract_docx_messages

FORMAT_REGISTRY: Dict[str, Any] = {
    'chatgpt': extract_chatgpt_messages,
    'claude': extract_claude_messages,
    'openwebui': extract_openwebui_messages,
    'docx': extract_docx_messages,
}

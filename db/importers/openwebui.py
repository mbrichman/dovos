"""
OpenWebUI format message extractor.

Extracts and flattens messages from OpenWebUI's tree-structured dict format.
OpenWebUI stores messages as a dict keyed by message ID with parent-child relationships.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _epoch_to_dt(ts: Any) -> datetime:
    """
    Convert epoch timestamp to datetime, handling various formats.
    
    Supports nanoseconds (> 10^12), milliseconds (> 10^11), and seconds.
    Returns current UTC time if conversion fails.
    """
    try:
        ts = int(ts)
        # Detect nanoseconds (> 10^12)
        if ts > 10**12:
            ts = ts / 10**9
        # Detect milliseconds (> 10^11)
        elif ts > 10**11:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        logger.warning(f"Failed to convert timestamp {ts}, using current time")
        return datetime.now(tz=timezone.utc)


def extract_messages(conversation_data: Optional[Dict], **kwargs) -> List[Dict]:
    """
    Extract and flatten messages from OpenWebUI format conversation data.
    
    Args:
        conversation_data: Dict with message_id -> message_data mapping
                          Each message has: id, role, content, timestamp, parentId, etc.
        **kwargs: Additional options (for extensibility)
        
    Returns:
        List of message dicts with keys:
        - role: 'user' or 'assistant' (normalized to lowercase, defaults to 'user')
        - content: message text (handles string and dict content)
        - created_at: datetime object in UTC
        - sequence: insertion order for deterministic ordering
        - model: model name if present (optional)
    """
    if conversation_data is None or not isinstance(conversation_data, dict):
        return []
    
    if not conversation_data:
        return []
    
    # First pass: collect all nodes with their metadata
    nodes = []
    for sequence, (mid, m) in enumerate(conversation_data.items()):
        # Skip None or non-dict entries
        if m is None or not isinstance(m, dict):
            continue
        
        # Extract and normalize role (default to 'user')
        role = (m.get("role") or "").lower().strip() or "user"
        
        # Extract content (handle both string and dict formats)
        content = m.get("content")
        if isinstance(content, dict):
            # Try common dict keys for content
            content = content.get("text") or content.get("content") or json.dumps(content, ensure_ascii=False)
        elif content is None:
            content = ""
        
        # Convert to string if needed
        if not isinstance(content, str):
            content = str(content)
        
        # Determine if the message contains file attachments
        has_files = bool(m.get("files")) and isinstance(m.get("files"), list) and len(m.get("files")) > 0
        
        # Skip empty or whitespace-only messages UNLESS they have attachments
        if (not content or not content.strip()) and not has_files:
            continue
        
        # Use a placeholder content for attachment-only messages so they are persisted
        if (not content or not content.strip()) and has_files:
            content = "[Attachment]"
        
        # Extract timestamp (try timestamp field first, then created_at)
        ts = m.get("timestamp") or m.get("created_at")
        created_at = _epoch_to_dt(ts) if ts is not None else datetime.now(tz=timezone.utc)
        
        # Extract model information
        # Assistant messages have 'model', user messages have 'models' list
        model = m.get("model")
        if not model:
            models = m.get("models")
            if isinstance(models, list) and models:
                model = models[0]
            elif isinstance(models, str):
                model = models
        
        # Normalize role - only keep valid conversation roles
        if role not in ("user", "assistant", "system", "tool"):
            role = "user"
        
        nodes.append({
            "id": mid,
            "sequence": sequence,  # Preserve insertion order
            "role": role,
            "content": content,
            "created_at": created_at,
            "model": model,
            "parentId": m.get("parentId"),  # For potential tree traversal
        })
    
    # Sort by timestamp, with tie-breaker by sequence and parent presence
    # This ensures deterministic ordering even with identical timestamps
    nodes.sort(key=lambda n: (
        n["created_at"],
        0 if not n.get("parentId") else 1,  # Roots first
        n.get("sequence", 0),  # Then by insertion order
        str(n["id"])  # Finally by ID for safety
    ))
    
    # Convert to output format (list of messages)
    messages = []
    for idx, node in enumerate(nodes):
        msg_dict = {
            "role": node["role"],
            "content": node["content"],
            "created_at": node["created_at"],
            "sequence": node.get("sequence", idx)  # Preserve sequence
        }
        
        # Only add model if present
        if node.get("model"):
            msg_dict["model"] = node["model"]
        
        # Extract attachments from the original message data
        # Need to get back to the original message dict
        msg_id = node["id"]
        original_msg = conversation_data.get(msg_id, {})
        if original_msg:
            from controllers.postgres_controller import extract_openwebui_attachments
            attachments = extract_openwebui_attachments(original_msg)
            if attachments:
                msg_dict["attachments"] = attachments
        
        messages.append(msg_dict)
    
    return messages

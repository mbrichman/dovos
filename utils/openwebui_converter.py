#!/usr/bin/env python3
"""
Convert Claude conversation JSON to OpenWebUI format
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


def parse_timestamp(timestamp_str: str) -> int:
    """Convert ISO timestamp to Unix timestamp"""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        # Fallback to current timestamp if parsing fails
        return int(datetime.now().timestamp())


def convert_message(claude_message: Dict[str, Any], parent_id: Optional[str] = None) -> Dict[str, Any]:
    """Convert a single Claude message to OpenWebUI format"""
    message_id = generate_uuid()
    
    # Extract content text
    content = claude_message.get('text', '')
    if not content and claude_message.get('content'):
        # Handle content array format
        content_parts = claude_message.get('content', [])
        if isinstance(content_parts, list) and content_parts:
            content = content_parts[0].get('text', '')
    
    # Convert timestamp
    timestamp = parse_timestamp(claude_message.get('created_at', ''))
    
    # Determine role
    role = claude_message.get('sender', 'user')
    if role not in ['user', 'assistant']:
        role = 'user'  # Default to user if unknown
    
    message = {
        "id": message_id,
        "parentId": parent_id,
        "childrenIds": [],
        "role": role,
        "content": content,
        "timestamp": timestamp
    }
    
    # Add model info for assistant messages
    if role == "assistant":
        message.update({
            "model": "claude-3-sonnet",
            "modelName": "claude-3-sonnet", 
            "modelIdx": 0,
            "done": True
        })
    else:
        # Add models array for user messages
        message["models"] = ["claude-3-sonnet"]
    
    return message


def convert_conversation(claude_conv: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a single Claude conversation to OpenWebUI format"""
    conv_id = generate_uuid()
    user_id = "00000000-0000-0000-0000-000000000000"  # Default user ID
    
    # Extract conversation metadata
    title = claude_conv.get('name', 'Untitled Conversation')
    created_timestamp = parse_timestamp(claude_conv.get('created_at', ''))
    updated_timestamp = parse_timestamp(claude_conv.get('updated_at', ''))
    
    # Convert messages
    claude_messages = claude_conv.get('chat_messages', [])
    messages = []
    message_dict = {}
    
    if not claude_messages:
        # Return empty conversation if no messages
        return {
            "id": conv_id,
            "user_id": user_id,
            "title": title,
            "chat": {
                "id": "",
                "title": title,
                "models": ["claude-3-sonnet"],
                "params": {},
                "history": {
                    "messages": {},
                    "currentId": None
                },
                "messages": [],
                "tags": [],
                "timestamp": created_timestamp * 1000,  # Convert to milliseconds
                "files": []
            },
            "updated_at": updated_timestamp,
            "created_at": created_timestamp,
            "share_id": None,
            "archived": False,
            "pinned": False,
            "meta": {},
            "folder_id": None
        }
    
    # Convert messages and build parent-child relationships
    parent_id = None
    current_id = None
    
    for claude_msg in claude_messages:
        openwebui_msg = convert_message(claude_msg, parent_id)
        messages.append(openwebui_msg)
        message_dict[openwebui_msg["id"]] = openwebui_msg
        
        # Update parent's children
        if parent_id and parent_id in message_dict:
            message_dict[parent_id]["childrenIds"].append(openwebui_msg["id"])
        
        parent_id = openwebui_msg["id"]
        current_id = openwebui_msg["id"]
    
    # Create the OpenWebUI conversation structure
    openwebui_conv = {
        "id": conv_id,
        "user_id": user_id,
        "title": title,
        "chat": {
            "id": "",
            "title": title,
            "models": ["claude-3-sonnet"],
            "params": {},
            "history": {
                "messages": message_dict,
                "currentId": current_id
            },
            "messages": messages,
            "tags": [],
            "timestamp": created_timestamp * 1000,  # Convert to milliseconds
            "files": []
        },
        "updated_at": updated_timestamp,
        "created_at": created_timestamp,
        "share_id": None,
        "archived": False,
        "pinned": False,
        "meta": {},
        "folder_id": None
    }
    
    return openwebui_conv


def convert_claude_to_openwebui(claude_file: str, output_file: str):
    """Convert Claude conversations JSON file to OpenWebUI format"""
    print(f"Reading Claude conversations from: {claude_file}")
    
    try:
        with open(claude_file, 'r', encoding='utf-8') as f:
            claude_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File {claude_file} not found")
        return
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {claude_file}: {e}")
        return
    
    # Convert each conversation
    openwebui_conversations = []
    
    print(f"Converting {len(claude_data)} conversations...")
    
    for i, claude_conv in enumerate(claude_data):
        try:
            openwebui_conv = convert_conversation(claude_conv)
            openwebui_conversations.append(openwebui_conv)
            
            if (i + 1) % 100 == 0:
                print(f"Converted {i + 1} conversations...")
                
        except Exception as e:
            print(f"Error converting conversation {i}: {e}")
            continue
    
    # Write output file
    print(f"Writing {len(openwebui_conversations)} conversations to: {output_file}")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(openwebui_conversations, f, indent=2, ensure_ascii=False)
        print("Conversion completed successfully!")
        
    except Exception as e:
        print(f"Error writing output file: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python claude_to_openwebui_converter.py <claude_file.json> <output_file.json>")
        print("Example: python claude_to_openwebui_converter.py conversations_claude.json openwebui_conversations.json")
        sys.exit(1)
    
    claude_file = sys.argv[1]
    output_file = sys.argv[2]
    
    convert_claude_to_openwebui(claude_file, output_file)
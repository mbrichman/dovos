#!/usr/bin/env python3

import json
import sys

# Load the JSON file
with open("Source JSON/conversations.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("Searching for message with Toronto vs PV comparison table...")

# Look for the message containing the Toronto vs PV table
target_message = None
target_conversation = None

for conv in data:
    for msg_id, msg_data in conv["mapping"].items():
        message = msg_data.get("message")
        if not message:
            continue
        
        content = message.get("content", {})
        parts = content.get("parts", [])
        
        if parts:
            text = "\n".join([str(p) for p in parts if isinstance(p, str)])
            
            # Look for distinctive content from the table message
            if ("Toronto vs PV" in text or 
                ("| PV (USD) |" in text and "| Toronto (USD equiv) |" in text) or
                ("Monthly Cost" in text and "Annual Cost" in text and "|" in text)):
                
                target_message = message
                target_conversation = conv
                target_msg_id = msg_id
                break
    
    if target_message:
        break

if not target_message:
    print("❌ Table message not found!")
    
    # Let's search more broadly for table content
    print("\nSearching for any messages with table syntax...")
    table_messages = []
    
    for conv in data:
        for msg_id, msg_data in conv["mapping"].items():
            message = msg_data.get("message")
            if not message:
                continue
            
            content = message.get("content", {})
            parts = content.get("parts", [])
            
            if parts:
                text = "\n".join([str(p) for p in parts if isinstance(p, str)])
                
                # Look for table patterns
                if ("|" in text and "----" in text) or text.count("|") > 5:
                    table_messages.append({
                        "conv_title": conv.get("title", "Unknown"),
                        "msg_id": msg_id,
                        "role": message.get("author", {}).get("role"),
                        "text": text,
                        "pipe_count": text.count("|")
                    })
    
    print(f"Found {len(table_messages)} messages with potential table content:")
    for i, msg in enumerate(table_messages[:5]):  # Show first 5
        print(f"\n{i+1}. {msg['conv_title']} ({msg['role']}) - {msg['pipe_count']} pipes")
        preview = msg["text"][:150].replace('\n', '\\n')
        print(f"   Preview: {preview}...")
    
    sys.exit(1)

# Extract the content
parts = target_message.get("content", {}).get("parts", [])
raw_content = "\n".join([str(p) for p in parts if isinstance(p, str)])

print("✅ Found the table message!")
print(f"Conversation: {target_conversation.get('title', 'Unknown')}")
print(f"Message ID: {target_msg_id}")
print(f"Role: {target_message.get('author', {}).get('role')}")
print(f"Content length: {len(raw_content)} characters")
print(f"Pipe characters: {raw_content.count('|')}")

# Save as unit test artifact
with open("table_test_message.txt", "w", encoding="utf-8") as f:
    f.write(raw_content)

print("\n✅ Raw content saved to: table_test_message.txt")

# Save metadata
metadata = {
    "conversation_title": target_conversation.get("title"),
    "message_id": target_msg_id,
    "role": target_message.get("author", {}).get("role"),
    "create_time": target_message.get("create_time"),
    "content_length": len(raw_content),
    "pipe_count": raw_content.count("|"),
    "has_tables": True
}

with open("table_test_metadata.json", "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)

print("✅ Metadata saved to: table_test_metadata.json")

# Quick analysis
print("\n=== QUICK ANALYSIS ===")
lines = raw_content.split('\n')
table_lines = [line for line in lines if '|' in line]
print(f"Lines with pipes: {len(table_lines)}")
if table_lines:
    print("First few table lines:")
    for i, line in enumerate(table_lines[:3]):
        print(f"  {i+1}: {repr(line)}")

# Check for other markdown features
features = []
if "##" in raw_content: features.append("Headers")
if "**" in raw_content: features.append("Bold")
if ">" in raw_content: features.append("Blockquotes") 
if "- " in raw_content: features.append("Lists")
if "```" in raw_content: features.append("Code blocks")

print(f"Markdown features found: {', '.join(features) if features else 'None'}")
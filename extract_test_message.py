#!/usr/bin/env python3

import json
import sys

# Load the JSON file
with open("Source JSON/conversations.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Find the "Desirable PV Neighborhoods" conversation
target_conversation = None
for conv in data:
    if conv.get("title") == "Desirable PV Neighborhoods":
        target_conversation = conv
        break

if not target_conversation:
    print("Conversation 'Desirable PV Neighborhoods' not found!")
    sys.exit(1)

print("Found conversation!")

# Find the assistant message with plugin artifacts (message ID: 0b9c3926-a4f7-4ad7-8439-507fe07a8674)
target_message_id = "0b9c3926-a4f7-4ad7-8439-507fe07a8674"
target_message = None

for msg_id, msg_data in target_conversation["mapping"].items():
    if msg_id == target_message_id:
        target_message = msg_data.get("message")
        break

if not target_message:
    print(f"Target message {target_message_id} not found!")
    sys.exit(1)

# Extract the raw content
content = target_message.get("content", {})
parts = content.get("parts", [])

if not parts:
    print("No content parts found!")
    sys.exit(1)

raw_content = "\n".join([str(p) for p in parts if isinstance(p, str)])

print(f"Extracted message content ({len(raw_content)} characters)")
print()

# Save as unit test artifact
with open("unit_test_message.txt", "w", encoding="utf-8") as f:
    f.write(raw_content)

print("Raw content saved to: unit_test_message.txt")

# Also save metadata
metadata = {
    "conversation_title": target_conversation["title"],
    "message_id": target_message_id,
    "role": target_message.get("author", {}).get("role"),
    "create_time": target_message.get("create_time"),
    "content_length": len(raw_content)
}

with open("unit_test_metadata.json", "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)

print("Metadata saved to: unit_test_metadata.json")

# Show some key insights about the content
print()
print("=== CONTENT ANALYSIS ===")
print(f"Total length: {len(raw_content)} characters")
print(f"Number of lines: {len(raw_content.split(chr(10)))}")
print(f"Contains 'businesses_map': {'businesses_map' in raw_content}")
print(f"Contains JSON structures: {'{\"name\":' in raw_content}")

# Show first 200 chars with escaping to see special characters
print()
print("First 200 characters (with escape codes):")
print(repr(raw_content[:200]))

# Show line breaks and structure
print()
print("Line structure (first 10 lines):")
lines = raw_content.split('\n')
for i, line in enumerate(lines[:10]):
    print(f"Line {i+1}: {repr(line)}")
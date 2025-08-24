#!/usr/bin/env python3
import json
import os
from pathlib import Path

def extract_claude_attachments(json_file_path, output_dir):
    """Extract attachments from Claude export JSON"""
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Load the JSON data
    with open(json_file_path, 'r', encoding='utf-8') as f:
        conversations = json.load(f)
    
    attachment_count = 0
    
    for conv_idx, conv in enumerate(conversations):
        conv_name = conv.get('name', f'conversation_{conv_idx}')
        # Clean filename
        safe_conv_name = "".join(c for c in conv_name if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
        
        for msg_idx, message in enumerate(conv.get('chat_messages', [])):
            if message.get('attachments'):
                for att_idx, attachment in enumerate(message['attachments']):
                    extracted_content = attachment.get('extracted_content')
                    if extracted_content:
                        # Determine file extension
                        file_type = attachment.get('file_type', 'txt')
                        if file_type == '':
                            ext = 'txt'
                        elif file_type.startswith('text/'):
                            ext = file_type.split('/')[-1]
                            if ext == 'x-python-script':
                                ext = 'py'
                        else:
                            ext = file_type
                        
                        # Create filename
                        filename = f"{conv_idx:03d}_{safe_conv_name}_msg{msg_idx}_att{att_idx}.{ext}"
                        filepath = Path(output_dir) / filename
                        
                        # Write the content
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(extracted_content)
                        
                        attachment_count += 1
                        
                        # Print info
                        file_size = attachment.get('file_size', 0)
                        orig_filename = attachment.get('file_name', 'unnamed')
                        print(f"Extracted: {filename} (size: {file_size} bytes, orig: '{orig_filename}')")
    
    print(f"\nTotal attachments extracted: {attachment_count}")
    return attachment_count

if __name__ == "__main__":
    json_file = "/Users/markrichman/projects/dovos/Source Files/conversations_claude.json"
    output_dir = "/Users/markrichman/projects/dovos/extracted_attachments"
    
    extract_claude_attachments(json_file, output_dir)
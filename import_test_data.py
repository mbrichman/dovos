#!/usr/bin/env python3
"""
Import synthetic test data for date filtering tests
"""

import json
import tempfile
import os
import sys
from chat_archive import ChatArchive

def import_test_data():
    """Import synthetic test data into the database"""
    
    # Load the test data
    with open('synthetic_test_data.json', 'r') as f:
        test_data = json.load(f)
    
    # Initialize ChatArchive
    archive = ChatArchive()
    
    # Create temporary files for each conversation format
    temp_files = []
    
    try:
        # Process ChatGPT conversations
        for i, conversation in enumerate(test_data['chatgpt_conversations']):
            # Create temporary file for this conversation
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                json.dump([conversation], temp_file, indent=2)
                temp_files.append(temp_file.name)
                
                print(f"Processing ChatGPT conversation: {conversation['title']}")
                archive.index_json_file(temp_file.name)
        
        # Process Claude conversations  
        for i, conversation in enumerate(test_data['claude_conversations']):
            # Create temporary file for this conversation
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                json.dump([conversation], temp_file, indent=2)
                temp_files.append(temp_file.name)
                
                print(f"Processing Claude conversation: {conversation['name']}")
                archive.index_json_file(temp_file.name)
                
        print(f"\nSuccessfully imported {len(test_data['chatgpt_conversations'])} ChatGPT conversations")
        print(f"Successfully imported {len(test_data['claude_conversations'])} Claude conversations")
        print("Total: 6 test conversations imported")
        
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

if __name__ == "__main__":
    import_test_data()
#!/usr/bin/env python3

import sys
sys.path.append('.')

from chat_archive import clean_text_content
import markdown
import re

# Load our preserved unit test artifact
with open("unit_test_message.txt", "r", encoding="utf-8") as f:
    raw_content = f.read()

print("Creating HTML test file...")

# Test our current cleaning function
current_cleaned = clean_text_content(raw_content)
current_html = markdown.markdown(current_cleaned, extensions=["extra"])

# Create an improved cleaning function for testing
def improved_clean_text_content(text):
    """Improved version for testing - removes ChatGPT Unicode markers and artifacts"""
    if not text or not isinstance(text, str):
        return text
    
    # Remove ChatGPT private use area Unicode characters (formatting markers)
    cleaned = re.sub(r'[\ue000-\uf8ff]', '', text)
    
    # Remove ChatGPT plugin/tool artifacts
    cleaned = re.sub(r'businesses_map\{[^}]*\}', '', cleaned)  # businesses_map{...} plugin data
    cleaned = re.sub(r'businesses_map(?=\s|$)', '', cleaned)  # standalone "businesses_map" word
    cleaned = re.sub(r'[a-zA-Z_]+_map\{[^}]*\}', '', cleaned)  # any_map{...} pattern
    cleaned = re.sub(r'\{"name":"[^}]*","location":"[^}]*","description":"[^}]*","[^}]*"\}', '', cleaned)  # structured place data
    cleaned = re.sub(r'"cite":"turn\d+search\d+"', '', cleaned)  # "cite":"turn0search15" patterns
    
    # Clean up excessive whitespace but preserve paragraph structure
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)     # Multiple spaces/tabs to single space
    cleaned = re.sub(r'\n[ \t]+', '\n', cleaned)  # Remove spaces at start of lines
    cleaned = re.sub(r'[ \t]+\n', '\n', cleaned)  # Remove spaces at end of lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)  # Limit consecutive newlines to 2
    
    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()
    
    return cleaned

# Test improved cleaning
improved_cleaned = improved_clean_text_content(raw_content)
improved_html = markdown.markdown(improved_cleaned, extensions=["extra"])

# Create HTML test file
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Message Rendering Test</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            line-height: 1.6;
        }}
        .test-section {{
            border: 2px solid #ccc;
            margin: 20px 0;
            padding: 20px;
            border-radius: 8px;
        }}
        .test-section h2 {{
            margin-top: 0;
            color: #333;
        }}
        .raw-content {{
            background: #f8f8f8;
            padding: 15px;
            border-left: 4px solid #ddd;
            white-space: pre-wrap;
            font-family: monospace;
            font-size: 12px;
        }}
        .current {{
            background: #fff5f5;
            border-color: #ff6b6b;
        }}
        .improved {{
            background: #f0fff4;
            border-color: #51cf66;
        }}
        .stats {{
            background: #e3f2fd;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        }}
    </style>
</head>
<body>
    <h1>Message Rendering Test: Puerto Vallarta Neighborhoods</h1>
    
    <div class="test-section">
        <h2>Original Raw Content</h2>
        <div class="stats">
            Length: {len(raw_content)} characters | Lines: {len(raw_content.split(chr(10)))}
        </div>
        <div class="raw-content">{raw_content}</div>
    </div>
    
    <div class="test-section current">
        <h2>Current Cleaning Function Result ❌</h2>
        <div class="stats">
            Length: {len(current_cleaned)} characters | Cleaned: {len(raw_content) - len(current_cleaned)} chars removed
        </div>
        <h3>Cleaned Text:</h3>
        <div class="raw-content">{current_cleaned}</div>
        <h3>Rendered HTML:</h3>
        <div style="border: 1px solid #ccc; padding: 15px; background: white;">
            {current_html}
        </div>
    </div>
    
    <div class="test-section improved">
        <h2>Improved Cleaning Function Result ✅</h2>
        <div class="stats">
            Length: {len(improved_cleaned)} characters | Cleaned: {len(raw_content) - len(improved_cleaned)} chars removed
        </div>
        <h3>Cleaned Text:</h3>
        <div class="raw-content">{improved_cleaned}</div>
        <h3>Rendered HTML:</h3>
        <div style="border: 1px solid #ccc; padding: 15px; background: white;">
            {improved_html}
        </div>
    </div>
    
    <div class="test-section">
        <h2>Analysis</h2>
        <h3>Issues Found:</h3>
        <ul>
            <li>Unicode control characters: {'✅ Fixed' if '\\ue2' not in improved_cleaned else '❌ Still present'}</li>
            <li>businesses_map artifacts: {'✅ Fixed' if 'businesses_map' not in improved_cleaned else '❌ Still present'}</li>
            <li>JSON plugin data: {'✅ Fixed' if '{\"name\":' not in improved_cleaned else '❌ Still present'}</li>
            <li>Proper paragraph structure: {'✅ Good' if improved_html.count('<p>') == 2 else '❌ Issues'}</li>
        </ul>
        
        <h3>Expected Result:</h3>
        <p>Should have two clean paragraphs with proper line spacing, no plugin artifacts, and readable flow.</p>
    </div>
</body>
</html>"""

# Save the test file
with open("message_rendering_test.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("✅ Created: message_rendering_test.html")
print("✅ Open this file in your browser to see the rendering comparison")

print(f"\nQuick comparison:")
print(f"Original: {len(raw_content)} chars")
print(f"Current:  {len(current_cleaned)} chars")
print(f"Improved: {len(improved_cleaned)} chars")
print(f"Current has 'businesses_map': {'businesses_map' in current_cleaned}")
print(f"Improved has 'businesses_map': {'businesses_map' in improved_cleaned}")
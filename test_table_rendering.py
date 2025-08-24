#!/usr/bin/env python3

import sys
sys.path.append('.')

from chat_archive import clean_text_content
import markdown
import re

# Load the table test message
with open("table_test_message.txt", "r", encoding="utf-8") as f:
    raw_content = f.read()

print("Creating table rendering test...")

# Current cleaning function
current_cleaned = clean_text_content(raw_content)
current_html = markdown.markdown(current_cleaned, extensions=["extra", "tables"])

# Improved cleaning function (same as before)
def improved_clean_text_content(text):
    """Improved version for testing - handles Unicode markers and preserves markdown"""
    if not text or not isinstance(text, str):
        return text
    
    # Remove ChatGPT private use area Unicode characters (formatting markers)
    cleaned = re.sub(r'[\ue000-\uf8ff]', '', text)
    
    # Remove ChatGPT plugin/tool artifacts
    cleaned = re.sub(r'businesses_map\{[^}]*\}', '', cleaned)
    cleaned = re.sub(r'businesses_map(?=\s|$)', '', cleaned)
    cleaned = re.sub(r'[a-zA-Z_]+_map\{[^}]*\}', '', cleaned)
    cleaned = re.sub(r'\{"name":"[^}]*","location":"[^}]*","description":"[^}]*","[^}]*"\}', '', cleaned)
    cleaned = re.sub(r'"cite":"turn\d+search\d+"', '', cleaned)
    
    # Clean up excessive whitespace but preserve markdown structure
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)     # Multiple spaces/tabs to single space
    cleaned = re.sub(r'\n[ \t]+', '\n', cleaned)  # Remove spaces at start of lines
    cleaned = re.sub(r'[ \t]+\n', '\n', cleaned)  # Remove spaces at end of lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)  # Limit consecutive newlines to 2
    
    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()
    
    return cleaned

# Test improved cleaning
improved_cleaned = improved_clean_text_content(raw_content)
improved_html = markdown.markdown(improved_cleaned, extensions=["extra", "tables"])

# Create comprehensive HTML test file
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Table Rendering Test</title>
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
            font-size: 11px;
            max-height: 300px;
            overflow-y: auto;
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
        .rendered {{
            border: 1px solid #ccc;
            padding: 20px;
            background: white;
            border-radius: 4px;
        }}
        .rendered table {{
            border-collapse: collapse;
            width: 100%;
            margin: 10px 0;
        }}
        .rendered th, .rendered td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        .rendered th {{
            background-color: #f2f2f2;
            font-weight: bold;
        }}
        .rendered h2, .rendered h3 {{
            color: #2c3e50;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }}
        .rendered blockquote {{
            border-left: 4px solid #3498db;
            padding-left: 20px;
            margin-left: 0;
            background: #f8f9fa;
            padding: 15px 20px;
        }}
        .analysis {{
            background: #fffbf0;
            border: 2px solid #f39c12;
        }}
    </style>
</head>
<body>
    <h1>Table Rendering Test: Toronto Budget Breakdown</h1>
    
    <div class="test-section">
        <h2>Original Raw Content</h2>
        <div class="stats">
            Length: {len(raw_content)} characters | Lines: {len(raw_content.split(chr(10)))} | Pipe chars: {raw_content.count('|')}
        </div>
        <div class="raw-content">{raw_content}</div>
    </div>
    
    <div class="test-section current">
        <h2>Current Cleaning Function Result</h2>
        <div class="stats">
            Length: {len(current_cleaned)} chars | Tables: {current_html.count('<table>')} | Cleaned: {len(raw_content) - len(current_cleaned)} chars removed
        </div>
        <h3>Cleaned Text:</h3>
        <div class="raw-content">{current_cleaned}</div>
        <h3>Rendered HTML:</h3>
        <div class="rendered">
            {current_html}
        </div>
    </div>
    
    <div class="test-section improved">
        <h2>Improved Cleaning Function Result</h2>
        <div class="stats">
            Length: {len(improved_cleaned)} chars | Tables: {improved_html.count('<table>')} | Cleaned: {len(raw_content) - len(improved_cleaned)} chars removed
        </div>
        <h3>Cleaned Text:</h3>
        <div class="raw-content">{improved_cleaned}</div>
        <h3>Rendered HTML:</h3>
        <div class="rendered">
            {improved_html}
        </div>
    </div>
    
    <div class="test-section analysis">
        <h2>Analysis</h2>
        <h3>Table Rendering:</h3>
        <ul>
            <li>Current version tables: {current_html.count('<table>')} 
                {'✅ Preserved' if current_html.count('<table>') > 0 else '❌ Lost'}</li>
            <li>Improved version tables: {improved_html.count('<table>')} 
                {'✅ Preserved' if improved_html.count('<table>') > 0 else '❌ Lost'}</li>
            <li>Header formatting: {'✅ Present' if '<h2>' in improved_html or '<h3>' in improved_html else '❌ Missing'}</li>
            <li>Bold text: {'✅ Present' if '<strong>' in improved_html else '❌ Missing'}</li>
            <li>Blockquotes: {'✅ Present' if '<blockquote>' in improved_html else '❌ Missing'}</li>
        </ul>
        
        <h3>Key Tests:</h3>
        <ul>
            <li>Pipe characters preserved: Original {raw_content.count('|')} → Cleaned {improved_cleaned.count('|')}</li>
            <li>Table separators (---): {'✅ Preserved' if '---' in improved_cleaned else '❌ Lost'}</li>
            <li>Proper line breaks in tables: {'✅ Good' if improved_cleaned.count('\\n|') > 0 else '❌ Issues'}</li>
        </ul>
        
        <h3>Expected Features:</h3>
        <p>Should render proper HTML tables with headers, multiple comparison tables, 
           formatted text (bold, headers), and blockquotes - all with clean spacing.</p>
    </div>
</body>
</html>"""

# Save the test file
with open("table_rendering_test.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("✅ Created: table_rendering_test.html")
print("✅ Open this file in your browser to validate table rendering")

print(f"\nQuick stats:")
print(f"Original pipe count: {raw_content.count('|')}")
print(f"Current cleaned pipe count: {current_cleaned.count('|')}")
print(f"Improved cleaned pipe count: {improved_cleaned.count('|')}")
print(f"Current HTML tables: {current_html.count('<table>')}")
print(f"Improved HTML tables: {improved_html.count('<table>')}")

# Show a sample of the tables structure
print(f"\nTable structure check:")
print(f"Has table separators (---): {'---' in improved_cleaned}")
print(f"Has header row structure: {'|' in improved_cleaned and '---' in improved_cleaned}")
print(f"Table lines in cleaned: {len([line for line in improved_cleaned.split('\\n') if '|' in line])}")
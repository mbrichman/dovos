#!/usr/bin/env python3

import sys
sys.path.append('.')

from chat_archive import clean_text_content
import markdown

# Load our preserved unit test artifact
with open("unit_test_message.txt", "r", encoding="utf-8") as f:
    raw_content = f.read()

print("=== ORIGINAL CONTENT ===")
print(f"Length: {len(raw_content)} characters")
print("Content (with escape codes):")
print(repr(raw_content))
print()
print("Visual original:")
print(raw_content)
print()

# Test current cleaning
cleaned = clean_text_content(raw_content)

print("=== AFTER CLEANING ===")
print(f"Length: {len(cleaned)} characters") 
print("Content (with escape codes):")
print(repr(cleaned))
print()
print("Visual cleaned:")
print(cleaned)
print()

# Test markdown conversion (this is what should happen in routes.py)
html = markdown.markdown(cleaned, extensions=["extra"])

print("=== AFTER MARKDOWN CONVERSION ===")
print("HTML:")
print(html)
print()

# What we WANT the cleaned content to look like
expected_cleaned = """Puerto Vallarta offers a variety of neighborhoods, each with its own unique appeal. Here are some of the most desirable areas:

Each of these neighborhoods offers a distinct lifestyle, catering to various preferences, whether you're seeking vibrant city life, beachfront luxury, or a peaceful residential setting."""

print("=== WHAT WE EXPECT ===")
print("Expected cleaned content:")
print(repr(expected_cleaned))
print()
print("Visual expected:")
print(expected_cleaned)
print()

expected_html = markdown.markdown(expected_cleaned, extensions=["extra"])
print("Expected HTML:")
print(expected_html)

# Check if we match expectations
if cleaned.strip() == expected_cleaned.strip():
    print("\n✅ SUCCESS: Cleaned content matches expectations!")
else:
    print("\n❌ MISMATCH: Cleaned content doesn't match expectations")
    print(f"Expected: {repr(expected_cleaned)}")
    print(f"Got:      {repr(cleaned)}")
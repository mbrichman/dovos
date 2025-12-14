#!/usr/bin/env python3
"""
Test script to verify OpenWebUI connection and API endpoint
"""

import requests
import json
import sys
from pathlib import Path

# Add parent directory to path to import db modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from db.repositories.unit_of_work import get_unit_of_work

def get_openwebui_settings():
    """Get OpenWebUI settings from database"""
    with get_unit_of_work() as uow:
        url = uow.settings.get_value("openwebui_url")
        api_key = uow.settings.get_value("openwebui_api_key")
        return url, api_key

def test_connection():
    """Test basic connection to OpenWebUI"""
    url, api_key = get_openwebui_settings()

    if not url or not api_key:
        print("✗ OpenWebUI settings not configured in database")
        print("  Please configure OpenWebUI URL and API key in the settings page")
        return False

    print(f"Testing connection to {url}...")

    try:
        response = requests.get(
            f"{url}/api/v1/chats",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✓ Connection successful!")
            print(f"  Status: {response.status_code}")
            return True
        else:
            print(f"✗ Connection failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Connection error: {e}")
        return False

def test_import_endpoint():
    """Test the import endpoint with a minimal conversation"""
    print(f"\nTesting import endpoint...")

    url, api_key = get_openwebui_settings()

    if not url or not api_key:
        print("✗ OpenWebUI settings not configured")
        return False

    # Minimal test conversation
    test_conv = {
        "id": "test-conv-123",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "title": "Test Import",
        "chat": {
            "title": "Test Import",
            "models": ["gpt-3.5-turbo"],
            "messages": [
                {
                    "id": "msg-1",
                    "role": "user",
                    "content": "Hello, this is a test",
                    "timestamp": 1704067200
                }
            ],
            "history": {
                "messages": {},
                "currentId": "msg-1"
            }
        },
        "created_at": 1704067200,
        "updated_at": 1704067200
    }

    try:
        response = requests.post(
            f"{url}/api/v1/chats/import",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=test_conv,
            timeout=30
        )
        
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text[:200]}...")
        
        if response.status_code == 200:
            print("✓ Import endpoint working!")
            return True
        else:
            print(f"✗ Import failed")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Import error: {e}")
        return False

def check_api_endpoints():
    """List available API endpoints"""
    print(f"\nChecking available API endpoints...")

    url, api_key = get_openwebui_settings()

    if not url or not api_key:
        print("✗ OpenWebUI settings not configured")
        return

    endpoints_to_test = [
        "/api/v1/chats",
        "/api/v1/chats/import",
        "/api/chats",
        "/api/chats/import",
    ]

    for endpoint in endpoints_to_test:
        try:
            response = requests.options(
                f"{url}{endpoint}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5
            )
            print(f"  {endpoint}: {response.status_code}")
        except:
            print(f"  {endpoint}: Not reachable")

if __name__ == "__main__":
    print("=" * 60)
    print("OpenWebUI Connection Test")
    print("=" * 60)

    url, api_key = get_openwebui_settings()

    if not url or not api_key:
        print("✗ OpenWebUI settings not configured in database")
        print("  Please configure OpenWebUI URL and API key in the settings page")
        print("=" * 60)
        sys.exit(1)

    print(f"URL: {url}")
    print(f"API Key: {api_key[:20]}...")
    print("=" * 60)

    test_connection()
    check_api_endpoints()
    test_import_endpoint()

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

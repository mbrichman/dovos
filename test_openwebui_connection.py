#!/usr/bin/env python3
"""
Test script to verify OpenWebUI connection and API endpoint
"""

import requests
import json
import config

def test_connection():
    """Test basic connection to OpenWebUI"""
    print(f"Testing connection to {config.OPENWEBUI_URL}...")
    
    try:
        response = requests.get(
            f"{config.OPENWEBUI_URL}/api/v1/chats",
            headers={"Authorization": f"Bearer {config.OPENWEBUI_API_KEY}"},
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
            f"{config.OPENWEBUI_URL}/api/v1/chats/import",
            headers={
                "Authorization": f"Bearer {config.OPENWEBUI_API_KEY}",
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
    
    endpoints_to_test = [
        "/api/v1/chats",
        "/api/v1/chats/import",
        "/api/chats",
        "/api/chats/import",
    ]
    
    for endpoint in endpoints_to_test:
        try:
            response = requests.options(
                f"{config.OPENWEBUI_URL}{endpoint}",
                headers={"Authorization": f"Bearer {config.OPENWEBUI_API_KEY}"},
                timeout=5
            )
            print(f"  {endpoint}: {response.status_code}")
        except:
            print(f"  {endpoint}: Not reachable")

if __name__ == "__main__":
    print("=" * 60)
    print("OpenWebUI Connection Test")
    print("=" * 60)
    print(f"URL: {config.OPENWEBUI_URL}")
    print(f"API Key: {config.OPENWEBUI_API_KEY[:20]}...")
    print("=" * 60)
    
    test_connection()
    check_api_endpoints()
    test_import_endpoint()
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

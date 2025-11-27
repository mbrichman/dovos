#!/usr/bin/env python3
"""
Diagnostic script to troubleshoot OpenWebUI export 403 errors.
This script tests the OpenWebUI connection and attempts a sample export.
"""

import sys
import json
import logging
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import config

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_connection():
    """Test basic connection to OpenWebUI"""
    print("\n" + "="*60)
    print("1. Testing Basic Connection")
    print("="*60)
    
    url = f"{config.OPENWEBUI_URL}/api/v1/chats"
    headers = {"Authorization": f"Bearer {config.OPENWEBUI_API_KEY}"}
    
    logger.info(f"Testing GET {url}")
    logger.debug(f"Headers: {headers}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        logger.info(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        logger.debug(f"Response body: {response.text[:500]}")
        
        if response.status_code == 200:
            print("✓ Connection successful!")
            return True
        else:
            print(f"✗ Connection failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Connection error: {e}")
        logger.error("Connection failed", exc_info=True)
        return False


def test_available_endpoints():
    """Test various possible endpoints"""
    print("\n" + "="*60)
    print("2. Testing Available Endpoints")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {config.OPENWEBUI_API_KEY}"}
    
    # Endpoints to test
    endpoints = [
        ("GET", "/api/v1/chats"),
        ("POST", "/api/v1/chats/new"),
        ("POST", "/api/v1/chats/import"),
        ("POST", "/api/v1/chats"),
        ("GET", "/api/chats"),
        ("POST", "/api/chats/new"),
        ("POST", "/api/chats/import"),
    ]
    
    results = {}
    for method, endpoint in endpoints:
        url = f"{config.OPENWEBUI_URL}{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=5)
            else:
                # POST with minimal test payload
                response = requests.post(url, headers=headers, json={}, timeout=5)
            
            results[endpoint] = response.status_code
            status_icon = "✓" if response.status_code < 400 else "✗"
            print(f"  {status_icon} {method} {endpoint}: {response.status_code}")
            logger.debug(f"{method} {url}: {response.status_code} - {response.text[:200]}")
            
        except requests.exceptions.RequestException as e:
            results[endpoint] = "ERROR"
            print(f"  ✗ {method} {endpoint}: Connection error")
            logger.debug(f"{method} {url}: {e}")
    
    return results


def test_export_format():
    """Test the export conversation format"""
    print("\n" + "="*60)
    print("3. Testing Export Format")
    print("="*60)
    
    # Create a minimal test conversation in OpenWebUI format
    test_conversation = {
        "id": "test-conv-123",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "title": "Test Export from Dovos",
        "chat": {
            "title": "Test Export from Dovos",
            "models": ["gpt-3.5-turbo"],
            "messages": [
                {
                    "id": "msg-1",
                    "role": "user",
                    "content": "Hello, this is a test message",
                    "timestamp": 1704067200
                },
                {
                    "id": "msg-2",
                    "role": "assistant",
                    "content": "This is a test response",
                    "timestamp": 1704067210
                }
            ],
            "history": {
                "messages": {
                    "msg-1": {
                        "id": "msg-1",
                        "role": "user",
                        "content": "Hello, this is a test message",
                        "timestamp": 1704067200
                    },
                    "msg-2": {
                        "id": "msg-2",
                        "parentId": "msg-1",
                        "role": "assistant",
                        "content": "This is a test response",
                        "timestamp": 1704067210
                    }
                },
                "currentId": "msg-2"
            }
        },
        "created_at": 1704067200,
        "updated_at": 1704067210
    }
    
    print(f"\nTest conversation format:")
    print(json.dumps(test_conversation, indent=2)[:500] + "...")
    
    # Test endpoints
    endpoints_to_try = [
        "/api/v1/chats/new",
        "/api/v1/chats/import",
        "/api/v1/chats",
    ]
    
    headers = {
        "Authorization": f"Bearer {config.OPENWEBUI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    for endpoint in endpoints_to_try:
        url = f"{config.OPENWEBUI_URL}{endpoint}"
        print(f"\nTrying POST {endpoint}...")
        logger.info(f"Testing POST {url}")
        logger.debug(f"Headers: {headers}")
        logger.debug(f"Payload: {json.dumps(test_conversation, indent=2)}")
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=test_conversation,
                timeout=30
            )
            
            logger.info(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            logger.debug(f"Response body: {response.text}")
            
            if response.status_code == 200:
                print(f"  ✓ Success! Status: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                return endpoint, True
            elif response.status_code == 403:
                print(f"  ✗ 403 Forbidden")
                print(f"  Response: {response.text[:500]}")
                # Try to parse error details
                try:
                    error_data = response.json()
                    print(f"  Error details: {json.dumps(error_data, indent=2)}")
                except:
                    pass
            else:
                print(f"  ✗ Failed with status {response.status_code}")
                print(f"  Response: {response.text[:500]}")
                
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Connection error: {e}")
            logger.error(f"Request failed for {url}", exc_info=True)
    
    return None, False


def check_api_key_permissions():
    """Check what permissions the API key has"""
    print("\n" + "="*60)
    print("4. Checking API Key Permissions")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {config.OPENWEBUI_API_KEY}"}
    
    # Try to get user info or other metadata
    test_endpoints = [
        "/api/v1/users/user",
        "/api/v1/auths/signin",
        "/api/v1/models",
    ]
    
    for endpoint in test_endpoints:
        url = f"{config.OPENWEBUI_URL}{endpoint}"
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code < 400:
                print(f"  ✓ {endpoint}: {response.status_code}")
                logger.debug(f"Response: {response.text[:200]}")
            else:
                print(f"  ✗ {endpoint}: {response.status_code}")
        except:
            print(f"  ? {endpoint}: Unable to reach")


def main():
    """Run all diagnostic tests"""
    print("\n" + "="*70)
    print("OpenWebUI Export Diagnostic Tool")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  URL: {config.OPENWEBUI_URL}")
    print(f"  API Key: {config.OPENWEBUI_API_KEY[:20]}...{config.OPENWEBUI_API_KEY[-10:]}")
    print("="*70)
    
    # Run tests
    connection_ok = test_connection()
    
    if not connection_ok:
        print("\n⚠ Basic connection failed. Check your URL and API key.")
        return
    
    test_available_endpoints()
    check_api_key_permissions()
    endpoint, success = test_export_format()
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    if success:
        print(f"✓ Export appears to be working with endpoint: {endpoint}")
        print(f"\nRecommendation: Update the export code to use {endpoint}")
    else:
        print("✗ Export is failing with 403 Forbidden")
        print("\nPossible causes:")
        print("  1. API key lacks permission to create/import chats")
        print("  2. The endpoint /api/v1/chats/new doesn't exist or requires different format")
        print("  3. OpenWebUI version mismatch (check OpenWebUI documentation)")
        print("\nRecommendations:")
        print("  1. Check OpenWebUI logs for more details")
        print("  2. Verify API key has admin or appropriate permissions")
        print("  3. Check OpenWebUI API documentation for correct endpoint")
        print("  4. Try using /api/v1/chats/import instead of /api/v1/chats/new")
    
    print("\nFor more details, check the logs above or OpenWebUI server logs.")
    print("="*70)


if __name__ == "__main__":
    main()

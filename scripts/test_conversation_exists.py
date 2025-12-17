#!/usr/bin/env python3
"""
Test script to verify different methods of checking if a conversation exists in OpenWebUI.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from db.repositories.unit_of_work import get_unit_of_work

# Disable SSL warnings
import urllib3
urllib3.disable_warnings()


def get_openwebui_settings():
    """Get OpenWebUI settings from database"""
    with get_unit_of_work() as uow:
        url = uow.settings.get_value("openwebui_url")
        api_key = uow.settings.get_value("openwebui_api_key")
        return url, api_key


def test_conversation_exists(openwebui_uuid):
    """Test different methods to check if a conversation exists in OpenWebUI"""

    openwebui_url, openwebui_api_key = get_openwebui_settings()

    if not openwebui_url or not openwebui_api_key:
        print("❌ OpenWebUI settings not configured")
        return

    print(f"\n{'='*70}")
    print(f"Testing conversation existence for UUID: {openwebui_uuid}")
    print(f"OpenWebUI URL: {openwebui_url}")
    print(f"{'='*70}\n")

    headers = {
        "Authorization": f"Bearer {openwebui_api_key}",
        "Content-Type": "application/json"
    }

    # Method 1: GET /api/v1/chats/{id}
    print("Method 1: GET /api/v1/chats/{id}")
    print("-" * 50)
    try:
        url = f"{openwebui_url}/api/v1/chats/{openwebui_uuid}"
        print(f"  URL: {url}")
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        print(f"  Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"  ✅ Conversation exists!")
            data = response.json()
            print(f"  Title: {data.get('title', 'N/A')}")
        elif response.status_code == 404:
            print(f"  ❌ Conversation not found (404)")
        else:
            print(f"  ⚠️  Unexpected status: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # Method 2: HEAD /api/v1/chats/{id}
    print("\nMethod 2: HEAD /api/v1/chats/{id}")
    print("-" * 50)
    try:
        url = f"{openwebui_url}/api/v1/chats/{openwebui_uuid}"
        print(f"  URL: {url}")
        response = requests.head(url, headers=headers, timeout=10, verify=False)
        print(f"  Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"  ✅ Conversation exists!")
        elif response.status_code == 404:
            print(f"  ❌ Conversation not found (404)")
        else:
            print(f"  ⚠️  Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # Method 3: Check if UUID is in the list from GET /api/v1/chats
    print("\nMethod 3: Check in conversation list (GET /api/v1/chats)")
    print("-" * 50)
    try:
        url = f"{openwebui_url}/api/v1/chats"
        print(f"  URL: {url}")
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        print(f"  Status Code: {response.status_code}")
        if response.status_code == 200:
            chats = response.json()
            print(f"  Total conversations: {len(chats)}")
            found = any(chat.get('id') == openwebui_uuid for chat in chats)
            if found:
                print(f"  ✅ Conversation found in list!")
            else:
                print(f"  ❌ Conversation not found in list")
        else:
            print(f"  ⚠️  Failed to get list: {response.status_code}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # Method 4: Try accessing the web URL (might redirect to login if not authenticated)
    print("\nMethod 4: Check web URL (GET /c/{id})")
    print("-" * 50)
    try:
        url = f"{openwebui_url}/c/{openwebui_uuid}"
        print(f"  URL: {url}")
        # Don't use auth header for web requests
        response = requests.get(url, timeout=10, verify=False, allow_redirects=False)
        print(f"  Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"  ✅ Web page accessible!")
        elif response.status_code in (301, 302, 307, 308):
            print(f"  ⚠️  Redirect (probably needs login): {response.headers.get('Location')}")
        elif response.status_code == 404:
            print(f"  ❌ Page not found (404)")
        else:
            print(f"  ⚠️  Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    print(f"\n{'='*70}")
    print("RECOMMENDATION:")
    print("Based on the results above, the best method for checking existence is:")
    print("  - GET /api/v1/chats/{id} (if it returns 200, exists; 404, doesn't exist)")
    print("  - Or HEAD /api/v1/chats/{id} (more efficient, no response body)")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    # Test with the UUID we found
    test_uuid = "eca5f12b-8411-4d93-8bdd-963df8636b92"

    if len(sys.argv) > 1:
        test_uuid = sys.argv[1]

    test_conversation_exists(test_uuid)

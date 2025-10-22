#!/usr/bin/env python3
"""
Test Backend Selection

This script tests which backend is actually being used by the application.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🔍 Testing Backend Selection")
print("=" * 50)

# Show environment variable
use_postgres = os.getenv('USE_POSTGRES', '').lower()
print(f"🔧 USE_POSTGRES environment variable: '{os.getenv('USE_POSTGRES', 'NOT SET')}'")
print(f"🔧 Resolved to: {use_postgres == 'true'}")

# Test the condition from routes.py
routes_condition = os.getenv('USE_POSTGRES', '').lower() == 'true'
print(f"🔧 Routes.py condition result: {routes_condition}")

print("\n📊 Testing Database Access:")

# Test PostgreSQL directly
print("\n1️⃣ PostgreSQL Database:")
try:
    from db.database import get_session_context, test_connection
    from sqlalchemy import text
    
    if test_connection():
        with get_session_context() as session:
            pg_count = session.execute(text("SELECT COUNT(*) FROM conversations")).scalar()
            print(f"   ✅ PostgreSQL: {pg_count} conversations")
    else:
        print("   ❌ PostgreSQL connection failed")
except Exception as e:
    print(f"   ❌ PostgreSQL error: {e}")

# Test Legacy System
print("\n2️⃣ Legacy System:")
try:
    # Temporarily disable postgres flag for legacy test
    original_flag = os.environ.get('USE_POSTGRES')
    os.environ['USE_POSTGRES'] = 'false'
    
    from controllers.conversation_controller import ConversationController
    controller = ConversationController()
    legacy_count = controller.search_model.conversation_model.get_count()
    print(f"   ✅ Legacy (ChromaDB): {legacy_count} conversations")
    
    # Restore original flag
    if original_flag:
        os.environ['USE_POSTGRES'] = original_flag
    else:
        os.environ.pop('USE_POSTGRES', None)
        
except Exception as e:
    print(f"   ❌ Legacy system error: {e}")

# Test API Adapter
print("\n3️⃣ API Adapter (with current flag):")
try:
    from db.adapters.legacy_api_adapter import get_legacy_adapter
    adapter = get_legacy_adapter()
    stats = adapter.get_stats()
    print(f"   ✅ API Adapter: {stats.get('document_count', 'unknown')} documents")
    print(f"   📋 Status: {stats.get('status', 'unknown')}")
except Exception as e:
    print(f"   ❌ API Adapter error: {e}")

print("\n🎯 Summary:")
print("If the numbers don't match, there might be:")
print("1. Issue with feature flag detection in routes.py")
print("2. Multiple processes running with different flags") 
print("3. Cached controllers or adapters")
print("4. Different database connections")

print("\n💡 Next steps:")
print("1. Restart your Flask app with: export USE_POSTGRES=true")
print("2. Check which backend your /api/stats endpoint uses")
print("3. Use the management script: python manage_postgres_flag.py status")
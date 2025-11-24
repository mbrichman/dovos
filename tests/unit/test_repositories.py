#!/usr/bin/env python3
"""
Test script to validate the repository pattern implementation.
"""

import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.database import test_connection, check_extensions
from db.repositories.unit_of_work import get_unit_of_work


def test_database_connection():
    """Test basic database connectivity."""
    print("Testing database connection...")
    
    if test_connection():
        print("✅ Database connection successful")
        return True
    else:
        print("❌ Database connection failed")
        return False


def test_extensions():
    """Test required PostgreSQL extensions."""
    print("\nTesting PostgreSQL extensions...")
    
    extensions = check_extensions()
    
    for ext_name, installed in extensions.items():
        status = "✅ Installed" if installed else "❌ Missing"
        print(f"  {ext_name}: {status}")
    
    return all(extensions.values())


def test_repositories():
    """Test basic repository operations."""
    print("\nTesting repository operations...")
    
    try:
        with get_unit_of_work() as uow:
            # Test conversation creation
            conversation = uow.conversations.create(
                title="Test Conversation from Repository"
            )
            print(f"✅ Created conversation: {conversation.id}")
            
            # Test message creation
            message = uow.messages.create(
                conversation_id=conversation.id,
                role="user",
                content="This is a test message from the repository pattern.",
                metadata={"test": True}
            )
            print(f"✅ Created message: {message.id}")
            
            # Test job creation
            job = uow.jobs.enqueue(
                kind="generate_embedding",
                payload={"message_id": str(message.id)}
            )
            print(f"✅ Created job: {job.id}")
            
            # Test queries
            conversations = uow.conversations.get_all(limit=5)
            print(f"✅ Retrieved {len(conversations)} conversations")
            
            messages = uow.messages.get_by_conversation(conversation.id)
            print(f"✅ Retrieved {len(messages)} messages for conversation")
            
            pending_jobs = uow.jobs.get_pending_jobs(limit=5)
            print(f"✅ Retrieved {len(pending_jobs)} pending jobs")
            
            # Test stats
            conv_stats = uow.conversations.get_stats()
            print(f"✅ Conversation stats: {conv_stats}")
            
            message_stats = uow.messages.get_message_stats()
            print(f"✅ Message stats: {message_stats}")
            
            return True
            
    except Exception as e:
        print(f"❌ Repository test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search_functionality():
    """Test search functionality."""
    print("\nTesting search functionality...")
    
    try:
        with get_unit_of_work() as uow:
            # Test full-text search
            results = uow.messages.search_full_text("test", limit=5)
            print(f"✅ Full-text search returned {len(results)} results")
            
            # Test trigram search
            results = uow.messages.search_trigram("repository", limit=5)
            print(f"✅ Trigram search returned {len(results)} results")
            
            return True
            
    except Exception as e:
        print(f"❌ Search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    print("Repository Pattern Test Suite")
    print("=" * 40)
    
    # Run tests
    tests = [
        test_database_connection,
        test_extensions,
        test_repositories,
        test_search_functionality
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 40)
    print("Test Summary:")
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Repository pattern is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    main()
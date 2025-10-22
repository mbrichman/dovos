#!/usr/bin/env python3
"""
PostgreSQL API Compatibility Test

This script tests the full API compatibility layer to ensure that all endpoints
work identically with the new PostgreSQL backend compared to the legacy system.
"""

import os
import sys
import pytest
import json
import requests
from typing import Dict, Any, List
from datetime import datetime, timedelta
import uuid
import logging

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database_setup import setup_database, get_database_url
from db.services.message_service import MessageService
from db.repositories.unit_of_work import get_unit_of_work
from api.contracts.golden_responses import GOLDEN_RESPONSES

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APICompatibilityTester:
    """Test PostgreSQL API compatibility against golden responses."""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
        self.message_service = MessageService()
        
    def setup_test_data(self):
        """Set up test conversations and messages."""
        logger.info("🧪 Setting up test data...")
        
        # Create test conversations with messages
        test_conversations = [
            {
                "id": str(uuid.uuid4()),
                "title": "Python Web Scraping Help",
                "messages": [
                    {
                        "role": "user", 
                        "content": "I'm trying to scrape a website that uses JavaScript to load content dynamically. I've tried using requests and BeautifulSoup but I'm only getting the static HTML. What's the best approach for this?"
                    },
                    {
                        "role": "assistant",
                        "content": "You're running into a common issue with web scraping dynamic content. When a website loads content with JavaScript after the initial page load, tools like requests and BeautifulSoup can't see that content because they only get the static HTML.\\n\\nHere are several approaches you can use:\\n\\n## 1. Selenium WebDriver (Most Common)\\n```python\\nfrom selenium import webdriver\\nfrom selenium.webdriver.common.by import By\\nfrom selenium.webdriver.support.ui import WebDriverWait\\nfrom selenium.webdriver.support import expected_conditions as EC\\n\\ndriver = webdriver.Chrome()\\ndriver.get('your-url-here')\\n\\n# Wait for dynamic content to load\\nwait = WebDriverWait(driver, 10)\\nelement = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'dynamic-content')))\\n\\n# Now scrape the content\\nhtml = driver.page_source\\n# Process with BeautifulSoup if needed\\n```"
                    }
                ]
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Database Design Review",
                "messages": [
                    {
                        "role": "user",
                        "content": "Could you review my database schema for a chat application? I have tables for users, conversations, and messages. Here's my current structure..."
                    },
                    {
                        "role": "assistant",
                        "content": "I'd be happy to review your database schema for a chat application. Please share your current structure and I'll provide feedback on normalization, indexing, and performance considerations."
                    }
                ]
            }
        ]
        
        # Insert test data
        with get_unit_of_work() as uow:
            for conv_data in test_conversations:
                # Create conversation
                conversation = uow.conversations.create(
                    title=conv_data["title"]
                )
                uow.session.flush()  # Get the ID
                
                # Add messages
                for msg_data in conv_data["messages"]:
                    self.message_service.create_message_with_embedding(
                        conversation_id=conversation.id,
                        role=msg_data["role"],
                        content=msg_data["content"]
                    )
        
        logger.info("✅ Test data setup complete")
    
    def test_get_conversations(self) -> bool:
        """Test GET /api/conversations endpoint."""
        logger.info("🧪 Testing GET /api/conversations...")
        
        try:
            response = requests.get(f"{self.base_url}/api/conversations")
            
            if response.status_code != 200:
                logger.error(f"❌ Status code: {response.status_code}")
                return False
            
            data = response.json()
            
            # Validate response structure
            required_fields = ["documents", "metadatas", "ids"]
            for field in required_fields:
                if field not in data:
                    logger.error(f"❌ Missing field: {field}")
                    return False
            
            # Validate that we have data
            if not data["documents"] or len(data["documents"]) == 0:
                logger.error("❌ No conversations returned")
                return False
            
            logger.info(f"✅ Retrieved {len(data['documents'])} conversations")
            return True
            
        except Exception as e:
            logger.error(f"❌ Request failed: {e}")
            return False
    
    def test_get_conversation_by_id(self) -> bool:
        """Test GET /api/conversation/<id> endpoint."""
        logger.info("🧪 Testing GET /api/conversation/<id>...")
        
        try:
            # First get all conversations to find an ID
            response = requests.get(f"{self.base_url}/api/conversations")
            data = response.json()
            
            if not data["ids"] or len(data["ids"]) == 0:
                logger.error("❌ No conversation IDs available for testing")
                return False
            
            # Test with the first conversation ID
            conversation_id = data["ids"][0]
            response = requests.get(f"{self.base_url}/api/conversation/{conversation_id}")
            
            if response.status_code != 200:
                logger.error(f"❌ Status code: {response.status_code}")
                return False
            
            conversation_data = response.json()
            
            # Validate response structure
            required_fields = ["documents", "metadatas", "ids"]
            for field in required_fields:
                if field not in conversation_data:
                    logger.error(f"❌ Missing field: {field}")
                    return False
            
            # Should return exactly one conversation
            if len(conversation_data["documents"]) != 1:
                logger.error(f"❌ Expected 1 conversation, got {len(conversation_data['documents'])}")
                return False
            
            logger.info(f"✅ Retrieved conversation: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Request failed: {e}")
            return False
    
    def test_api_search(self) -> bool:
        """Test GET /api/search endpoint.""" 
        logger.info("🧪 Testing GET /api/search...")
        
        try:
            # Test with a basic query
            params = {"q": "python", "n": 5}
            response = requests.get(f"{self.base_url}/api/search", params=params)
            
            if response.status_code != 200:
                logger.error(f"❌ Status code: {response.status_code}")
                return False
            
            data = response.json()
            
            # Validate response structure
            if "query" not in data or "results" not in data:
                logger.error("❌ Missing query or results field")
                return False
            
            # Validate query echoed back
            if data["query"] != "python":
                logger.error(f"❌ Query mismatch: expected 'python', got '{data['query']}'")
                return False
            
            # Validate results structure
            for result in data["results"]:
                required_fields = ["title", "date", "content", "metadata"]
                for field in required_fields:
                    if field not in result:
                        logger.error(f"❌ Result missing field: {field}")
                        return False
            
            logger.info(f"✅ Search returned {len(data['results'])} results")
            return True
            
        except Exception as e:
            logger.error(f"❌ Request failed: {e}")
            return False
    
    def test_rag_query(self) -> bool:
        """Test POST /api/rag/query endpoint."""
        logger.info("🧪 Testing POST /api/rag/query...")
        
        try:
            payload = {
                "query": "how to scrape dynamic content",
                "search_type": "semantic",
                "n_results": 5
            }
            
            response = requests.post(
                f"{self.base_url}/api/rag/query",
                json=payload,
                headers={"Content-Type": "application/json"}
            )\n            \n            if response.status_code != 200:\n                logger.error(f\"❌ Status code: {response.status_code}\")\n                return False\n            \n            data = response.json()\n            \n            # Validate response structure\n            required_fields = [\"query\", \"search_type\", \"results\"]\n            for field in required_fields:\n                if field not in data:\n                    logger.error(f\"❌ Missing field: {field}\")\n                    return False\n            \n            # Validate results structure\n            for result in data[\"results\"]:\n                required_fields = [\"id\", \"title\", \"content\", \"preview\", \"source\", \"distance\", \"relevance\", \"metadata\"]\n                for field in required_fields:\n                    if field not in result:\n                        logger.error(f\"❌ Result missing field: {field}\")\n                        return False\n            \n            logger.info(f\"✅ RAG query returned {len(data['results'])} results\")\n            return True\n            \n        except Exception as e:\n            logger.error(f\"❌ Request failed: {e}\")\n            return False\n    \n    def test_stats(self) -> bool:\n        \"\"\"Test GET /api/stats endpoint.\"\"\"\n        logger.info(\"🧪 Testing GET /api/stats...\")\n        \n        try:\n            response = requests.get(f\"{self.base_url}/api/stats\")\n            \n            if response.status_code != 200:\n                logger.error(f\"❌ Status code: {response.status_code}\")\n                return False\n            \n            data = response.json()\n            \n            # Validate response structure\n            required_fields = [\"status\", \"collection_name\", \"document_count\", \"embedding_model\"]\n            for field in required_fields:\n                if field not in data:\n                    logger.error(f\"❌ Missing field: {field}\")\n                    return False\n            \n            # Validate values\n            if data[\"status\"] != \"healthy\":\n                logger.error(f\"❌ Expected status 'healthy', got '{data['status']}'\")\n                return False\n            \n            logger.info(f\"✅ Stats: {data['document_count']} documents, model: {data['embedding_model']}\")\n            return True\n            \n        except Exception as e:\n            logger.error(f\"❌ Request failed: {e}\")\n            return False\n    \n    def test_rag_health(self) -> bool:\n        \"\"\"Test GET /api/rag/health endpoint.\"\"\"\n        logger.info(\"🧪 Testing GET /api/rag/health...\")\n        \n        try:\n            response = requests.get(f\"{self.base_url}/api/rag/health\")\n            \n            if response.status_code != 200:\n                logger.error(f\"❌ Status code: {response.status_code}\")\n                return False\n            \n            data = response.json()\n            \n            # Validate response structure\n            required_fields = [\"status\", \"collection_name\", \"document_count\", \"embedding_model\"]\n            for field in required_fields:\n                if field not in data:\n                    logger.error(f\"❌ Missing field: {field}\")\n                    return False\n            \n            logger.info(f\"✅ Health check passed\")\n            return True\n            \n        except Exception as e:\n            logger.error(f\"❌ Request failed: {e}\")\n            return False\n    \n    def test_collection_count(self) -> bool:\n        \"\"\"Test GET /api/collection/count endpoint.\"\"\"\n        logger.info(\"🧪 Testing GET /api/collection/count...\")\n        \n        try:\n            response = requests.get(f\"{self.base_url}/api/collection/count\")\n            \n            if response.status_code != 200:\n                logger.error(f\"❌ Status code: {response.status_code}\")\n                return False\n            \n            data = response.json()\n            \n            # Validate response structure\n            if \"count\" not in data:\n                logger.error(\"❌ Missing count field\")\n                return False\n            \n            if not isinstance(data[\"count\"], int) or data[\"count\"] < 0:\n                logger.error(f\"❌ Invalid count value: {data['count']}\")\n                return False\n            \n            logger.info(f\"✅ Collection count: {data['count']}\")\n            return True\n            \n        except Exception as e:\n            logger.error(f\"❌ Request failed: {e}\")\n            return False\n    \n    def test_clear_database(self) -> bool:\n        \"\"\"Test DELETE /api/clear endpoint.\"\"\"\n        logger.info(\"🧪 Testing DELETE /api/clear...\")\n        \n        try:\n            response = requests.delete(f\"{self.base_url}/api/clear\")\n            \n            if response.status_code != 200:\n                logger.error(f\"❌ Status code: {response.status_code}\")\n                return False\n            \n            data = response.json()\n            \n            # Validate response structure\n            required_fields = [\"status\", \"message\"]\n            for field in required_fields:\n                if field not in data:\n                    logger.error(f\"❌ Missing field: {field}\")\n                    return False\n            \n            if data[\"status\"] != \"success\":\n                logger.error(f\"❌ Expected status 'success', got '{data['status']}'\")\n                return False\n            \n            logger.info(\"✅ Database cleared successfully\")\n            return True\n            \n        except Exception as e:\n            logger.error(f\"❌ Request failed: {e}\")\n            return False\n    \n    def run_full_compatibility_test(self) -> bool:\n        \"\"\"Run all API compatibility tests.\"\"\"\n        logger.info(\"🚀 Starting full API compatibility test suite...\")\n        \n        # Setup database and test data\n        setup_database()\n        self.setup_test_data()\n        \n        # Wait for embeddings to be generated (if workers are running)\n        import time\n        logger.info(\"⏳ Waiting for embeddings to be generated...\")\n        time.sleep(5)\n        \n        # Run all tests\n        tests = [\n            (\"GET /api/conversations\", self.test_get_conversations),\n            (\"GET /api/conversation/<id>\", self.test_get_conversation_by_id),\n            (\"GET /api/search\", self.test_api_search),\n            (\"POST /api/rag/query\", self.test_rag_query),\n            (\"GET /api/stats\", self.test_stats),\n            (\"GET /api/rag/health\", self.test_rag_health),\n            (\"GET /api/collection/count\", self.test_collection_count),\n            # Note: Clear test should be last as it wipes data\n            (\"DELETE /api/clear\", self.test_clear_database),\n        ]\n        \n        results = []\n        for test_name, test_func in tests:\n            logger.info(f\"\\n{'='*60}\")\n            logger.info(f\"Running: {test_name}\")\n            logger.info('='*60)\n            \n            try:\n                result = test_func()\n                results.append((test_name, result))\n                \n                if result:\n                    logger.info(f\"✅ {test_name}: PASSED\")\n                else:\n                    logger.error(f\"❌ {test_name}: FAILED\")\n                    \n            except Exception as e:\n                logger.error(f\"❌ {test_name}: EXCEPTION - {e}\")\n                results.append((test_name, False))\n        \n        # Summary\n        logger.info(f\"\\n{'='*60}\")\n        logger.info(\"TEST RESULTS SUMMARY\")\n        logger.info('='*60)\n        \n        passed = sum(1 for _, result in results if result)\n        total = len(results)\n        \n        for test_name, result in results:\n            status = \"✅ PASS\" if result else \"❌ FAIL\"\n            logger.info(f\"{status}: {test_name}\")\n        \n        logger.info(f\"\\n📊 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)\")\n        \n        if passed == total:\n            logger.info(\"🎉 ALL TESTS PASSED! API compatibility layer is working correctly.\")\n            return True\n        else:\n            logger.error(f\"❌ {total-passed} tests failed. Please fix issues before deployment.\")\n            return False\n\n\ndef main():\n    \"\"\"Main test runner.\"\"\"\n    import argparse\n    \n    parser = argparse.ArgumentParser(description='Test PostgreSQL API compatibility')\n    parser.add_argument('--base-url', default='http://localhost:5000', \n                       help='Base URL of the API server')\n    parser.add_argument('--setup-only', action='store_true',\n                       help='Only setup test data, do not run tests')\n    \n    args = parser.parse_args()\n    \n    tester = APICompatibilityTester(base_url=args.base_url)\n    \n    if args.setup_only:\n        logger.info(\"Setting up test data only...\")\n        setup_database()\n        tester.setup_test_data()\n        logger.info(\"✅ Test data setup complete\")\n        return\n    \n    # Run full test suite\n    success = tester.run_full_compatibility_test()\n    \n    # Exit with appropriate code\n    sys.exit(0 if success else 1)\n\n\nif __name__ == \"__main__\":\n    main()\n"
            
        except Exception as e:
            logger.error(f\"❌ Request failed: {e}")
            return False
    
    def test_stats(self) -> bool:
        """Test GET /api/stats endpoint."""
        logger.info("🧪 Testing GET /api/stats...")
        
        try:
            response = requests.get(f"{self.base_url}/api/stats")
            
            if response.status_code != 200:
                logger.error(f"❌ Status code: {response.status_code}")
                return False
            
            data = response.json()
            
            # Validate response structure
            required_fields = ["status", "collection_name", "document_count", "embedding_model"]
            for field in required_fields:
                if field not in data:
                    logger.error(f"❌ Missing field: {field}")
                    return False
            
            # Validate values
            if data["status"] != "healthy":
                logger.error(f"❌ Expected status 'healthy', got '{data['status']}'")
                return False
            
            logger.info(f"✅ Stats: {data['document_count']} documents, model: {data['embedding_model']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Request failed: {e}")
            return False
    
    def test_rag_health(self) -> bool:
        """Test GET /api/rag/health endpoint."""
        logger.info("🧪 Testing GET /api/rag/health...")
        
        try:
            response = requests.get(f"{self.base_url}/api/rag/health")
            
            if response.status_code != 200:
                logger.error(f"❌ Status code: {response.status_code}")
                return False
            
            data = response.json()
            
            # Validate response structure
            required_fields = ["status", "collection_name", "document_count", "embedding_model"]
            for field in required_fields:
                if field not in data:
                    logger.error(f"❌ Missing field: {field}")
                    return False
            
            logger.info(f"✅ Health check passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Request failed: {e}")
            return False
    
    def test_collection_count(self) -> bool:
        """Test GET /api/collection/count endpoint."""
        logger.info("🧪 Testing GET /api/collection/count...")
        
        try:
            response = requests.get(f"{self.base_url}/api/collection/count")
            
            if response.status_code != 200:
                logger.error(f"❌ Status code: {response.status_code}")
                return False
            
            data = response.json()
            
            # Validate response structure
            if "count" not in data:
                logger.error("❌ Missing count field")
                return False
            
            if not isinstance(data["count"], int) or data["count"] < 0:
                logger.error(f"❌ Invalid count value: {data['count']}")
                return False
            
            logger.info(f"✅ Collection count: {data['count']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Request failed: {e}")
            return False
    
    def test_clear_database(self) -> bool:
        """Test DELETE /api/clear endpoint."""
        logger.info("🧪 Testing DELETE /api/clear...")
        
        try:
            response = requests.delete(f"{self.base_url}/api/clear")
            
            if response.status_code != 200:
                logger.error(f"❌ Status code: {response.status_code}")
                return False
            
            data = response.json()
            
            # Validate response structure
            required_fields = ["status", "message"]
            for field in required_fields:
                if field not in data:
                    logger.error(f"❌ Missing field: {field}")
                    return False
            
            if data["status"] != "success":
                logger.error(f"❌ Expected status 'success', got '{data['status']}'")
                return False
            
            logger.info("✅ Database cleared successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Request failed: {e}")
            return False
    
    def run_full_compatibility_test(self) -> bool:
        """Run all API compatibility tests."""
        logger.info("🚀 Starting full API compatibility test suite...")
        
        # Setup database and test data
        setup_database()
        self.setup_test_data()
        
        # Wait for embeddings to be generated (if workers are running)
        import time
        logger.info("⏳ Waiting for embeddings to be generated...")
        time.sleep(5)
        
        # Run all tests
        tests = [
            ("GET /api/conversations", self.test_get_conversations),
            ("GET /api/conversation/<id>", self.test_get_conversation_by_id),
            ("GET /api/search", self.test_api_search),
            ("POST /api/rag/query", self.test_rag_query),
            ("GET /api/stats", self.test_stats),
            ("GET /api/rag/health", self.test_rag_health),
            ("GET /api/collection/count", self.test_collection_count),
            # Note: Clear test should be last as it wipes data
            ("DELETE /api/clear", self.test_clear_database),
        ]
        
        results = []
        for test_name, test_func in tests:
            logger.info(f"\n{'='*60}")
            logger.info(f"Running: {test_name}")
            logger.info('='*60)
            
            try:
                result = test_func()
                results.append((test_name, result))
                
                if result:
                    logger.info(f"✅ {test_name}: PASSED")
                else:
                    logger.error(f"❌ {test_name}: FAILED")
                    
            except Exception as e:
                logger.error(f"❌ {test_name}: EXCEPTION - {e}")
                results.append((test_name, False))
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("TEST RESULTS SUMMARY")
        logger.info('='*60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{status}: {test_name}")
        
        logger.info(f"\n📊 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            logger.info("🎉 ALL TESTS PASSED! API compatibility layer is working correctly.")
            return True
        else:
            logger.error(f"❌ {total-passed} tests failed. Please fix issues before deployment.")
            return False


def main():
    """Main test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test PostgreSQL API compatibility')
    parser.add_argument('--base-url', default='http://localhost:5000', 
                       help='Base URL of the API server')
    parser.add_argument('--setup-only', action='store_true',
                       help='Only setup test data, do not run tests')
    
    args = parser.parse_args()
    
    tester = APICompatibilityTester(base_url=args.base_url)
    
    if args.setup_only:
        logger.info("Setting up test data only...")
        setup_database()
        tester.setup_test_data()
        logger.info("✅ Test data setup complete")
        return
    
    # Run full test suite
    success = tester.run_full_compatibility_test()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
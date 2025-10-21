"""
Golden Response Snapshots

These are frozen snapshots of actual API responses that must be preserved
during the migration. These serve as reference implementations and regression tests.

DO NOT MODIFY these snapshots unless you're absolutely certain the frontend
can handle the changes.
"""

# Sample response for GET /api/conversations
API_CONVERSATIONS_SAMPLE = {
    "conversations": [
        {
            "id": "chatgpt-chat-0",
            "title": "Python Web Scraping Help",
            "preview": "I'm trying to scrape a website that uses JavaScript to load content dynamically. I've tried using requests and BeautifulSoup but I'm only getting the static HTML...",
            "date": "2025-01-15T14:30:22Z",
            "source": "chatgpt"
        },
        {
            "id": "claude-chat-1", 
            "title": "Database Design Review",
            "preview": "Could you review my database schema for a chat application? I have tables for users, conversations, and messages. Here's my current structure...",
            "date": "2025-01-14T09:15:45Z",
            "source": "claude"
        }
    ],
    "pagination": {
        "page": 1,
        "limit": 50,
        "total": 2,
        "has_next": False,
        "has_prev": False
    }
}

# Sample response for GET /api/conversation/<id>
API_CONVERSATION_DETAIL_SAMPLE = {
    "id": "chatgpt-chat-0",
    "title": "Python Web Scraping Help",
    "source": "chatgpt",
    "date": "2025-01-15T14:30:22Z",
    "assistant_name": "ChatGPT",
    "messages": [
        {
            "id": "user-1",
            "role": "user",
            "content": "I'm trying to scrape a website that uses JavaScript to load content dynamically. I've tried using requests and BeautifulSoup but I'm only getting the static HTML. What's the best approach for this?",
            "timestamp": "2025-01-15 14:30:22"
        },
        {
            "id": "assistant-1",
            "role": "assistant", 
            "content": "You're running into a common issue with web scraping dynamic content. When a website loads content with JavaScript after the initial page load, tools like requests and BeautifulSoup can't see that content because they only get the static HTML.\n\nHere are several approaches you can use:\n\n## 1. Selenium WebDriver (Most Common)\n```python\nfrom selenium import webdriver\nfrom selenium.webdriver.common.by import By\nfrom selenium.webdriver.support.ui import WebDriverWait\nfrom selenium.webdriver.support import expected_conditions as EC\n\ndriver = webdriver.Chrome()\ndriver.get('your-url-here')\n\n# Wait for dynamic content to load\nwait = WebDriverWait(driver, 10)\nelement = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'dynamic-content')))\n\n# Now scrape the content\nhtml = driver.page_source\n# Process with BeautifulSoup if needed\n```",
            "timestamp": "2025-01-15 14:31:05"
        }
    ]
}

# Sample response for GET /api/search
API_SEARCH_SAMPLE = {
    "query": "python web scraping",
    "results": [
        {
            "title": "Python Web Scraping Help",
            "date": "2025-01-15T14:30:22Z",
            "content": "I'm trying to scrape a website that uses JavaScript to load content dynamically. I've tried using requests and BeautifulSoup but I'm only getting the static HTML. What's the best approach for this? You're running into a common issue with web scraping dynamic content...",
            "metadata": {
                "id": "chatgpt-chat-0",
                "title": "Python Web Scraping Help",
                "source": "chatgpt",
                "earliest_ts": "2025-01-15T14:30:22Z",
                "latest_ts": "2025-01-15T14:35:10Z",
                "message_count": 4,
                "is_chunk": False
            }
        }
    ]
}

# Sample response for POST /api/rag/query
API_RAG_QUERY_SAMPLE = {
    "query": "how to scrape dynamic content",
    "search_type": "semantic",
    "results": [
        {
            "id": "chatgpt-chat-0",
            "title": "Python Web Scraping Help",
            "content": "I'm trying to scrape a website that uses JavaScript to load content dynamically. I've tried using requests and BeautifulSoup but I'm only getting the static HTML. What's the best approach for this? You're running into a common issue with web scraping dynamic content. When a website loads content with JavaScript after the initial page load, tools like requests and BeautifulSoup can't see that content because they only get the static HTML.",
            "preview": "I'm trying to scrape a website that uses JavaScript to load content dynamically. I've tried using requests and BeautifulSoup but I'm only getting the static HTML. What's the best approach for this? You're running into a common issue with web scraping dynamic content. When a website loads content with JavaScript after the initial page load, tools like requests and BeautifulSoup can't see that content...",
            "source": "chatgpt",
            "distance": 0.15,
            "relevance": 0.85,
            "metadata": {
                "id": "chatgpt-chat-0",
                "title": "Python Web Scraping Help",
                "source": "chatgpt",
                "earliest_ts": "2025-01-15T14:30:22Z",
                "latest_ts": "2025-01-15T14:35:10Z",
                "message_count": 4,
                "is_chunk": False
            }
        }
    ]
}

# Sample response for GET /api/stats
API_STATS_SAMPLE = {
    "status": "healthy",
    "collection_name": "chat_history",
    "document_count": 1247,
    "embedding_model": "all-MiniLM-L6-v2"
}

# Sample response for GET /api/rag/health
API_RAG_HEALTH_HEALTHY_SAMPLE = {
    "status": "healthy",
    "collection_name": "chat_history",
    "document_count": 1247,
    "embedding_model": "all-MiniLM-L6-v2"
}

API_RAG_HEALTH_UNHEALTHY_SAMPLE = {
    "status": "unhealthy",
    "error": "ChromaDB connection failed"
}

# Sample response for POST /export_to_openwebui/<id>
API_EXPORT_SUCCESS_SAMPLE = {
    "success": True,
    "message": "Conversation exported to OpenWebUI successfully"
}

API_EXPORT_ERROR_SAMPLE = {
    "success": False,
    "error": "OpenWebUI API error: 500",
    "detail": "Internal server error from OpenWebUI API"
}

# Sample response for POST /clear_db
API_CLEAR_DB_SUCCESS_SAMPLE = {
    "status": "success",
    "message": "Database cleared successfully"
}

API_CLEAR_DB_ERROR_SAMPLE = {
    "status": "error",
    "message": "Failed to clear database: Permission denied"
}

# Sample error responses
API_ERROR_NOT_FOUND_SAMPLE = {
    "error": "Conversation not found"
}

API_ERROR_BAD_REQUEST_SAMPLE = {
    "error": "Query text is required"
}

API_ERROR_INTERNAL_SERVER_SAMPLE = {
    "error": "Internal server error occurred"
}

# Registry of all golden responses for automated testing
GOLDEN_RESPONSES = {
    "GET /api/conversations": API_CONVERSATIONS_SAMPLE,
    "GET /api/conversation/<id>": API_CONVERSATION_DETAIL_SAMPLE,
    "GET /api/search": API_SEARCH_SAMPLE,
    "POST /api/rag/query": API_RAG_QUERY_SAMPLE,
    "GET /api/stats": API_STATS_SAMPLE,
    "GET /api/rag/health (healthy)": API_RAG_HEALTH_HEALTHY_SAMPLE,
    "GET /api/rag/health (unhealthy)": API_RAG_HEALTH_UNHEALTHY_SAMPLE,
    "POST /export_to_openwebui/<id> (success)": API_EXPORT_SUCCESS_SAMPLE,
    "POST /export_to_openwebui/<id> (error)": API_EXPORT_ERROR_SAMPLE,
    "POST /clear_db (success)": API_CLEAR_DB_SUCCESS_SAMPLE,
    "POST /clear_db (error)": API_CLEAR_DB_ERROR_SAMPLE,
    "ERROR (404)": API_ERROR_NOT_FOUND_SAMPLE,
    "ERROR (400)": API_ERROR_BAD_REQUEST_SAMPLE,
    "ERROR (500)": API_ERROR_INTERNAL_SERVER_SAMPLE,
}


def validate_all_golden_responses():
    """
    Validate all golden responses against the API contract.
    This should be run as part of CI to ensure contract compliance.
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from api.contracts.api_contract import APIContract
    
    results = {}
    for endpoint, response in GOLDEN_RESPONSES.items():
        # Map endpoint names to contract schema keys
        schema_key = endpoint.replace(" (healthy)", "").replace(" (unhealthy)", "").replace(" (success)", "").replace(" (error)", "")
        if schema_key.startswith("ERROR"):
            schema_key = "ERROR"
        
        is_valid = APIContract.validate_response(schema_key, response)
        results[endpoint] = is_valid
        
        if not is_valid:
            print(f"❌ Golden response validation failed for: {endpoint}")
        else:
            print(f"✅ Golden response valid for: {endpoint}")
    
    all_valid = all(results.values())
    print(f"\n{'✅ All golden responses are valid!' if all_valid else '❌ Some golden responses are invalid!'}")
    return all_valid


if __name__ == "__main__":
    validate_all_golden_responses()
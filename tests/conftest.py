"""
Test configuration and fixtures
"""
import pytest
import json
import os
from typing import Dict, Any
import tempfile
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from api.contracts.api_contract import APIContract


@pytest.fixture(scope="session")
def app():
    """Create application for testing"""
    # Use test configuration
    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        # Force legacy mode for consistent testing
        "USE_PG_SINGLE_STORE": False
    })
    
    # Create a test context
    with app.app_context():
        yield app


@pytest.fixture(scope="session") 
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def test_data():
    """Sample test data for API testing"""
    return {
        "conversations": [
            {
                "id": "test-conv-1",
                "title": "Test Conversation 1",
                "content": "This is a test conversation with multiple messages between a user and assistant.",
                "metadata": {
                    "id": "test-conv-1",
                    "title": "Test Conversation 1",
                    "source": "chatgpt",
                    "earliest_ts": "2025-01-01T10:00:00Z"
                }
            },
            {
                "id": "test-conv-2", 
                "title": "Test Conversation 2",
                "content": "Another test conversation with different content for search testing.",
                "metadata": {
                    "id": "test-conv-2",
                    "title": "Test Conversation 2", 
                    "source": "claude",
                    "earliest_ts": "2025-01-02T15:30:00Z"
                }
            }
        ],
        "messages": [
            {"id": "user-1", "role": "user", "content": "Hello, how are you?", "timestamp": "2025-01-01T10:00:00Z"},
            {"id": "assistant-1", "role": "assistant", "content": "I'm doing well, thank you for asking!", "timestamp": "2025-01-01T10:01:00Z"},
            {"id": "user-2", "role": "user", "content": "What can you help me with?", "timestamp": "2025-01-01T10:02:00Z"},
            {"id": "assistant-2", "role": "assistant", "content": "I can help with various tasks...", "timestamp": "2025-01-01T10:03:00Z"}
        ],
        "search_query": "test conversation",
        "rag_query": {
            "query": "help with tasks",
            "n_results": 5,
            "search_type": "semantic"
        }
    }


@pytest.fixture
def golden_responses_dir():
    """Directory for golden response files"""
    golden_dir = os.path.join(os.path.dirname(__file__), "golden_responses")
    os.makedirs(golden_dir, exist_ok=True)
    return golden_dir


@pytest.fixture
def contract_validator():
    """Contract validation fixture"""
    return APIContract


def save_golden_response(response_data: Dict[str, Any], endpoint: str, golden_dir: str):
    """Helper to save golden responses"""
    # Clean endpoint name for filename
    filename = endpoint.replace("/", "_").replace("<", "").replace(">", "").replace(" ", "_")
    filepath = os.path.join(golden_dir, f"{filename}.json")
    
    with open(filepath, 'w') as f:
        json.dump(response_data, f, indent=2, sort_keys=True)


def load_golden_response(endpoint: str, golden_dir: str) -> Dict[str, Any]:
    """Helper to load golden responses"""
    filename = endpoint.replace("/", "_").replace("<", "").replace(">", "").replace(" ", "_")
    filepath = os.path.join(golden_dir, f"{filename}.json")
    
    if not os.path.exists(filepath):
        return None
        
    with open(filepath, 'r') as f:
        return json.load(f)


@pytest.fixture
def golden_response_helpers(golden_responses_dir):
    """Provide golden response helper functions"""
    return {
        "save": lambda data, endpoint: save_golden_response(data, endpoint, golden_responses_dir),
        "load": lambda endpoint: load_golden_response(endpoint, golden_responses_dir),
        "dir": golden_responses_dir
    }


@pytest.fixture(scope="session")
def performance_baseline():
    """Performance baseline metrics"""
    return {
        "response_time_thresholds": {
            "GET /api/conversations": 2.0,  # seconds
            "GET /api/conversation/<id>": 1.0,
            "GET /api/search": 3.0,
            "POST /api/rag/query": 5.0,
            "GET /api/stats": 0.5,
            "GET /api/rag/health": 0.5
        },
        "content_length_thresholds": {
            "GET /api/conversations": 10000,  # bytes
            "GET /api/conversation/<id>": 50000,
            "GET /api/search": 20000,
            "POST /api/rag/query": 30000
        }
    }


# Marks for organizing tests
pytestmark = pytest.mark.contract
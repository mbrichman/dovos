"""
Utilities for generating synthetic but realistic test data.

These utilities create fake but structurally valid data that can be used
in golden responses without exposing real user data.
"""

from uuid import uuid4
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import random


class SyntheticDataGenerator:
    """Generate realistic synthetic data for testing."""
    
    # Generic topics for synthetic conversations
    GENERIC_TOPICS = [
        "How to improve productivity",
        "Best practices for Python development",
        "Database optimization techniques",
        "Understanding machine learning basics",
        "Web development frameworks comparison",
        "API design principles",
        "Testing strategies and approaches",
        "Cloud infrastructure setup",
        "Data analysis workflows",
        "Security considerations in applications",
    ]
    
    # Generic assistant responses
    GENERIC_RESPONSES = [
        "That's a great question. Here are the key considerations: 1) Performance optimization 2) Best practices 3) Common pitfalls to avoid.",
        "There are several approaches to this problem. The most common solutions involve: traditional methods and modern approaches.",
        "This is an important topic in the field. Let me break down the essential concepts and practical applications.",
        "There's quite a bit to cover here. First, let's establish the fundamentals, then we can explore more advanced concepts.",
        "This depends on your specific use case. Generally speaking, you'll want to consider: scalability, maintainability, and performance.",
    ]
    
    # Generic sources
    SOURCES = ["chatgpt", "claude", "openwebui"]
    
    @staticmethod
    def fake_uuid() -> str:
        """Generate a fake UUID."""
        return str(uuid4())
    
    @staticmethod
    def fake_timestamp(days_back: int = 30) -> str:
        """Generate a fake ISO timestamp within the last N days."""
        offset = random.randint(0, days_back)
        timestamp = datetime.utcnow() - timedelta(days=offset)
        return timestamp.isoformat() + "Z"
    
    @staticmethod
    def fake_conversation_title() -> str:
        """Generate a generic but realistic conversation title."""
        return random.choice(SyntheticDataGenerator.GENERIC_TOPICS)
    
    @staticmethod
    def fake_user_message() -> str:
        """Generate a generic user question."""
        questions = [
            "Can you explain this concept?",
            "What are the best practices for this?",
            "How do I implement this?",
            "What are the common pitfalls?",
            "Could you provide an example?",
        ]
        return random.choice(questions)
    
    @staticmethod
    def fake_assistant_response() -> str:
        """Generate a generic assistant response."""
        return random.choice(SyntheticDataGenerator.GENERIC_RESPONSES)
    
    @staticmethod
    def fake_source() -> str:
        """Generate a fake source platform."""
        return random.choice(SyntheticDataGenerator.SOURCES)
    
    @staticmethod
    def fake_model() -> str:
        """Generate a fake model name."""
        models = ["gpt-4", "claude-3-opus", "mistral-7b", "neural-chat"]
        return random.choice(models)
    
    @staticmethod
    def fake_search_score() -> float:
        """Generate a realistic search relevance score."""
        return round(random.uniform(0.65, 1.0), 3)
    
    @staticmethod
    def fake_embedding_model() -> str:
        """Generate a fake embedding model name."""
        models = ["all-MiniLM-L6-v2", "sentence-transformers/paraphrase-MiniLM-L6-v2", "bgem3-base"]
        return random.choice(models)


def generate_conversation_pair(include_metadata: bool = True) -> Dict[str, Any]:
    """
    Generate a synthetic user-assistant conversation pair.
    
    Args:
        include_metadata: Whether to include metadata like source and date
        
    Returns:
        Dict with conversation structure
    """
    user_msg = SyntheticDataGenerator.fake_user_message()
    assistant_msg = SyntheticDataGenerator.fake_assistant_response()
    
    conversation = {
        "id": SyntheticDataGenerator.fake_uuid(),
        "title": SyntheticDataGenerator.fake_conversation_title(),
        "messages": [
            {
                "role": "user",
                "content": user_msg,
                "timestamp": SyntheticDataGenerator.fake_timestamp(30)
            },
            {
                "role": "assistant",
                "content": assistant_msg,
                "timestamp": SyntheticDataGenerator.fake_timestamp(29)
            }
        ]
    }
    
    if include_metadata:
        conversation["source"] = SyntheticDataGenerator.fake_source()
        conversation["model"] = SyntheticDataGenerator.fake_model()
    
    return conversation


def generate_search_result() -> Dict[str, Any]:
    """Generate a synthetic search result."""
    return {
        "id": SyntheticDataGenerator.fake_uuid(),
        "content": SyntheticDataGenerator.fake_assistant_response(),
        "score": SyntheticDataGenerator.fake_search_score(),
        "metadata": {
            "source": SyntheticDataGenerator.fake_source(),
            "date": SyntheticDataGenerator.fake_timestamp(60)
        }
    }


def generate_conversations_list(count: int = 10) -> List[Dict[str, Any]]:
    """Generate a list of synthetic conversations."""
    return [generate_conversation_pair() for _ in range(count)]


def generate_search_results(count: int = 5) -> List[Dict[str, Any]]:
    """Generate a list of synthetic search results."""
    return [generate_search_result() for _ in range(count)]

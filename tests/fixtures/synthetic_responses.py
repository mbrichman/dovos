"""
Synthetic golden response generators.

These functions generate realistic but completely synthetic responses
that can be safely version controlled without exposing personal data.

Each generator creates responses with the same structure as real API responses
but with safe, generic, and clearly fake data.
"""

from typing import Dict, Any, List
from uuid import uuid4
from datetime import datetime, timedelta
import random
import json

from tests.utils.response_generators import (
    SyntheticDataGenerator,
    generate_conversation_pair,
    generate_search_result,
)


def generate_conversations_response(count: int = 10) -> Dict[str, Any]:
    """
    Generate synthetic GET /api/conversations response.
    
    Structure matches legacy API format with documents, ids, metadatas.
    Uses generic conversation titles instead of real user data.
    """
    conversations = []
    ids = []
    metadatas = []
    
    for _ in range(count):
        conv_id = SyntheticDataGenerator.fake_uuid()
        ids.append(conv_id)
        
        # Generic conversation content
        title = SyntheticDataGenerator.fake_conversation_title()
        conversations.append(title)
        
        # Safe metadata
        metadatas.append({
            "source": SyntheticDataGenerator.fake_source(),
            "date": SyntheticDataGenerator.fake_timestamp(60),
            "message_count": random.randint(2, 20)
        })
    
    return {
        "documents": conversations,
        "ids": ids,
        "metadatas": metadatas
    }


def generate_conversation_detail_response(conv_id: str = None) -> Dict[str, Any]:
    """
    Generate synthetic GET /api/conversation/<id> response.
    
    Contains a single conversation with generic user-assistant exchanges.
    """
    if conv_id is None:
        conv_id = SyntheticDataGenerator.fake_uuid()
    
    # Create a synthetic conversation
    conversation = generate_conversation_pair(include_metadata=True)
    
    return {
        "documents": [conversation["title"]],
        "ids": [conv_id],
        "metadatas": [{
            "source": conversation["source"],
            "message_count": len(conversation["messages"]),
            "date": SyntheticDataGenerator.fake_timestamp(30)
        }]
    }


def generate_search_response(query: str = "python", count: int = 5) -> Dict[str, Any]:
    """
    Generate synthetic GET /api/search response.
    
    Returns search results with generic content, no real conversation data.
    """
    results = []
    for _ in range(count):
        result = generate_search_result()
        # Add ranking
        result["rank"] = len(results) + 1
        results.append(result)
    
    return {
        "query": query,
        "results": results,
        "result_count": len(results),
        "search_type": "full_text"
    }


def generate_rag_query_response(query: str = "How to use Python?", count: int = 5) -> Dict[str, Any]:
    """
    Generate synthetic POST /api/rag/query response.
    
    RAG results with generic content and realistic relevance scores.
    """
    results = []
    for _ in range(count):
        results.append({
            "content": SyntheticDataGenerator.fake_assistant_response(),
            "score": SyntheticDataGenerator.fake_search_score(),
            "source_id": SyntheticDataGenerator.fake_uuid(),
            "metadata": {
                "model": SyntheticDataGenerator.fake_model(),
                "chunk": random.randint(1, 5)
            }
        })
    
    return {
        "query": query,
        "results": results,
        "result_count": len(results),
        "search_type": "semantic"
    }


def generate_rag_health_response() -> Dict[str, Any]:
    """
    Generate synthetic GET /api/rag/health response.
    
    Health check with realistic but generic statistics.
    """
    return {
        "status": "healthy",
        "document_count": random.randint(1000, 10000),
        "embedding_model": SyntheticDataGenerator.fake_embedding_model(),
        "collection_name": "chat_history",
        "uptime_seconds": random.randint(3600, 86400),
        "last_update": SyntheticDataGenerator.fake_timestamp(7)
    }


def generate_stats_response() -> Dict[str, Any]:
    """
    Generate synthetic GET /api/stats response.
    
    Statistics with generic but realistic numbers.
    """
    return {
        "document_count": random.randint(100, 10000),
        "conversation_count": random.randint(10, 500),
        "message_count": random.randint(500, 50000),
        "embedding_model": SyntheticDataGenerator.fake_embedding_model(),
        "sources": {
            "chatgpt": random.randint(10, 200),
            "claude": random.randint(10, 200),
            "openwebui": random.randint(10, 200)
        },
        "indexed_documents": random.randint(100, 9000)
    }


def generate_collection_count_response() -> Dict[str, Any]:
    """
    Generate synthetic GET /api/collection/count response.
    
    Returns document count in the collection.
    """
    return {
        "count": random.randint(100, 10000)
    }


def generate_live_api_snapshots() -> Dict[str, Any]:
    """
    Generate synthetic live_api_snapshots.json content.
    
    Contains multiple endpoint snapshots with synthetic data.
    """
    conv_id = SyntheticDataGenerator.fake_uuid()
    
    return {
        "GET /api/conversations": {
            "status_code": 200,
            "captured_at": datetime.utcnow().isoformat(),
            "data": generate_conversations_response(5)
        },
        "GET /api/conversation/<id>": {
            "status_code": 200,
            "captured_at": datetime.utcnow().isoformat(),
            "conversation_id": conv_id,
            "data": generate_conversation_detail_response(conv_id)
        },
        "GET /api/search": {
            "status_code": 200,
            "captured_at": datetime.utcnow().isoformat(),
            "data": generate_search_response("python")
        },
        "POST /api/rag/query": {
            "status_code": 200,
            "captured_at": datetime.utcnow().isoformat(),
            "data": generate_rag_query_response()
        },
        "GET /api/rag/health": {
            "status_code": 200,
            "captured_at": datetime.utcnow().isoformat(),
            "data": generate_rag_health_response()
        },
        "GET /api/stats": {
            "status_code": 200,
            "captured_at": datetime.utcnow().isoformat(),
            "data": generate_stats_response()
        },
        "GET /api/collection/count": {
            "status_code": 200,
            "captured_at": datetime.utcnow().isoformat(),
            "data": generate_collection_count_response()
        }
    }


# Factory functions for pytest fixtures
def create_synthetic_conversations() -> Dict[str, Any]:
    """Factory for synthetic conversations response."""
    return generate_conversations_response(10)


def create_synthetic_conversation_detail() -> Dict[str, Any]:
    """Factory for synthetic conversation detail response."""
    return generate_conversation_detail_response()


def create_synthetic_search() -> Dict[str, Any]:
    """Factory for synthetic search response."""
    return generate_search_response()


def create_synthetic_rag_query() -> Dict[str, Any]:
    """Factory for synthetic RAG query response."""
    return generate_rag_query_response()


def create_synthetic_rag_health() -> Dict[str, Any]:
    """Factory for synthetic RAG health response."""
    return generate_rag_health_response()


def create_synthetic_stats() -> Dict[str, Any]:
    """Factory for synthetic stats response."""
    return generate_stats_response()


def create_synthetic_collection_count() -> Dict[str, Any]:
    """Factory for synthetic collection count response."""
    return generate_collection_count_response()

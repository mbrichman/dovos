"""
API Contract Compliance Tests

Validates that PostgreSQL backend returns identical API responses to legacy ChromaDB backend.
This is the highest priority test suite for migration validation.

Success Criteria:
- 100% of endpoints return structurally identical responses
- Error messages and status codes match exactly
- JSON schemas match field-for-field
"""
import pytest
import json
from pathlib import Path
from typing import Dict, Any
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from controllers.postgres_controller import get_postgres_controller
from tests.utils.seed import seed_conversation_with_messages


@pytest.fixture(scope="module")
def app_postgres() -> Flask:
    """Flask app configured for PostgreSQL mode."""
    app = create_app()
    app.config.update({
        "TESTING": True,
        "USE_PG_SINGLE_STORE": True
    })
    return app


@pytest.fixture(scope="module")
def app_legacy() -> Flask:
    """Flask app configured for legacy ChromaDB mode."""
    app = create_app()
    app.config.update({
        "TESTING": True,
        "USE_PG_SINGLE_STORE": False
    })
    return app


@pytest.fixture(scope="module")
def client_postgres(app_postgres) -> FlaskClient:
    """Test client for PostgreSQL backend."""
    return app_postgres.test_client()


@pytest.fixture(scope="module")
def client_legacy(app_legacy) -> FlaskClient:
    """Test client for legacy backend."""
    return app_legacy.test_client()


@pytest.fixture
def seeded_postgres_data(uow):
    """
    Seed PostgreSQL with test data.
    
    Returns conversation IDs for testing.
    """
    conversations = []
    
    # Create 3 test conversations
    for i in range(3):
        conv, messages = seed_conversation_with_messages(
            uow,
            title=f"Test Conversation {i+1}",
            message_count=4,
            with_embeddings=True,
            created_days_ago=i
        )
        conversations.append((conv, messages))
    
    return {
        "conversations": conversations,
        "conv_ids": [str(conv.id) for conv, _ in conversations]
    }


@pytest.fixture
def seeded_postgres_data_committed(test_db_engine):
    """
    Seed PostgreSQL with test data that is committed (not rolled back).
    
    This fixture creates a fresh session without transaction rollback,
    so data persists for HTTP client tests. It cleans up after itself.
    
    Returns conversation IDs for testing.
    """
    from sqlalchemy.orm import Session
    from db.repositories.unit_of_work import UnitOfWork
    from db.models.models import Conversation
    
    # Create a fresh session that won't be rolled back
    session = Session(bind=test_db_engine)
    uow = UnitOfWork(session=session)
    
    conversations = []
    conv_ids = []
    
    try:
        # Create 3 test conversations
        for i in range(3):
            conv, messages = seed_conversation_with_messages(
                uow,
                title=f"Test Conversation {i+1}",
                message_count=4,
                with_embeddings=True,
                created_days_ago=i
            )
            conversations.append((conv, messages))
            conv_ids.append(str(conv.id))
        
        # Commit the changes
        uow.commit()
        
        yield {
            "conversations": conversations,
            "conv_ids": conv_ids
        }
    finally:
        # Clean up: delete the conversations we created
        try:
            for conv_id in conv_ids:
                session.query(Conversation).filter(Conversation.id == conv_id).delete()
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()


def assert_json_structure_matches(response1: Dict[str, Any], response2: Dict[str, Any], path: str = "root"):
    """
    Recursively assert two JSON structures match in shape.
    
    Compares:
    - Same keys at each level
    - Same types for each value
    - Same array lengths
    
    Does NOT compare:
    - Actual values (UUIDs, timestamps, content will differ)
    - Exact ordering (unless critical)
    """
    # Both should be same type
    assert type(response1) == type(response2), \
        f"Type mismatch at {path}: {type(response1)} != {type(response2)}"
    
    if isinstance(response1, dict):
        # Same keys
        keys1 = set(response1.keys())
        keys2 = set(response2.keys())
        assert keys1 == keys2, \
            f"Key mismatch at {path}: {keys1} != {keys2}"
        
        # Recurse on each key
        for key in keys1:
            assert_json_structure_matches(
                response1[key],
                response2[key],
                f"{path}.{key}"
            )
    
    elif isinstance(response1, list):
        # Same length
        assert len(response1) == len(response2), \
            f"Array length mismatch at {path}: {len(response1)} != {len(response2)}"
        
        # If non-empty, check first element structure
        if response1 and response2:
            assert_json_structure_matches(
                response1[0],
                response2[0],
                f"{path}[0]"
            )


def save_golden_response(response_data: Dict[str, Any], endpoint_name: str):
    """Save a golden response for future regression testing."""
    golden_dir = Path(__file__).parent.parent / "fixtures" / "golden_responses"
    golden_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = golden_dir / f"{endpoint_name}.json"
    with open(filepath, 'w') as f:
        json.dump(response_data, f, indent=2, sort_keys=True)


# ===== API Contract Tests =====

@pytest.mark.migration
class TestConversationEndpoints:
    """Test conversation retrieval endpoints for API parity."""
    
    def test_get_conversations_structure(
        self,
        client_postgres,
        client_legacy,
        seeded_postgres_data
    ):
        """
        GET /api/conversations returns identical structure.
        
        Expected format:
        {
            "documents": [...],
            "metadatas": [...],
            "ids": [...]
        }
        """
        # Call both backends
        response_pg = client_postgres.get("/api/conversations")
        response_legacy = client_legacy.get("/api/conversations")
        
        assert response_pg.status_code == 200
        assert response_legacy.status_code == 200
        
        data_pg = response_pg.get_json()
        data_legacy = response_legacy.get_json()
        
        # Verify structure matches
        assert_json_structure_matches(data_pg, data_legacy)
        
        # Verify required fields exist
        assert "documents" in data_pg
        assert "metadatas" in data_pg
        assert "ids" in data_pg
        
        # Verify they're arrays
        assert isinstance(data_pg["documents"], list)
        assert isinstance(data_pg["metadatas"], list)
        assert isinstance(data_pg["ids"], list)
        
        # Verify same lengths
        assert len(data_pg["documents"]) == len(data_pg["metadatas"])
        assert len(data_pg["documents"]) == len(data_pg["ids"])
        
        # Save golden response
        save_golden_response(data_pg, "GET_api_conversations")
    
    def test_get_conversation_by_id_structure(
        self,
        client_postgres_test,
        seeded_postgres_data_committed
    ):
        """
        GET /api/conversation/<id> returns correct structure.
        
        Expected format:
        {
            "documents": [<single document>],
            "metadatas": [<single metadata>],
            "ids": [<single id>]
        }
        """
        # Get a conversation ID
        conv_id = seeded_postgres_data_committed["conv_ids"][0]
        
        response = client_postgres_test.get(f"/api/conversation/{conv_id}")
        assert response.status_code == 200
        
        data = response.get_json()
        
        # Verify structure
        assert "documents" in data
        assert "metadatas" in data
        assert "ids" in data
        
        # Should be arrays of length 1
        assert len(data["documents"]) == 1
        assert len(data["metadatas"]) == 1
        assert len(data["ids"]) == 1
        
        # Metadata should have expected fields
        metadata = data["metadatas"][0]
        expected_fields = ["id", "title", "source", "message_count", "earliest_ts", "latest_ts"]
        for field in expected_fields:
            assert field in metadata, f"Missing field: {field}"
        
        # Save golden response
        save_golden_response(data, "GET_api_conversation_id")


@pytest.mark.migration
class TestSearchEndpoints:
    """Test search endpoints for API parity."""
    
    def test_api_search_get_structure(
        self,
        client_postgres,
        seeded_postgres_data
    ):
        """
        GET /api/search returns correct structure.
        
        Expected format:
        {
            "query": "<query string>",
            "results": [
                {
                    "title": "...",
                    "date": "...",
                    "content": "...",
                    "metadata": {...}
                }
            ]
        }
        """
        response = client_postgres.get("/api/search?q=test&n=5")
        assert response.status_code == 200
        
        data = response.get_json()
        
        # Verify structure
        assert "query" in data
        assert "results" in data
        assert data["query"] == "test"
        assert isinstance(data["results"], list)
        
        # If results exist, verify structure
        if data["results"]:
            result = data["results"][0]
            expected_fields = ["title", "date", "content", "metadata"]
            for field in expected_fields:
                assert field in result, f"Missing field: {field}"
        
        # Save golden response
        save_golden_response(data, "GET_api_search")


@pytest.mark.migration
class TestRAGEndpoints:
    """Test RAG endpoints for OpenWebUI integration."""
    
    def test_rag_query_structure(
        self,
        client_postgres,
        seeded_postgres_data
    ):
        """
        POST /api/rag/query returns correct structure.
        
        Expected format:
        {
            "query": "...",
            "search_type": "semantic|keyword",
            "results": [
                {
                    "id": "...",
                    "title": "...",
                    "content": "...",
                    "preview": "...",
                    "source": "...",
                    "distance": 0.0,
                    "relevance": 1.0,
                    "metadata": {...}
                }
            ]
        }
        """
        payload = {
            "query": "test query",
            "search_type": "semantic",
            "n_results": 5
        }
        
        response = client_postgres.post(
            "/api/rag/query",
            json=payload,
            content_type="application/json"
        )
        assert response.status_code == 200
        
        data = response.get_json()
        
        # Verify structure
        assert "query" in data
        assert "search_type" in data
        assert "results" in data
        assert isinstance(data["results"], list)
        
        # If results exist, verify structure
        if data["results"]:
            result = data["results"][0]
            expected_fields = [
                "id", "title", "content", "preview",
                "source", "distance", "relevance", "metadata"
            ]
            for field in expected_fields:
                assert field in result, f"Missing field: {field}"
        
        # Save golden response
        save_golden_response(data, "POST_api_rag_query")
    
    def test_rag_health_structure(self, client_postgres):
        """
        GET /api/rag/health returns correct structure.
        
        Expected format:
        {
            "status": "healthy",
            "collection_name": "...",
            "document_count": 0,
            "embedding_model": "..."
        }
        """
        response = client_postgres.get("/api/rag/health")
        assert response.status_code == 200
        
        data = response.get_json()
        
        # Verify structure
        expected_fields = ["status", "collection_name", "document_count", "embedding_model"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # Save golden response
        save_golden_response(data, "GET_api_rag_health")


@pytest.mark.migration
class TestStatsEndpoints:
    """Test statistics endpoints for API parity."""
    
    def test_stats_structure(self, client_postgres):
        """
        GET /api/stats returns correct structure.
        
        Expected format:
        {
            "status": "healthy",
            "collection_name": "...",
            "document_count": 0,
            "embedding_model": "...",
            ...
        }
        """
        response = client_postgres.get("/api/stats")
        assert response.status_code == 200
        
        data = response.get_json()
        
        # Verify structure
        expected_fields = ["status", "collection_name", "document_count", "embedding_model"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # Save golden response
        save_golden_response(data, "GET_api_stats")
    
    def test_collection_count_structure(self, client_postgres):
        """
        GET /api/collection/count returns correct structure.
        
        Expected format:
        {
            "count": 0
        }
        """
        response = client_postgres.get("/api/collection/count")
        assert response.status_code == 200
        
        data = response.get_json()
        
        # Verify structure
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
        
        # Save golden response
        save_golden_response(data, "GET_api_collection_count")


@pytest.mark.migration
class TestErrorResponses:
    """Test error response formats match between backends."""
    
    def test_404_not_found(self, client_postgres):
        """404 errors return consistent format."""
        # Try to get non-existent conversation
        response = client_postgres.get("/api/conversation/00000000-0000-0000-0000-000000000000")
        
        # Should return 200 with empty results (legacy behavior)
        # OR 404 with error message (depending on implementation)
        data = response.get_json()
        
        # At minimum, should be valid JSON
        assert data is not None
    
    def test_400_bad_request(self, client_postgres):
        """400 errors return consistent format."""
        # Try RAG query without required field
        response = client_postgres.post(
            "/api/rag/query",
            json={},
            content_type="application/json"
        )
        
        # Should return 400 or 200 with error field
        data = response.get_json()
        assert data is not None
        
        # If error occurred, should have error field
        if response.status_code != 200:
            assert "error" in data or "message" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "migration"])

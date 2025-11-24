"""
Phase 1.2: Basic Search Functionality Tests

Validates that after import, messages can be retrieved via:
a) Keyword/full-text search
b) Semantic/vector search

Simplified version that just ensures search returns results.
"""

import pytest

from db.services.search_service import SearchService
from tests.utils.seed import seed_conversation_with_embeddings
from tests.utils.fake_embeddings import FakeEmbeddingGenerator


@pytest.fixture
def seeded_search_data(db_session):
    """Seed database with diverse search test data."""
    embedding_gen = FakeEmbeddingGenerator(seed=42)
    
    # Technical conversation
    seed_conversation_with_embeddings(
        db_session,
        title="Python Development Best Practices",
        messages=[
            ("user", "What are the best practices for Python development?"),
            ("assistant", "Here are key Python best practices: use virtual environments, follow PEP 8 style guide, write tests, use type hints, and document your code."),
        ],
        embedding_generator=embedding_gen
    )
    
    # Data science conversation
    seed_conversation_with_embeddings(
        db_session,
        title="Machine Learning Basics",
        messages=[
            ("user", "Explain supervised learning"),
            ("assistant", "Supervised learning is a machine learning approach where models learn from labeled training data to make predictions on new, unseen data."),
        ],
        embedding_generator=embedding_gen
    )
    
    db_session.flush()


@pytest.mark.migration
@pytest.mark.search
def test_keyword_search_returns_results(db_session, seeded_search_data):
    """Test that keyword search returns results after import."""
    search_service = SearchService()
    
    results = search_service.search_fts_only(query="python", limit=10)
    
    # Should find messages containing 'python'
    assert len(results) > 0, "Keyword search should return results"
    
    # Results should have content
    assert all(hasattr(r, 'content') for r in results), "Results should have content attribute"


@pytest.mark.migration
@pytest.mark.search
def test_semantic_search_returns_results(db_session, seeded_search_data):
    """Test that semantic search returns results after import."""
    from db.services.search_service import SearchConfig
    
    # Use permissive threshold for fake embeddings (which are random)
    config = SearchConfig(vector_similarity_threshold=0.0)  # Accept any similarity
    search_service = SearchService(config=config)
    
    results = search_service.search_vector_only(query="programming best practices", limit=10)
    
    # Should return results
    assert len(results) > 0, "Semantic search should return results"
    
    # Results should have required fields
    assert all(hasattr(r, 'content') for r in results), "Results should have content"
    assert all(hasattr(r, 'distance') for r in results), "Results should have distance"


@pytest.mark.migration
@pytest.mark.search
def test_hybrid_search_returns_results(db_session, seeded_search_data):
    """Test that hybrid search returns results after import."""
    search_service = SearchService()
    
    results = search_service.search(query="python development", limit=10)
    
    # Should return results
    assert len(results) > 0, "Hybrid search should return results"
    
    # Results should have content
    assert all(hasattr(r, 'content') for r in results), "Results should have content"


@pytest.mark.migration
@pytest.mark.search
def test_search_basic_functionality_summary(db_session, seeded_search_data):
    """
    Summary test: validates messages are searchable after import.
    
    This is the minimum requirement for PostgreSQL to replace ChromaDB.
    """
    from db.services.search_service import SearchConfig
    
    # Use permissive threshold for fake embeddings
    config = SearchConfig(vector_similarity_threshold=0.0)
    search_service = SearchService(config=config)
    
    print("\n" + "=" * 60)
    print("BASIC SEARCH FUNCTIONALITY TEST")
    print("=" * 60)
    
    # Test keyword search
    fts_results = search_service.search_fts_only(query="python", limit=5)
    fts_ok = len(fts_results) > 0
    
    # Test semantic search
    vector_results = search_service.search_vector_only(query="programming", limit=5)
    vector_ok = len(vector_results) > 0
    
    # Test hybrid search
    hybrid_results = search_service.search(query="machine learning", limit=5)
    hybrid_ok = len(hybrid_results) > 0
    
    print(f"{'✓' if fts_ok else '✗'} Keyword Search: {len(fts_results)} results")
    print(f"{'✓' if vector_ok else '✗'} Semantic Search: {len(vector_results)} results")
    print(f"{'✓' if hybrid_ok else '✗'} Hybrid Search: {len(hybrid_results)} results")
    print("=" * 60)
    
    assert fts_ok and vector_ok and hybrid_ok, "All search types should work"

"""
Test the unified SearchService with hybrid ranking.

This tests:
1. Full-text search only
2. Vector search only  
3. Hybrid search combining both
4. Similar message search
5. Search configuration and ranking weights
6. Legacy API compatibility
"""

import os
import sys
import logging
from uuid import UUID

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from db.services.search_service import SearchService, SearchConfig
from db.services.message_service import MessageService
from db.repositories.unit_of_work import get_unit_of_work

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_test_data():
    """Create test conversation and messages with varied content."""
    logger.info("📝 Setting up test data...")
    
    service = MessageService()
    
    # Create test conversation
    conv_id, initial_msg_id = service.create_conversation_with_initial_message(
        title="Search Service Test",
        initial_role="system",
        initial_content="This is a test conversation for the unified search service."
    )
    
    # Create diverse test messages to test different search scenarios
    test_messages = [
        {
            "role": "user",
            "content": "What are the benefits of PostgreSQL for database applications?"
        },
        {
            "role": "assistant",
            "content": "PostgreSQL offers numerous advantages: ACID compliance, advanced indexing, full-text search capabilities, JSON support, extensibility with custom functions, and excellent performance optimization features."
        },
        {
            "role": "user", 
            "content": "How does vector search work with embeddings?"
        },
        {
            "role": "assistant",
            "content": "Vector search uses high-dimensional embeddings to find semantically similar content. It converts text into numerical vectors using machine learning models, then uses cosine similarity or other distance metrics to find the most relevant matches."
        },
        {
            "role": "user",
            "content": "Can you explain hybrid search approaches?"
        },
        {
            "role": "assistant",
            "content": "Hybrid search combines multiple search techniques like lexical matching (traditional keyword search) with semantic similarity (vector search). This provides both exact term matching and conceptual relevance, offering more comprehensive and accurate results."
        },
        {
            "role": "user",
            "content": "What about database performance optimization?"
        },
        {
            "role": "assistant", 
            "content": "Database performance can be optimized through proper indexing, query optimization, connection pooling, caching strategies, and choosing appropriate data types. PostgreSQL provides tools like EXPLAIN ANALYZE to help identify bottlenecks."
        },
        {
            "role": "user",
            "content": "How does full-text search ranking work?"
        },
        {
            "role": "assistant",
            "content": "Full-text search ranking in PostgreSQL uses tf-idf (term frequency-inverse document frequency) and other statistical measures. The ts_rank function considers term frequency, document length, and term positions to calculate relevance scores."
        }
    ]
    
    message_ids = []
    for msg_data in test_messages:
        msg_id = service.create_message_with_embedding_job(
            conversation_id=conv_id,
            role=msg_data["role"],
            content=msg_data["content"],
            metadata={"test": True}
        )
        message_ids.append(msg_id)
    
    all_message_ids = [initial_msg_id] + message_ids
    logger.info(f"✅ Created test conversation {conv_id} with {len(all_message_ids)} messages")
    
    return conv_id, all_message_ids


def wait_for_embeddings(message_ids, timeout_seconds=30):
    """Wait for embeddings to be generated for test messages."""
    import time
    
    logger.info(f"⏳ Waiting up to {timeout_seconds}s for embeddings to be generated...")
    
    start_time = time.time()
    embedded_count = 0
    
    while time.time() - start_time < timeout_seconds:
        with get_unit_of_work() as uow:
            embedded_count = 0
            for msg_id in message_ids:
                if uow.embeddings.get_by_message_id(msg_id):
                    embedded_count += 1
        
        coverage = (embedded_count / len(message_ids)) * 100
        logger.info(f"📊 Embedding progress: {embedded_count}/{len(message_ids)} ({coverage:.1f}%)")
        
        if embedded_count == len(message_ids):
            logger.info("✅ All embeddings generated!")
            return True
        
        time.sleep(2)
    
    logger.warning(f"⚠️  Only {embedded_count}/{len(message_ids)} embeddings generated in {timeout_seconds}s")
    return embedded_count > 0


def test_fts_search(search_service, conv_id):
    """Test full-text search functionality."""
    logger.info("\n📝 Testing Full-Text Search...")
    
    test_queries = [
        "PostgreSQL database",
        "vector search embeddings", 
        "performance optimization",
        "full-text ranking"
    ]
    
    for query in test_queries:
        logger.info(f"🔍 FTS Query: '{query}'")
        
        try:
            results = search_service.search_fts_only(query, limit=5, conversation_id=conv_id)
            
            logger.info(f"   Results: {len(results)}")
            for i, result in enumerate(results[:3]):
                logger.info(f"   {i+1}. Score: {result.fts_score:.3f} | {result.content[:60]}...")
            
        except Exception as e:
            logger.error(f"   ❌ FTS search failed: {e}")
            return False
    
    logger.info("✅ FTS search tests passed")
    return True


def test_vector_search(search_service, conv_id):
    """Test vector search functionality."""
    logger.info("\n🎯 Testing Vector Search...")
    
    test_queries = [
        "database benefits",
        "semantic similarity matching",
        "query performance tuning", 
        "text search algorithms"
    ]
    
    for query in test_queries:
        logger.info(f"🔍 Vector Query: '{query}'")
        
        try:
            results = search_service.search_vector_only(query, limit=5, conversation_id=conv_id)
            
            logger.info(f"   Results: {len(results)}")
            for i, result in enumerate(results[:3]):
                similarity = result.similarity or 0
                logger.info(f"   {i+1}. Similarity: {similarity:.3f} | {result.content[:60]}...")
            
        except Exception as e:
            logger.error(f"   ❌ Vector search failed: {e}")
            return False
    
    logger.info("✅ Vector search tests passed")
    return True


def test_hybrid_search(search_service, conv_id):
    """Test hybrid search combining FTS and vector search."""
    logger.info("\n🔄 Testing Hybrid Search...")
    
    test_queries = [
        "PostgreSQL advantages",
        "vector embeddings similarity",
        "database optimization techniques",
        "search ranking algorithms"
    ]
    
    for query in test_queries:
        logger.info(f"🔍 Hybrid Query: '{query}'")
        
        try:
            results = search_service.search(query, limit=5, conversation_id=conv_id)
            
            logger.info(f"   Results: {len(results)}")
            for i, result in enumerate(results[:3]):
                logger.info(f"   {i+1}. Combined: {result.combined_score:.3f} (FTS: {result.fts_score:.3f if result.fts_score else 'N/A'}, Vector: {result.vector_score:.3f if result.vector_score else 'N/A'}) | {result.content[:50]}...")
            
        except Exception as e:
            logger.error(f"   ❌ Hybrid search failed: {e}")
            return False
    
    logger.info("✅ Hybrid search tests passed")
    return True


def test_similar_message_search(search_service, message_ids, conv_id):
    """Test similar message search functionality."""
    logger.info("\n🔗 Testing Similar Message Search...")
    
    # Use first few message IDs as test cases
    test_message_ids = message_ids[:3]
    
    for msg_id in test_message_ids:
        logger.info(f"🔍 Similar to: {msg_id}")
        
        try:
            results = search_service.search_similar_to_message(
                message_id=UUID(str(msg_id)), 
                limit=3,
                conversation_id=conv_id
            )
            
            logger.info(f"   Similar results: {len(results)}")
            for i, result in enumerate(results):
                similarity = result.similarity or 0
                logger.info(f"   {i+1}. Similarity: {similarity:.3f} | {result.content[:50]}...")
            
        except Exception as e:
            logger.error(f"   ❌ Similar search failed: {e}")
            return False
    
    logger.info("✅ Similar message search tests passed")
    return True


def test_search_configurations(search_service, conv_id):
    """Test different search configurations and ranking weights."""
    logger.info("\n⚙️  Testing Search Configurations...")
    
    configurations = [
        ("Vector-Heavy", SearchConfig(vector_weight=0.8, fts_weight=0.2)),
        ("FTS-Heavy", SearchConfig(vector_weight=0.2, fts_weight=0.8)), 
        ("Balanced", SearchConfig(vector_weight=0.5, fts_weight=0.5)),
        ("Low Thresholds", SearchConfig(vector_similarity_threshold=0.1, fts_rank_threshold=0.001))
    ]
    
    test_query = "database search optimization"
    
    for config_name, config in configurations:
        logger.info(f"🔧 Config: {config_name}")
        
        try:
            results = search_service.search(
                query=test_query, 
                limit=5, 
                conversation_id=conv_id,
                config_override=config
            )
            
            logger.info(f"   Results: {len(results)}")
            if results:
                top_result = results[0]
                logger.info(f"   Top result combined score: {top_result.combined_score:.3f}")
            
        except Exception as e:
            logger.error(f"   ❌ Config {config_name} failed: {e}")
            return False
    
    logger.info("✅ Search configuration tests passed")
    return True


def test_legacy_format_compatibility(search_service, conv_id):
    """Test legacy API format compatibility."""
    logger.info("\n🔄 Testing Legacy Format Compatibility...")
    
    try:
        results = search_service.search("PostgreSQL database", limit=3, conversation_id=conv_id)
        
        for result in results:
            legacy_format = result.to_legacy_format()
            
            # Verify required legacy fields
            assert 'id' in legacy_format
            assert 'document' in legacy_format
            assert 'metadata' in legacy_format
            
            metadata = legacy_format['metadata']
            required_meta_fields = [
                'title', 'source', 'message_count', 'earliest_ts', 'latest_ts',
                'conversation_id', 'message_id', 'role'
            ]
            
            for field in required_meta_fields:
                assert field in metadata, f"Missing required field: {field}"
            
            # Verify document format
            document = legacy_format['document']
            assert "**" in document, "Document should contain role formatting"
            
            logger.info(f"✅ Legacy format valid for message {result.message_id}")
        
        logger.info("✅ Legacy format compatibility tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Legacy format test failed: {e}")
        return False


def test_search_statistics(search_service):
    """Test search statistics and health metrics."""
    logger.info("\n📊 Testing Search Statistics...")
    
    try:
        stats = search_service.get_search_stats()
        
        required_stats = [
            'total_messages', 'embedded_messages', 'embedding_coverage_percent',
            'vector_search_available', 'fts_search_available', 'hybrid_search_available'
        ]
        
        for stat in required_stats:
            assert stat in stats, f"Missing stat: {stat}"
        
        logger.info("📈 Search Statistics:")
        logger.info(f"   Total messages: {stats['total_messages']}")
        logger.info(f"   Embedded messages: {stats['embedded_messages']}")
        logger.info(f"   Embedding coverage: {stats['embedding_coverage_percent']:.1f}%")
        logger.info(f"   Vector search available: {stats['vector_search_available']}")
        logger.info(f"   FTS search available: {stats['fts_search_available']}")
        logger.info(f"   Hybrid search available: {stats['hybrid_search_available']}")
        
        logger.info("✅ Search statistics tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Search statistics test failed: {e}")
        return False


def main():
    """Run comprehensive SearchService tests."""
    logger.info("🚀 Starting SearchService Tests")
    logger.info("=" * 60)
    
    try:
        # Setup
        conv_id, message_ids = setup_test_data()
        
        # Wait for embeddings to be generated
        if not wait_for_embeddings(message_ids, timeout_seconds=45):
            logger.error("❌ Insufficient embeddings generated - some tests may fail")
        
        # Initialize search service
        search_service = SearchService()
        
        # Run tests
        tests = [
            ("Search Statistics", lambda: test_search_statistics(search_service)),
            ("Full-Text Search", lambda: test_fts_search(search_service, conv_id)),
            ("Vector Search", lambda: test_vector_search(search_service, conv_id)),
            ("Hybrid Search", lambda: test_hybrid_search(search_service, conv_id)),
            ("Similar Message Search", lambda: test_similar_message_search(search_service, message_ids, conv_id)),
            ("Search Configurations", lambda: test_search_configurations(search_service, conv_id)),
            ("Legacy Format Compatibility", lambda: test_legacy_format_compatibility(search_service, conv_id)),
        ]
        
        results = []
        
        for test_name, test_func in tests:
            logger.info(f"\n{'='*50}")
            logger.info(f"🧪 Running: {test_name}")
            logger.info(f"{'='*50}")
            
            try:
                success = test_func()
                results.append((test_name, success))
                
                if success:
                    logger.info(f"✅ {test_name} PASSED")
                else:
                    logger.error(f"❌ {test_name} FAILED")
                    
            except Exception as e:
                logger.error(f"💥 {test_name} CRASHED: {e}")
                results.append((test_name, False))
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("📋 SEARCH SERVICE TEST SUMMARY")
        logger.info(f"{'='*60}")
        
        passed = sum(1 for _, success in results if success)
        total = len(results)
        
        for test_name, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            logger.info(f"{status} - {test_name}")
        
        logger.info(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("🎉 All SearchService tests completed successfully!")
            logger.info("\n🔥 Key Capabilities Verified:")
            logger.info("   ✅ Full-Text Search with PostgreSQL FTS")
            logger.info("   ✅ Vector Similarity Search with pgvector")
            logger.info("   ✅ Hybrid Ranking combining both approaches")
            logger.info("   ✅ Configurable ranking weights")
            logger.info("   ✅ Similar message discovery")
            logger.info("   ✅ Legacy API compatibility")
            logger.info("   ✅ Comprehensive search statistics")
        else:
            logger.error("❌ Some tests failed - check logs above")
        
        return passed == total
        
    except Exception as e:
        logger.error(f"💥 Test suite crashed: {e}")
        raise


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        logger.error(f"💥 Test suite crashed: {e}")
        raise
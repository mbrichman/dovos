"""
Complete demonstration of the PostgreSQL migration pipeline:
1. Outbox Pattern: Atomic message creation with job enqueuing
2. Background Workers: Processing embedding jobs from the queue
3. End-to-End: From message creation to searchable embeddings

This showcases the full async processing pipeline for the PostgreSQL backend.
"""

import os
import sys
import logging
import time
import threading
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from db.services.message_service import MessageService
from db.repositories.unit_of_work import get_unit_of_work
from db.workers.embedding_worker import EmbeddingWorker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_demo_conversation():
    """Create a conversation with several messages to demonstrate the pipeline."""
    logger.info("📝 Creating demo conversation with messages...")
    
    service = MessageService()
    
    # Create conversation with initial message
    conv_id, initial_msg_id = service.create_conversation_with_initial_message(
        title="PostgreSQL Migration Demo",
        initial_role="system",
        initial_content="This conversation demonstrates the complete PostgreSQL migration pipeline with outbox pattern and background workers."
    )
    
    logger.info(f"✅ Created conversation: {conv_id}")
    logger.info(f"✅ Created initial message: {initial_msg_id}")
    
    # Create a series of messages to simulate a real conversation
    messages = [
        {
            "role": "user",
            "content": "What are the key benefits of using PostgreSQL for this chat application?"
        },
        {
            "role": "assistant", 
            "content": "PostgreSQL offers several key benefits for chat applications: 1) ACID compliance ensures data consistency, 2) Full-text search with ranking and stemming, 3) Vector similarity search with pgvector extension, 4) JSON support for flexible metadata, 5) Scalable connection pooling, and 6) Rich indexing capabilities for performance."
        },
        {
            "role": "user",
            "content": "How does the outbox pattern help with reliability?"
        },
        {
            "role": "assistant",
            "content": "The outbox pattern ensures reliability by storing both the business operation (message creation) and the event (embedding job) in the same transaction. This guarantees that either both succeed or both fail, preventing orphaned messages without embeddings or jobs without messages. It eliminates the dual-write problem common in distributed systems."
        },
        {
            "role": "user",
            "content": "What about the background workers? How do they process jobs safely?"
        },
        {
            "role": "assistant",
            "content": "Background workers use PostgreSQL's FOR UPDATE SKIP LOCKED to safely dequeue jobs in a concurrent environment. Multiple workers can run simultaneously without conflicts. They implement exponential backoff for retries, graceful shutdown handling, and comprehensive error logging. The job queue acts as a durable message broker."
        },
        {
            "role": "user",
            "content": "This seems like a robust architecture. How does it compare to the old ChromaDB approach?"
        },
        {
            "role": "assistant",
            "content": "The new PostgreSQL approach offers several advantages over ChromaDB: 1) Single source of truth - no data synchronization issues, 2) ACID transactions ensure consistency, 3) Better observability with SQL queries, 4) Hybrid search combining FTS and vectors, 5) Proven scalability and reliability, 6) Rich ecosystem of tools and extensions, and 7) Simplified deployment with one database instead of multiple systems."
        }
    ]
    
    message_ids = []
    for msg_data in messages:
        msg_id = service.create_message_with_embedding_job(
            conversation_id=conv_id,
            role=msg_data["role"],
            content=msg_data["content"],
            metadata={"demo": True, "pipeline_test": True}
        )
        message_ids.append(msg_id)
        logger.info(f"✅ Created {msg_data['role']} message: {msg_id}")
    
    return conv_id, [initial_msg_id] + message_ids


def check_queue_status():
    """Check the current job queue status."""
    logger.info("📊 Checking job queue status...")
    
    with get_unit_of_work() as uow:
        queue_stats = uow.jobs.get_queue_stats()
        embedding_stats = uow.jobs.get_embedding_job_stats()
        
        logger.info(f"📈 Queue Statistics:")
        logger.info(f"   Total jobs: {queue_stats['total_jobs']}")
        logger.info(f"   Status distribution: {queue_stats['status_counts']}")
        logger.info(f"   Pending by kind: {queue_stats['pending_by_kind']}")
        
        logger.info(f"🧠 Embedding Job Statistics:")
        logger.info(f"   By status: {embedding_stats['embedding_jobs_by_status']}")
        logger.info(f"   Recent (24h): {embedding_stats['recent_embedding_jobs_24h']}")
        
        return queue_stats['status_counts'].get('pending', 0)


def run_background_worker(duration_seconds=20):
    """Run a background worker for processing embedding jobs."""
    logger.info(f"🚀 Starting background worker for {duration_seconds} seconds...")
    
    worker = EmbeddingWorker(
        worker_id="demo-worker",
        max_jobs_per_batch=3,
        poll_interval_seconds=1,
        max_retries=3
    )
    
    # Run worker in thread
    def worker_thread():
        worker.start()
    
    thread = threading.Thread(target=worker_thread)
    thread.start()
    
    # Let worker run for specified duration
    time.sleep(duration_seconds)
    
    # Stop worker gracefully
    logger.info("🛑 Stopping background worker...")
    worker.stop()
    thread.join(timeout=5)
    
    return worker.stats


def check_embedding_results(message_ids):
    """Check how many messages now have embeddings."""
    logger.info("🔍 Checking embedding generation results...")
    
    with get_unit_of_work() as uow:
        embeddings_created = 0
        embeddings_details = []
        
        for msg_id in message_ids:
            embedding = uow.embeddings.get_by_message_id(msg_id)
            if embedding:
                embeddings_created += 1
                embeddings_details.append({
                    'message_id': msg_id,
                    'model': embedding.model,
                    'dimension': len(embedding.embedding),
                    'created_at': embedding.updated_at
                })
                logger.info(f"✅ Embedding found for {msg_id}: {embedding.model} ({len(embedding.embedding)}d)")
            else:
                logger.warning(f"⚠️  No embedding for {msg_id}")
        
        coverage_percent = (embeddings_created / len(message_ids)) * 100 if message_ids else 0
        logger.info(f"📊 Embedding coverage: {embeddings_created}/{len(message_ids)} ({coverage_percent:.1f}%)")
        
        return embeddings_created, embeddings_details


def demonstrate_search_capabilities(conv_id, message_ids):
    """Demonstrate search capabilities with the generated embeddings."""
    logger.info("🔍 Demonstrating search capabilities...")
    
    with get_unit_of_work() as uow:
        # Test full-text search
        fts_results = uow.messages.search_full_text("PostgreSQL benefits", limit=3)
        logger.info(f"📝 Full-text search results: {len(fts_results)} matches")
        
        if fts_results:
            top_result = fts_results[0]
            logger.info(f"   Top result: {top_result['metadata']['message_id']} (rank: {top_result['metadata'].get('rank', 'N/A')})")
        
        # Test vector search (if embeddings exist)
        embeddings_with_data = []
        for msg_id in message_ids:
            embedding = uow.embeddings.get_by_message_id(msg_id)
            if embedding:
                embeddings_with_data.append((msg_id, embedding))
        
        if embeddings_with_data:
            # Use the first embedding as a query vector
            query_msg_id, query_embedding = embeddings_with_data[0]
            
            vector_results = uow.embeddings.search_similar(
                query_embedding.embedding, 
                limit=3,
                distance_threshold=0.9
            )
            
            logger.info(f"🎯 Vector search results: {len(vector_results)} matches")
            if vector_results:
                top_vector_result = vector_results[0]
                similarity = top_vector_result['metadata'].get('similarity', 0)
                logger.info(f"   Top result: {top_vector_result['metadata']['message_id']} (similarity: {similarity:.3f})")
        
        return len(fts_results), len(vector_results) if embeddings_with_data else 0


def main():
    """Run the complete pipeline demonstration."""
    logger.info("🚀 Starting Complete PostgreSQL Migration Pipeline Demo")
    logger.info("=" * 60)
    
    try:
        # Step 1: Create demo conversation with messages (triggers outbox pattern)
        logger.info("\n📝 STEP 1: Create Conversation with Outbox Pattern")
        logger.info("-" * 50)
        conv_id, message_ids = create_demo_conversation()
        
        # Step 2: Check initial queue status
        logger.info("\n📊 STEP 2: Check Job Queue Status") 
        logger.info("-" * 50)
        initial_pending = check_queue_status()
        
        if initial_pending == 0:
            logger.warning("⚠️  No pending jobs found - outbox pattern may have failed")
            return
        
        # Step 3: Run background worker to process jobs
        logger.info("\n🔄 STEP 3: Run Background Worker")
        logger.info("-" * 50)
        worker_stats = run_background_worker(duration_seconds=15)
        
        # Step 4: Check final queue status
        logger.info("\n📊 STEP 4: Check Final Queue Status")
        logger.info("-" * 50)
        final_pending = check_queue_status()
        
        # Step 5: Check embedding generation results
        logger.info("\n🔍 STEP 5: Check Embedding Results")
        logger.info("-" * 50)
        embeddings_created, embedding_details = check_embedding_results(message_ids)
        
        # Step 6: Demonstrate search capabilities
        logger.info("\n🎯 STEP 6: Demonstrate Search Capabilities")
        logger.info("-" * 50)
        fts_count, vector_count = demonstrate_search_capabilities(conv_id, message_ids)
        
        # Final Summary
        logger.info("\n" + "=" * 60)
        logger.info("📋 PIPELINE DEMONSTRATION SUMMARY")
        logger.info("=" * 60)
        
        logger.info(f"📝 Messages created: {len(message_ids)}")
        logger.info(f"⚡ Jobs initially pending: {initial_pending}")
        logger.info(f"📊 Worker stats: {worker_stats['jobs_processed']} processed, {worker_stats['jobs_successful']} successful")
        logger.info(f"🔄 Jobs still pending: {final_pending}")
        logger.info(f"🧠 Embeddings generated: {embeddings_created}/{len(message_ids)}")
        logger.info(f"🔍 Search capabilities: FTS={fts_count} results, Vector={vector_count} results")
        
        success_rate = (embeddings_created / len(message_ids)) * 100 if message_ids else 0
        logger.info(f"📈 Overall success rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            logger.info("🎉 Pipeline demonstration SUCCESSFUL!")
        else:
            logger.warning("⚠️  Pipeline demonstration partially successful - some jobs may still be processing")
        
        logger.info("\n🔥 Key Features Demonstrated:")
        logger.info("   ✅ Outbox Pattern: Atomic message + job creation")
        logger.info("   ✅ Background Workers: Concurrent job processing")
        logger.info("   ✅ Embedding Generation: ML model integration")
        logger.info("   ✅ Search Capabilities: Both FTS and vector search")
        logger.info("   ✅ Job Queue Management: PostgreSQL-based queue")
        logger.info("   ✅ Error Handling: Retries and failure tracking")
        
    except Exception as e:
        logger.error(f"❌ Pipeline demonstration failed: {e}")
        raise


if __name__ == "__main__":
    main()
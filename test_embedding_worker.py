"""
Test the embedding worker by creating messages with jobs and processing them.
"""

import os
import sys
import logging
import time
import threading
from uuid import UUID

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from db.services.message_service import MessageService
from db.repositories.unit_of_work import get_unit_of_work
from db.workers.embedding_worker import EmbeddingWorker, EmbeddingGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_embedding_generator():
    """Test the embedding generator directly."""
    logger.info("🧪 Testing embedding generator...")
    
    generator = EmbeddingGenerator()
    
    test_texts = [
        "Hello, this is a test message.",
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning is a subset of artificial intelligence."
    ]
    
    for i, text in enumerate(test_texts):
        logger.info(f"Generating embedding for text {i+1}: {text[:50]}...")
        try:
            embedding = generator.generate_embedding(text)
            logger.info(f"✅ Generated embedding with dimension: {len(embedding)}")
            
            # Verify it's the expected dimension
            assert len(embedding) == 384, f"Expected 384 dimensions, got {len(embedding)}"
            
        except Exception as e:
            logger.error(f"❌ Failed to generate embedding: {e}")
            return False
    
    logger.info("✅ Embedding generator test passed!")
    return True


def create_test_jobs():
    """Create test messages with embedding jobs."""
    logger.info("📝 Creating test messages with embedding jobs...")
    
    service = MessageService()
    
    # Create a test conversation
    conv_id, initial_msg_id = service.create_conversation_with_initial_message(
        title="Embedding Worker Test",
        initial_role="system",
        initial_content="This conversation is for testing the embedding worker."
    )
    
    logger.info(f"✅ Created conversation: {conv_id}")
    
    # Create several test messages
    test_messages = [
        {
            "role": "user",
            "content": "What is machine learning and how does it work?"
        },
        {
            "role": "assistant", 
            "content": "Machine learning is a method of data analysis that automates analytical model building. It uses algorithms that iteratively learn from data, allowing computers to find hidden insights without being explicitly programmed."
        },
        {
            "role": "user",
            "content": "Can you give me some examples of machine learning in everyday life?"
        },
        {
            "role": "assistant",
            "content": "Sure! Examples include: email spam filtering, recommendation systems on Netflix and Spotify, voice assistants like Siri and Alexa, image recognition in photos, fraud detection in banking, and predictive text on your phone."
        },
        {
            "role": "user",
            "content": "How do neural networks relate to machine learning?"
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
        logger.info(f"✅ Created message: {msg_id}")
    
    return conv_id, message_ids


def check_job_queue_before():
    """Check the job queue status before processing."""
    logger.info("📊 Checking job queue before processing...")
    
    with get_unit_of_work() as uow:
        queue_stats = uow.jobs.get_queue_stats()
        embedding_stats = uow.jobs.get_embedding_job_stats()
        
        logger.info(f"Total jobs: {queue_stats['total_jobs']}")
        logger.info(f"Status counts: {queue_stats['status_counts']}")
        logger.info(f"Pending by kind: {queue_stats['pending_by_kind']}")
        
        # Get pending embedding jobs
        pending_jobs = uow.jobs.get_pending_jobs(kinds=['generate_embedding'])
        logger.info(f"📋 Found {len(pending_jobs)} pending embedding jobs")
        
        return len(pending_jobs)


def check_results_after(message_ids):
    """Check that embeddings were created after processing."""
    logger.info("🔍 Checking results after processing...")
    
    with get_unit_of_work() as uow:
        # Check embedding creation
        embeddings_created = 0
        for msg_id in message_ids:
            embedding = uow.embeddings.get_by_message_id(msg_id)
            if embedding:
                embeddings_created += 1
                logger.info(f"✅ Embedding created for message {msg_id} (model: {embedding.model})")
            else:
                logger.warning(f"⚠️  No embedding found for message {msg_id}")
        
        # Check job completion
        from db.models.models import Job
        completed_jobs = uow.session.query(Job).filter_by(status='completed', kind='generate_embedding').count()
        logger.info(f"📈 Completed embedding jobs: {completed_jobs}")
        
        # Final queue stats
        queue_stats = uow.jobs.get_queue_stats()
        logger.info(f"Final queue status: {queue_stats['status_counts']}")
        
        return embeddings_created


def test_worker_processing():
    """Test the worker processing jobs."""
    logger.info("🔄 Testing worker processing...")
    
    # Create test jobs
    conv_id, message_ids = create_test_jobs()
    
    # Check initial queue state
    initial_pending = check_job_queue_before()
    
    if initial_pending == 0:
        logger.warning("⚠️  No pending jobs found - nothing to process")
        return False
    
    # Create and start worker in a separate thread
    logger.info("🚀 Starting embedding worker...")
    worker = EmbeddingWorker(
        worker_id="test-worker",
        max_jobs_per_batch=3,
        poll_interval_seconds=1,
        max_retries=3
    )
    
    # Run worker in thread for limited time
    def run_worker():
        worker.start()
    
    worker_thread = threading.Thread(target=run_worker)
    worker_thread.start()
    
    # Let worker run for a bit
    logger.info("⏳ Letting worker process jobs for 10 seconds...")
    time.sleep(10)
    
    # Stop worker
    logger.info("🛑 Stopping worker...")
    worker.stop()
    worker_thread.join(timeout=5)
    
    # Check results
    embeddings_created = check_results_after(message_ids)
    
    success = embeddings_created == len(message_ids)
    if success:
        logger.info(f"✅ All {len(message_ids)} messages have embeddings!")
    else:
        logger.warning(f"⚠️  Only {embeddings_created}/{len(message_ids)} messages have embeddings")
    
    return success


def test_concurrent_workers():
    """Test multiple workers processing jobs concurrently."""
    logger.info("🔄 Testing concurrent workers...")
    
    # Create more test jobs
    service = MessageService()
    
    conv_id, _ = service.create_conversation_with_initial_message(
        title="Concurrent Worker Test",
        initial_role="system", 
        initial_content="Testing concurrent embedding workers."
    )
    
    # Create a bunch of messages
    bulk_data = []
    for i in range(10):
        bulk_data.append({
            "conversation_id": conv_id,
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"This is test message number {i+1} for concurrent processing testing.",
            "metadata": {"test": True, "batch": "concurrent", "index": i}
        })
    
    message_ids = service.bulk_create_messages_with_jobs(bulk_data)
    logger.info(f"✅ Created {len(message_ids)} messages for concurrent processing")
    
    # Create multiple workers
    workers = []
    threads = []
    
    num_workers = 3
    logger.info(f"🚀 Starting {num_workers} concurrent workers...")
    
    for i in range(num_workers):
        worker = EmbeddingWorker(
            worker_id=f"concurrent-worker-{i+1}",
            max_jobs_per_batch=2,
            poll_interval_seconds=1
        )
        
        def run_worker(w):
            w.start()
        
        thread = threading.Thread(target=run_worker, args=(worker,))
        
        workers.append(worker)
        threads.append(thread)
        thread.start()
    
    # Let workers run
    logger.info("⏳ Letting workers process for 15 seconds...")
    time.sleep(15)
    
    # Stop all workers
    logger.info("🛑 Stopping all workers...")
    for worker in workers:
        worker.stop()
    
    for thread in threads:
        thread.join(timeout=5)
    
    # Check results
    embeddings_created = check_results_after(message_ids)
    
    success = embeddings_created == len(message_ids)
    if success:
        logger.info(f"✅ Concurrent processing successful: {embeddings_created}/{len(message_ids)} embeddings created!")
    else:
        logger.warning(f"⚠️  Concurrent processing partial: {embeddings_created}/{len(message_ids)} embeddings created")
    
    return success


def main():
    """Run all embedding worker tests."""
    logger.info("🚀 Starting embedding worker tests...")
    
    tests = [
        ("Embedding Generator", test_embedding_generator),
        ("Single Worker Processing", test_worker_processing), 
        ("Concurrent Workers", test_concurrent_workers)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"🧪 Running test: {test_name}")
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
    logger.info(f"\n{'='*50}")
    logger.info("📋 TEST SUMMARY")
    logger.info(f"{'='*50}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All embedding worker tests completed successfully!")
    else:
        logger.error("❌ Some tests failed - check logs above")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        logger.error(f"💥 Test suite crashed: {e}")
        raise
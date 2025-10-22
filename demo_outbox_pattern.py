"""
Demonstration of the Outbox Pattern for Atomic Message Creation and Job Enqueuing.

This script shows how to use the MessageService to atomically create messages
and enqueue background jobs for embedding generation in a single transaction.
"""

import os
import sys
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from db.services.message_service import MessageService
from db.repositories.unit_of_work import get_unit_of_work

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demonstrate_outbox_pattern():
    """Demonstrate the outbox pattern for atomic writes."""
    
    logger.info("🚀 Starting Outbox Pattern Demonstration")
    
    service = MessageService()
    
    # Step 1: Create a conversation and initial message atomically
    logger.info("\n📝 Step 1: Creating conversation with initial message")
    conv_id, msg_id = service.create_conversation_with_initial_message(
        title="Outbox Pattern Demo",
        initial_role="system",
        initial_content="This conversation demonstrates atomic message creation with background job enqueuing.",
        initial_metadata={"demo": True, "created_at": datetime.utcnow().isoformat()}
    )
    
    logger.info(f"✅ Created conversation: {conv_id}")
    logger.info(f"✅ Created initial message: {msg_id}")
    
    # Step 2: Add a user message 
    logger.info("\n💬 Step 2: Adding user message")
    user_msg_id = service.create_message_with_embedding_job(
        conversation_id=conv_id,
        role="user", 
        content="Tell me about the outbox pattern and why it's useful for ensuring data consistency.",
        metadata={"message_type": "question"}
    )
    
    logger.info(f"✅ Created user message: {user_msg_id}")
    
    # Step 3: Add an assistant response
    logger.info("\n🤖 Step 3: Adding assistant response")
    assistant_msg_id = service.create_message_with_embedding_job(
        conversation_id=conv_id,
        role="assistant",
        content=(
            "The outbox pattern is a microservices design pattern that ensures reliable "
            "message publishing by storing events in a database table within the same "
            "transaction as the business operation. This guarantees that either both "
            "the business change and the event are saved, or neither are, maintaining "
            "data consistency even in distributed systems."
        ),
        metadata={"message_type": "answer", "tokens": 67}
    )
    
    logger.info(f"✅ Created assistant message: {assistant_msg_id}")
    
    # Step 4: Update a message (triggers new embedding job only if content changes)
    logger.info("\n📝 Step 4: Updating message content")
    updated_msg_id = service.update_message_with_embedding_job(
        message_id=assistant_msg_id,
        content=(
            "The outbox pattern is a microservices design pattern that ensures reliable "
            "message publishing by storing events in a database table within the same "
            "transaction as the business operation. This guarantees that either both "
            "the business change and the event are saved, or neither are, maintaining "
            "data consistency even in distributed systems. It's particularly valuable "
            "when you need to ensure that side effects (like sending notifications or "
            "updating search indexes) happen reliably after a database change."
        ),
        metadata={"message_type": "answer", "tokens": 95, "updated": True}
    )
    
    logger.info(f"✅ Updated message: {updated_msg_id}")
    
    # Step 5: Create multiple messages in a single transaction
    logger.info("\n📦 Step 5: Creating multiple messages in bulk")
    bulk_data = [
        {
            "conversation_id": conv_id,
            "role": "user",
            "content": "Can you give me a practical example?",
            "metadata": {"message_type": "follow_up"}
        },
        {
            "conversation_id": conv_id, 
            "role": "assistant",
            "content": (
                "Sure! Imagine an e-commerce system where placing an order should: "
                "1) Save the order to database, 2) Send confirmation email, "
                "3) Update inventory, 4) Trigger shipment. With the outbox pattern, "
                "you save the order and outbox events in one transaction, then a "
                "background processor handles the side effects reliably."
            ),
            "metadata": {"message_type": "example", "tokens": 58}
        },
        {
            "conversation_id": conv_id,
            "role": "user", 
            "content": "That makes sense! Thanks for the explanation.",
            "metadata": {"message_type": "acknowledgment"}
        }
    ]
    
    bulk_msg_ids = service.bulk_create_messages_with_jobs(bulk_data)
    logger.info(f"✅ Created {len(bulk_msg_ids)} messages in bulk: {bulk_msg_ids}")
    
    # Step 6: Check job status and queue statistics
    logger.info("\n📊 Step 6: Checking job queue status")
    
    with get_unit_of_work() as uow:
        # Get queue statistics
        queue_stats = uow.jobs.get_queue_stats()
        embedding_stats = uow.jobs.get_embedding_job_stats()
        
        logger.info("📈 Queue Statistics:")
        logger.info(f"   Total jobs: {queue_stats['total_jobs']}")
        logger.info(f"   Status distribution: {queue_stats['status_counts']}")
        logger.info(f"   Pending by kind: {queue_stats['pending_by_kind']}")
        
        logger.info("🧠 Embedding Job Statistics:")
        logger.info(f"   Embedding jobs by status: {embedding_stats['embedding_jobs_by_status']}")
        logger.info(f"   Recent embedding jobs (24h): {embedding_stats['recent_embedding_jobs_24h']}")
        
        # Show some pending jobs
        pending_jobs = uow.jobs.get_pending_jobs(kinds=['generate_embedding'], limit=5)
        logger.info(f"📋 Recent pending embedding jobs ({len(pending_jobs)}):")
        for job in pending_jobs:
            logger.info(f"   Job {job.id}: {job.payload.get('message_id', 'unknown')} - {job.created_at}")
    
    # Step 7: Demonstrate message with job status
    logger.info("\n🔍 Step 7: Checking message job status")
    status_info = service.get_message_with_job_status(assistant_msg_id)
    if status_info:
        logger.info(f"📧 Message {assistant_msg_id}:")
        logger.info(f"   Embedding status: {status_info['embedding_status']}")
        logger.info(f"   Recent jobs: {len(status_info['recent_jobs'])}")
        if status_info['latest_job']:
            logger.info(f"   Latest job: {status_info['latest_job'].status} (ID: {status_info['latest_job'].id})")
    
    logger.info("\n🎉 Outbox Pattern Demonstration Complete!")
    logger.info("🔥 Key Benefits Demonstrated:")
    logger.info("   ✅ Atomic message creation with job enqueuing")
    logger.info("   ✅ Automatic rollback on failures")
    logger.info("   ✅ Bulk operations in single transactions")
    logger.info("   ✅ Consistent state across message and job tables")
    logger.info("   ✅ Background job queue for async processing")


if __name__ == "__main__":
    try:
        demonstrate_outbox_pattern()
    except Exception as e:
        logger.error(f"❌ Demonstration failed: {e}")
        raise
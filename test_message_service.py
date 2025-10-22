"""
Test the message service with outbox pattern for atomic writes.
"""

import os
import sys
import logging
import uuid
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from db.services.message_service import MessageService, create_message_atomically
from db.repositories.unit_of_work import get_unit_of_work

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_outbox_pattern():
    """Test the outbox pattern for atomic message creation with job enqueuing."""
    logger.info("Testing outbox pattern...")
    
    service = MessageService()
    
    # First, create a conversation for testing
    with get_unit_of_work() as uow:
        conversation = uow.conversations.create(title="Test Outbox Pattern")
        logger.info(f"Created test conversation: {conversation.id}")
        conversation_id = conversation.id
    
    # Test 1: Create message atomically with embedding job
    logger.info("\n--- Test 1: Atomic Message Creation ---")
    try:
        message_id = service.create_message_with_embedding_job(
            conversation_id=conversation_id,
            role='user',
            content='This is a test message for the outbox pattern.',
            metadata={'test': True, 'timestamp': datetime.utcnow().isoformat()}
        )
        
        # Verify message was created
        with get_unit_of_work() as uow:
            retrieved_message = uow.messages.get_by_id(message_id)
            assert retrieved_message is not None
            assert retrieved_message.content == 'This is a test message for the outbox pattern.'
            
            # Verify embedding job was enqueued
            pending_jobs = uow.jobs.get_pending_jobs(kinds=['generate_embedding'])
            embedding_jobs_for_message = [
                job for job in pending_jobs
                if job.payload.get('message_id') == str(message_id)
            ]
            
            assert len(embedding_jobs_for_message) == 1
            job = embedding_jobs_for_message[0]
            assert job.kind == 'generate_embedding'
            assert job.payload['content'] == 'This is a test message for the outbox pattern.'
            assert job.payload['model'] == 'all-MiniLM-L6-v2'
            
            logger.info(f"✓ Message created: {message_id}")
            logger.info(f"✓ Embedding job enqueued: {job.id}")
    
    except Exception as e:
        logger.error(f"Test 1 failed: {e}")
        raise
    
    # Test 2: Update message with new embedding job (content change)
    logger.info("\n--- Test 2: Message Update with Content Change ---")
    try:
        updated_message = service.update_message_with_embedding_job(
            message_id=message_id,
            content='This is the updated content for testing.',
            metadata={'test': True, 'updated': True}
        )
        
        with get_unit_of_work() as uow:
            # Verify message was updated
            retrieved_message = uow.messages.get_by_id(message_id)
            assert retrieved_message.content == 'This is the updated content for testing.'
            assert retrieved_message.message_metadata['updated'] is True
            
            # Verify new embedding job was enqueued
            all_pending_jobs = uow.jobs.get_pending_jobs(kinds=['generate_embedding'])
            embedding_jobs_for_message = [
                job for job in all_pending_jobs
                if job.payload.get('message_id') == str(message_id)
            ]
            
            # Should now have 2 jobs (original + update)
            assert len(embedding_jobs_for_message) == 2
            
            # Latest job should have updated content
            latest_job = max(embedding_jobs_for_message, key=lambda j: j.created_at)
            assert latest_job.payload['content'] == 'This is the updated content for testing.'
            
            logger.info(f"✓ Message updated: {message_id}")
            logger.info(f"✓ New embedding job enqueued: {latest_job.id}")
    
    except Exception as e:
        logger.error(f"Test 2 failed: {e}")
        raise
    
    # Test 3: Update message without content change (no new job)
    logger.info("\n--- Test 3: Message Update without Content Change ---")
    try:
        updated_message = service.update_message_with_embedding_job(
            message_id=message_id,
            metadata={'test': True, 'metadata_only_update': True}
        )
        
        with get_unit_of_work() as uow:
            # Verify metadata was updated
            retrieved_message = uow.messages.get_by_id(message_id)
            assert retrieved_message.message_metadata['metadata_only_update'] is True
            
            # Verify no new embedding job was created
            all_pending_jobs = uow.jobs.get_pending_jobs(kinds=['generate_embedding'])
            embedding_jobs_for_message = [
                job for job in all_pending_jobs
                if job.payload.get('message_id') == str(message_id)
            ]
            
            # Should still have 2 jobs (no new job added)
            assert len(embedding_jobs_for_message) == 2
            
            logger.info(f"✓ Message metadata updated without new embedding job")
    
    except Exception as e:
        logger.error(f"Test 3 failed: {e}")
        raise
    
    # Test 4: Create conversation with initial message
    logger.info("\n--- Test 4: Conversation with Initial Message ---")
    try:
        conversation_2_id, initial_message_id = service.create_conversation_with_initial_message(
            title="Outbox Test Conversation 2",
            initial_role='system',
            initial_content='Welcome to the outbox pattern test!',
            initial_metadata={'welcome': True}
        )
        
        with get_unit_of_work() as uow:
            # Verify conversation and message were created
            retrieved_conv = uow.conversations.get_by_id(conversation_2_id)
            retrieved_msg = uow.messages.get_by_id(initial_message_id)
            
            assert retrieved_conv.title == "Outbox Test Conversation 2"
            assert retrieved_msg.role == 'system'
            assert retrieved_msg.conversation_id == conversation_2_id
            
            # Verify embedding job
            pending_jobs = uow.jobs.get_pending_jobs(kinds=['generate_embedding'])
            embedding_jobs_for_message = [
                job for job in pending_jobs
                if job.payload.get('message_id') == str(initial_message_id)
            ]
            
            assert len(embedding_jobs_for_message) == 1
            
            logger.info(f"✓ Conversation created: {conversation_2_id}")
            logger.info(f"✓ Initial message created: {initial_message_id}")
            logger.info(f"✓ Embedding job enqueued")
    
    except Exception as e:
        logger.error(f"Test 4 failed: {e}")
        raise
    
    # Test 5: Bulk message creation
    logger.info("\n--- Test 5: Bulk Message Creation ---")
    try:
        messages_data = [
            {
                'conversation_id': conversation_id,
                'role': 'user',
                'content': 'First bulk message',
                'metadata': {'bulk': True, 'order': 1}
            },
            {
                'conversation_id': conversation_id,
                'role': 'assistant',
                'content': 'Second bulk message',
                'metadata': {'bulk': True, 'order': 2}
            },
            {
                'conversation_id': conversation_id,
                'role': 'user',
                'content': 'Third bulk message',
                'metadata': {'bulk': True, 'order': 3}
            }
        ]
        
        bulk_message_ids = service.bulk_create_messages_with_jobs(messages_data)
        
        assert len(bulk_message_ids) == 3
        
        with get_unit_of_work() as uow:
            # Verify all messages were created
            for i, message_id in enumerate(bulk_message_ids):
                retrieved_msg = uow.messages.get_by_id(message_id)
                assert retrieved_msg.message_metadata['order'] == i + 1
            
            # Verify all embedding jobs were created
            all_pending_jobs = uow.jobs.get_pending_jobs(kinds=['generate_embedding'])
            bulk_jobs = [
                job for job in all_pending_jobs
                if any(job.payload.get('message_id') == str(msg_id) for msg_id in bulk_message_ids)
            ]
            
            assert len(bulk_jobs) == 3
            
            logger.info(f"✓ Created {len(bulk_message_ids)} messages in bulk")
            logger.info(f"✓ Enqueued {len(bulk_jobs)} embedding jobs")
    
    except Exception as e:
        logger.error(f"Test 5 failed: {e}")
        raise
    
    # Test 6: Message with job status
    logger.info("\n--- Test 6: Message with Job Status ---")
    try:
        status_info = service.get_message_with_job_status(message_id)
        
        assert status_info is not None
        assert status_info['message_data']['id'] == message_id
        assert status_info['embedding_status'] in ['queued', 'pending', 'none']
        assert status_info['latest_job'] is not None
        assert len(status_info['recent_jobs']) > 0
        
        logger.info(f"✓ Message job status: {status_info['embedding_status']}")
        logger.info(f"✓ Found {len(status_info['recent_jobs'])} recent jobs")
    
    except Exception as e:
        logger.error(f"Test 6 failed: {e}")
        raise
    
    # Test 7: Convenience function
    logger.info("\n--- Test 7: Convenience Function ---")
    try:
        convenience_message_id = create_message_atomically(
            conversation_id=conversation_id,
            role='assistant',
            content='This message was created with the convenience function.',
            metadata={'convenience': True}
        )
        
        with get_unit_of_work() as uow:
            retrieved_msg = uow.messages.get_by_id(convenience_message_id)
            assert retrieved_msg.content == 'This message was created with the convenience function.'
            
            # Verify job was enqueued
            pending_jobs = uow.jobs.get_pending_jobs(kinds=['generate_embedding'])
            convenience_jobs = [
                job for job in pending_jobs
                if job.payload.get('message_id') == str(convenience_message_id)
            ]
            
            assert len(convenience_jobs) == 1
            
            logger.info(f"✓ Convenience function created message: {convenience_message_id}")
    
    except Exception as e:
        logger.error(f"Test 7 failed: {e}")
        raise
    
    logger.info("\n🎉 All outbox pattern tests passed!")


def test_transaction_rollback():
    """Test that transaction rollback works correctly."""
    logger.info("\n--- Testing Transaction Rollback ---")
    
    # Create a conversation for testing
    with get_unit_of_work() as uow:
        conversation = uow.conversations.create(title="Rollback Test")
        rollback_conversation_id = conversation.id
    
    # Simulate a transaction that should rollback
    message_id = None
    try:
        with get_unit_of_work() as uow:
            # Create message
            message = uow.messages.create(
                conversation_id=rollback_conversation_id,
                role='user',
                content='This message should be rolled back'
            )
            message_id = message.id
            
            # Enqueue job
            uow.jobs.enqueue(
                kind='generate_embedding',
                payload={'message_id': str(message.id), 'content': 'test'}
            )
            
            # Force an error to trigger rollback
            raise Exception("Simulated error to test rollback")
    
    except Exception as e:
        logger.info(f"Expected exception caught: {e}")
    
    # Verify that both message and job were rolled back
    with get_unit_of_work() as uow:
        retrieved_message = uow.messages.get_by_id(message_id)
        assert retrieved_message is None, "Message should have been rolled back"
        
        all_jobs = uow.jobs.get_pending_jobs()
        rollback_jobs = [
            job for job in all_jobs
            if job.payload.get('message_id') == str(message_id)
        ]
        assert len(rollback_jobs) == 0, "Job should have been rolled back"
    
    logger.info("✓ Transaction rollback test passed!")


if __name__ == "__main__":
    try:
        test_outbox_pattern()
        test_transaction_rollback()
        logger.info("\n🎯 All message service tests completed successfully!")
    
    except Exception as e:
        logger.error(f"\n❌ Tests failed: {e}")
        raise
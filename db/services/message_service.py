"""
Message service implementing the outbox pattern for atomic message creation
and embedding job enqueuing.
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime

from db.models.models import Message, Conversation
from db.repositories.unit_of_work import UnitOfWork, get_unit_of_work

logger = logging.getLogger(__name__)


class MessageService:
    """
    Service for message operations using the outbox pattern.
    
    Ensures atomic operations where message creation/updates and
    background job enqueuing happen in a single transaction.
    """
    
    def create_message_with_embedding_job(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Create a new message and atomically enqueue an embedding generation job.
        
        This implements the outbox pattern - both the message creation and
        job enqueuing happen in a single database transaction.
        """
        with get_unit_of_work() as uow:
            # Create the message
            message = uow.messages.create(
                conversation_id=conversation_id,
                role=role,
                content=content,
                message_metadata=metadata or {}
            )
            
            # Enqueue embedding generation job in same transaction
            job_payload = {
                'message_id': str(message.id),
                'conversation_id': str(conversation_id),
                'content': content,
                'model': 'all-MiniLM-L6-v2'  # Default model
            }
            
            uow.jobs.enqueue(
                kind='generate_embedding',
                payload=job_payload
            )
            
            message_id = message.id
            logger.info(f"Created message {message_id} with embedding job")
            return message_id
    
    def update_message_with_embedding_job(
        self,
        message_id: UUID,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[UUID]:
        """
        Update an existing message and enqueue a new embedding generation job
        if the content changed.
        """
        with get_unit_of_work() as uow:
            # Get existing message
            message = uow.messages.get_by_id(message_id)
            if not message:
                logger.warning(f"Message {message_id} not found for update")
                return None
            
            # Track if content changed
            content_changed = content is not None and content != message.content
            
            # Update message fields
            update_data = {}
            if content is not None:
                update_data['content'] = content
            if metadata is not None:
                update_data['message_metadata'] = metadata
            
            if update_data:
                updated_message = uow.messages.update(message_id, **update_data)
                
                # If content changed, enqueue new embedding job
                if content_changed:
                    job_payload = {
                        'message_id': str(message_id),
                        'conversation_id': str(message.conversation_id),
                        'content': content,
                        'model': 'all-MiniLM-L6-v2'
                    }
                    
                    uow.jobs.enqueue(
                        kind='generate_embedding',
                        payload=job_payload
                    )
                    
                    logger.info(f"Updated message {message_id} with new embedding job")
                else:
                    logger.info(f"Updated message {message_id} (no content change)")
                
                return message_id
            
            return message_id
    
    def create_conversation_with_initial_message(
        self,
        title: str,
        initial_role: str,
        initial_content: str,
        initial_metadata: Optional[Dict[str, Any]] = None
    ) -> tuple[UUID, UUID]:
        """
        Create a new conversation with an initial message, atomically
        enqueuing the embedding job.
        """
        with get_unit_of_work() as uow:
            # Create conversation
            conversation = uow.conversations.create(title=title)
            
            # Create initial message
            message = uow.messages.create(
                conversation_id=conversation.id,
                role=initial_role,
                content=initial_content,
                message_metadata=initial_metadata or {}
            )
            
            # Enqueue embedding job
            job_payload = {
                'message_id': str(message.id),
                'conversation_id': str(conversation.id),
                'content': initial_content,
                'model': 'all-MiniLM-L6-v2'
            }
            
            uow.jobs.enqueue(
                kind='generate_embedding',
                payload=job_payload
            )
            
            conversation_id = conversation.id
            message_id = message.id
            logger.info(f"Created conversation {conversation_id} with initial message {message_id}")
            return conversation_id, message_id
    
    def bulk_create_messages_with_jobs(
        self,
        messages_data: List[Dict[str, Any]]
    ) -> List[UUID]:
        """
        Create multiple messages in a single transaction with their embedding jobs.
        
        messages_data should be a list of dicts with keys:
        - conversation_id: UUID
        - role: str
        - content: str 
        - metadata: Optional[Dict[str, Any]]
        """
        with get_unit_of_work() as uow:
            created_messages = []
            
            for msg_data in messages_data:
                # Create message
                message = uow.messages.create(
                    conversation_id=msg_data['conversation_id'],
                    role=msg_data['role'],
                    content=msg_data['content'],
                    message_metadata=msg_data.get('metadata', {})
                )
                created_messages.append(message.id)
                
                # Enqueue embedding job
                job_payload = {
                    'message_id': str(message.id),
                    'conversation_id': str(msg_data['conversation_id']),
                    'content': msg_data['content'],
                    'model': 'all-MiniLM-L6-v2'
                }
                
                uow.jobs.enqueue(
                    kind='generate_embedding',
                    payload=job_payload
                )
            
            logger.info(f"Created {len(created_messages)} messages with embedding jobs")
            return created_messages
    
    def reprocess_message_embedding(self, message_id: UUID) -> bool:
        """
        Force reprocessing of a message's embedding by enqueuing a new job.
        """
        with get_unit_of_work() as uow:
            message = uow.messages.get_by_id(message_id)
            if not message:
                logger.warning(f"Message {message_id} not found for reprocessing")
                return False
            
            job_payload = {
                'message_id': str(message_id),
                'conversation_id': str(message.conversation_id),
                'content': message.content,
                'model': 'all-MiniLM-L6-v2',
                'reprocess': True
            }
            
            uow.jobs.enqueue(
                kind='generate_embedding',
                payload=job_payload
            )
            
            logger.info(f"Enqueued reprocessing job for message {message_id}")
            return True
    
    def get_message_with_job_status(self, message_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get a message along with information about its embedding job status.
        """
        with get_unit_of_work() as uow:
            message = uow.messages.get_with_embedding(message_id)
            if not message:
                return None
            
            # Look for recent embedding jobs for this message
            from db.models.models import Job
            from sqlalchemy import text
            embedding_jobs = uow.session.query(Job)\
                .filter_by(kind='generate_embedding')\
                .filter(text("payload->>'message_id' = :message_id"))\
                .params(message_id=str(message_id))\
                .order_by(Job.created_at.desc())\
                .limit(5)\
                .all()
            
            # Determine embedding status
            has_embedding = message.embedding is not None
            latest_job = embedding_jobs[0] if embedding_jobs else None
            
            if latest_job:
                job_status = latest_job.status
                if job_status == 'completed' and has_embedding:
                    embedding_status = 'current'
                elif job_status == 'running':
                    embedding_status = 'processing'
                elif job_status == 'pending':
                    embedding_status = 'queued'
                elif job_status == 'failed':
                    embedding_status = 'failed'
                else:
                    embedding_status = 'unknown'
            else:
                embedding_status = 'none' if not has_embedding else 'legacy'
            
            # Access message attributes within session to avoid detachment
            message_data = {
                'id': message.id,
                'conversation_id': message.conversation_id,
                'role': message.role,
                'content': message.content,
                'message_metadata': message.message_metadata,
                'created_at': message.created_at,
                'updated_at': message.updated_at
            }
            
            return {
                'message': message,  # Keep object for compatibility 
                'message_data': message_data,  # Safe data access
                'embedding_status': embedding_status,
                'latest_job': latest_job,
                'recent_jobs': embedding_jobs
            }


# Convenience function for single-message operations
def create_message_atomically(
    conversation_id: UUID,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> UUID:
    """Convenience function to create a message with embedding job atomically."""
    service = MessageService()
    return service.create_message_with_embedding_job(
        conversation_id=conversation_id,
        role=role,
        content=content,
        metadata=metadata
    )

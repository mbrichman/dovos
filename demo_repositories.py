#!/usr/bin/env python3
"""
Demonstration script showcasing the repository pattern capabilities.
"""

import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.repositories.unit_of_work import get_unit_of_work
from config import USE_PG_SINGLE_STORE


def demo_conversation_management():
    """Demonstrate conversation and message management."""
    print("=" * 50)
    print("CONVERSATION MANAGEMENT DEMO")
    print("=" * 50)
    
    with get_unit_of_work() as uow:
        # Create a conversation
        conversation = uow.conversations.create(
            title="Repository Pattern Demo - Chat about Python"
        )
        print(f"✅ Created conversation: {conversation.title}")
        print(f"   ID: {conversation.id}")
        
        # Add some messages
        messages_data = [
            ("user", "What are the benefits of using repository patterns in Python?"),
            ("assistant", "Repository patterns provide several key benefits in Python applications:\n\n1. **Separation of concerns**: Business logic is separated from data access logic\n2. **Testability**: Easy to mock repositories for unit testing\n3. **Flexibility**: Can switch between different data stores (SQLite, PostgreSQL, MongoDB)\n4. **Consistency**: Standardized interface for data operations\n5. **Transaction management**: Clean boundary for database transactions"),
            ("user", "How does this work with PostgreSQL specifically?"),
            ("assistant", "With PostgreSQL, repository patterns work especially well because:\n\n1. **Advanced features**: Can leverage PostgreSQL's full-text search, vector operations, and JSON support\n2. **ACID transactions**: Strong consistency guarantees for complex operations\n3. **Performance**: Efficient indexing and query optimization\n4. **Scalability**: Built-in connection pooling and concurrent access patterns"),
        ]
        
        created_messages = []
        for role, content in messages_data:
            message = uow.messages.create(
                conversation_id=conversation.id,
                role=role,
                content=content,
                message_metadata={"demo": True, "timestamp": datetime.utcnow().isoformat()}
            )
            created_messages.append(message)
            print(f"✅ Added {role} message: {content[:50]}...")
        
        print(f"\n📊 Created {len(created_messages)} messages")
        
        # Demonstrate retrieval
        retrieved_conversation = uow.conversations.get_with_messages(conversation.id)
        print(f"📄 Retrieved conversation with {len(retrieved_conversation.messages)} messages")
        
        # Get formatted document for API compatibility
        doc = uow.conversations.get_full_document_by_id(conversation.id)
        if doc:
            print(f"📝 Generated document preview: {doc['document'][:100]}...")
            print(f"📈 Metadata: {doc['metadata']}")
        
        return conversation.id, [m.id for m in created_messages]


def demo_search_capabilities(conversation_id, message_ids):
    """Demonstrate various search capabilities."""
    print("\n" + "=" * 50)
    print("SEARCH CAPABILITIES DEMO")
    print("=" * 50)
    
    with get_unit_of_work() as uow:
        # Full-text search
        print("\n🔍 Full-Text Search Results:")
        fts_results = uow.messages.search_full_text("repository patterns", limit=3)
        for i, result in enumerate(fts_results, 1):
            print(f"  {i}. {result['metadata']['title']}")
            print(f"     Rank: {result['metadata']['rank']}")
            print(f"     Role: {result['metadata']['role']}")
        
        # Trigram similarity search (fuzzy matching)
        print("\n🔍 Trigram Similarity Search (typo-tolerant):")
        trigram_results = uow.messages.search_trigram("repositry patern", limit=3)  # Intentional typos
        for i, result in enumerate(trigram_results, 1):
            print(f"  {i}. {result['metadata']['title']}")
            print(f"     Similarity: {result['metadata']['similarity']}")
        
        # Search within specific conversation
        print(f"\n🔍 Search within Conversation {conversation_id}:")
        conv_results = uow.messages.search_full_text("PostgreSQL", limit=5, conversation_id=conversation_id)
        for i, result in enumerate(conv_results, 1):
            print(f"  {i}. Found in {result['metadata']['role']} message")
            print(f"     Content preview: {result['document'][:100]}...")


def demo_job_queue():
    """Demonstrate job queue functionality."""
    print("\n" + "=" * 50)
    print("JOB QUEUE DEMO")
    print("=" * 50)
    
    with get_unit_of_work() as uow:
        # Create some embedding jobs
        job_payloads = [
            {"message_id": "550e8400-e29b-41d4-a716-446655440001", "model": "all-MiniLM-L6-v2"},
            {"message_id": "550e8400-e29b-41d4-a716-446655440002", "model": "all-MiniLM-L6-v2"},
            {"message_id": "550e8400-e29b-41d4-a716-446655440003", "model": "all-MiniLM-L6-v2"},
        ]
        
        created_jobs = []
        for payload in job_payloads:
            job = uow.jobs.enqueue("generate_embedding", payload)
            created_jobs.append(job)
            print(f"✅ Enqueued embedding job {job.id} for message {payload['message_id']}")
        
        # Get pending jobs
        pending_jobs = uow.jobs.get_pending_jobs(kinds=["generate_embedding"])
        print(f"\n📋 Pending embedding jobs: {len(pending_jobs)}")
        
        # Simulate job processing
        print("\n🔄 Simulating job processing:")
        for i, job in enumerate(created_jobs[:2]):  # Process first 2 jobs
            # Dequeue (this would be done by a worker)
            dequeued_job = uow.jobs.dequeue_next(kinds=["generate_embedding"])
            if dequeued_job:
                print(f"  📤 Dequeued job {dequeued_job.id} (attempts: {dequeued_job.attempts})")
                
                # Mark as completed (simulate successful processing)
                success = uow.jobs.mark_completed(dequeued_job.id)
                if success:
                    print(f"  ✅ Marked job {dequeued_job.id} as completed")
        
        # Get queue statistics
        stats = uow.jobs.get_queue_stats()
        print(f"\n📊 Queue Statistics:")
        print(f"  Total jobs: {stats['total_jobs']}")
        print(f"  Status distribution: {stats['status_counts']}")
        print(f"  Pending by kind: {stats['pending_by_kind']}")


def demo_statistics():
    """Demonstrate various statistics and analytics."""
    print("\n" + "=" * 50)
    print("STATISTICS & ANALYTICS DEMO")
    print("=" * 50)
    
    with get_unit_of_work() as uow:
        # Conversation statistics
        conv_stats = uow.conversations.get_stats()
        print("📊 Conversation Statistics:")
        print(f"  Total conversations: {conv_stats['total_conversations']}")
        print(f"  Total messages: {conv_stats['total_messages']}")
        print(f"  Recent conversations (30 days): {conv_stats['recent_conversations']}")
        print(f"  Average messages per conversation: {conv_stats['avg_messages_per_conversation']}")
        
        # Message statistics
        message_stats = uow.messages.get_message_stats()
        print(f"\n📊 Message Statistics:")
        print(f"  Total messages: {message_stats['total_messages']}")
        print(f"  Role distribution: {message_stats['role_distribution']}")
        print(f"  Embedded messages: {message_stats['embedded_messages']}")
        print(f"  Embedding coverage: {message_stats['embedding_coverage_percent']}%")
        print(f"  Recent messages (24h): {message_stats['recent_messages_24h']}")
        
        # Embedding statistics
        embedding_stats = uow.embeddings.get_coverage_stats()
        print(f"\n📊 Embedding Statistics:")
        print(f"  Total messages: {embedding_stats['total_messages']}")
        print(f"  Embedded messages: {embedding_stats['embedded_messages']}")
        print(f"  Coverage percentage: {embedding_stats['coverage_percent']}%")
        print(f"  Stale embeddings: {embedding_stats['stale_embeddings']}")
        
        # Job statistics
        job_stats = uow.jobs.get_embedding_job_stats()
        print(f"\n📊 Job Statistics:")
        print(f"  Embedding jobs by status: {job_stats['embedding_jobs_by_status']}")
        print(f"  Recent embedding jobs (24h): {job_stats['recent_embedding_jobs_24h']}")
        print(f"  Total embedding jobs: {job_stats['total_embedding_jobs']}")


def main():
    """Main demonstration function."""
    print("REPOSITORY PATTERN DEMONSTRATION")
    print("This demo showcases the PostgreSQL repository implementation")
    print("with full-text search, job queues, and analytics capabilities.")
    
    # Check feature flag
    if not USE_PG_SINGLE_STORE:
        print("\n⚠️  PostgreSQL single store is disabled.")
        print("   Set USE_PG_SINGLE_STORE=true in your .env file to run this demo.")
        return
    
    try:
        # Run demonstrations
        conversation_id, message_ids = demo_conversation_management()
        demo_search_capabilities(conversation_id, message_ids)
        demo_job_queue()
        demo_statistics()
        
        print("\n" + "=" * 50)
        print("🎉 DEMONSTRATION COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        print("\nKey capabilities demonstrated:")
        print("✅ Unit of Work transaction management")
        print("✅ Repository CRUD operations")
        print("✅ Full-text search with PostgreSQL")
        print("✅ Trigram fuzzy search")
        print("✅ PostgreSQL job queue with concurrency")
        print("✅ Comprehensive statistics and analytics")
        print("✅ Legacy API format compatibility")
        
    except Exception as e:
        print(f"\n❌ Demonstration failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
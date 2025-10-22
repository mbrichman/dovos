#!/usr/bin/env python3
"""
PostgreSQL Database Inspector

This script checks what data currently exists in the PostgreSQL database.
"""

import os
import sys
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import get_session_context, test_connection, check_extensions

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_database_contents():
    """Check what data exists in the PostgreSQL database."""
    logger.info("🔍 Checking PostgreSQL database contents...")
    
    try:
        # Test database connection
        if not test_connection():
            logger.error("❌ Cannot connect to PostgreSQL database")
            return False
        logger.info("✅ Database connection established")
        
        with get_session_context() as session:
            # Check conversations
            conversations_count = session.execute(
                "SELECT COUNT(*) FROM conversations"
            ).scalar()
            
            logger.info(f"📚 Conversations: {conversations_count}")
            
            if conversations_count > 0:
                # Get conversation details
                conversations = session.execute("""
                    SELECT id, title, created_at, updated_at 
                    FROM conversations 
                    ORDER BY created_at DESC 
                    LIMIT 10
                """).fetchall()
                
                logger.info("   Recent conversations:")
                for conv in conversations:
                    logger.info(f"   • {conv.title} (ID: {str(conv.id)[:8]}..., {conv.created_at})")
            
            # Check messages
            messages_count = session.execute(
                "SELECT COUNT(*) FROM messages"
            ).scalar()
            
            logger.info(f"💬 Messages: {messages_count}")
            
            if messages_count > 0:
                # Get message breakdown by role
                role_counts = uow.session.execute("""
                    SELECT role, COUNT(*) as count 
                    FROM messages 
                    GROUP BY role 
                    ORDER BY count DESC
                """).fetchall()
                
                logger.info("   Messages by role:")
                for role, count in role_counts:
                    logger.info(f"   • {role}: {count}")
                
                # Get recent messages
                recent_messages = uow.session.execute("""
                    SELECT m.role, LEFT(m.content, 100) as content_preview, 
                           c.title as conversation_title, m.created_at
                    FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    ORDER BY m.created_at DESC
                    LIMIT 5
                """).fetchall()
                
                logger.info("   Recent messages:")
                for msg in recent_messages:
                    preview = msg.content_preview.replace('\n', ' ')
                    logger.info(f"   • [{msg.role}] {preview}... (from: {msg.conversation_title})")
            
            # Check embeddings
            embeddings_count = uow.session.execute(
                "SELECT COUNT(*) FROM message_embeddings"
            ).scalar()
            
            logger.info(f"🎯 Embeddings: {embeddings_count}")
            
            if embeddings_count > 0:
                # Check embedding dimensions
                sample_embedding = uow.session.execute("""
                    SELECT embedding 
                    FROM message_embeddings 
                    LIMIT 1
                """).scalar()
                
                if sample_embedding:
                    # Convert vector to list to get dimensions
                    embedding_dim = len(eval(str(sample_embedding)))
                    logger.info(f"   Embedding dimensions: {embedding_dim}")
                    logger.info(f"   Coverage: {embeddings_count}/{messages_count} messages have embeddings")
            
            # Check jobs
            jobs_count = uow.session.execute(
                "SELECT COUNT(*) FROM jobs"
            ).scalar()
            
            pending_jobs = uow.session.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'pending'"
            ).scalar()
            
            completed_jobs = uow.session.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'completed'"
            ).scalar()
            
            failed_jobs = uow.session.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'failed'"
            ).scalar()
            
            logger.info(f"⚙️  Jobs: {jobs_count} total")
            logger.info(f"   • Pending: {pending_jobs}")
            logger.info(f"   • Completed: {completed_jobs}")
            logger.info(f"   • Failed: {failed_jobs}")
            
            # Overall summary
            logger.info("\n📊 Database Summary:")
            logger.info("=" * 50)
            
            if conversations_count == 0:
                logger.info("❌ No data found - database is empty")
                logger.info("💡 Run a test to import data:")
                logger.info("   python test_manual_chat_import.py")
            else:
                logger.info(f"✅ Database contains data:")
                logger.info(f"   📚 {conversations_count} conversations")
                logger.info(f"   💬 {messages_count} messages")
                logger.info(f"   🎯 {embeddings_count} embeddings")
                logger.info(f"   ⚙️  {jobs_count} background jobs")
                
                # Search readiness
                if embeddings_count > 0:
                    logger.info("🔍 Search capabilities:")
                    logger.info("   ✅ Full-text search ready")
                    logger.info("   ✅ Vector search ready")
                    logger.info("   ✅ Hybrid search ready")
                else:
                    logger.info("⚠️  Search limitations:")
                    logger.info("   ✅ Full-text search ready")
                    logger.info("   ❌ Vector search not ready (no embeddings)")
                    logger.info("   ❌ Hybrid search not ready (no embeddings)")
                    
                    if pending_jobs > 0:
                        logger.info(f"⏳ {pending_jobs} embedding jobs pending - start worker:")
                        logger.info("   python -m db.workers.embedding_worker")
            
        return conversations_count > 0
        
    except Exception as e:
        logger.error(f"❌ Error checking database: {e}")
        logger.error("💡 Make sure PostgreSQL is running and accessible")
        return False


def check_specific_tables():
    """Check if all required tables exist."""
    logger.info("🔧 Checking database schema...")
    
    try:
        with get_unit_of_work() as uow:
            # Check if tables exist
            tables = [
                'conversations',
                'messages', 
                'message_embeddings',
                'jobs'
            ]
            
            existing_tables = []
            for table in tables:
                try:
                    count = uow.session.execute(f"SELECT COUNT(*) FROM {table}").scalar()
                    existing_tables.append((table, count))
                    logger.info(f"✅ {table}: {count} records")
                except Exception:
                    logger.error(f"❌ {table}: table missing or inaccessible")
            
            if len(existing_tables) == len(tables):
                logger.info("✅ All required tables exist")
                return True
            else:
                logger.error("❌ Some tables are missing - run setup:")
                logger.error("   python -c 'from db.database_setup import setup_database; setup_database()'")
                return False
                
    except Exception as e:
        logger.error(f"❌ Schema check failed: {e}")
        return False


def main():
    """Main function."""
    logger.info("🚀 PostgreSQL Database Inspector")
    logger.info("=" * 50)
    
    # Check database URL
    db_url = get_database_url()
    if db_url:
        # Hide password in URL for logging
        safe_url = db_url.split('@')[1] if '@' in db_url else db_url
        logger.info(f"🔗 Database: postgresql://***@{safe_url}")
    else:
        logger.error("❌ No database URL configured")
        return
    
    # Check schema
    schema_ok = check_specific_tables()
    
    if schema_ok:
        # Check contents
        has_data = check_database_contents()
        
        if not has_data:
            logger.info("\n💡 To add test data, run:")
            logger.info("   export USE_POSTGRES=true")
            logger.info("   python test_manual_chat_import.py")
    
    logger.info("\n🎯 To enable PostgreSQL backend in your app:")
    logger.info("   export USE_POSTGRES=true")
    logger.info("   python app.py")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Simple PostgreSQL Database Checker

Quickly check if there's data in the PostgreSQL database.
"""

import os
import sys
import logging
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import get_session_context, test_connection, check_extensions

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def quick_data_check():
    """Quick check of database contents."""
    logger.info("🔍 Checking PostgreSQL Database")
    logger.info("=" * 40)
    
    # Test connection
    if not test_connection():
        logger.error("❌ Cannot connect to PostgreSQL")
        logger.error("💡 Make sure PostgreSQL is running and DATABASE_URL is set")
        return False
    
    logger.info("✅ PostgreSQL connection OK")
    
    # Check extensions
    extensions = check_extensions()
    logger.info(f"🔧 Extensions: pg_trgm={extensions.get('pg_trgm', False)}, vector={extensions.get('vector', False)}")
    
    try:
        with get_session_context() as session:
            # Check tables and counts
            tables_info = []
            
            tables = ['conversations', 'messages', 'message_embeddings', 'jobs']
            
            for table in tables:
                try:
                    result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    tables_info.append((table, count))
                    logger.info(f"📊 {table}: {count} records")
                except Exception as e:
                    logger.error(f"❌ {table}: Error - {e}")
                    return False
            
            # Summary
            total_conversations = tables_info[0][1] if len(tables_info) > 0 else 0
            total_messages = tables_info[1][1] if len(tables_info) > 1 else 0
            total_embeddings = tables_info[2][1] if len(tables_info) > 2 else 0
            total_jobs = tables_info[3][1] if len(tables_info) > 3 else 0
            
            logger.info("")
            logger.info("📋 Summary:")
            
            if total_conversations == 0:
                logger.info("❌ No data found - database is empty")
                logger.info("💡 To add test data:")
                logger.info("   export USE_POSTGRES=true")
                logger.info("   python3 test_manual_chat_import.py")
                return False
            else:
                logger.info(f"✅ Database has data:")
                logger.info(f"   📚 {total_conversations} conversations")
                logger.info(f"   💬 {total_messages} messages")
                logger.info(f"   🎯 {total_embeddings} embeddings")
                logger.info(f"   ⚙️ {total_jobs} background jobs")
                
                # Check recent conversations
                if total_conversations > 0:
                    logger.info("")
                    logger.info("📖 Recent conversations:")
                    result = session.execute(text("""
                        SELECT title, created_at 
                        FROM conversations 
                        ORDER BY created_at DESC 
                        LIMIT 5
                    """))
                    
                    for row in result:
                        logger.info(f"   • {row.title} ({row.created_at})")
                
                # Search readiness
                logger.info("")
                if total_embeddings > 0:
                    logger.info("🔍 Search Status: ✅ All search types ready (FTS + Vector + Hybrid)")
                else:
                    logger.info("🔍 Search Status: ⚠️ Only FTS ready (no vector embeddings)")
                    if total_jobs > 0:
                        pending = session.execute(text("SELECT COUNT(*) FROM jobs WHERE status = 'pending'")).scalar()
                        if pending > 0:
                            logger.info(f"   ⏳ {pending} embedding jobs pending")
                
                return True
                
    except Exception as e:
        logger.error(f"❌ Database check failed: {e}")
        return False


if __name__ == "__main__":
    success = quick_data_check()
    
    if success:
        logger.info("")
        logger.info("🎯 Your PostgreSQL backend is ready!")
        logger.info("   Set: export USE_POSTGRES=true")
        logger.info("   Run: python3 app.py")
    else:
        logger.info("")
        logger.info("💡 Next steps:")
        logger.info("   1. Make sure PostgreSQL is running")
        logger.info("   2. Check DATABASE_URL environment variable")
        logger.info("   3. Run test to add data: python3 test_manual_chat_import.py")
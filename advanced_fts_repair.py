#!/usr/bin/env python3
"""
Advanced FTS5 corruption repair script
"""

import sqlite3
import os
from pathlib import Path
from config import PERSIST_DIR

def find_fts_database():
    """Find the FTS database file"""
    fts_dir = Path(PERSIST_DIR)
    db_path = fts_dir / "conversations_fts.db"
    if db_path.exists():
        return str(db_path)
    return None

def check_fts_integrity():
    """Check FTS5 database integrity"""
    db_path = find_fts_database()
    if not db_path:
        print("❌ FTS database not found")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Database tables: {tables}")
        
        # Check FTS integrity
        try:
            cursor.execute("INSERT INTO conversations_fts(conversations_fts) VALUES('integrity-check')")
            print("✅ FTS integrity check passed")
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"❌ FTS integrity check failed: {e}")
            conn.close()
            return False
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        return False

def repair_fts_corruption():
    """Advanced FTS5 repair procedure"""
    db_path = find_fts_database()
    if not db_path:
        print("❌ FTS database not found")
        return False
    
    print(f"🔧 Repairing FTS database: {db_path}")
    
    try:
        # First, backup the database
        backup_path = db_path + ".backup"
        if os.path.exists(db_path):
            import shutil
            shutil.copy2(db_path, backup_path)
            print(f"✅ Backup created: {backup_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Try to rebuild the FTS index
        try:
            print("🔄 Rebuilding FTS index...")
            cursor.execute("INSERT INTO conversations_fts(conversations_fts) VALUES('rebuild')")
            conn.commit()
            print("✅ FTS index rebuilt successfully")
        except sqlite3.Error as e:
            print(f"⚠️  FTS rebuild failed: {e}")
            
            # If rebuild fails, try to recreate the tables
            print("🔄 Recreating FTS tables...")
            
            # Drop existing FTS table
            try:
                cursor.execute("DROP TABLE IF EXISTS conversations_fts")
                print("🗑️  Dropped existing FTS table")
            except sqlite3.Error as e:
                print(f"⚠️  Could not drop FTS table: {e}")
            
            # Recreate the content table if it's corrupted
            try:
                cursor.execute("DROP TABLE IF EXISTS conversations_content")
                print("🗑️  Dropped corrupted content table")
            except sqlite3.Error as e:
                print(f"⚠️  Could not drop content table: {e}")
            
            # Recreate both tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations_content(
                    rowid INTEGER PRIMARY KEY,
                    doc_id TEXT UNIQUE,
                    title TEXT,
                    content TEXT,
                    source TEXT,
                    date_str TEXT,
                    conversation_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
                    doc_id UNINDEXED,
                    title,
                    content,
                    source,
                    date_str UNINDEXED,
                    conversation_id UNINDEXED,
                    content='conversations_content',
                    tokenize='porter unicode61'
                );
            """)
            
            # Create index
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_id 
                ON conversations_content(doc_id);
            """)
            
            conn.commit()
            print("✅ FTS tables recreated")
        
        # Vacuum to reclaim space and fix any internal inconsistencies
        try:
            print("🔍 Vacuuming database...")
            cursor.execute("VACUUM")
            conn.commit()
            print("✅ Database vacuumed")
        except sqlite3.Error as e:
            print(f"⚠️  Vacuum failed: {e}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error during repair: {e}")
        return False

def full_fts_rebuild():
    """Complete rebuild of FTS system"""
    try:
        # Import models
        from models.fts_model import FTSModel
        from models.conversation_model import ConversationModel
        
        print("🔄 Performing full FTS rebuild...")
        
        # Initialize models
        fts_model = FTSModel()
        conversation_model = ConversationModel()
        
        # Get all documents from ChromaDB
        print("📄 Retrieving documents from ChromaDB...")
        try:
            docs = conversation_model.get_documents(include=["documents", "metadatas"], limit=9999)
        except Exception as e:
            print(f"❌ Error getting documents from ChromaDB: {e}")
            return False
        
        if not docs or not docs.get("documents"):
            print("⚠️  No documents found in ChromaDB")
            # Still clear the FTS to ensure clean state
            fts_model.clear_index()
            return True
        
        # Clear existing FTS
        print("🗑️  Clearing existing FTS index...")
        fts_model.clear_index()
        
        # Process documents
        documents = docs["documents"]
        metadatas = docs.get("metadatas", [])
        ids = docs.get("ids", [])
        
        print(f"📝 Processing {len(documents)} documents...")
        
        fts_documents = []
        for i, doc in enumerate(documents):
            meta = metadatas[i] if i < len(metadatas) else {}
            doc_id = ids[i] if i < len(ids) else f"doc_{i}"
            
            title = meta.get('title', 'Untitled')
            source = meta.get('source', 'unknown')
            conversation_id = meta.get('conversation_id') or meta.get('id', '')
            
            # Get date string
            date_str = "Unknown"
            for date_field in ['latest_ts', 'earliest_ts', 'created', 'modified']:
                if meta.get(date_field):
                    date_str = str(meta[date_field])
                    break
            
            content = doc.strip() if doc else ""
            
            # Skip empty documents
            if not content:
                continue
                
            fts_doc = {
                'doc_id': doc_id,
                'title': title,
                'content': content,
                'source': source,
                'date_str': date_str,
                'conversation_id': conversation_id
            }
            
            fts_documents.append(fts_doc)
            
            # Show progress
            if (i + 1) % 100 == 0:
                print(f"📝 Processed {i + 1}/{len(documents)} documents...")
        
        print(f"💾 Indexing {len(fts_documents)} documents...")
        
        # Add documents to FTS
        if fts_documents:
            fts_model.add_documents(fts_documents)
            print(f"✅ Indexed {len(fts_documents)} documents")
        else:
            print("⚠️  No valid documents to index")
        
        # Verify
        count = fts_model.get_document_count()
        print(f"🔍 Final document count: {count}")
        
        # Test search
        try:
            test_results = fts_model.search("test", limit=1)
            print("✅ FTS search test successful")
        except Exception as e:
            print(f"⚠️  FTS search test failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during full rebuild: {e}")
        return False

def optimize_database():
    """Optimize the FTS database"""
    db_path = find_fts_database()
    if not db_path:
        print("❌ FTS database not found")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        
        print("🔍 Optimizing FTS database...")
        conn.execute("PRAGMA optimize")
        conn.execute("VACUUM")
        conn.commit()
        conn.close()
        
        print("✅ Database optimized")
        return True
        
    except Exception as e:
        print(f"❌ Error optimizing database: {e}")
        return False

if __name__ == "__main__":
    print("=== FTS5 Corruption Repair Tool ===")
    print()
    
    # Check integrity first
    print("1. Checking FTS integrity...")
    integrity_ok = check_fts_integrity()
    
    if not integrity_ok:
        print("\n2. Attempting repair...")
        repair_success = repair_fts_corruption()
        
        if repair_success:
            print("\n3. Checking integrity after repair...")
            integrity_ok = check_fts_integrity()
        else:
            print("❌ Repair failed")
    
    if not integrity_ok:
        print("\n4. Performing full rebuild...")
        rebuild_success = full_fts_rebuild()
        
        if rebuild_success:
            print("\n5. Final integrity check...")
            integrity_ok = check_fts_integrity()
    
    if integrity_ok:
        print("\n6. Optimizing database...")
        optimize_database()
        print("\n🎉 FTS system is healthy!")
    else:
        print("\n❌ FTS system remains unhealthy!")
        print("💡 Try manually running: python migrate_to_fts.py")

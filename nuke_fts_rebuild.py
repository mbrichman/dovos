#!/usr/bin/env python3
"""
Nuclear option: Delete and rebuild FTS5 database completely
"""

import sys
import os
import sqlite3

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.conversation_model import ConversationModel
from models.fts_model import FTSModel
from config import PERSIST_DIR
from pathlib import Path

def nuke_and_rebuild_fts():
    """Completely delete FTS5 database file and rebuild from scratch"""
    print("💣 Nuclear option: Completely rebuilding FTS5 database...")
    
    # Delete the entire FTS database file
    fts_db_path = Path(PERSIST_DIR) / "conversations_fts.db"
    if fts_db_path.exists():
        print(f"🗑️  Deleting corrupted FTS database: {fts_db_path}")
        os.remove(fts_db_path)
    
    # Create a fresh FTS model (will create new database)
    print("🔨 Creating fresh FTS5 database...")
    fts_model = FTSModel()
    
    # Get documents from ChromaDB
    print("📄 Getting documents from ChromaDB...")
    conversation_model = ConversationModel()
    
    try:
        docs = conversation_model.get_documents(include=["documents", "metadatas"], limit=9999)
    except Exception as e:
        print(f"❌ Error getting documents from ChromaDB: {e}")
        return False
    
    if not docs or not docs.get("documents"):
        print("✅ No documents found in ChromaDB - fresh FTS5 database created")
        return True
    
    documents = docs["documents"]
    metadatas = docs.get("metadatas", [])
    ids = docs.get("ids", [])
    
    print(f"📝 Found {len(documents)} documents to index...")
    
    # Prepare documents for FTS indexing
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
        
        # Show progress for every 50 documents
        if (i + 1) % 50 == 0:
            print(f"📝 Processed {i + 1}/{len(documents)} documents...")
    
    print(f"💾 Indexing {len(fts_documents)} documents in fresh FTS5 database...")
    
    # Batch insert into FTS - use smaller batches to avoid memory issues
    batch_size = 100
    total_indexed = 0
    
    try:
        for i in range(0, len(fts_documents), batch_size):
            batch = fts_documents[i:i + batch_size]
            fts_model.add_documents(batch)
            total_indexed += len(batch)
            print(f"💾 Indexed {total_indexed}/{len(fts_documents)} documents...")
        
        print(f"✅ Successfully indexed {total_indexed} documents in fresh FTS5 database")
        
    except Exception as e:
        print(f"❌ Error indexing documents in FTS5: {e}")
        return False
    
    # Verify integrity
    fts_count = fts_model.get_document_count()
    print(f"🔍 Final FTS5 document count: {fts_count}")
    
    # Test search
    print("\n🔍 Testing search for 'shrimp'...")
    try:
        test_results = fts_model.search("shrimp", limit=3)
        print(f"✅ Found {len(test_results)} results for 'shrimp'")
        for result in test_results[:2]:
            print(f"  - {result['title'][:50]}... [Score: {result['rank']:.2f}]")
    except Exception as e:
        print(f"❌ Search test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = nuke_and_rebuild_fts()
    if success:
        print("\n🎉 FTS5 database completely rebuilt! Search should now work perfectly.")
    else:
        print("\n❌ Failed to rebuild FTS5 database!")
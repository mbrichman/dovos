#!/usr/bin/env python3
"""
Quick migration script to populate FTS5 from ChromaDB
"""

import sys
import os

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.conversation_model import ConversationModel
from models.fts_model import FTSModel

def migrate_data():
    """Migrate all conversations from ChromaDB to FTS5"""
    print("🚀 Migrating conversations from ChromaDB to FTS5...")
    
    conversation_model = ConversationModel()
    fts_model = FTSModel()
    
    # Clear existing FTS data first
    print("🗑️  Clearing existing FTS data...")
    fts_model.clear_index()
    
    # Get all documents from ChromaDB
    try:
        docs = conversation_model.get_documents(include=["documents", "metadatas"], limit=9999)
    except Exception as e:
        print(f"❌ Error getting documents from ChromaDB: {e}")
        return False
    
    if not docs or not docs.get("documents"):
        print("❌ No documents found in ChromaDB")
        return False
    
    documents = docs["documents"]
    metadatas = docs.get("metadatas", [])
    ids = docs.get("ids", [])
    
    print(f"📄 Found {len(documents)} documents to migrate")
    
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
        
        # Show progress for every 100 documents
        if (i + 1) % 100 == 0:
            print(f"📝 Processed {i + 1}/{len(documents)} documents...")
    
    print(f"💾 Indexing {len(fts_documents)} documents in FTS5...")
    
    # Batch insert into FTS
    try:
        fts_model.add_documents(fts_documents)
    except Exception as e:
        print(f"❌ Error adding documents to FTS5: {e}")
        return False
    
    # Verify
    fts_count = fts_model.get_document_count()
    print(f"✅ Migration complete! Indexed {fts_count} documents")
    
    # Test search for 'shrimp' to verify
    print("\n🔍 Testing search for 'shrimp'...")
    test_results = fts_model.search("shrimp", limit=5)
    print(f"Found {len(test_results)} results for 'shrimp'")
    
    for result in test_results[:2]:  # Show first 2 results
        print(f"  - {result['title'][:50]}... [Score: {result['rank']:.2f}]")
    
    # Test search for 'chicken' to verify  
    print("\n🔍 Testing search for 'chicken'...")
    test_results = fts_model.search("chicken", limit=5)
    print(f"Found {len(test_results)} results for 'chicken'")
    
    for result in test_results[:2]:  # Show first 2 results
        print(f"  - {result['title'][:50]}... [Score: {result['rank']:.2f}]")
    
    return True

if __name__ == "__main__":
    success = migrate_data()
    if success:
        print("\n🎉 Migration successful! Search should now work.")
    else:
        print("\n❌ Migration failed!")
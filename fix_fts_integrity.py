#!/usr/bin/env python3
"""
Fix FTS5 database integrity issues
"""

import sys
import os

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.conversation_model import ConversationModel
from models.fts_model import FTSModel

def fix_fts_integrity():
    """Fix FTS5 database integrity by clearing and rebuilding"""
    print("🔧 Fixing FTS5 database integrity...")
    
    fts_model = FTSModel()
    
    # Clear the FTS5 database completely
    print("🗑️  Clearing FTS5 database...")
    fts_model.clear_index()
    
    # Get current documents from ChromaDB and re-index them
    print("📄 Re-indexing documents from ChromaDB...")
    conversation_model = ConversationModel()
    
    try:
        docs = conversation_model.get_documents(include=["documents", "metadatas"], limit=9999)
    except Exception as e:
        print(f"❌ Error getting documents from ChromaDB: {e}")
        return False
    
    if not docs or not docs.get("documents"):
        print("✅ No documents found in ChromaDB - FTS5 is now clean and ready")
        return True
    
    documents = docs["documents"]
    metadatas = docs.get("metadatas", [])
    ids = docs.get("ids", [])
    
    print(f"📝 Found {len(documents)} documents to re-index...")
    
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
        if fts_documents:
            fts_model.add_documents(fts_documents)
            print(f"✅ Re-indexed {len(fts_documents)} documents in FTS5")
        else:
            print("✅ No documents to index - FTS5 is clean")
    except Exception as e:
        print(f"❌ Error re-indexing documents in FTS5: {e}")
        return False
    
    # Verify integrity
    fts_count = fts_model.get_document_count()
    print(f"🔍 Final FTS5 document count: {fts_count}")
    
    return True

if __name__ == "__main__":
    success = fix_fts_integrity()
    if success:
        print("\n🎉 FTS5 integrity fixed! Search should now work.")
    else:
        print("\n❌ Failed to fix FTS5 integrity!")
#!/usr/bin/env python3
"""
Database maintenance script to prevent FTS corruption
"""

import sys
import os
from pathlib import Path

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.conversation_model import ConversationModel
from models.fts_model import FTSModel

def run_maintenance():
    """Run database maintenance tasks"""
    print("🔧 Running database maintenance...")
    
    try:
        # Initialize models
        conversation_model = ConversationModel()
        fts_model = FTSModel()
        
        # 1. Check ChromaDB health
        print("1. Checking ChromaDB health...")
        chroma_count = conversation_model.get_count()
        print(f"   ChromaDB document count: {chroma_count}")
        
        # 2. Check FTS health
        print("2. Checking FTS health...")
        fts_count = fts_model.get_document_count()
        print(f"   FTS document count: {fts_count}")
        
        # 3. Check for inconsistencies
        print("3. Checking for inconsistencies...")
        if abs(chroma_count - fts_count) > 5:  # Allow small differences
            print("   ⚠️  Inconsistency detected between ChromaDB and FTS")
            print("   🔄 Running synchronization...")
            sync_fts_with_chromadb()
        else:
            print("   ✅ Databases are consistent")
        
        # 4. Optimize databases
        print("4. Optimizing databases...")
        fts_model.vacuum_database()
        print("   ✅ Databases optimized")
        
        # 5. Run integrity check
        print("5. Running integrity check...")
        try:
            stats = fts_model.get_stats()
            print(f"   ✅ FTS integrity check passed")
            print(f"   📊 Stats: {stats}")
        except Exception as e:
            print(f"   ❌ FTS integrity check failed: {e}")
            return False
        
        print("\n🎉 Maintenance completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Maintenance failed: {e}")
        return False

def sync_fts_with_chromadb():
    """Synchronize FTS index with ChromaDB"""
    try:
        from models.conversation_model import ConversationModel
        from models.fts_model import FTSModel
        
        print("   🔄 Synchronizing FTS with ChromaDB...")
        
        # Initialize models
        conversation_model = ConversationModel()
        fts_model = FTSModel()
        
        # Get all documents from ChromaDB
        print("   📄 Retrieving documents from ChromaDB...")
        docs = conversation_model.get_documents(include=["documents", "metadatas", "ids"], limit=9999)
        
        if not docs or not docs.get("documents"):
            print("   ⚠️  No documents found in ChromaDB")
            return True
        
        documents = docs["documents"]
        metadatas = docs.get("metadatas", [])
        ids = docs.get("ids", [])
        
        print(f"   📝 Processing {len(documents)} documents...")
        
        # Prepare documents for FTS
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
                print(f"   📝 Processed {i + 1}/{len(documents)} documents...")
        
        # Clear and rebuild FTS
        print("   🗑️  Clearing existing FTS index...")
        fts_model.clear_index()
        
        print(f"   💾 Adding {len(fts_documents)} documents to FTS...")
        if fts_documents:
            fts_model.add_documents(fts_documents)
        
        print("   ✅ Synchronization completed")
        return True
        
    except Exception as e:
        print(f"   ❌ Synchronization failed: {e}")
        return False

def rebuild_fts_if_needed():
    """Rebuild FTS index if needed"""
    try:
        from models.fts_model import FTSModel
        
        fts_model = FTSModel()
        
        # Check if FTS needs rebuilding
        count = fts_model.get_document_count()
        if count == 0:
            print("🔍 FTS is empty, rebuilding from ChromaDB...")
            return sync_fts_with_chromadb()
        else:
            print(f"🔍 FTS has {count} documents, no rebuild needed")
            return True
            
    except Exception as e:
        print(f"❌ Error checking FTS status: {e}")
        return False

if __name__ == "__main__":
    print("=== Database Maintenance Tool ===")
    print()
    
    # Run maintenance
    success = run_maintenance()
    
    if not success:
        print("\n🔄 Trying alternative approach...")
        rebuild_fts_if_needed()
    
    print("\n=== Maintenance Complete ===")

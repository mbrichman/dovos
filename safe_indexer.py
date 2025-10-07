#!/usr/bin/env python3
"""
Safe indexing script with FTS corruption prevention
"""

import sys
import os
import signal
import atexit
from pathlib import Path

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.conversation_model import ConversationModel
from models.fts_model import FTSModel

class SafeIndexer:
    def __init__(self):
        self.fts_model = None
        self.conversation_model = None
        self.interrupted = False
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Register cleanup function
        atexit.register(self.cleanup)
    
    def signal_handler(self, signum, frame):
        """Handle interrupt signals"""
        print(f"\n⚠️  Received signal {signum}, shutting down gracefully...")
        self.interrupted = True
    
    def cleanup(self):
        """Cleanup operations"""
        if self.fts_model:
            try:
                # Optimize the database
                self.fts_model.vacuum_database()
                print("✅ Database optimized")
            except Exception as e:
                print(f"⚠️  Error during cleanup: {e}")
    
    def safe_index_json(self, json_path, chunk_size=0):
        """Safely index JSON file with FTS corruption prevention"""
        print("🚀 Starting safe indexing process...")
        
        # Initialize models
        self.conversation_model = ConversationModel()
        self.fts_model = FTSModel()
        
        # Check if file exists
        if not os.path.exists(json_path):
            print(f"❌ File not found: {json_path}")
            return False, "File not found"
        
        # Perform indexing with error handling
        try:
            print(f"📄 Indexing {json_path}...")
            success, message = self.conversation_model.index_json(json_path, chunk_size)
            
            if not success:
                print(f"❌ Indexing failed: {message}")
                return False, message
            
            print(f"✅ Indexing completed: {message}")
            
            # Update FTS index
            print("🔄 Updating FTS index...")
            self.update_fts_index()
            
            print("✅ Safe indexing completed successfully!")
            return True, "Indexing completed successfully"
            
        except Exception as e:
            print(f"❌ Error during indexing: {e}")
            return False, str(e)
    
    def update_fts_index(self):
        """Safely update FTS index with new documents"""
        if not self.conversation_model or not self.fts_model:
            raise Exception("Models not initialized")
        
        # Get recently added documents (those not yet in FTS)
        try:
            # Get all documents from ChromaDB
            all_docs = self.conversation_model.get_documents(
                include=["documents", "metadatas", "ids"], 
                limit=9999
            )
            
            if not all_docs or not all_docs.get("documents"):
                print("⚠️  No documents found in ChromaDB")
                return
            
            documents = all_docs["documents"]
            metadatas = all_docs.get("metadatas", [])
            ids = all_docs.get("ids", [])
            
            print(f"📝 Processing {len(documents)} documents for FTS...")
            
            # Prepare documents for FTS
            fts_documents = []
            for i, doc in enumerate(documents):
                if self.interrupted:
                    print("⏹️  Interrupted by user")
                    break
                
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
                
                # Show progress every 50 documents
                if (i + 1) % 50 == 0:
                    print(f"📝 Processed {i + 1}/{len(documents)} documents...")
            
            if self.interrupted:
                return
            
            # Add documents to FTS (this will replace existing ones with same doc_id)
            if fts_documents:
                print(f"💾 Adding {len(fts_documents)} documents to FTS...")
                self.fts_model.add_documents(fts_documents)
                print(f"✅ Added {len(fts_documents)} documents to FTS")
                
                # Verify count
                fts_count = self.fts_model.get_document_count()
                print(f"🔍 FTS document count: {fts_count}")
            else:
                print("⚠️  No documents to add to FTS")
                
        except Exception as e:
            print(f"❌ Error updating FTS index: {e}")
            raise
    
    def check_health(self):
        """Check the health of both databases"""
        try:
            # Check ChromaDB
            count = self.conversation_model.get_count()
            print(f"📊 ChromaDB document count: {count}")
            
            # Check FTS
            fts_count = self.fts_model.get_document_count()
            print(f"📊 FTS document count: {fts_count}")
            
            # Check FTS integrity
            stats = self.fts_model.get_stats()
            print(f"📊 FTS stats: {stats}")
            
            return True
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python safe_indexer.py <json_file> [chunk_size]")
        print("Example: python safe_indexer.py conversations.json")
        sys.exit(1)
    
    json_file = sys.argv[1]
    chunk_size = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    
    # Create safe indexer
    indexer = SafeIndexer()
    
    # Check health before indexing
    print("🔍 Checking database health before indexing...")
    indexer.check_health()
    
    # Perform safe indexing
    success, message = indexer.safe_index_json(json_file, chunk_size)
    
    if success:
        print("\n✅ Indexing completed successfully!")
        
        # Check health after indexing
        print("\n🔍 Checking database health after indexing...")
        indexer.check_health()
    else:
        print(f"\n❌ Indexing failed: {message}")
        sys.exit(1)

if __name__ == "__main__":
    main()

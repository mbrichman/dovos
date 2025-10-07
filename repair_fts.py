#!/usr/bin/env python3
"""
Script to repair FTS5 corruption in SQLite database
"""

import sqlite3
import os
from config import PERSIST_DIR

def repair_fts_database():
    """Repair FTS5 corruption in the ChromaDB SQLite database"""
    
    # Find the SQLite database file in Chroma storage
    db_path = None
    for root, dirs, files in os.walk(PERSIST_DIR):
        for file in files:
            if file.endswith('.db') or file.endswith('.sqlite'):
                db_path = os.path.join(root, file)
                break
        if db_path:
            break
    
    if not db_path:
        print("No SQLite database found in Chroma storage")
        return False
    
    print(f"Found database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if FTS tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_content'")
        content_tables = cursor.fetchall()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_seg%'")
        seg_tables = cursor.fetchall()
        
        print(f"Content tables: {content_tables}")
        print(f"Segment tables: {seg_tables}")
        
        # Try to rebuild FTS indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        all_tables = cursor.fetchall()
        
        for table in all_tables:
            table_name = table[0]
            if table_name.endswith('_content'):
                # This might be an FTS content table
                fts_table = table_name.replace('_content', '')
                try:
                    print(f"Rebuilding FTS index for {fts_table}...")
                    cursor.execute(f"INSERT INTO {fts_table}({fts_table}) VALUES('rebuild')")
                    print(f"Successfully rebuilt {fts_table}")
                except Exception as e:
                    print(f"Error rebuilding {fts_table}: {e}")
        
        conn.commit()
        conn.close()
        print("FTS repair completed")
        return True
        
    except Exception as e:
        print(f"Error repairing database: {e}")
        return False

def rebuild_entire_fts():
    """Rebuild the entire FTS system from scratch"""
    try:
        # Import your models
        from models.fts_model import FTSModel
        from models.conversation_model import ConversationModel
        
        print("Reinitializing FTS model...")
        fts_model = FTSModel()
        
        # Rebuild from scratch
        print("Rebuilding FTS index...")
        fts_model.rebuild_index()
        
        print("FTS rebuild completed successfully")
        return True
        
    except Exception as e:
        print(f"Error in FTS rebuild: {e}")
        return False

if __name__ == "__main__":
    print("Attempting to repair FTS5 corruption...")
    success = repair_fts_database()
    
    if not success:
        print("\nAttempting full FTS rebuild...")
        rebuild_entire_fts()

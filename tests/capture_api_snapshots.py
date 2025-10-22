#!/usr/bin/env python3
"""
API Snapshot Capture Script

This script runs all API endpoints and captures their responses as golden snapshots
for regression testing during the PostgreSQL migration. 

Run this script to capture the current API behavior as the baseline.
"""
import pytest
import json
import os
import sys
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from api.contracts.api_contract import APIContract

def capture_all_snapshots():
    """Capture all API endpoint responses as golden snapshots"""
    
    # Create Flask app
    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "USE_PG_SINGLE_STORE": False  # Force legacy mode for baseline
    })
    
    client = app.test_client()
    
    # Create snapshots directory
    snapshots_dir = os.path.join(os.path.dirname(__file__), "golden_responses")
    os.makedirs(snapshots_dir, exist_ok=True)
    
    print("🔍 Capturing API snapshots from current system...")
    print("=" * 60)
    
    snapshots = {}
    
    with app.app_context():
        # 1. Test /api/conversations
        print("📝 Capturing /api/conversations...")
        try:
            response = client.get('/api/conversations')
            if response.status_code == 200:
                data = response.get_json()
                if APIContract.validate_response("GET /api/conversations", data):
                    snapshots["GET /api/conversations"] = {
                        "status_code": response.status_code,
                        "data": data,
                        "captured_at": datetime.now().isoformat(),
                        "conversation_count": len(data.get("conversations", [])),
                        "total_conversations": data.get("pagination", {}).get("total", 0)
                    }
                    print(f"   ✅ Captured {len(data.get('conversations', []))} conversations")
                else:
                    print("   ❌ Response failed contract validation")
            else:
                print(f"   ❌ Status {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 2. Test /api/conversation/<id> (if conversations exist)
        print("📝 Capturing /api/conversation/<id>...")
        conversations = snapshots.get("GET /api/conversations", {}).get("data", {}).get("conversations", [])
        if conversations:
            conv_id = conversations[0]["id"]
            try:
                response = client.get(f'/api/conversation/{conv_id}')
                if response.status_code == 200:
                    data = response.get_json()
                    if APIContract.validate_response("GET /api/conversation/<id>", data):
                        snapshots["GET /api/conversation/<id>"] = {
                            "status_code": response.status_code,
                            "data": data,
                            "captured_at": datetime.now().isoformat(),
                            "conversation_id": conv_id,
                            "message_count": len(data.get("messages", []))
                        }
                        print(f"   ✅ Captured conversation with {len(data.get('messages', []))} messages")
                    else:
                        print("   ❌ Response failed contract validation")
                else:
                    print(f"   ❌ Status {response.status_code}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        else:
            print("   ⚠️  No conversations available for detail testing")
        
        # 3. Test /api/search
        print("📝 Capturing /api/search...")
        try:
            response = client.get('/api/search?q=python&n=5')
            if response.status_code == 200:
                data = response.get_json()
                if APIContract.validate_response("GET /api/search", data):
                    snapshots["GET /api/search"] = {
                        "status_code": response.status_code,
                        "data": data,
                        "captured_at": datetime.now().isoformat(),
                        "query": "python",
                        "result_count": len(data.get("results", []))
                    }
                    print(f"   ✅ Captured {len(data.get('results', []))} search results")
                else:
                    print("   ❌ Response failed contract validation")
            elif response.status_code == 400:
                # Search may return 400 if no data - capture this too
                snapshots["GET /api/search"] = {
                    "status_code": response.status_code,
                    "captured_at": datetime.now().isoformat(),
                    "note": "Search returned 400 - likely no data indexed"
                }
                print("   ⚠️  Search returned 400 (likely no data indexed)")
            else:
                print(f"   ❌ Status {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 4. Test /api/rag/query
        print("📝 Capturing /api/rag/query...")
        try:
            query_data = {
                "query": "How to use Python for data analysis?",
                "n_results": 3,
                "search_type": "semantic"
            }
            response = client.post('/api/rag/query', json=query_data, content_type='application/json')
            
            if response.status_code == 200:
                data = response.get_json()
                if APIContract.validate_response("POST /api/rag/query", data):
                    snapshots["POST /api/rag/query"] = {
                        "status_code": response.status_code,
                        "data": data,
                        "captured_at": datetime.now().isoformat(),
                        "query": query_data["query"],
                        "result_count": len(data.get("results", []))
                    }
                    print(f"   ✅ Captured {len(data.get('results', []))} RAG results")
                else:
                    print("   ❌ Response failed contract validation")
            else:
                # RAG may fail if not configured - capture the error response
                snapshots["POST /api/rag/query"] = {
                    "status_code": response.status_code,
                    "captured_at": datetime.now().isoformat(),
                    "note": f"RAG endpoint returned {response.status_code}"
                }
                print(f"   ⚠️  RAG query returned {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 5. Test /api/rag/health
        print("📝 Capturing /api/rag/health...")
        try:
            response = client.get('/api/rag/health')
            if response.status_code == 200:
                data = response.get_json()
                if APIContract.validate_response("GET /api/rag/health", data):
                    snapshots["GET /api/rag/health"] = {
                        "status_code": response.status_code,
                        "data": data,
                        "captured_at": datetime.now().isoformat(),
                        "health_status": data.get("status")
                    }
                    print(f"   ✅ Captured health status: {data.get('status')}")
                else:
                    print("   ❌ Response failed contract validation")
            else:
                print(f"   ❌ Status {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 6. Test /api/stats
        print("📝 Capturing /api/stats...")
        try:
            response = client.get('/api/stats')
            if response.status_code == 200:
                data = response.get_json()
                if APIContract.validate_response("GET /api/stats", data):
                    snapshots["GET /api/stats"] = {
                        "status_code": response.status_code,
                        "data": data,
                        "captured_at": datetime.now().isoformat(),
                        "document_count": data.get("document_count"),
                        "embedding_model": data.get("embedding_model")
                    }
                    print(f"   ✅ Captured stats: {data.get('document_count')} documents")
                else:
                    print("   ❌ Response failed contract validation")
            else:
                print(f"   ❌ Status {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 7. Test error handling
        print("📝 Capturing error responses...")
        try:
            # Test 404 error
            response = client.get('/api/conversation/nonexistent-id')
            if response.status_code in [404, 500]:
                error_data = response.get_json() if response.get_json() else {"error": "Not found"}
                snapshots["ERROR 404"] = {
                    "status_code": response.status_code,
                    "data": error_data,
                    "captured_at": datetime.now().isoformat()
                }
                print(f"   ✅ Captured 404 error response")
        except Exception as e:
            print(f"   ❌ Error capturing 404: {e}")
    
    # Save all snapshots to file
    snapshot_file = os.path.join(snapshots_dir, "live_api_snapshots.json")
    with open(snapshot_file, 'w') as f:
        json.dump(snapshots, f, indent=2, sort_keys=True)
    
    print("=" * 60)
    print(f"📄 Saved {len(snapshots)} snapshots to: {snapshot_file}")
    
    # Create summary report
    create_snapshot_report(snapshots, snapshots_dir)
    
    return snapshots

def create_snapshot_report(snapshots, snapshots_dir):
    """Create a human-readable report of captured snapshots"""
    
    report_file = os.path.join(snapshots_dir, "snapshot_report.md")
    
    with open(report_file, 'w') as f:
        f.write("# API Snapshot Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("This report contains the baseline API responses captured from the current system.\n")
        f.write("These responses serve as golden snapshots for regression testing during migration.\n\n")
        
        f.write("## Captured Endpoints\n\n")
        
        for endpoint, snapshot in snapshots.items():
            f.write(f"### {endpoint}\n\n")
            f.write(f"- **Status Code**: {snapshot['status_code']}\n")
            f.write(f"- **Captured At**: {snapshot['captured_at']}\n")
            
            if 'conversation_count' in snapshot:
                f.write(f"- **Conversations**: {snapshot['conversation_count']}\n")
            if 'message_count' in snapshot:
                f.write(f"- **Messages**: {snapshot['message_count']}\n")
            if 'result_count' in snapshot:
                f.write(f"- **Results**: {snapshot['result_count']}\n")
            if 'document_count' in snapshot:
                f.write(f"- **Documents**: {snapshot['document_count']}\n")
            if 'health_status' in snapshot:
                f.write(f"- **Health**: {snapshot['health_status']}\n")
            if 'note' in snapshot:
                f.write(f"- **Note**: {snapshot['note']}\n")
            
            f.write("\n")
        
        f.write("\n## Usage\n\n")
        f.write("These snapshots can be used in tests to:\n")
        f.write("1. Validate that migrated API responses match exactly\n")
        f.write("2. Detect any unintended changes in response structure\n") 
        f.write("3. Ensure frontend compatibility is preserved\n")
        f.write("4. Benchmark performance against baseline\n\n")
        
        f.write("## Files\n\n")
        f.write("- `live_api_snapshots.json` - Full response data\n")
        f.write("- `snapshot_report.md` - This human-readable report\n")
    
    print(f"📄 Created report: {report_file}")

if __name__ == "__main__":
    print("🚀 Starting API snapshot capture...")
    snapshots = capture_all_snapshots()
    print(f"\n✅ Capture complete! {len(snapshots)} endpoints captured.")
    print("\nThese snapshots will serve as the baseline for PostgreSQL migration testing.")
    print("Run this script again after migration to compare responses.")
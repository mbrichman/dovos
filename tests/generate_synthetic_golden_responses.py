#!/usr/bin/env python3
"""
Generate Synthetic Golden Responses

This script regenerates all golden response files with completely synthetic,
safe data instead of real personal information from the production database.

The synthetic responses maintain the same structure as real API responses
but contain only generic, safe, and clearly fictional data.

Usage:
    python tests/generate_synthetic_golden_responses.py
"""

import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fixtures.synthetic_responses import (
    generate_conversations_response,
    generate_conversation_detail_response,
    generate_search_response,
    generate_rag_query_response,
    generate_rag_health_response,
    generate_stats_response,
    generate_collection_count_response,
    generate_live_api_snapshots,
)


def get_golden_responses_directory():
    """Get or create golden responses directory."""
    golden_dir = os.path.join(os.path.dirname(__file__), "golden_responses")
    os.makedirs(golden_dir, exist_ok=True)
    return golden_dir


def save_golden_response(data, filename, golden_dir):
    """Save a golden response to file."""
    filepath = os.path.join(golden_dir, filename)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    return filepath


def generate_all_golden_responses():
    """Generate all golden responses with synthetic data."""
    
    golden_dir = get_golden_responses_directory()
    
    print("🔄 Generating synthetic golden responses...")
    print("=" * 60)
    
    # 1. GET /api/conversations
    print("📝 Generating GET__api_conversations_live.json...")
    conversations_data = generate_conversations_response(count=50)
    filepath = save_golden_response(
        conversations_data,
        "GET__api_conversations_live.json",
        golden_dir
    )
    print(f"   ✅ Saved to {os.path.basename(filepath)}")
    print(f"      - {len(conversations_data.get('documents', []))} conversations")
    
    # 2. GET /api/conversation/<id>
    print("📝 Generating GET__api_conversation_id_live.json...")
    conversation_detail = generate_conversation_detail_response()
    filepath = save_golden_response(
        conversation_detail,
        "GET__api_conversation_id_live.json",
        golden_dir
    )
    print(f"   ✅ Saved to {os.path.basename(filepath)}")
    
    # 3. GET /api/search
    print("📝 Generating GET__api_search_live.json...")
    search_data = generate_search_response(query="python", count=10)
    filepath = save_golden_response(
        search_data,
        "GET__api_search_live.json",
        golden_dir
    )
    print(f"   ✅ Saved to {os.path.basename(filepath)}")
    print(f"      - {len(search_data.get('results', []))} search results")
    
    # 4. POST /api/rag/query
    print("📝 Generating POST__api_rag_query_live.json...")
    rag_data = generate_rag_query_response(count=10)
    filepath = save_golden_response(
        rag_data,
        "POST__api_rag_query_live.json",
        golden_dir
    )
    print(f"   ✅ Saved to {os.path.basename(filepath)}")
    print(f"      - {len(rag_data.get('results', []))} RAG results")
    
    # 5. GET /api/rag/health
    print("📝 Generating GET__api_rag_health_live.json...")
    health_data = generate_rag_health_response()
    filepath = save_golden_response(
        health_data,
        "GET__api_rag_health_live.json",
        golden_dir
    )
    print(f"   ✅ Saved to {os.path.basename(filepath)}")
    
    # 6. GET /api/stats
    print("📝 Generating GET__api_stats_live.json...")
    stats_data = generate_stats_response()
    filepath = save_golden_response(
        stats_data,
        "GET__api_stats_live.json",
        golden_dir
    )
    print(f"   ✅ Saved to {os.path.basename(filepath)}")
    
    # 7. GET /api/collection/count
    print("📝 Generating GET__api_collection_count_live.json...")
    count_data = generate_collection_count_response()
    filepath = save_golden_response(
        count_data,
        "GET__api_collection_count_live.json",
        golden_dir
    )
    print(f"   ✅ Saved to {os.path.basename(filepath)}")
    
    # 8. live_api_snapshots.json (comprehensive snapshot)
    print("📝 Generating live_api_snapshots.json...")
    snapshots = generate_live_api_snapshots()
    filepath = save_golden_response(
        snapshots,
        "live_api_snapshots.json",
        golden_dir
    )
    print(f"   ✅ Saved to {os.path.basename(filepath)}")
    
    print("=" * 60)
    print(f"✅ All golden responses regenerated with synthetic safe data!")
    print(f"📁 Location: {golden_dir}")
    print("\\n📋 Summary:")
    print("   ✓ All files contain only synthetic, safe data")
    print("   ✓ No personal information, locations, or real names")
    print("   ✓ Files are deterministically regenerable")
    print("   ✓ API structure validation still works")
    
    return golden_dir


if __name__ == "__main__":
    try:
        generate_all_golden_responses()
        print(f"\\n🎉 Generation complete!")
        sys.exit(0)
    except Exception as e:
        print(f"\\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

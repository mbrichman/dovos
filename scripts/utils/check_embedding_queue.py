#!/usr/bin/env python3
"""
Check the status of the embedding job queue.

Usage:
    python scripts/utils/check_embedding_queue.py
    
    # Or in Docker:
    docker compose exec dovos-rag python scripts/utils/check_embedding_queue.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from db.repositories.unit_of_work import get_unit_of_work


def check_queue():
    """Check and display embedding queue status."""
    
    with get_unit_of_work() as uow:
        jobs = uow.jobs.get_all()
        
        # Group by status
        pending = [j for j in jobs if j.status == 'pending']
        processing = [j for j in jobs if j.status == 'running']
        completed = [j for j in jobs if j.status == 'completed']
        failed = [j for j in jobs if j.status == 'failed']
        
        # Print summary
        print("=" * 60)
        print("📊 EMBEDDING QUEUE STATUS")
        print("=" * 60)
        print(f"  🟡 Pending:    {len(pending):>5}")
        print(f"  🔵 Processing: {len(processing):>5}")
        print(f"  🟢 Completed:  {len(completed):>5}")
        print(f"  🔴 Failed:     {len(failed):>5}")
        print(f"  ━━━━━━━━━━━━━━━━━━━━━")
        print(f"  📦 Total:      {len(jobs):>5}")
        print("=" * 60)
        
        # Show pending jobs
        if pending:
            print(f"\n🔄 Next {min(10, len(pending))} pending jobs:")
            for i, job in enumerate(pending[:10], 1):
                payload = job.payload or {}
                conv_id = payload.get('conversation_id', 'Unknown')
                title = payload.get('conversation_title', 'Untitled')
                # Truncate long titles
                if len(title) > 50:
                    title = title[:47] + "..."
                print(f"  {i:2}. Job {job.id} - Conv {conv_id}")
                print(f"      {title}")
        
        # Show processing jobs
        if processing:
            print(f"\n⚙️  Currently processing:")
            for job in processing:
                payload = job.payload or {}
                title = payload.get('conversation_title', 'Untitled')
                if len(title) > 50:
                    title = title[:47] + "..."
                print(f"  - Job {job.id}: {title}")
        
        # Show failed jobs
        if failed:
            print(f"\n❌ Failed jobs (last 5):")
            for job in failed[-5:]:
                payload = job.payload or {}
                title = payload.get('conversation_title', 'Untitled')
                error = payload.get('error', 'Unknown error')
                print(f"  - Job {job.id}: {title}")
                print(f"    Error: {error}")
        
        # Show completion percentage
        if jobs:
            completion_pct = (len(completed) / len(jobs)) * 100
            print(f"\n📈 Progress: {completion_pct:.1f}% complete")
        
        print()


if __name__ == "__main__":
    try:
        check_queue()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

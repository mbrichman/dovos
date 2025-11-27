#!/usr/bin/env python3
"""
Backfill sequence numbers in message metadata for all existing conversations.

This script assigns sequence numbers (0, 1, 2, ...) to messages within each conversation,
ordered by (created_at, id). This ensures deterministic ordering when messages have
identical timestamps.

Usage:
    python scripts/database/backfill_message_sequences.py [--dry-run]
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / '.env')

from db.repositories.unit_of_work import get_unit_of_work
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_sequences(dry_run=False):
    """Backfill sequence numbers for all messages."""
    
    with get_unit_of_work() as uow:
        # Get all conversations
        conversations = uow.conversations.get_all()
        
        if not conversations:
            logger.info("No conversations found")
            return
        
        total_conversations = len(conversations)
        total_messages_updated = 0
        
        logger.info(f"Processing {total_conversations} conversations...")
        
        for conv_idx, conversation in enumerate(conversations, 1):
            # Get all messages for this conversation, ordered by (created_at, id)
            messages = uow.messages.get_by_conversation(conversation.id)
            
            if not messages:
                continue
            
            messages_to_update = []
            
            for sequence, msg in enumerate(messages):
                # Check if sequence is already set correctly
                current_sequence = None
                if msg.message_metadata and isinstance(msg.message_metadata, dict):
                    try:
                        current_sequence = int(msg.message_metadata.get('sequence', -1))
                    except (ValueError, TypeError):
                        current_sequence = None
                
                # Only update if sequence is missing or different
                if current_sequence != sequence:
                    # Update metadata
                    if not msg.message_metadata:
                        msg.message_metadata = {}
                    
                    msg.message_metadata['sequence'] = sequence
                    messages_to_update.append((msg.id, sequence))
            
            if messages_to_update:
                if not dry_run:
                    # Flush changes for this conversation
                    uow.session.flush()
                    total_messages_updated += len(messages_to_update)
                
                logger.info(
                    f"[{conv_idx}/{total_conversations}] {conversation.title}: "
                    f"Updated {len(messages_to_update)} messages with sequences"
                )
            else:
                logger.debug(
                    f"[{conv_idx}/{total_conversations}] {conversation.title}: "
                    f"No updates needed ({len(messages)} messages already correct)"
                )
        
        if not dry_run:
            uow.commit()
            logger.info(f"✅ Successfully backfilled {total_messages_updated} messages")
        else:
            logger.info(f"🔍 DRY RUN: Would update {total_messages_updated} messages")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Backfill sequence numbers in message metadata'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes'
    )
    
    args = parser.parse_args()
    
    try:
        logger.info(f"Starting backfill... (dry_run={args.dry_run})")
        backfill_sequences(dry_run=args.dry_run)
        logger.info("✅ Backfill complete!")
        return 0
    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

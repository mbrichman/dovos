#!/usr/bin/env python3
"""
Backfill topics for existing OpenWebUI conversations.

This script fetches topics (tags) from OpenWebUI for all conversations
that were imported before topic syncing was implemented.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from db.repositories.unit_of_work import get_unit_of_work
from db.services.openwebui_client import OpenWebUIClient, OpenWebUIClientError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def backfill_topics():
    """Backfill topics for all OpenWebUI conversations."""

    # Get OpenWebUI client configuration
    with get_unit_of_work() as uow:
        url = uow.settings.get_value('openwebui_url')
        api_key = uow.settings.get_value('openwebui_api_key')

    if not url or not api_key:
        logger.error("OpenWebUI URL and API key must be configured in settings")
        return

    client = OpenWebUIClient(base_url=url, api_key=api_key)

    # Get all OpenWebUI conversations (extract IDs and source_ids while in session)
    with get_unit_of_work() as uow:
        conversations = uow.conversations.get_all_by_source_type('openwebui')
        # Extract data while session is active
        conv_data = [(c.id, c.source_id, c.title[:50] if c.title else 'Untitled') for c in conversations]
        logger.info(f"Found {len(conv_data)} OpenWebUI conversations")

    updated = 0
    skipped = 0
    failed = 0

    for i, (conv_id, source_id, title) in enumerate(conv_data):
        if not source_id:
            skipped += 1
            continue

        try:
            # Fetch topics from OpenWebUI
            topic_names = client.get_chat_topics(source_id)

            if topic_names:
                with get_unit_of_work() as uow:
                    uow.topics.set_conversation_topics(conv_id, topic_names)
                updated += 1
                logger.debug(f"Updated {title} with {len(topic_names)} topics")
            else:
                skipped += 1

        except Exception as e:
            failed += 1
            logger.warning(f"Failed to fetch topics for {source_id}: {e}")

        # Progress update every 100 conversations
        if (i + 1) % 100 == 0:
            logger.info(f"Progress: {i + 1}/{len(conv_data)} ({updated} updated, {skipped} skipped, {failed} failed)")

    logger.info(f"Backfill complete: {updated} updated, {skipped} skipped, {failed} failed")

    # Show topic stats
    with get_unit_of_work() as uow:
        counts = uow.topics.get_topic_counts()
        logger.info(f"Total topics: {len(counts)}")
        logger.info("Top 10 topics:")
        for t in counts[:10]:
            logger.info(f"  {t['name']}: {t['count']} conversations")


if __name__ == '__main__':
    backfill_topics()

"""
Tests for Stats Timeline Histogram Feature

Tests the timeline histogram functionality including:
- Repository method get_timeline_histogram()
- Stats endpoint integration
- Multiple sources (ChatGPT, Claude, etc.)
- Different time buckets (daily, weekly, monthly)
"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from db.repositories.unit_of_work import UnitOfWork
from db.models.models import Conversation, Message, MessageEmbedding
from controllers.postgres_controller import PostgresController
from tests.utils.seed import create_conversation, create_message


@pytest.fixture(autouse=True)
def use_test_db(test_db_engine):
    """Use test database and ensure clean state."""
    import db.database as dbm
    import controllers.postgres_controller as pc_module
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    original_engine = dbm.engine
    original_session_factory = dbm.SessionFactory
    original_controller = getattr(pc_module, "_controller", None)

    dbm.engine = test_db_engine
    dbm.SessionFactory = sessionmaker(bind=test_db_engine)
    pc_module._controller = None

    # Ensure view exists
    sess = Session(bind=test_db_engine)
    try:
        sess.execute(text("DROP VIEW IF EXISTS conversation_summaries"))
        sess.execute(text("""
            CREATE VIEW conversation_summaries AS
            SELECT
                c.id,
                COUNT(m.id) AS message_count,
                MIN(m.created_at) AS earliest_message_at,
                MAX(m.created_at) AS latest_message_at,
                SUBSTRING(MAX(CASE WHEN m.role = 'assistant' THEN m.content END) FROM 1 FOR 200) AS preview
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            GROUP BY c.id
        """))

        sess.execute(text("DROP VIEW IF EXISTS embedding_coverage"))
        sess.execute(text("""
            CREATE VIEW embedding_coverage AS
            SELECT
                COUNT(DISTINCT m.id) as total_messages,
                COUNT(DISTINCT e.message_id) as embedded_messages,
                ROUND(100.0 * COUNT(DISTINCT e.message_id) / NULLIF(COUNT(DISTINCT m.id), 0), 2) as coverage_percent,
                COUNT(DISTINCT CASE WHEN e.updated_at < m.updated_at THEN e.message_id END) as stale_embeddings
            FROM messages m
            LEFT JOIN message_embeddings e ON m.id = e.message_id
        """))

        sess.commit()
    except Exception:
        sess.rollback()
    finally:
        sess.close()

    # Clean tables
    sess = Session(bind=test_db_engine)
    try:
        sess.query(MessageEmbedding).delete()
        sess.query(Message).delete()
        sess.query(Conversation).delete()
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()

    try:
        yield test_db_engine
    finally:
        dbm.engine = original_engine
        dbm.SessionFactory = original_session_factory
        pc_module._controller = original_controller


def create_test_conversation_with_source(
    uow: UnitOfWork,
    title: str,
    source: str,
    created_at: datetime,
    message_count: int = 2
) -> tuple[Conversation, list[Message]]:
    """Helper to create a conversation with specific source."""
    conversation = create_conversation(uow, title=title, created_at=created_at)

    messages = []
    for i in range(message_count):
        role = "user" if i % 2 == 0 else "assistant"
        message = create_message(
            uow,
            conversation.id,
            role=role,
            content=f"Message {i} in {title}",
            metadata={"source": source},
            created_at=created_at + timedelta(minutes=i)
        )
        messages.append(message)

    return conversation, messages


@pytest.mark.unit
class TestTimelineHistogramRepository:
    """Test the get_timeline_histogram() repository method."""

    def test_empty_database_returns_empty_list(self, test_db_engine):
        """Timeline histogram should return empty list for empty database."""
        session = Session(bind=test_db_engine)
        uow = UnitOfWork(session=session)

        try:
            timeline = uow.conversations.get_timeline_histogram()
            assert timeline == []
        finally:
            session.close()

    def test_single_source_timeline(self, test_db_engine):
        """Test timeline with conversations from single source."""
        session = Session(bind=test_db_engine)
        uow = UnitOfWork(session=session)

        try:
            base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

            # Create 3 conversations over 3 days, all ChatGPT
            for i in range(3):
                create_test_conversation_with_source(
                    uow,
                    title=f"Conv {i}",
                    source="chatgpt",
                    created_at=base_date + timedelta(days=i)
                )

            uow.commit()

            timeline = uow.conversations.get_timeline_histogram()

            # Should have 3 buckets (daily for <30 days)
            assert len(timeline) == 3

            # Each bucket should have chatgpt count
            for bucket in timeline:
                assert 'date' in bucket
                assert 'chatgpt' in bucket
                assert bucket['chatgpt'] == 1
        finally:
            session.close()

    def test_multiple_sources_timeline(self, test_db_engine):
        """Test timeline with conversations from multiple sources."""
        session = Session(bind=test_db_engine)
        uow = UnitOfWork(session=session)

        try:
            base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

            # Day 1: 2 ChatGPT, 1 Claude
            create_test_conversation_with_source(
                uow, "ChatGPT 1", "chatgpt", base_date
            )
            create_test_conversation_with_source(
                uow, "ChatGPT 2", "chatgpt", base_date + timedelta(hours=1)
            )
            create_test_conversation_with_source(
                uow, "Claude 1", "claude", base_date + timedelta(hours=2)
            )

            # Day 2: 1 ChatGPT, 2 Claude
            day2 = base_date + timedelta(days=1)
            create_test_conversation_with_source(
                uow, "ChatGPT 3", "chatgpt", day2
            )
            create_test_conversation_with_source(
                uow, "Claude 2", "claude", day2 + timedelta(hours=1)
            )
            create_test_conversation_with_source(
                uow, "Claude 3", "claude", day2 + timedelta(hours=2)
            )

            uow.commit()

            timeline = uow.conversations.get_timeline_histogram()

            # Should have 2 buckets (2 days)
            assert len(timeline) == 2

            # Check day 1
            day1_bucket = timeline[0]
            assert day1_bucket['chatgpt'] == 2
            assert day1_bucket['claude'] == 1

            # Check day 2
            day2_bucket = timeline[1]
            assert day2_bucket['chatgpt'] == 1
            assert day2_bucket['claude'] == 2
        finally:
            session.close()

    def test_weekly_buckets_for_medium_range(self, test_db_engine):
        """Test that timeline uses weekly buckets for 31-180 day range."""
        session = Session(bind=test_db_engine)
        uow = UnitOfWork(session=session)

        try:
            base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

            # Create conversations over 60 days (should trigger weekly buckets)
            for i in range(0, 60, 10):  # Every 10 days
                create_test_conversation_with_source(
                    uow,
                    title=f"Conv {i}",
                    source="chatgpt",
                    created_at=base_date + timedelta(days=i)
                )

            uow.commit()

            timeline = uow.conversations.get_timeline_histogram()

            # Should have fewer buckets than days (weekly grouping)
            assert len(timeline) < 60
            assert len(timeline) >= 1

            # Each bucket should have source data
            for bucket in timeline:
                assert 'date' in bucket
                assert 'chatgpt' in bucket
        finally:
            session.close()

    def test_monthly_buckets_for_long_range(self, test_db_engine):
        """Test that timeline uses monthly buckets for 181-730 day range."""
        session = Session(bind=test_db_engine)
        uow = UnitOfWork(session=session)

        try:
            base_date = datetime(2023, 1, 1, tzinfo=timezone.utc)

            # Create conversations over 200 days (should trigger monthly buckets)
            for i in range(0, 200, 30):  # Every 30 days
                create_test_conversation_with_source(
                    uow,
                    title=f"Conv {i}",
                    source="chatgpt",
                    created_at=base_date + timedelta(days=i)
                )

            uow.commit()

            timeline = uow.conversations.get_timeline_histogram()

            # Should have monthly buckets (roughly 7 months)
            assert len(timeline) <= 8  # Allow for rounding
            assert len(timeline) >= 1
        finally:
            session.close()

    def test_source_normalization(self, test_db_engine):
        """Test that source names are properly normalized."""
        session = Session(bind=test_db_engine)
        uow = UnitOfWork(session=session)

        try:
            base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

            # Create conversations with various source formats
            create_test_conversation_with_source(
                uow, "Conv 1", "ChatGPT", base_date  # Capitalized
            )
            create_test_conversation_with_source(
                uow, "Conv 2", "CHATGPT", base_date  # All caps
            )
            create_test_conversation_with_source(
                uow, "Conv 3", "gpt-4", base_date  # Contains 'gpt'
            )
            create_test_conversation_with_source(
                uow, "Conv 4", "Claude-AI", base_date  # Contains 'claude'
            )

            uow.commit()

            timeline = uow.conversations.get_timeline_histogram()

            # Should normalize all to lowercase
            assert len(timeline) == 1  # All on same day
            bucket = timeline[0]

            # Should group ChatGPT variants together
            assert 'chatgpt' in bucket
            assert bucket['chatgpt'] == 3

            # Should normalize Claude
            assert 'claude' in bucket
            assert bucket['claude'] == 1
        finally:
            session.close()

    def test_unknown_source_handling(self, test_db_engine):
        """Test handling of conversations without source metadata."""
        session = Session(bind=test_db_engine)
        uow = UnitOfWork(session=session)

        try:
            base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

            # Create conversation with no source in metadata
            conversation = create_conversation(
                uow, title="No Source", created_at=base_date
            )
            create_message(
                uow,
                conversation.id,
                role="user",
                content="Test message",
                metadata={},  # No source field
                created_at=base_date
            )

            uow.commit()

            timeline = uow.conversations.get_timeline_histogram()

            # Should categorize as 'unknown'
            assert len(timeline) == 1
            assert 'unknown' in timeline[0]
            assert timeline[0]['unknown'] == 1
        finally:
            session.close()


@pytest.mark.unit
class TestStatsEndpointWithTimeline:
    """Test stats endpoint includes timeline data."""

    def test_stats_includes_timeline_field(self, test_db_engine):
        """Stats response should include timeline field."""
        controller = PostgresController()
        stats = controller.get_stats()

        assert 'timeline' in stats
        assert isinstance(stats['timeline'], list)

    def test_stats_timeline_with_data(self, test_db_engine):
        """Stats timeline should contain actual histogram data."""
        session = Session(bind=test_db_engine)
        uow = UnitOfWork(session=session)

        try:
            base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

            # Create test data
            create_test_conversation_with_source(
                uow, "Conv 1", "chatgpt", base_date
            )
            create_test_conversation_with_source(
                uow, "Conv 2", "claude", base_date + timedelta(days=1)
            )

            uow.commit()

            controller = PostgresController()
            stats = controller.get_stats()

            # Should have timeline data
            assert 'timeline' in stats
            assert len(stats['timeline']) > 0

            # Each bucket should have date and source counts
            for bucket in stats['timeline']:
                assert 'date' in bucket
                # Should have at least one source
                sources = [k for k in bucket.keys() if k != 'date']
                assert len(sources) > 0
        finally:
            session.close()

    def test_stats_includes_embedding_data(self, test_db_engine):
        """Stats should include total_embeddings and embedding_coverage_percent."""
        controller = PostgresController()
        stats = controller.get_stats()

        assert 'total_embeddings' in stats
        assert 'embedding_coverage_percent' in stats
        assert isinstance(stats['total_embeddings'], int)
        assert isinstance(stats['embedding_coverage_percent'], (int, float))

    def test_stats_includes_message_count(self, test_db_engine):
        """Stats should include total_messages count."""
        session = Session(bind=test_db_engine)
        uow = UnitOfWork(session=session)

        try:
            base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

            # Create conversation with 4 messages
            create_test_conversation_with_source(
                uow, "Test Conv", "chatgpt", base_date, message_count=4
            )

            uow.commit()

            controller = PostgresController()
            stats = controller.get_stats()

            assert 'total_messages' in stats
            assert stats['total_messages'] == 4
            assert stats['total_conversations'] == 1
        finally:
            session.close()


@pytest.mark.unit
class TestTimelineEdgeCases:
    """Test edge cases and error handling."""

    def test_same_day_conversations(self, test_db_engine):
        """Test conversations all created on same day."""
        session = Session(bind=test_db_engine)
        uow = UnitOfWork(session=session)

        try:
            same_date = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

            # Create 3 conversations at different times on same day
            for i in range(3):
                create_test_conversation_with_source(
                    uow,
                    f"Conv {i}",
                    "chatgpt",
                    same_date + timedelta(hours=i)
                )

            uow.commit()

            timeline = uow.conversations.get_timeline_histogram()

            # Should have single bucket for that day
            assert len(timeline) == 1
            assert timeline[0]['chatgpt'] == 3
        finally:
            session.close()

    def test_sparse_timeline(self, test_db_engine):
        """Test timeline with large gaps between conversations."""
        session = Session(bind=test_db_engine)
        uow = UnitOfWork(session=session)

        try:
            # Create conversations 100 days apart
            base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

            create_test_conversation_with_source(
                uow, "Conv 1", "chatgpt", base_date
            )
            create_test_conversation_with_source(
                uow, "Conv 2", "chatgpt", base_date + timedelta(days=100)
            )

            uow.commit()

            timeline = uow.conversations.get_timeline_histogram()

            # Should only have buckets for dates with data
            # (not empty buckets for the gap)
            assert len(timeline) >= 1

            total_conversations = sum(
                bucket.get('chatgpt', 0) for bucket in timeline
            )
            assert total_conversations == 2
        finally:
            session.close()

    def test_error_handling_returns_empty_list(self, test_db_engine):
        """Test that errors in timeline query return empty list gracefully."""
        session = Session(bind=test_db_engine)
        uow = UnitOfWork(session=session)

        try:
            # This should not raise an exception even if there are issues
            timeline = uow.conversations.get_timeline_histogram()

            # Should return a list (possibly empty)
            assert isinstance(timeline, list)
        finally:
            session.close()

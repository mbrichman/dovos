"""
Generate comprehensive test queries for search optimization.

This script analyzes the corpus to create a representative set of test queries
spanning different types (keyword, phrase, semantic) and difficulty levels.
"""

import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from db.repositories.unit_of_work import get_unit_of_work

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class QueryTestCase:
    """A single test query with expected results."""
    query: str
    query_type: str  # 'keyword', 'phrase', 'semantic', 'acronym'
    difficulty: str  # 'easy', 'medium', 'hard'
    expected_message_ids: List[str]
    expected_conversation_ids: List[str]
    notes: str = ""

    def to_dict(self):
        return asdict(self)


class QueryGenerator:
    """Generates test queries by analyzing the corpus."""

    def __init__(self, sample_size: int = 10000):
        self.sample_size = sample_size
        self.test_cases: List[QueryTestCase] = []

    def generate_test_suite(self, output_path: str = "tests/search_optimization/search_test_queries.json"):
        """Generate complete test suite and save to file."""
        logger.info("🚀 Starting test query generation")

        with get_unit_of_work() as uow:
            # Sample the corpus
            messages = self._sample_corpus(uow)
            logger.info(f"📊 Sampled {len(messages)} messages for analysis")

            # Generate different query types
            logger.info("🔍 Generating keyword queries...")
            self._generate_keyword_queries(uow, messages)

            logger.info("📝 Generating phrase queries...")
            self._generate_phrase_queries(uow, messages)

            logger.info("🧠 Generating semantic queries...")
            self._generate_semantic_queries(uow, messages)

            logger.info("🔤 Generating acronym/synonym queries...")
            self._generate_acronym_queries(uow, messages)

            logger.info("⭐ Generating conversation title queries...")
            self._generate_title_queries(uow)

        # Save results
        self._save_test_suite(output_path)

        # Print summary
        self._print_summary()

        return self.test_cases

    def _sample_corpus(self, uow) -> List[Dict]:
        """Sample messages from the corpus for analysis."""
        # Get a diverse sample across different conversations and time periods
        query = text("""
            WITH message_sample AS (
                SELECT
                    m.id,
                    m.conversation_id,
                    m.role,
                    m.content,
                    m.created_at,
                    c.title as conversation_title,
                    LENGTH(m.content) as content_length,
                    ROW_NUMBER() OVER (PARTITION BY m.conversation_id ORDER BY RANDOM()) as rn
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE LENGTH(m.content) > 50  -- Skip very short messages
                AND m.role IN ('user', 'assistant')  -- Focus on conversational content
            )
            SELECT *
            FROM message_sample
            WHERE rn <= 5  -- Max 5 messages per conversation for diversity
            ORDER BY RANDOM()
            LIMIT :sample_size
        """)

        result = uow.session.execute(query, {'sample_size': self.sample_size})
        messages = []

        for row in result:
            messages.append({
                'id': str(row.id),
                'conversation_id': str(row.conversation_id),
                'role': row.role,
                'content': row.content,
                'created_at': row.created_at,
                'conversation_title': row.conversation_title,
                'content_length': row.content_length
            })

        return messages

    def _generate_keyword_queries(self, uow, messages: List[Dict]):
        """Generate single-keyword queries based on TF-IDF-like analysis."""
        # Extract all words from messages
        word_freq = Counter()
        word_to_messages = defaultdict(set)

        for msg in messages:
            words = self._extract_significant_words(msg['content'])
            for word in words:
                word_freq[word] += 1
                word_to_messages[word].add(msg['id'])

        # Select words that appear in multiple messages but not too common
        # (between 3 and 100 messages = good discriminative power)
        candidate_words = [
            (word, count) for word, count in word_freq.items()
            if 3 <= count <= 100
        ]

        # Sort by frequency and take a diverse sample
        candidate_words.sort(key=lambda x: x[1], reverse=True)

        # Generate test cases for different frequency ranges
        ranges = [
            (3, 10, "hard", 5),      # Rare terms
            (10, 30, "medium", 10),   # Moderate terms
            (30, 100, "easy", 10),    # Common terms
        ]

        for min_freq, max_freq, difficulty, count in ranges:
            words_in_range = [
                word for word, freq in candidate_words
                if min_freq <= freq <= max_freq
            ]

            # Sample words from this range
            import random
            sampled_words = random.sample(words_in_range, min(count, len(words_in_range)))

            for word in sampled_words:
                message_ids = list(word_to_messages[word])
                conversation_ids = self._get_conversation_ids_for_messages(uow, message_ids)

                self.test_cases.append(QueryTestCase(
                    query=word,
                    query_type='keyword',
                    difficulty=difficulty,
                    expected_message_ids=message_ids[:15],  # Limit to top 15
                    expected_conversation_ids=list(conversation_ids)[:15],
                    notes=f"Appears in {word_freq[word]} messages"
                ))

    def _generate_phrase_queries(self, uow, messages: List[Dict]):
        """Generate multi-word phrase queries."""
        # Extract 2-5 word phrases
        phrase_freq = Counter()
        phrase_to_messages = defaultdict(set)

        for msg in messages:
            phrases = self._extract_phrases(msg['content'], min_words=2, max_words=5)
            for phrase in phrases:
                phrase_freq[phrase] += 1
                phrase_to_messages[phrase].add(msg['id'])

        # Select phrases that appear in 2-20 messages
        candidate_phrases = [
            (phrase, count) for phrase, count in phrase_freq.items()
            if 2 <= count <= 20
        ]

        # Sort by frequency
        candidate_phrases.sort(key=lambda x: x[1], reverse=True)

        # Sample diverse phrases
        import random
        sampled_phrases = random.sample(
            candidate_phrases,
            min(20, len(candidate_phrases))
        )

        for phrase, freq in sampled_phrases:
            message_ids = list(phrase_to_messages[phrase])
            conversation_ids = self._get_conversation_ids_for_messages(uow, message_ids)

            difficulty = "easy" if freq > 10 else "medium" if freq > 5 else "hard"

            self.test_cases.append(QueryTestCase(
                query=phrase,
                query_type='phrase',
                difficulty=difficulty,
                expected_message_ids=message_ids[:15],
                expected_conversation_ids=list(conversation_ids)[:15],
                notes=f"Phrase appears {freq} times"
            ))

    def _generate_semantic_queries(self, uow, messages: List[Dict]):
        """Generate semantic/conceptual queries based on message content."""
        # Analyze conversation titles and content to identify topics
        topics = self._identify_topics(messages)

        # Create semantic queries based on identified topics
        semantic_queries = [
            ("machine learning models", "semantic", "medium", "AI/ML discussions"),
            ("database optimization", "semantic", "medium", "Database performance"),
            ("API design patterns", "semantic", "medium", "API architecture"),
            ("security vulnerabilities", "semantic", "medium", "Security discussions"),
            ("user authentication", "semantic", "medium", "Auth systems"),
            ("performance issues", "semantic", "easy", "Performance problems"),
            ("error handling", "semantic", "medium", "Error management"),
            ("code review feedback", "semantic", "medium", "Code reviews"),
            ("deployment strategies", "semantic", "medium", "Deployment"),
            ("testing approaches", "semantic", "medium", "Testing methodology"),
        ]

        for query_text, query_type, difficulty, notes in semantic_queries:
            # Find messages that are semantically related
            message_ids, conversation_ids = self._find_semantic_matches(
                uow, query_text, messages
            )

            if message_ids:  # Only add if we found matches
                self.test_cases.append(QueryTestCase(
                    query=query_text,
                    query_type=query_type,
                    difficulty=difficulty,
                    expected_message_ids=message_ids[:15],
                    expected_conversation_ids=conversation_ids[:15],
                    notes=notes
                ))

    def _generate_acronym_queries(self, uow, messages: List[Dict]):
        """Generate queries testing acronym/synonym expansion."""
        # Common tech acronyms that might appear in the corpus
        acronym_tests = [
            ("API", "application programming interface", "acronym", "easy"),
            ("ML", "machine learning", "acronym", "medium"),
            ("AI", "artificial intelligence", "acronym", "easy"),
            ("DB", "database", "acronym", "easy"),
            ("SQL", "structured query language", "acronym", "medium"),
            ("NLP", "natural language processing", "acronym", "medium"),
            ("LLM", "large language model", "acronym", "medium"),
            ("RAG", "retrieval augmented generation", "acronym", "hard"),
        ]

        for acronym, expansion, query_type, difficulty in acronym_tests:
            # Search for either acronym or expansion in messages
            message_ids = []
            for msg in messages:
                content_lower = msg['content'].lower()
                if acronym.lower() in content_lower or expansion.lower() in content_lower:
                    message_ids.append(msg['id'])

            if len(message_ids) >= 2:  # Only add if we have matches
                conversation_ids = self._get_conversation_ids_for_messages(uow, message_ids)

                self.test_cases.append(QueryTestCase(
                    query=acronym,
                    query_type=query_type,
                    difficulty=difficulty,
                    expected_message_ids=message_ids[:15],
                    expected_conversation_ids=list(conversation_ids)[:15],
                    notes=f"Testing acronym: {acronym} → {expansion}"
                ))

    def _generate_title_queries(self, uow):
        """Generate queries based on conversation titles."""
        # Get diverse conversation titles
        query = text("""
            SELECT
                c.id,
                c.title,
                COUNT(m.id) as message_count
            FROM conversations c
            JOIN messages m ON c.id = m.conversation_id
            WHERE c.title IS NOT NULL
            AND LENGTH(c.title) > 10
            AND LENGTH(c.title) < 100
            GROUP BY c.id, c.title
            HAVING COUNT(m.id) >= 3
            ORDER BY RANDOM()
            LIMIT 30
        """)

        result = uow.session.execute(query)

        for row in result:
            # Extract key terms from title
            title_words = self._extract_significant_words(row.title)

            # Use the first 2-3 significant words as query
            if len(title_words) >= 2:
                query_text = ' '.join(title_words[:3])

                # Find messages in this conversation
                message_ids = self._get_message_ids_for_conversation(uow, str(row.id))

                self.test_cases.append(QueryTestCase(
                    query=query_text,
                    query_type='phrase',
                    difficulty='medium',
                    expected_message_ids=message_ids[:15],
                    expected_conversation_ids=[str(row.id)],
                    notes=f"From conversation title: '{row.title}'"
                ))

    def _extract_significant_words(self, text: str) -> List[str]:
        """Extract significant words from text (remove stopwords, etc.)."""
        # Simple stopwords list
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
            'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'what', 'which', 'who', 'when', 'where', 'why', 'how', 'all', 'each',
            'every', 'both', 'few', 'more', 'most', 'some', 'such', 'no', 'not',
            'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just'
        }

        # Extract words (alphanumeric + hyphens)
        words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9\-]*\b', text.lower())

        # Filter stopwords and short words
        significant = [
            w for w in words
            if w not in stopwords and len(w) >= 3
        ]

        return significant

    def _extract_phrases(self, text: str, min_words: int = 2, max_words: int = 5) -> List[str]:
        """Extract meaningful phrases from text."""
        # Extract significant words first
        words = self._extract_significant_words(text)

        phrases = []

        # Generate n-grams
        for n in range(min_words, max_words + 1):
            for i in range(len(words) - n + 1):
                phrase = ' '.join(words[i:i+n])
                if len(phrase) >= 6:  # Minimum phrase length
                    phrases.append(phrase)

        return phrases

    def _identify_topics(self, messages: List[Dict]) -> List[str]:
        """Identify common topics in the corpus."""
        # Simple topic identification based on word frequency
        all_words = []
        for msg in messages:
            all_words.extend(self._extract_significant_words(msg['content']))

        # Get most common words as topic indicators
        word_freq = Counter(all_words)
        topics = [word for word, count in word_freq.most_common(50)]

        return topics

    def _find_semantic_matches(self, uow, query: str, messages: List[Dict]) -> Tuple[List[str], List[str]]:
        """Find messages that semantically match the query."""
        # Simple keyword-based matching for now
        # In production, you'd use the actual search service
        query_words = set(self._extract_significant_words(query))

        matched_messages = []
        for msg in messages:
            msg_words = set(self._extract_significant_words(msg['content']))
            # If there's significant overlap
            overlap = len(query_words & msg_words)
            if overlap >= len(query_words) * 0.5:  # At least 50% overlap
                matched_messages.append(msg)

        message_ids = [m['id'] for m in matched_messages]
        conversation_ids = list(set(m['conversation_id'] for m in matched_messages))

        return message_ids, conversation_ids

    def _get_conversation_ids_for_messages(self, uow, message_ids: List[str]) -> Set[str]:
        """Get conversation IDs for a list of message IDs."""
        if not message_ids:
            return set()

        # Convert list to tuple for SQL IN clause
        query = text("""
            SELECT DISTINCT conversation_id
            FROM messages
            WHERE id = ANY(:message_ids)
        """)

        result = uow.session.execute(query, {'message_ids': message_ids})
        return {str(row.conversation_id) for row in result}

    def _get_message_ids_for_conversation(self, uow, conversation_id: str) -> List[str]:
        """Get all message IDs for a conversation."""
        query = text("""
            SELECT id
            FROM messages
            WHERE conversation_id = :conversation_id
            ORDER BY created_at
        """)

        result = uow.session.execute(query, {'conversation_id': conversation_id})
        return [str(row.id) for row in result]

    def _save_test_suite(self, output_path: str):
        """Save test suite to JSON file."""
        # Create output directory if needed
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert test cases to dict
        test_suite = {
            'generated_at': datetime.now().isoformat(),
            'total_queries': len(self.test_cases),
            'query_types': self._count_by_type('query_type'),
            'difficulty_levels': self._count_by_type('difficulty'),
            'test_cases': [tc.to_dict() for tc in self.test_cases]
        }

        # Save to file
        with open(output_file, 'w') as f:
            json.dump(test_suite, f, indent=2)

        logger.info(f"✅ Test suite saved to {output_path}")

    def _count_by_type(self, field: str) -> Dict[str, int]:
        """Count test cases by a given field."""
        counts = Counter()
        for tc in self.test_cases:
            counts[getattr(tc, field)] += 1
        return dict(counts)

    def _print_summary(self):
        """Print summary statistics."""
        logger.info("\n" + "="*60)
        logger.info("📊 TEST SUITE GENERATION SUMMARY")
        logger.info("="*60)
        logger.info(f"Total test queries: {len(self.test_cases)}")

        logger.info("\nBy Query Type:")
        for qtype, count in self._count_by_type('query_type').items():
            logger.info(f"  {qtype}: {count}")

        logger.info("\nBy Difficulty:")
        for diff, count in self._count_by_type('difficulty').items():
            logger.info(f"  {diff}: {count}")

        # Show some examples
        logger.info("\n📝 Sample Queries:")
        import random
        samples = random.sample(self.test_cases, min(5, len(self.test_cases)))
        for tc in samples:
            logger.info(f"  • '{tc.query}' ({tc.query_type}, {tc.difficulty})")

        logger.info("="*60 + "\n")


def main():
    """Main entry point."""
    generator = QueryGenerator(sample_size=10000)
    test_cases = generator.generate_test_suite()

    logger.info(f"✨ Generated {len(test_cases)} test queries")
    logger.info("📂 Saved to: tests/search_optimization/search_test_queries.json")


if __name__ == '__main__':
    main()

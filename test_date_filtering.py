#!/usr/bin/env python3
"""
Unit tests for date filtering functionality (TDD RED phase)
Tests the date filtering logic with our Claude test data
"""

import unittest
import sys
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add the project directory to the path
sys.path.insert(0, '/Users/markrichman/projects/dovos')

from routes import filter_by_date


class TestDateFiltering(unittest.TestCase):
    
    def setUp(self):
        """Set up test data that matches our Claude test records"""
        # Today: 2025-08-21
        today = datetime(2025, 8, 21)
        yesterday = today - timedelta(days=1)  # 2025-08-20
        august_2nd = datetime(2025, 8, 2)
        
        # Mock documents matching our Claude test data
        self.test_documents = [
            {
                'ids': ['chat-0'],
                'metadatas': [{
                    'title': 'Test Claude Today',
                    'source': 'claude',
                    'earliest_ts': '2025-08-21T12:30:00.123456Z'
                }],
                'documents': ['Test conversation from today']
            },
            {
                'ids': ['chat-1'], 
                'metadatas': [{
                    'title': 'Test Claude Yesterday',
                    'source': 'claude',
                    'earliest_ts': '2025-08-20T09:15:00.789012Z'
                }],
                'documents': ['Test conversation from yesterday']
            },
            {
                'ids': ['chat-2'],
                'metadatas': [{
                    'title': 'Test Claude August 2nd',
                    'source': 'claude', 
                    'earliest_ts': '2025-08-02T14:45:00.456789Z'
                }],
                'documents': ['Test conversation from August 2nd']
            }
        ]
        
        # Flatten the test data into the format expected by filter functions
        self.all_docs = {
            'ids': [],
            'metadatas': [],
            'documents': []
        }
        
        for doc in self.test_documents:
            self.all_docs['ids'].extend(doc['ids'])
            self.all_docs['metadatas'].extend(doc['metadatas'])
            self.all_docs['documents'].extend(doc['documents'])

    def test_filter_by_date_today(self):
        """Test filtering for today's conversations"""
        # Use actual today's date for the test
        now = datetime.now()
        today_str = now.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        # Create test data with today's date
        test_data = {
            'ids': ['chat-today', 'chat-yesterday'],
            'metadatas': [
                {'title': 'Today Test', 'source': 'claude', 'earliest_ts': today_str},
                {'title': 'Yesterday Test', 'source': 'claude', 'earliest_ts': '2024-01-01T12:00:00.000000Z'}
            ],
            'documents': ['Today doc', 'Yesterday doc']
        }
        
        # Filter for today
        filtered = filter_by_date(test_data, 'today')
        
        # Should return only the "today" conversation
        self.assertEqual(len(filtered['ids']), 1)
        self.assertEqual(filtered['metadatas'][0]['title'], 'Today Test')

    @patch('routes.datetime')  
    def test_filter_by_date_week(self, mock_datetime):
        """Test filtering for past week conversations"""
        mock_datetime.now.return_value = datetime(2025, 8, 21, 15, 0, 0)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        # Filter for past week
        filtered = filter_by_date(self.all_docs, 'week')
        
        # Should return today and yesterday conversations (both within past week)
        self.assertEqual(len(filtered['ids']), 2)
        titles = [meta['title'] for meta in filtered['metadatas']]
        self.assertIn('Test Claude Today', titles)
        self.assertIn('Test Claude Yesterday', titles)

    @patch('routes.datetime')
    def test_filter_by_date_month(self, mock_datetime):
        """Test filtering for past month conversations"""
        mock_datetime.now.return_value = datetime(2025, 8, 21, 15, 0, 0)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        # Filter for past month
        filtered = filter_by_date(self.all_docs, 'month')
        
        # Should return all conversations (all within past month)
        self.assertEqual(len(filtered['ids']), 3)
        titles = [meta['title'] for meta in filtered['metadatas']]
        self.assertIn('Test Claude Today', titles)
        self.assertIn('Test Claude Yesterday', titles)
        self.assertIn('Test Claude August 2nd', titles)

    @patch('routes.datetime')
    def test_filter_by_date_year(self, mock_datetime):
        """Test filtering for past year conversations"""
        mock_datetime.now.return_value = datetime(2025, 8, 21, 15, 0, 0)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        # Filter for past year
        filtered = filter_by_date(self.all_docs, 'year')
        
        # Should return all conversations (all within past year)
        self.assertEqual(len(filtered['ids']), 3)

    def test_filter_by_date_all(self):
        """Test filtering with 'all' returns everything unchanged"""
        filtered = filter_by_date(self.all_docs, 'all')
        
        # Should return all conversations unchanged
        self.assertEqual(len(filtered['ids']), 3)
        self.assertEqual(filtered, self.all_docs)

    @patch('routes.datetime')
    def test_filter_handles_invalid_dates(self, mock_datetime):
        """Test that filtering handles invalid date strings gracefully"""
        mock_datetime.now.return_value = datetime(2025, 8, 21, 15, 0, 0)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        # Add a record with invalid date
        test_data_with_invalid = {
            'ids': self.all_docs['ids'] + ['chat-invalid'],
            'metadatas': self.all_docs['metadatas'] + [{
                'title': 'Invalid Date Test',
                'source': 'claude',
                'earliest_ts': 'invalid-date-string'
            }],
            'documents': self.all_docs['documents'] + ['Invalid date conversation']
        }
        
        # Should handle invalid date gracefully and not crash
        filtered = filter_by_date(test_data_with_invalid, 'today')
        
        # Should still return the valid today conversation
        self.assertGreaterEqual(len(filtered['ids']), 1)


class TestWebDateFiltering(unittest.TestCase):
    """Integration tests for the web interface date filtering"""
    
    @patch('routes.archive')
    def test_conversations_route_date_filtering(self, mock_archive):
        """Test that the conversations route properly applies date filters"""
        # Mock the archive.get_documents call
        mock_archive.get_documents.return_value = {
            'ids': ['chat-0', 'chat-1', 'chat-2'],
            'metadatas': [
                {'title': 'Test Claude Today', 'source': 'claude', 'earliest_ts': '2025-08-21T12:30:00.123456Z'},
                {'title': 'Test Claude Yesterday', 'source': 'claude', 'earliest_ts': '2025-08-20T09:15:00.789012Z'}, 
                {'title': 'Test Claude August 2nd', 'source': 'claude', 'earliest_ts': '2025-08-02T14:45:00.456789Z'}
            ],
            'documents': ['doc1', 'doc2', 'doc3']
        }
        
        # This test will verify the web interface integration
        # Implementation will be added in GREEN phase
        pass


if __name__ == '__main__':
    print("Running date filtering tests (TDD RED phase)...")
    print("These tests should FAIL until we implement the fixes.")
    
    # Run the tests
    unittest.main(verbosity=2)
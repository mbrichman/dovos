"""
Service for conversation data retrieval and search.

Handles all conversation query operations, abstracting away the search backend.
Follows Single Responsibility Principle - only handles queries, not formatting.
"""

from typing import Dict, List, Any, Optional, Tuple


class ConversationQueryService:
    """Service for querying conversations from search backend."""
    
    def __init__(self, search_service):
        """
        Initialize with search service dependency.
        
        Args:
            search_service: Search service instance (postgres_controller or compatible)
        """
        self.search_service = search_service
    
    def get_all_conversations(
        self,
        limit: int = 9999,
        include: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get all conversations from the database.
        
        Args:
            limit: Maximum number of conversations to retrieve
            include: List of fields to include (documents, metadatas, etc.)
            
        Returns:
            Dict with documents, metadatas, and ids
        """
        if include is None:
            include = ["documents", "metadatas"]
        
        return self.search_service.get_all_conversations(
            include=include,
            limit=limit
        )
    
    def get_conversation_by_id(self, doc_id: str) -> Dict[str, Any]:
        """
        Get a single conversation by ID.
        
        Args:
            doc_id: Conversation ID to retrieve
            
        Returns:
            Dict with documents, metadatas, and ids for the conversation
        """
        return self.search_service.get_conversation_by_id(doc_id)
    
    def search_conversations(
        self,
        query_text: str,
        n_results: int = 10,
        date_range: Optional[Tuple[str, str]] = None,
        keyword_search: bool = False,
        search_type: str = "auto"
    ) -> Dict[str, Any]:
        """
        Search conversations with query and optional filters.
        
        Args:
            query_text: Search query string
            n_results: Number of results to return
            date_range: Optional tuple of (start_date, end_date) for filtering
            keyword_search: Whether to use keyword (FTS) search
            search_type: Type of search (auto, fts, semantic, hybrid)
            
        Returns:
            Dict with search results (documents, metadatas, ids)
        """
        return self.search_service.search_conversations(
            query_text=query_text,
            n_results=n_results,
            date_range=date_range,
            keyword_search=keyword_search,
            search_type=search_type
        )

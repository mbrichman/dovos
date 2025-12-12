"""
RAGController - Handles RAG (Retrieval-Augmented Generation) query operations

This controller separates RAG business logic from routing, supporting both:
- Standard RAG queries (semantic/hybrid search)
- Contextual RAG queries (with message window expansion)
"""

import logging
from typing import Dict, Any, List, Optional
from flask import request

from db.services.contextual_retrieval_service import ContextualRetrievalService
from db.repositories.unit_of_work import get_unit_of_work
from config import (
    RAG_DEFAULT_WINDOW_SIZE,
    RAG_MAX_WINDOW_SIZE,
    RAG_ADAPTIVE_WINDOWING,
    RAG_DEDUPLICATE_MESSAGES,
    RAG_DEFAULT_TOP_K_WINDOWS,
    RAG_DEFAULT_MAX_TOKENS,
    RAG_PROXIMITY_DECAY_LAMBDA,
    RAG_APPLY_RECENCY_BONUS
)

logger = logging.getLogger(__name__)


class RAGController:
    """Controller for RAG query operations with contextual retrieval support"""
    
    def __init__(self, postgres_controller):
        """Initialize RAGController
        
        Args:
            postgres_controller: PostgresController instance for standard queries
        """
        self.postgres_controller = postgres_controller
        
        # Load configuration
        self.default_window_size = RAG_DEFAULT_WINDOW_SIZE
        self.max_window_size = RAG_MAX_WINDOW_SIZE
        self.adaptive_windowing = RAG_ADAPTIVE_WINDOWING
        self.deduplicate_messages = RAG_DEDUPLICATE_MESSAGES
        self.default_top_k_windows = RAG_DEFAULT_TOP_K_WINDOWS
        self.default_max_tokens = RAG_DEFAULT_MAX_TOKENS
        self.proximity_decay_lambda = RAG_PROXIMITY_DECAY_LAMBDA
        self.apply_recency_bonus = RAG_APPLY_RECENCY_BONUS
    
    def handle_rag_query(self) -> Dict[str, Any]:
        """Handle RAG query from Flask request
        
        Determines execution mode (contextual vs standard) and delegates accordingly.
        
        Returns:
            Dict with query results or error information
        """
        try:
            data = request.get_json()
            query_text = data.get('query', '')
            
            if not query_text:
                return {"error": "Query text is required"}
            
            # Determine if contextual retrieval is requested
            context_window = data.get('context_window')
            asymmetric_before = data.get('asymmetric_before')
            asymmetric_after = data.get('asymmetric_after')
            use_contextual = (
                context_window is not None or 
                asymmetric_before is not None or 
                asymmetric_after is not None or 
                data.get('use_contextual', False)
            )
            
            if use_contextual:
                return self._execute_contextual_query(data, query_text)
            else:
                return self._execute_standard_query()
        
        except ValueError as e:
            # Validation errors
            logger.error(f"RAG query validation failed: {e}")
            return {"error": str(e)}
        
        except Exception as e:
            # Unexpected errors
            logger.error(f"RAG query failed: {e}", exc_info=True)
            return {"error": str(e)}
    
    def _execute_standard_query(self) -> Dict[str, Any]:
        """Execute standard RAG query via postgres_controller
        
        Returns:
            Dict with query results
        """
        try:
            return self.postgres_controller.rag_query()
        except Exception as e:
            logger.error(f"Standard RAG query failed: {e}")
            raise
    
    def _execute_contextual_query(self, data: Dict[str, Any], query_text: str) -> Dict[str, Any]:
        """Execute contextual RAG query with window expansion
        
        Args:
            data: Request data dictionary
            query_text: Query string
        
        Returns:
            Dict with formatted contextual results
        """
        # Validate parameters
        self._validate_contextual_params(data)
        
        # Parse parameters with defaults
        context_window = data.get('context_window') or self.default_window_size
        context_window = min(context_window, self.max_window_size)
        
        top_k_windows = min(
            data.get('n_results', self.default_top_k_windows),
            self.default_top_k_windows * 2
        )
        
        adaptive_context = data.get('adaptive_context', self.adaptive_windowing)
        asymmetric_before = data.get('asymmetric_before')
        asymmetric_after = data.get('asymmetric_after')
        deduplicate = data.get('deduplicate', self.deduplicate_messages)
        max_tokens = data.get('max_tokens', self.default_max_tokens)
        include_markers = data.get('include_markers', True)
        
        # Execute contextual retrieval
        with get_unit_of_work() as uow:
            contextual_service = ContextualRetrievalService(uow)
            
            windows = contextual_service.retrieve_with_context(
                query=query_text,
                top_k_windows=top_k_windows,
                context_window=context_window,
                adaptive_context=adaptive_context,
                asymmetric_before=asymmetric_before,
                asymmetric_after=asymmetric_after,
                deduplicate=deduplicate,
                max_tokens=max_tokens if max_tokens and max_tokens > 0 else None,
                include_markers=include_markers,
                proximity_decay_lambda=self.proximity_decay_lambda,
                apply_recency_bonus=self.apply_recency_bonus
            )
        
        # Format and return results
        params = {
            'context_window': context_window,
            'adaptive_context': adaptive_context
        }
        return self._format_contextual_results(windows, query_text, params)
    
    def _validate_contextual_params(self, data: Dict[str, Any]) -> None:
        """Validate contextual retrieval parameters
        
        Args:
            data: Request data dictionary
        
        Raises:
            ValueError: If parameters are invalid
        """
        context_window = data.get('context_window')
        asymmetric_before = data.get('asymmetric_before')
        asymmetric_after = data.get('asymmetric_after')
        
        if context_window and context_window > self.max_window_size:
            raise ValueError(f"context_window must be <= {self.max_window_size}")
        
        if asymmetric_before and asymmetric_before > self.max_window_size:
            raise ValueError(f"asymmetric_before must be <= {self.max_window_size}")
        
        if asymmetric_after and asymmetric_after > self.max_window_size:
            raise ValueError(f"asymmetric_after must be <= {self.max_window_size}")
    
    def _format_contextual_results(
        self, 
        windows: List[Any], 
        query: str, 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format contextual retrieval results for API response
        
        Args:
            windows: List of ContextWindow objects
            query: Original query string
            params: Retrieval parameters
        
        Returns:
            Dict with formatted results
        """
        formatted_results = []
        
        for window in windows:
            meta = window.metadata
            
            # Extract preview from content (first 500 chars)
            preview = window.content[:500] + "..." if len(window.content) > 500 else window.content
            
            formatted_results.append({
                "id": meta.conversation_id,
                "window_id": meta.window_id,
                "title": meta.conversation_title,
                "content": window.content,
                "preview": preview,
                "source": "postgres_contextual",
                "relevance": meta.aggregated_score,
                "metadata": {
                    "conversation_id": meta.conversation_id,
                    "matched_message_id": meta.matched_message_id,
                    "window_size": meta.window_size,
                    "match_position": meta.match_position,
                    "before_count": meta.before_count,
                    "after_count": meta.after_count,
                    "base_score": meta.base_score,
                    "aggregated_score": meta.aggregated_score,
                    "roles": meta.roles,
                    "token_estimate": meta.token_estimate,
                    "retrieval_params": meta.retrieval_params
                }
            })
        
        return {
            "query": query,
            "retrieval_mode": "contextual",
            "context_window": params.get('context_window'),
            "adaptive_context": params.get('adaptive_context'),
            "results": formatted_results
        }


def get_rag_controller(postgres_controller) -> RAGController:
    """Factory function to create RAGController instance
    
    Args:
        postgres_controller: PostgresController instance
    
    Returns:
        RAGController instance
    """
    return RAGController(postgres_controller)

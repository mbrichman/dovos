"""
Unified SearchService with hybrid ranking combining:
1. Lexical Full-Text Search (PostgreSQL FTS)
2. Semantic Vector Search (pgvector)
3. Hybrid ranking that blends both approaches
4. Query expansion and result optimization
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass
import math

from db.repositories.unit_of_work import get_unit_of_work
from db.workers.embedding_worker import EmbeddingGenerator

logger = logging.getLogger(__name__)


@dataclass
class SearchConfig:
    """Configuration for search behavior and ranking weights."""
    # Ranking weights (must sum to 1.0)
    vector_weight: float = 0.6
    fts_weight: float = 0.4
    
    # Search thresholds
    vector_similarity_threshold: float = 0.2  # Minimum cosine similarity
    fts_rank_threshold: float = 0.01  # Minimum FTS rank
    
    # Result limits
    max_results: int = 50
    max_fts_results: int = 100
    max_vector_results: int = 100
    
    # Query processing
    enable_query_expansion: bool = True
    enable_typo_tolerance: bool = True
    
    def __post_init__(self):
        """Validate configuration."""
        if abs(self.vector_weight + self.fts_weight - 1.0) > 0.01:
            raise ValueError("vector_weight + fts_weight must equal 1.0")


@dataclass 
class SearchResult:
    """Unified search result with metadata."""
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: str
    conversation_title: str
    
    # Scores
    combined_score: float
    vector_score: Optional[float] = None
    fts_score: Optional[float] = None
    
    # Additional metadata
    similarity: Optional[float] = None
    fts_rank: Optional[float] = None
    distance: Optional[float] = None
    source: str = "hybrid"
    
    def to_legacy_format(self) -> Dict[str, Any]:
        """Convert to legacy API format for compatibility."""
        # Format timestamp for legacy compatibility
        timestamp_str = self.created_at
        
        # Build document content in legacy format
        if self.role == 'user':
            document_content = f"**You said** *(on {timestamp_str})*:\n\n{self.content}"
        elif self.role == 'assistant':
            document_content = f"**Assistant said** *(on {timestamp_str})*:\n\n{self.content}"
        elif self.role == 'system':
            document_content = f"**System** *(on {timestamp_str})*:\n\n{self.content}"
        else:
            document_content = f"**{self.role.capitalize()}** *(on {timestamp_str})*:\n\n{self.content}"
        
        return {
            'id': self.conversation_id,  # Use conversation ID for API compatibility
            'document': document_content,
            'metadata': {
                'title': self.conversation_title,
                'source': self.source,
                'message_count': 1,  # Single message
                'earliest_ts': self.created_at,
                'latest_ts': self.created_at,
                'conversation_id': self.conversation_id,
                'message_id': self.message_id,
                'role': self.role,
                'combined_score': self.combined_score,
                'vector_score': self.vector_score,
                'fts_score': self.fts_score,
                'similarity': self.similarity,
                'fts_rank': self.fts_rank,
                'distance': self.distance
            }
        }


class SearchService:
    """
    Unified search service that combines FTS and vector search with hybrid ranking.
    """
    
    def __init__(self, config: Optional[SearchConfig] = None):
        self.config = config or SearchConfig()
        self._embedding_generator = None
        
    @property
    def embedding_generator(self) -> EmbeddingGenerator:
        """Lazy load the embedding generator."""
        if self._embedding_generator is None:
            self._embedding_generator = EmbeddingGenerator()
        return self._embedding_generator
    
    def search(self, 
               query: str, 
               limit: Optional[int] = None,
               conversation_id: Optional[UUID] = None,
               config_override: Optional[SearchConfig] = None) -> List[SearchResult]:
        """
        Perform hybrid search combining FTS and vector similarity.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            conversation_id: Optional conversation filter
            config_override: Override default search configuration
            
        Returns:
            List of SearchResult objects ranked by hybrid score
        """
        config = config_override or self.config
        limit = limit or config.max_results
        
        logger.info(f"🔍 Hybrid search: '{query[:50]}...' (limit: {limit})")
        
        try:
            # Generate query embedding for vector search
            query_embedding = self._generate_query_embedding(query)
            
            with get_unit_of_work() as uow:
                # Perform both search types in parallel
                fts_results = self._fts_search(uow, query, config, conversation_id)
                vector_results = self._vector_search(uow, query_embedding, config, conversation_id)
                
                # Combine and rank results
                combined_results = self._combine_and_rank_results(
                    fts_results, vector_results, config
                )
                
                # Apply final filters and limits
                final_results = combined_results[:limit]
                
                logger.info(f"✅ Search complete: {len(fts_results)} FTS + {len(vector_results)} vector → {len(final_results)} final")
                
                return final_results
                
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            raise
    
    def search_fts_only(self, 
                        query: str, 
                        limit: Optional[int] = None,
                        conversation_id: Optional[UUID] = None) -> List[SearchResult]:
        """Perform full-text search only."""
        limit = limit or self.config.max_results
        
        logger.info(f"📝 FTS-only search: '{query[:50]}...'")
        
        with get_unit_of_work() as uow:
            fts_results = self._fts_search(uow, query, self.config, conversation_id)
            
            # Convert to SearchResult format
            search_results = []
            for result in fts_results[:limit]:
                meta = result['metadata']
                search_results.append(SearchResult(
                    message_id=meta['message_id'],
                    conversation_id=meta['conversation_id'],
                    role=meta['role'],
                    content=self._extract_content_from_document(result['document']),
                    created_at=meta['earliest_ts'],
                    conversation_title=meta['title'],
                    combined_score=meta.get('rank', 0),
                    fts_score=meta.get('rank', 0),
                    fts_rank=meta.get('rank', 0),
                    source='fts'
                ))
            
            logger.info(f"✅ FTS search complete: {len(search_results)} results")
            return search_results
    
    def search_vector_only(self, 
                          query: str, 
                          limit: Optional[int] = None,
                          conversation_id: Optional[UUID] = None) -> List[SearchResult]:
        """Perform vector search only."""
        limit = limit or self.config.max_results
        
        logger.info(f"🎯 Vector-only search: '{query[:50]}...'")
        
        try:
            query_embedding = self._generate_query_embedding(query)
            
            with get_unit_of_work() as uow:
                vector_results = self._vector_search(uow, query_embedding, self.config, conversation_id)
                
                # Convert to SearchResult format
                search_results = []
                for result in vector_results[:limit]:
                    meta = result['metadata']
                    search_results.append(SearchResult(
                        message_id=meta['message_id'],
                        conversation_id=meta['conversation_id'],
                        role=meta['role'],
                        content=self._extract_content_from_document(result['document']),
                        created_at=meta['earliest_ts'],
                        conversation_title=meta['title'],
                        combined_score=meta.get('similarity', 0),
                        vector_score=meta.get('similarity', 0),
                        similarity=meta.get('similarity', 0),
                        distance=meta.get('distance', 0),
                        source='vector'
                    ))
                
                logger.info(f"✅ Vector search complete: {len(search_results)} results")
                return search_results
                
        except Exception as e:
            logger.error(f"❌ Vector search failed: {e}")
            # Fallback to FTS if vector search fails
            logger.info("🔄 Falling back to FTS search")
            return self.search_fts_only(query, limit, conversation_id)
    
    def search_similar_to_message(self, 
                                 message_id: UUID, 
                                 limit: Optional[int] = None,
                                 conversation_id: Optional[UUID] = None) -> List[SearchResult]:
        """Find messages similar to a given message using vector search."""
        limit = limit or self.config.max_results
        
        logger.info(f"🔗 Similar message search: {message_id}")
        
        with get_unit_of_work() as uow:
            # Get the source message's embedding
            source_embedding = uow.embeddings.get_by_message_id(message_id)
            if not source_embedding:
                logger.warning(f"No embedding found for message {message_id}")
                return []
            
            # Perform vector search using the source embedding
            vector_results = uow.embeddings.search_similar(
                query_embedding=source_embedding.embedding,
                limit=limit + 1,  # +1 because source message will be included
                distance_threshold=1.0 - self.config.vector_similarity_threshold,
                conversation_id=conversation_id
            )
            
            # Filter out the source message itself
            filtered_results = [r for r in vector_results if r['metadata']['message_id'] != str(message_id)]
            
            # Convert to SearchResult format
            search_results = []
            for result in filtered_results[:limit]:
                meta = result['metadata']
                search_results.append(SearchResult(
                    message_id=meta['message_id'],
                    conversation_id=meta['conversation_id'],
                    role=meta['role'],
                    content=self._extract_content_from_document(result['document']),
                    created_at=meta['earliest_ts'],
                    conversation_title=meta['title'],
                    combined_score=meta.get('similarity', 0),
                    vector_score=meta.get('similarity', 0),
                    similarity=meta.get('similarity', 0),
                    distance=meta.get('distance', 0),
                    source='similar'
                ))
            
            logger.info(f"✅ Similar search complete: {len(search_results)} results")
            return search_results
    
    def _generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for search query."""
        return self.embedding_generator.generate_embedding(query)
    
    def _fts_search(self, uow, query: str, config: SearchConfig, conversation_id: Optional[UUID]) -> List[Dict[str, Any]]:
        """Perform full-text search."""
        # Expand query if enabled
        if config.enable_query_expansion:
            expanded_query = self._expand_query(query)
        else:
            expanded_query = query
        
        # Search with expanded query
        results = uow.messages.search_full_text(
            query=expanded_query,
            limit=config.max_fts_results,
            conversation_id=conversation_id
        )
        
        # Filter by rank threshold
        filtered_results = [
            r for r in results 
            if r['metadata'].get('rank', 0) >= config.fts_rank_threshold
        ]
        
        logger.debug(f"FTS: {len(results)} raw → {len(filtered_results)} after threshold")
        return filtered_results
    
    def _vector_search(self, uow, query_embedding: List[float], config: SearchConfig, conversation_id: Optional[UUID]) -> List[Dict[str, Any]]:
        """Perform vector similarity search."""
        distance_threshold = 1.0 - config.vector_similarity_threshold
        
        results = uow.embeddings.search_similar(
            query_embedding=query_embedding,
            limit=config.max_vector_results,
            distance_threshold=distance_threshold,
            conversation_id=conversation_id
        )
        
        # Filter by similarity threshold
        filtered_results = [
            r for r in results 
            if r['metadata'].get('similarity', 0) >= config.vector_similarity_threshold
        ]
        
        logger.debug(f"Vector: {len(results)} raw → {len(filtered_results)} after threshold")
        return filtered_results
    
    def _combine_and_rank_results(self, 
                                 fts_results: List[Dict[str, Any]], 
                                 vector_results: List[Dict[str, Any]], 
                                 config: SearchConfig) -> List[SearchResult]:
        """Combine FTS and vector results with hybrid ranking."""
        
        # Index results by message_id for merging
        fts_by_id = {r['metadata']['message_id']: r for r in fts_results}
        vector_by_id = {r['metadata']['message_id']: r for r in vector_results}
        
        # Get all unique message IDs
        all_message_ids = set(fts_by_id.keys()) | set(vector_by_id.keys())
        
        combined_results = []
        
        for message_id in all_message_ids:
            fts_result = fts_by_id.get(message_id)
            vector_result = vector_by_id.get(message_id)
            
            # Extract scores (normalize to 0-1 range)
            fts_score = 0.0
            vector_score = 0.0
            
            if fts_result:
                fts_rank = fts_result['metadata'].get('rank', 0)
                fts_score = self._normalize_fts_score(fts_rank)
            
            if vector_result:
                similarity = vector_result['metadata'].get('similarity', 0)
                vector_score = max(0, similarity)  # Similarity is already 0-1
            
            # Calculate combined score
            combined_score = (
                config.fts_weight * fts_score + 
                config.vector_weight * vector_score
            )
            
            # Use the result with more complete data (prefer vector for content quality)
            base_result = vector_result or fts_result
            meta = base_result['metadata']
            
            # Create unified search result
            search_result = SearchResult(
                message_id=meta['message_id'],
                conversation_id=meta['conversation_id'],
                role=meta['role'],
                content=self._extract_content_from_document(base_result['document']),
                created_at=meta['earliest_ts'],
                conversation_title=meta['title'],
                combined_score=combined_score,
                vector_score=vector_score if vector_result else None,
                fts_score=fts_score if fts_result else None,
                similarity=vector_result['metadata'].get('similarity') if vector_result else None,
                fts_rank=fts_result['metadata'].get('rank') if fts_result else None,
                distance=vector_result['metadata'].get('distance') if vector_result else None,
                source='hybrid'
            )
            
            combined_results.append(search_result)
        
        # Sort by combined score (descending)
        combined_results.sort(key=lambda x: x.combined_score, reverse=True)
        
        logger.debug(f"Combined: {len(all_message_ids)} unique messages")
        return combined_results
    
    def _normalize_fts_score(self, fts_rank: float) -> float:
        """Normalize FTS rank to 0-1 scale."""
        # PostgreSQL ts_rank typically returns values between 0 and 1
        # But can be higher, so we use a logarithmic normalization
        if fts_rank <= 0:
            return 0.0
        
        # Use log normalization to handle wide range of FTS scores
        normalized = math.log(1 + fts_rank) / math.log(2)  # log2(1 + rank)
        return min(1.0, normalized)
    
    def _expand_query(self, query: str) -> str:
        """Expand query with synonyms and related terms."""
        # Simple query expansion - in production, use a proper synonym dictionary
        expanded_terms = []
        words = query.lower().split()
        
        # Basic synonym mapping
        synonyms = {
            'search': ['find', 'lookup', 'query'],
            'message': ['text', 'content', 'chat'],
            'conversation': ['chat', 'discussion', 'dialogue'],
            'database': ['db', 'storage', 'data'],
            'postgresql': ['postgres', 'pg', 'psql'],
            'embedding': ['vector', 'similarity', 'semantic']
        }
        
        for word in words:
            expanded_terms.append(word)
            if word in synonyms:
                expanded_terms.extend(synonyms[word][:1])  # Add one synonym
        
        # Join with OR for PostgreSQL FTS
        expanded_query = ' | '.join(expanded_terms) if len(expanded_terms) > len(words) else query
        
        logger.debug(f"Query expansion: '{query}' → '{expanded_query}'")
        return expanded_query
    
    def _extract_content_from_document(self, document: str) -> str:
        """Extract plain content from formatted document."""
        # Simple extraction - remove markdown-like formatting
        lines = document.split('\n')
        content_lines = []
        
        for line in lines:
            # Skip header lines with **...**
            if line.startswith('**') and '**' in line[2:]:
                continue
            # Skip empty lines
            if not line.strip():
                continue
            content_lines.append(line)
        
        return '\n'.join(content_lines)
    
    def get_search_stats(self) -> Dict[str, Any]:
        """Get search-related statistics."""
        with get_unit_of_work() as uow:
            # Get message and embedding counts
            message_stats = uow.messages.get_message_stats()
            
            # Get embedding coverage
            total_messages = message_stats['total_messages']
            embedded_messages = message_stats['embedded_messages']
            
            # Get job queue stats for embedding jobs
            embedding_job_stats = uow.jobs.get_embedding_job_stats()
            
            return {
                'total_messages': total_messages,
                'embedded_messages': embedded_messages,
                'embedding_coverage_percent': message_stats['embedding_coverage_percent'],
                'pending_embedding_jobs': embedding_job_stats['embedding_jobs_by_status'].get('pending', 0),
                'failed_embedding_jobs': embedding_job_stats['embedding_jobs_by_status'].get('failed', 0),
                'vector_search_available': embedded_messages > 0,
                'fts_search_available': True,  # Always available with PostgreSQL
                'hybrid_search_available': embedded_messages > 0
            }
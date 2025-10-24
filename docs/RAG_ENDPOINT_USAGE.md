# Contextual RAG Endpoint Usage Guide

## Overview

The `/api/rag/query` endpoint now supports **contextual window expansion** for message-level retrieval with surrounding conversation context.

## Endpoint

```
POST /api/rag/query
```

## Features

- ✅ Message-level semantic search
- ✅ Contextual window expansion (configurable before/after)
- ✅ Adaptive windowing for complete user↔assistant turns
- ✅ Deduplication of overlapping windows
- ✅ Proximity decay scoring
- ✅ Token budget enforcement
- ✅ Context markers for highlighting matched content
- ✅ Backward compatible with legacy behavior

## Request Parameters

### Required
- `query` (string): Search query text

### Optional - Contextual Retrieval
- `context_window` (int): Number of messages before/after match (default: 3, max: 10)
  - **Setting this enables contextual mode**
- `use_contextual` (bool): Explicitly enable contextual mode (default: false)
- `n_results` (int): Maximum number of windows to return (default: 8)
- `adaptive_context` (bool): Adaptively include complete turns (default: true)
- `asymmetric_before` (int): Override messages before match
- `asymmetric_after` (int): Override messages after match
- `deduplicate` (bool): Merge overlapping windows (default: true)
- `max_tokens` (int): Token budget per window (0 = no limit, default: 0)
- `include_markers` (bool): Include context markers in content (default: true)

### Legacy Parameters (backward compatible)
- `n_results` (int): Number of results (default: 5)
- `search_type` (string): 'semantic' or 'keyword' (default: 'semantic')

## Response Format

### Contextual Mode Response

```json
{
  "query": "search query",
  "retrieval_mode": "contextual",
  "context_window": 3,
  "adaptive_context": true,
  "results": [
    {
      "id": "conversation-uuid",
      "window_id": "conversation-uuid:message-uuid",
      "title": "Conversation Title",
      "content": "[CTX_START]\n**You** *(on 2024-01-01 10:00:00)*:\nMessage 1\n\n[MATCH_START]\n**Assistant** *(on 2024-01-01 10:01:00)*:\nMatched message\n[MATCH_END]\n\n**You** *(on 2024-01-01 10:02:00)*:\nMessage 3\n[CTX_END]",
      "preview": "Short preview...",
      "source": "postgres_contextual",
      "relevance": 0.89,
      "metadata": {
        "conversation_id": "uuid",
        "matched_message_id": "uuid",
        "window_size": 5,
        "match_position": 2,
        "before_count": 2,
        "after_count": 2,
        "base_score": 0.91,
        "aggregated_score": 0.89,
        "roles": ["user", "assistant", "user", "assistant", "user"],
        "token_estimate": 250,
        "retrieval_params": {
          "query": "...",
          "top_k_windows": 8,
          "context_window": 3,
          "adaptive_context": true,
          "deduplicate": true
        }
      }
    }
  ]
}
```

## Usage Examples

### Basic Contextual Query

```bash
curl -X POST http://localhost:5001/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "database optimization",
    "context_window": 3,
    "n_results": 5
  }'
```

### Asymmetric Window

```bash
curl -X POST http://localhost:5001/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "explain the architecture",
    "asymmetric_before": 5,
    "asymmetric_after": 2,
    "n_results": 3
  }'
```

### With Token Budget

```bash
curl -X POST http://localhost:5001/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning model",
    "context_window": 5,
    "max_tokens": 500,
    "n_results": 3
  }'
```

### Without Markers (Clean Output)

```bash
curl -X POST http://localhost:5001/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "api design patterns",
    "context_window": 2,
    "include_markers": false,
    "n_results": 5
  }'
```

### Legacy Mode (Backward Compatible)

```bash
# Omitting context_window triggers legacy behavior
curl -X POST http://localhost:5001/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "test query",
    "n_results": 5,
    "search_type": "semantic"
  }'
```

## Python Example

```python
import requests

def contextual_rag_query(query, context_window=3, n_results=5):
    """Query RAG with contextual window expansion."""
    response = requests.post(
        'http://localhost:5001/api/rag/query',
        json={
            'query': query,
            'context_window': context_window,
            'n_results': n_results,
            'adaptive_context': True,
            'deduplicate': True,
            'include_markers': True
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"Query: {data['query']}")
        print(f"Mode: {data['retrieval_mode']}")
        print(f"Results: {len(data['results'])}")
        
        for i, result in enumerate(data['results'], 1):
            print(f"\n--- Result {i} ---")
            print(f"Title: {result['title']}")
            print(f"Relevance: {result['relevance']:.2f}")
            print(f"Window Size: {result['metadata']['window_size']}")
            print(f"\nContent:\n{result['content']}")
    else:
        print(f"Error: {response.status_code}")
        print(response.json())

# Example usage
contextual_rag_query("PostgreSQL performance optimization", context_window=3)
```

## Context Markers

When `include_markers: true`:

- `[CTX_START]` - Beginning of context window
- `[MATCH_START]` - Beginning of matched message
- `[MATCH_END]` - End of matched message
- `[CTX_END]` - End of context window

## Configuration

Environment variables (set in `.env`):

```bash
RAG_WINDOW_SIZE=3                  # Default context window
RAG_MAX_WINDOW_SIZE=10             # Maximum window size
RAG_ADAPTIVE_WINDOWING=true        # Enable adaptive windowing
RAG_DEDUPLICATE_MESSAGES=true     # Merge overlapping windows
RAG_DEFAULT_TOP_K_WINDOWS=8        # Default number of results
RAG_DEFAULT_MAX_TOKENS=0           # Token budget (0 = no limit)
RAG_PROXIMITY_DECAY_LAMBDA=0.3     # Proximity decay factor
RAG_APPLY_RECENCY_BONUS=false      # Recency scoring bonus
```

## Error Responses

### 400 - Bad Request
```json
{
  "error": "Query text is required"
}
```

```json
{
  "error": "asymmetric_before must be <= 10"
}
```

### 500 - Server Error
```json
{
  "error": "Search failed: [error details]"
}
```

## Performance Considerations

- **Window Size**: Larger windows provide more context but increase latency
  - Small (1-2): ~50-100ms per query
  - Medium (3-5): ~100-200ms per query  
  - Large (7-10): ~200-400ms per query

- **Token Budget**: Enforcing token limits adds minimal overhead (~5-10ms)

- **Deduplication**: Merging overlapping windows is fast (~5ms per merge)

- **Adaptive Windowing**: Adds ~5-10ms per window for turn detection

## Tips

1. **Start with defaults** - `context_window=3` works well for most use cases

2. **Use adaptive windowing** - Ensures complete user↔assistant exchanges

3. **Enable markers during development** - Helps visualize matched content

4. **Disable markers in production** - Cleaner output for end users

5. **Set token budgets** - Prevents overwhelming OpenWebUI with large windows

6. **Use asymmetric windows** - When you need more historical context than future context

## Backward Compatibility

The endpoint maintains full backward compatibility:

- **Without `context_window` parameter**: Uses legacy message-level search
- **With `context_window` parameter**: Uses new contextual retrieval
- Legacy responses maintain the same structure for existing integrations

## Health Check

Check RAG service health:

```bash
curl http://localhost:5001/api/rag/health
```

Response:
```json
{
  "status": "healthy",
  "collection_name": "chat_history",
  "document_count": 1523,
  "embedding_model": "all-MiniLM-L6-v2"
}
```

## Troubleshooting

### No results returned
- Verify embeddings exist for messages (check embedding worker)
- Try increasing `n_results` parameter
- Check if query matches conversation content

### Empty context windows
- Conversation may have fewer messages than requested window size
- Check `window_size` in metadata to see actual window size

### High latency
- Reduce `context_window` size
- Decrease `n_results` count
- Enable deduplication to reduce processing

### Markers not appearing
- Verify `include_markers: true` in request
- Check that `context_window` is set (enables contextual mode)

## Related Documentation

- Architecture: `docs/RAG_CONTEXT_STRATEGIES.md`
- Configuration: `.env.example`
- Tests: `tests/integration/test_contextual_rag_endpoint.py`

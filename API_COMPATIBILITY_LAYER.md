# PostgreSQL API Compatibility Layer

This document describes the complete API compatibility layer that enables the chat application to use the new PostgreSQL backend while maintaining 100% API compatibility with the existing frontend.

## Overview

The compatibility layer consists of three main components:

1. **LegacyAPIAdapter** - Translates between new PostgreSQL services and legacy API formats
2. **PostgresController** - Provides Flask route handlers that use the adapter
3. **Updated Routes** - Conditionally switches between legacy and PostgreSQL controllers

## Architecture

```
Frontend (unchanged)
       ↓
   Flask Routes (routes.py)
       ↓ (feature flag: USE_POSTGRES=true)
PostgresController 
       ↓
 LegacyAPIAdapter
       ↓
SearchService + MessageService + Repositories
       ↓
   PostgreSQL Database
```

## Feature Flag

The system uses the `USE_POSTGRES` environment variable to control which backend to use:

- `USE_POSTGRES=true` → PostgreSQL backend with compatibility layer
- `USE_POSTGRES=false` (or unset) → Legacy ChromaDB/SQLite backend

## API Endpoints Supported

All existing API endpoints are fully supported with identical response formats:

### Conversation Endpoints
- `GET /api/conversations` - List all conversations
- `GET /api/conversation/<id>` - Get specific conversation by ID

### Search Endpoints  
- `GET /api/search` - Search conversations with query parameters
- `POST /api/rag/query` - RAG query endpoint for OpenWebUI integration

### Statistics & Health
- `GET /api/stats` - Database statistics
- `GET /api/rag/health` - Health check endpoint
- `GET /api/collection/count` - Collection count

### Management
- `DELETE /api/clear` - Clear entire database
- `POST /api/export/openwebui/<id>` - Export conversation to OpenWebUI

## Files Created/Modified

### New Files
- `db/adapters/legacy_api_adapter.py` - Main adapter translating API calls
- `controllers/postgres_controller.py` - Flask controller using PostgreSQL backend
- `test_api_compatibility.py` - Comprehensive test suite for API compatibility

### Modified Files
- `routes.py` - Updated to conditionally use PostgreSQL controller based on feature flag

## Key Features

### 1. Legacy Format Translation

The adapter converts PostgreSQL data to exact legacy formats:

```python
# PostgreSQL SearchResult → Legacy ChromaDB format
{
    "documents": [["**You said** *(on timestamp)*:\n\nContent..."]],
    "metadatas": [[{
        "id": "uuid",
        "title": "Conversation Title",
        "source": "postgres",
        "message_count": 1,
        "earliest_ts": "ISO timestamp",
        "latest_ts": "ISO timestamp",
        "is_chunk": False,
        "conversation_id": "uuid"
    }]],
    "distances": [[0.15]]
}
```

### 2. Search Compatibility

All search types are supported:
- **FTS Only** (`keyword=true` or `search_type=fts`)
- **Semantic Only** (`search_type=semantic`) 
- **Hybrid** (`search_type=hybrid`)
- **Auto** (default) - Uses hybrid if embeddings available, otherwise FTS

### 3. Error Handling

Comprehensive error handling maintains API contract:
- Returns proper HTTP status codes
- Includes error messages in expected format
- Graceful degradation when services unavailable

### 4. Legacy ID Support

Handles both UUID and legacy ID formats:
- New: `"550e8400-e29b-41d4-a716-446655440000"`
- Legacy: `"chat-0"`, `"docx-1"` (mapped to conversation index)

## Usage

### Development Setup

1. Set environment variable:
```bash
export USE_POSTGRES=true
```

2. Start the Flask application:
```bash
python app.py
```

3. All API calls will now use PostgreSQL backend transparently

### Testing

Run the full compatibility test suite:

```bash
# Setup test data and run all tests
python test_api_compatibility.py

# Only setup test data (for manual testing)
python test_api_compatibility.py --setup-only

# Test against different server
python test_api_compatibility.py --base-url http://localhost:8000
```

### Switching Back to Legacy

To revert to the original ChromaDB/SQLite backend:

```bash
export USE_POSTGRES=false
# or
unset USE_POSTGRES
```

Restart the application and it will use the legacy backend.

## Response Format Compliance

The compatibility layer ensures exact response format matching:

### Conversations List Response
```json
{
  "documents": ["concatenated message content..."],
  "metadatas": [{
    "id": "conversation-uuid",
    "title": "Conversation Title",
    "source": "postgres",
    "message_count": 3,
    "earliest_ts": "2025-01-15T10:30:00Z",
    "latest_ts": "2025-01-15T10:35:00Z", 
    "is_chunk": false,
    "conversation_id": "conversation-uuid"
  }],
  "ids": ["conversation-uuid"]
}
```

### Search Results Response
```json
{
  "query": "search query",
  "results": [{
    "title": "Result Title",
    "date": "2025-01-15T10:30:00Z",
    "content": "Preview content...",
    "metadata": {
      "id": "conversation-uuid",
      "title": "Result Title",
      "source": "postgres",
      "conversation_id": "conversation-uuid",
      "message_id": "message-uuid",
      "role": "user"
    }
  }]
}
```

### RAG Query Response
```json
{
  "query": "rag query",
  "search_type": "semantic",
  "results": [{
    "id": "conversation-uuid",
    "title": "Result Title", 
    "content": "Full content...",
    "preview": "Preview...",
    "source": "postgres",
    "distance": 0.15,
    "relevance": 0.85,
    "metadata": { ... }
  }]
}
```

## Benefits

1. **Zero Frontend Changes** - Existing frontend works unchanged
2. **Gradual Migration** - Can switch between backends via feature flag
3. **Enhanced Performance** - PostgreSQL backend with hybrid search
4. **Enterprise Features** - Atomic transactions, proper concurrency, scalability
5. **Backward Compatibility** - Legacy ID formats and API contracts preserved
6. **Comprehensive Testing** - Full test suite ensures compatibility

## Deployment Strategy

### Phase 1: Parallel Deployment
- Deploy with `USE_POSTGRES=false` (legacy mode)
- Validate all functionality works as before
- Background: Setup PostgreSQL infrastructure

### Phase 2: Limited Testing  
- Switch to `USE_POSTGRES=true` in development/staging
- Run compatibility tests and performance benchmarks
- Identify and fix any edge cases

### Phase 3: Production Migration
- Schedule maintenance window
- Switch production to `USE_POSTGRES=true` 
- Monitor for any issues
- Keep rollback option available (`USE_POSTGRES=false`)

### Phase 4: Cleanup (Future)
- After confirming PostgreSQL backend stability
- Remove legacy backend code and feature flags
- Update frontend to use new features (if desired)

## Monitoring

Key metrics to monitor during migration:

- **API Response Times** - Should be similar or better
- **Error Rates** - Should remain at baseline levels  
- **Search Relevance** - Validate hybrid search quality
- **Database Performance** - Monitor PostgreSQL metrics
- **Memory Usage** - Track application memory consumption

## Support

The compatibility layer maintains detailed logging for troubleshooting:

```python
logger.info("🔍 Hybrid search: 'query' (limit: 10)")  
logger.info("✅ Search complete: 5 FTS + 3 vector → 8 final")
logger.error("❌ Search failed: connection timeout")
```

Monitor logs during migration to identify any issues quickly.
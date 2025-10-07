# RAG Integration with OpenWebUI

## Configuration Instructions

To integrate your ChromaDB-based RAG service with OpenWebUI, follow these steps:

### 1. Start the RAG Service

First, make sure your RAG service is running:

```bash
cd /Users/markrichman/projects/dovos
python rag_service.py
```

The service will start on port 8000.

### 2. Configure OpenWebUI

In your OpenWebUI instance, you'll need to configure the external RAG service:

1. Go to Settings → Admin Settings → RAG Settings
2. Enable "Enable RAG API" 
3. Set the RAG API Base URL to: `http://localhost:8000/rag`
4. Save the settings

### 3. Using the RAG Service

Once configured, OpenWebUI will automatically use your RAG service for:

- Contextual conversation enrichment
- Document retrieval
- Knowledge base querying

### API Endpoints

Your RAG service provides the following endpoints:

- `POST /rag/query` - Semantic or keyword search
- `POST /rag/search` - Hybrid search combining both methods
- `GET /rag/health` - Health check

### Query Format

To query the RAG service directly:

```bash
curl -X POST http://localhost:8000/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Your search query here",
    "n_results": 5,
    "search_type": "semantic"
  }'
```

### Hybrid Search

For more sophisticated searches combining both semantic and keyword matching:

```bash
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Your search query here",
    "n_results": 5,
    "semantic_weight": 0.7
  }'
```

## Integration Benefits

1. **Semantic Search**: Find relevant conversations based on meaning, not just keywords
2. **Keyword Search**: Fast exact and partial matching for specific terms
3. **Hybrid Approach**: Best of both worlds with weighted combination
4. **Context Enrichment**: Provide OpenWebUI with relevant conversation history
5. **Performance**: Leverages your existing ChromaDB vector store

## Troubleshooting

If you encounter issues:

1. Check that the RAG service is running: `curl http://localhost:8000/rag/health`
2. Verify ChromaDB connectivity and collection status
3. Ensure network access between OpenWebUI and the RAG service
4. Check OpenWebUI logs for RAG-related errors

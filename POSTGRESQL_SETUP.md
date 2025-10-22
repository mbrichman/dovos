# PostgreSQL Backend Setup & Feature Flag

This guide explains how to enable and use the new PostgreSQL backend for the chat application.

## Quick Start

### 1. Enable PostgreSQL Backend

```bash
# Option A: Use the management script (recommended)
python manage_postgres_flag.py enable

# Option B: Set environment variable manually
export USE_POSTGRES=true
```

### 2. Test the Setup

```bash
# Run integration test to verify everything works
python manage_postgres_flag.py test

# Or run the tests manually
python test_manual_chat_import.py
python test_e2e_chat_import_search.py
```

### 3. Start Your Application

```bash
# Your Flask app will now use PostgreSQL automatically
python app.py
```

## Feature Flag Control

The PostgreSQL backend is controlled by the `USE_POSTGRES` environment variable:

| Value | Backend | Description |
|-------|---------|-------------|
| `true` | PostgreSQL | New backend with hybrid search, embeddings, etc. |
| `false` | Legacy | Original ChromaDB/SQLite backend |
| *unset* | Legacy | Default - uses original backend |

## Management Commands

### Check Current Status
```bash
python manage_postgres_flag.py status
```

### Enable PostgreSQL Backend
```bash
python manage_postgres_flag.py enable
```

### Disable PostgreSQL Backend  
```bash
python manage_postgres_flag.py disable
```

### Run Integration Test
```bash
python manage_postgres_flag.py test
```

## Manual Environment Setup

### For Current Session Only
```bash
# Enable for this session
export USE_POSTGRES=true

# Disable for this session  
export USE_POSTGRES=false

# Check current value
echo $USE_POSTGRES
```

### For Persistent Setup
Add to your shell profile (`.zshrc`, `.bashrc`, etc.):

```bash
# Enable PostgreSQL backend permanently
echo 'export USE_POSTGRES=true' >> ~/.zshrc
source ~/.zshrc
```

## Features Comparison

### PostgreSQL Backend (`USE_POSTGRES=true`)
✅ **New Features:**
- Hybrid semantic + full-text search
- Vector similarity search with pgvector
- Background embedding generation
- Enterprise-grade PostgreSQL database
- Atomic transactions with outbox pattern
- Concurrent workers for embedding processing
- Advanced search ranking and relevance

✅ **API Compatibility:**
- 100% compatible with existing frontend
- Same response formats as legacy system
- All existing endpoints work identically

### Legacy Backend (`USE_POSTGRES=false`)
✅ **Current Features:**
- ChromaDB vector search
- SQLite metadata storage
- Full-text search
- All existing functionality

⚠️ **Limitations:**
- No hybrid search
- No background embedding generation
- SQLite limitations for concurrent access

## Testing the Migration

### 1. Import and Search Test
```bash
# This test imports a realistic chat conversation and tests all search methods
python test_manual_chat_import.py
```

### 2. Full Integration Test
```bash
# This test runs comprehensive validation of the entire pipeline
python test_e2e_chat_import_search.py
```

### 3. API Compatibility Test
```bash
# This test validates API endpoint compatibility
python test_api_compatibility.py
```

## Deployment Strategy

### Phase 1: Development Testing
1. Enable PostgreSQL in development: `USE_POSTGRES=true`
2. Run all integration tests
3. Validate search quality and performance
4. Test with real data

### Phase 2: Staging Validation  
1. Deploy with PostgreSQL enabled
2. Import production data subset
3. Run performance benchmarks
4. Validate frontend compatibility

### Phase 3: Production Migration
1. Schedule maintenance window
2. Switch to `USE_POSTGRES=true`
3. Monitor application metrics
4. Keep rollback option ready (`USE_POSTGRES=false`)

### Phase 4: Full Migration
1. After confirming stability
2. Remove legacy backend code
3. Update documentation
4. Train team on new features

## Troubleshooting

### Check Feature Flag Status
```bash
python manage_postgres_flag.py status
```

### Test Database Connection
```bash
# Test if PostgreSQL is accessible
python -c "from db.database_setup import setup_database; setup_database(); print('✅ PostgreSQL connection OK')"
```

### Verify Search Functionality
```bash
# Run quick search test
python test_manual_chat_import.py
```

### Reset to Legacy Backend
```bash
# If you need to rollback
python manage_postgres_flag.py disable
# Restart your application
```

## Configuration Files

The feature flag is checked in these locations:

- **`routes.py`** (line 18): `use_postgres = os.getenv('USE_POSTGRES', '').lower() == 'true'`
- **Test files**: Automatically set `os.environ['USE_POSTGRES'] = 'true'`

## Support

If you encounter issues:

1. **Check Status**: `python manage_postgres_flag.py status`
2. **Run Tests**: `python manage_postgres_flag.py test`
3. **View Logs**: Check application logs for PostgreSQL connection errors
4. **Rollback**: `python manage_postgres_flag.py disable` if needed

The new PostgreSQL backend is fully backward compatible, so you can switch between backends safely for testing and validation.
# PostgreSQL Backend Setup

This guide explains how to set up and use PostgreSQL as the database backend for the chat application.

## Quick Start

### 1. Configure Database Connection

Set the `DATABASE_URL` environment variable in your `.env` file:

```env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/dovos
```

### 2. Test the Setup

```bash
# Run integration tests to verify everything works
python tests/e2e/manual_chat_import.py
python tests/e2e/test_e2e_chat_import_search.py
```

### 3. Start Your Application

```bash
# The Flask app uses PostgreSQL automatically
python app.py
```

## Database Management

### Check Database Status
```bash
python scripts/database/simple_db_check.py
```

### Verify Data
```bash
python scripts/database/check_postgres_data.py
```

### Run Database Migrations
```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "Description"
```

## Features

### PostgreSQL Backend Features
✅ **Search Capabilities:**
- Hybrid semantic + full-text search
- Vector similarity search with pgvector
- Advanced search ranking and relevance
- Full-text search with PostgreSQL FTS

✅ **Data Management:**
- Enterprise-grade PostgreSQL database
- Atomic transactions with proper isolation
- Background embedding generation
- Concurrent workers for embedding processing

✅ **Architecture:**
- Clean repository pattern with unit of work
- Service layer for business logic
- Outbox pattern for reliable async processing
- Comprehensive test coverage

## Testing

### 1. Import and Search Test
```bash
# This test imports a realistic chat conversation and tests all search methods
python tests/e2e/manual_chat_import.py
```

### 2. Full Integration Test
```bash
# This test runs comprehensive validation of the entire pipeline
python tests/e2e/test_e2e_chat_import_search.py
```

### 3. Run All Tests
```bash
# Run the complete test suite
pytest

# Run with coverage report
pytest --cov=. --cov-report=html
```

## Deployment Strategy

### Phase 1: Development Testing
1. Set up PostgreSQL database connection
2. Run all integration tests
3. Validate search quality and performance
4. Test with real data

### Phase 2: Staging Validation  
1. Deploy with PostgreSQL configured
2. Import production data subset
3. Run performance benchmarks
4. Validate all functionality

### Phase 3: Production Deployment
1. Schedule maintenance window
2. Deploy application with PostgreSQL
3. Monitor application metrics
4. Verify all services are healthy

### Phase 4: Post-Deployment
1. Monitor performance and stability
2. Optimize queries as needed
3. Update team documentation
4. Train team on PostgreSQL-specific features

## Troubleshooting

### Check Database Status
```bash
python scripts/database/simple_db_check.py
```

### Test Database Connection
```bash
# Test if PostgreSQL is accessible
python -c "from db.database import test_connection; print('✅ PostgreSQL OK' if test_connection() else '❌ Connection failed')"
```

### Verify Search Functionality
```bash
# Run quick search test
python tests/e2e/manual_chat_import.py
```

### Check Logs
```bash
# View application logs for errors
tail -f logs/app.log
```

## Configuration

Key configuration values are in `config/__init__.py`:

- **DATABASE_URL**: PostgreSQL connection string
- **EMBEDDING_MODEL**: Model used for vector embeddings
- **EMBEDDING_DIM**: Dimension of embedding vectors
- **RAG settings**: Context window and retrieval parameters

## Support

If you encounter issues:

1. **Check Status**: `python manage_postgres_flag.py status`
2. **Run Tests**: `python manage_postgres_flag.py test`
3. **View Logs**: Check application logs for PostgreSQL connection errors
4. **Rollback**: `python manage_postgres_flag.py disable` if needed

The new PostgreSQL backend is fully backward compatible, so you can switch between backends safely for testing and validation.
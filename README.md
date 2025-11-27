# Dovos

A chat conversation archive and search application with PostgreSQL full-text search, RAG (Retrieval-Augmented Generation) integration, and OpenWebUI compatibility.

## Description

Dovos is a Flask-based web application designed to import, archive, and search through chat conversations from multiple sources (ChatGPT, Claude, etc.). It features:

- **Full-Text Search**: PostgreSQL-backed FTS for fast, accurate conversation search
- **Vector Search**: Semantic search with pgvector embeddings
- **Hybrid Search**: Combined FTS and vector similarity ranking
- **OpenWebUI Compatibility**: Export and integration with Open WebUI
- **PostgreSQL Backend**: Enterprise-grade database with proper ACID guarantees
- **Chat Import**: Support for ChatGPT and Claude conversation formats
- **Modern Web UI**: Flask-based interface with Jinja2 templates

## Setup and Installation

### Requirements

- Python 3.8+
- PostgreSQL 12+ with pgvector extension

### Python Environment Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root (use `.env.example` as a template):

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/dovos

# Flask
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
```

## Directory Structure

```
dovos/
├── alembic/              # Database migrations
├── api/                  # API endpoints
├── controllers/          # MVC controllers
├── data/                 # Application data (ignored by git)
│   └── source/          # Source conversation files
├── db/                   # Database layer
│   ├── adapters/        # Legacy API format adapter
│   ├── models/          # SQLAlchemy models
│   ├── repositories/    # Repository pattern implementations
│   ├── services/        # Business logic services
│   └── workers/         # Background workers (embedding, etc.)
├── docs/                 # Project documentation
├── models/              # Legacy models (being migrated)
├── scripts/             # Utility scripts
│   ├── archived/       # Deprecated scripts (gitignored)
│   ├── database/       # DB maintenance scripts
│   └── utils/          # General utility scripts
├── static/              # Static web assets
├── templates/           # Jinja2 templates
├── tests/               # Test suite
│   ├── unit/           # Unit tests
│   ├── integration/    # Integration tests
│   ├── e2e/            # End-to-end tests
│   └── fixtures/       # Test fixtures
├── app.py               # Flask application entry point
├── config/              # Application configuration
├── routes.py            # Web routes
└── requirements.txt     # Python dependencies
```

## Development Workflow

### Running Locally

```bash
# Start the Flask development server
python app.py

# Or use Flask CLI
flask run
```

The application will be available at `http://localhost:5000`

### Running with Services

Use the provided startup script to launch all services:

```bash
./start_services.sh
```

### Code Style

- Python: Follow PEP 8 guidelines
- Use type hints where applicable
- Run `python -m compileall -q .` to check for syntax errors

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=. --cov-report=html
```

### Test Organization

- **Unit tests** (`tests/unit/`): Test individual functions and classes in isolation
- **Integration tests** (`tests/integration/`): Test interactions between components
- **E2E tests** (`tests/e2e/`): Test complete user workflows
- **Fixtures** (`tests/fixtures/`): Shared test data and fixtures

**Note**: JSON test fixtures are currently preserved in the root directory and will be migrated to `tests/fixtures/` in a future update.

## Database Setup

### PostgreSQL Configuration

See `docs/POSTGRESQL_SETUP.md` for detailed PostgreSQL setup instructions.

### Database Scripts

- **Status Checks**: `scripts/database/simple_db_check.py` - Quick database health checks
- **Data Verification**: `scripts/database/check_postgres_data.py` - Validate data integrity

### Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Documentation

Additional documentation is available in the `docs/` directory:

- **API Compatibility**: `docs/API_COMPATIBILITY_LAYER.md`
- **PostgreSQL Setup**: `docs/POSTGRESQL_SETUP.md`
- **OpenWebUI Integration**: `docs/OPENWEBUI_EXPORT.md`, `docs/OPENWEBUI_RAG_INTEGRATION.md`
- **Export Implementation**: `docs/EXPORT_TO_OPENWEBUI_IMPLEMENTATION.md`
- **Quick Start**: `docs/QUICK_START_EXPORT.md`
- **Architecture**: `docs/MVC_STRUCTURE.md`
- **UI Plans**: `docs/UI_MODERNIZATION_PLAN.md`
- **Migration Status**: `docs/MIGRATION_STATUS.md`

## Utilities

### Chat Converters

- `scripts/utils/claude_to_docx.py` - Export Claude conversations to Word documents
- `scripts/utils/claude_to_openwebui_converter.py` - Convert Claude format to OpenWebUI format
- `scripts/utils/chat_archive.py` - Archive chat conversations

### Data Import

- `scripts/utils/import_test_data.py` - Import test conversation data
- `scripts/utils/extract_attachments.py` - Extract attachments from conversations

### Demo Scripts

- `scripts/utils/demo_complete_pipeline.py` - Demonstrate the full processing pipeline
- `scripts/utils/demo_repositories.py` - Repository pattern examples
- `scripts/utils/demo_outbox_pattern.py` - Outbox pattern implementation demo

## Notes

- **Archived Scripts**: Deprecated database repair scripts are stored in `scripts/archived/` and ignored by git
- **Data Directory**: Source conversation files live in `data/source/`; the entire `data/` directory is gitignored
- **ChromaDB Storage**: Vector embeddings are stored in `chroma_storage/` (gitignored, ~1GB)
- **Extracted Attachments**: Attachment files are stored in `extracted_attachments/` (gitignored)

## Contributing

1. Create a feature branch from `main`
2. Make your changes
3. Ensure tests pass: `pytest`
4. Commit with descriptive messages
5. Push and create a pull request

## License

[Add your license information here]

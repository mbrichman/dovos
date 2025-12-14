# Dovos

[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker)](https://ghcr.io/mbrichman/dovos)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A chat conversation archive and search application with PostgreSQL full-text search, RAG (Retrieval-Augmented Generation) integration, and OpenWebUI compatibility.

## Description

Dovos is a Flask-based web application designed to import, archive, and search through chat conversations from multiple sources. It features:

- **Full-Text Search**: PostgreSQL-backed FTS for fast, accurate conversation search
- **Vector Search**: Semantic search with pgvector embeddings
- **Hybrid Search**: Combined FTS and vector similarity ranking
- **OpenWebUI Compatibility**: Export and integration with Open WebUI
- **PostgreSQL Backend**: Enterprise-grade database with proper ACID guarantees
- **Chat Import**: Support for Claude and OpenWebUI conversation formats (free) + ChatGPT and DOCX (premium)
- **Modern Web UI**: Flask-based interface with Jinja2 templates

### Premium Features

🔒 **ChatGPT Importer** and **DOCX Importer** are available with Dovos Pro/Enterprise licenses.  
See [PREMIUM_FEATURES.md](PREMIUM_FEATURES.md) for details.

## Setup and Installation

### Requirements

**Option 1: Docker (Recommended)**
- Docker and Docker Compose
- No additional dependencies needed

**Option 2: Local Development**
- Python 3.8+
- PostgreSQL 12+ with pgvector extension

### Quick Start with Docker (Recommended)

**Option A: Using Pre-built Image from GitHub Container Registry**

```bash
# 1. Download the docker-compose file for GHCR
wget https://raw.githubusercontent.com/mbrichman/dovos/main/docker-compose.ghcr.yml

# 2. Create .env file (optional - uses defaults if not provided)
cat > .env << EOF
POSTGRES_USER=dovos
POSTGRES_PASSWORD=dovos_password
POSTGRES_DB=dovos
SECRET_KEY=change-this-secret-key-in-production
EOF

# 3. Start the stack (PostgreSQL + Dovos)
docker compose -f docker-compose.ghcr.yml up -d

# 4. Run database migrations
docker compose -f docker-compose.ghcr.yml exec dovos-rag alembic upgrade head

# 5. Access the application
open http://localhost:5001
```

**Option B: Building from Source**

```bash
# 1. Clone the repository
git clone https://github.com/mbrichman/dovos.git
cd dovos

# 2. Configure environment
cp .env.example .env
# Edit .env with your settings

# 3. Start the entire stack
docker compose up -d

# 4. Run database migrations
docker compose exec dovos-rag alembic upgrade head

# 5. Access the application
open http://localhost:5001
```

### Alternative: Local Python Environment Setup

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

**For Docker deployment:**
```env
# PostgreSQL credentials
POSTGRES_USER=dovos
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=dovos

# Application settings
OPENWEBUI_URL=http://your-openwebui-url:3000
OPENWEBUI_API_KEY=your-api-key
SECRET_KEY=your-secret-key-here
```

**For local development:**
```env
# Database
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/dovos

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

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

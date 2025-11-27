# Next Steps for Dovos Test Suite

**Last Updated:** 2025-11-27  
**Current Status:** Test restoration complete (176/178 passing, 98.9%)  
**Ready for:** Enhancement work

---

## Immediate Priority (Optional)

### Priority 5: Fix Flask App/Test DB Split
**Status:** 1 test currently skipped due to this issue  
**Effort:** 2-3 hours  
**Impact:** Un-skip 1 test, enable exact `==` assertions instead of `>=`

#### Problem
- Flask app routes connect to production database
- Test fixtures seed test database
- Session-scoped Flask app fixture can't be overridden by function-scoped test DB
- Result: HTTP requests via Flask client query production DB instead of test DB

#### Solution
Modify Flask app factory to accept database URL parameter:

**File:** `app.py` or Flask app initialization
```python
def create_app(database_url=None):
    app = Flask(__name__)
    
    # Use provided database URL or default to production
    if database_url:
        app.config['DATABASE_URL'] = database_url
    
    # Initialize controllers with app-specific database connection
    return app
```

**File:** `tests/conftest.py`
```python
@pytest.fixture(scope='function')
def client(test_db_url):
    """Flask test client using test database."""
    app = create_app(database_url=test_db_url)
    with app.test_client() as client:
        yield client
```

#### Tests to Un-skip
- `tests/migration/test_api_contract_compliance.py::test_get_conversation_by_id_structure`

#### Files Modified
- `app.py` or Flask factory
- `tests/conftest.py` (update client fixture)
- `tests/migration/test_api_contract_compliance.py` (remove skip marker)

---

## Future Enhancements

### Enhancement 1: Add Controller Unit Tests
**Priority:** Medium  
**Effort:** 1-2 weeks  
**Current Coverage:** 0%

#### Files to Test
1. **`controllers/postgres_controller.py`** (~2300 lines, 0% coverage)
   - Priority: HIGH - main API entry point
   - Coverage target: 80%+
   
2. **`controllers/conversation_controller.py`** (legacy UI controller)
   - Priority: MEDIUM
   - Coverage target: 60%+

#### Test Categories
- GET endpoints (conversations, conversation by ID, stats, settings)
- POST endpoints (upload, export, RAG query)
- DELETE endpoints (delete conversation, clear database)
- Error handling (invalid IDs, malformed data, database errors)

#### New Test File
**Create:** `tests/unit/test_postgres_controller.py`

**Template:**
```python
import pytest
from controllers.postgres_controller import PostgresController

def test_get_conversations(postgres_controller, seed_conversations):
    """Test retrieving conversations list."""
    # Seed test data
    seed_conversations(count=5)
    
    # Call controller method
    result = postgres_controller.get_conversations()
    
    # Verify response format
    assert "documents" in result
    assert "metadatas" in result
    assert "ids" in result
    assert len(result["documents"]) == 5

def test_get_conversations_empty(postgres_controller):
    """Test retrieving from empty database."""
    result = postgres_controller.get_conversations()
    assert len(result["documents"]) == 0

def test_get_conversation_by_id_not_found(postgres_controller):
    """Test 404 handling for non-existent conversation."""
    result = postgres_controller.get_conversation_by_id("fake-uuid")
    # Verify error response format
```

---

### Enhancement 2: Add Route Integration Tests
**Priority:** Medium  
**Effort:** 1 week  
**Current Coverage:** ~15%

#### Untested Routes
- `POST /upload` - File upload handling
- `POST /export_to_openwebui/<doc_id>` - Export functionality
- `DELETE /api/conversation/<doc_id>` - Delete conversation
- `POST /clear_db` - Clear database
- `GET /settings` - Settings retrieval
- `POST /api/settings` - Settings update

#### New Test File
**Create:** `tests/integration/test_routes_complete.py`

**Template:**
```python
def test_upload_docx_file(client):
    """Test uploading DOCX file via HTTP."""
    # Create test file
    # POST to /upload
    # Verify conversation created
    # Verify messages extracted

def test_delete_conversation(client, seed_conversations):
    """Test DELETE endpoint."""
    conv, _ = seed_conversations(count=1)[0]
    
    response = client.delete(f'/api/conversation/{conv.id}')
    
    assert response.status_code == 200
    assert response.json['success'] == True
    
    # Verify conversation deleted
    response = client.get(f'/api/conversation/{conv.id}')
    assert response.status_code == 404

def test_settings_management(client):
    """Test settings GET/POST endpoints."""
    # GET settings
    response = client.get('/settings')
    assert response.status_code == 200
    
    # POST settings
    response = client.post('/api/settings', json={
        'openwebui_url': 'http://test.example.com'
    })
    assert response.status_code == 200
```

#### Error Case Tests
```python
def test_invalid_conversation_id_404(client):
    """Test 404 for invalid conversation ID."""
    response = client.get('/api/conversation/invalid-uuid')
    assert response.status_code == 404

def test_malformed_json_400(client):
    """Test 400 for malformed request data."""
    response = client.post('/api/rag/query', data='not-json')
    assert response.status_code == 400
```

---

### Enhancement 3: Add E2E Workflow Tests
**Priority:** Low  
**Effort:** 1 week

#### Test Workflows
1. **Upload → Search → View → Export**
   - Upload DOCX file
   - Wait for embeddings
   - Search for content
   - Verify results
   - Export to OpenWebUI

2. **Bulk Upload → RAG Query**
   - Upload multiple conversations
   - Perform RAG queries
   - Verify contextual results

3. **Settings Management Workflow**
   - Configure OpenWebUI URL
   - Test export with settings
   - Verify settings persistence

4. **Conversation Lifecycle**
   - Create conversation
   - Add messages
   - Search conversation
   - Delete conversation
   - Verify cleanup

#### New Files
**Create:**
- `tests/e2e/test_complete_workflows.py`
- `tests/e2e/test_upload_to_export.py`
- `tests/e2e/test_settings_workflow.py`

---

## Performance Testing (Optional)

### Enhancement 4: Add Performance Benchmarks
**Priority:** Low  
**Effort:** 3-5 days

#### Scenarios to Benchmark
- Search with 10k+ conversations
- RAG query latency
- Concurrent API requests (10-100 concurrent users)
- Large conversation imports
- Embedding generation throughput

#### Tools
- pytest-benchmark
- locust (for load testing)

#### New Directory
**Create:** `tests/perf/`

**Example:**
```python
def test_search_performance_10k_conversations(benchmark, seed_conversations):
    """Benchmark search with 10k conversations."""
    seed_conversations(count=10000)
    
    def search():
        search_service.search("test query", limit=10)
    
    result = benchmark(search)
    assert result < 0.5  # Should complete in < 500ms
```

---

## Known Technical Debt

### Issue: Intermittent Torch Model Loading
**Tests affected:**
- `test_hybrid_search_returns_results`
- `test_search_basic_functionality_summary`

**Problem:** Race condition in torch model initialization on Apple Silicon  
**Workaround:** Tests pass when run individually  
**Permanent fix:** Requires torch/sentence-transformers update or model pre-loading

---

## Testing Commands

### Run Full Suite
```bash
source venv/bin/activate
pytest tests/ --tb=no -q
```

### Run with Coverage
```bash
pytest tests/ --cov=controllers --cov=routes --cov-report=html
open htmlcov/index.html
```

### Run Specific Categories
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# E2E tests only
pytest tests/e2e/ -v
```

### Run Performance Tests
```bash
pytest tests/perf/ --benchmark-only
```

---

## Success Criteria for Each Enhancement

### Priority 5
- ✅ 1 test un-skipped
- ✅ All API tests use exact `==` assertions
- ✅ No test/production DB confusion

### Enhancement 1 (Controllers)
- ✅ 80%+ coverage for postgres_controller
- ✅ 60%+ coverage for conversation_controller
- ✅ All happy paths tested
- ✅ Error cases tested

### Enhancement 2 (Routes)
- ✅ All untested routes have tests
- ✅ Error handling validated (404, 400, 500)
- ✅ File upload tested
- ✅ Settings management tested

### Enhancement 3 (E2E)
- ✅ 4+ complete workflows tested
- ✅ End-to-end validation of critical paths
- ✅ Integration with external services (OpenWebUI) tested

### Enhancement 4 (Performance)
- ✅ Baseline metrics established
- ✅ Performance regression tests in place
- ✅ Load testing scenarios defined

---

## Getting Started on Next Enhancement

### For Priority 5 (Flask App Fix)
1. Read the "Solution" section above
2. Create a new branch: `git checkout -b fix-flask-test-db`
3. Modify Flask app factory
4. Update conftest.py
5. Run tests to verify
6. Remove skip marker
7. Commit and merge

### For Controller Tests
1. Create a new branch: `git checkout -b add-controller-tests`
2. Create `tests/unit/test_postgres_controller.py`
3. Start with simple GET tests
4. Add error case tests
5. Run coverage: `pytest tests/unit/test_postgres_controller.py --cov=controllers/postgres_controller`
6. Iterate until 80%+ coverage

### For Route Tests
1. Create a new branch: `git checkout -b add-route-tests`
2. Create `tests/integration/test_routes_complete.py`
3. Test one route at a time
4. Use Flask test client
5. Verify response formats

---

## Questions to Answer Before Starting

### Priority 5
- Does Flask app factory pattern exist?
- Where is the app initialized?
- Are there existing tests that would break?

### Controller Tests
- What's the current architecture pattern?
- Are controllers testable in isolation?
- Do we need to refactor for testability?

### Route Tests
- What's the expected request/response format for each route?
- Are there API contracts defined?
- What error codes should each endpoint return?

---

## Resources

### Documentation
- `TEST_STATUS.md` - Current state and completed work
- `TEST_ANALYSIS.md` - Original analysis (deprecated but historical)
- `docs/` - Any architecture/API documentation

### Code References
- `tests/conftest.py` - Fixture definitions and patterns
- `tests/integration/test_api_conversations.py` - Example of good integration tests
- `tests/unit/test_contextual_retrieval.py` - Example of good unit tests

### External
- pytest documentation: https://docs.pytest.org/
- Flask testing: https://flask.palletsprojects.com/en/latest/testing/
- Coverage.py: https://coverage.readthedocs.io/

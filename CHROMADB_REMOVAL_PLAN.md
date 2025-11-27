# ChromaDB Legacy Code Removal Plan

**Branch**: `remove-chromadb-legacy`  
**Goal**: Remove all ChromaDB/legacy code paths and the USE_POSTGRES feature flag  
**Status**: Planning phase

---

## Background

The application was originally built on ChromaDB and was refactored to use PostgreSQL with pgvector. A feature flag `USE_POSTGRES` was used during migration, but the codebase is now fully PostgreSQL-based. This plan removes all legacy ChromaDB code and the feature flag.

## Safety Net

- ✅ **178 tests passing** (98.9% coverage)
- ✅ Tests validate PostgreSQL functionality
- ✅ No production ChromaDB dependencies

---

## Phase 1: Identify Legacy Components

### Files to Remove

#### Legacy ChromaDB Storage
- `chroma_db/` directory (SQLite storage)
- `chroma_storage/` directory (ChromaDB persist directory)

#### Legacy Models
- `models/search_model.py.backup` (backup file)
- `models/fts_model.py` (if unused)
- `models/conversation_view_model.py` (if ChromaDB-specific)

#### Legacy Code Files
- Any remaining ChromaDB adapter/service files

### Files to Update

#### Configuration
- `README.md` - Remove ChromaDB references, USE_POSTGRES flag
- `.env.example` - Remove USE_POSTGRES, CHROMA_PERSIST_DIRECTORY
- `config.py` - Remove USE_POSTGRES flag handling
- `requirements.txt` - Remove chromadb dependency (if present)

#### Code Files
- `db/adapters/legacy_api_adapter.py` - Check if needed or rename
- `tests/conftest.py` - Remove USE_POSTGRES fixture logic
- `tests/integration/test_backend_selection.py` - Remove or update
- `tests/integration/test_api_compatibility.py` - Remove or update
- `tests/e2e/test_e2e_chat_import_search.py` - Remove USE_POSTGRES
- `tests/e2e/manual_chat_import.py` - Remove USE_POSTGRES

#### Documentation
- `docs/POSTGRESQL_SETUP.md` - Remove USE_POSTGRES references
- `docs/API_COMPATIBILITY_LAYER.md` - Remove ChromaDB references
- `docs/TEST_PLAN_POSTGRES_MIGRATION.md` - Mark as historical/completed
- `docs/TEST_INFRASTRUCTURE_SETUP.md` - Update

#### Scripts
- `scripts/database/simple_db_check.py` - Remove USE_POSTGRES checks
- `scripts/database/check_postgres_data.py` - Remove USE_POSTGRES checks
- `scripts/database/manage_postgres_flag.py` - Delete (manages the flag)

#### Templates
- `templates/postgres_mode.html` - Delete (flag toggle UI)

---

## Phase 2: Code Removal Strategy

### Step 1: Remove Environment Variable References

**Find all**: `USE_POSTGRES`, `CHROMA_PERSIST_DIRECTORY`

**Action**: 
- Remove from .env.example
- Remove from config.py
- Remove conditional logic that checks this flag

### Step 2: Remove ChromaDB Directories

```bash
git rm -r chroma_db/
git rm -r chroma_storage/
```

### Step 3: Remove Legacy Models

```bash
git rm models/search_model.py.backup
# Evaluate and potentially remove:
# - models/fts_model.py
# - models/conversation_view_model.py
```

### Step 4: Update Tests

**Remove from tests:**
- `os.environ['USE_POSTGRES'] = 'true'` lines
- Backend selection test (if ChromaDB-specific)
- API compatibility test (if obsolete)

**Update conftest.py:**
- Remove USE_POSTGRES fixture logic
- Simplify database fixture to always use PostgreSQL

### Step 5: Remove Feature Flag Scripts

```bash
git rm scripts/database/manage_postgres_flag.py
git rm templates/postgres_mode.html
```

### Step 6: Update Documentation

**README.md:**
- Remove "Multiple Database Support" mention
- Update description to PostgreSQL-only
- Remove ChromaDB RAG reference (or clarify it's for embeddings only)
- Remove USE_POSTGRES from env variables

**Other docs:**
- Update POSTGRESQL_SETUP.md
- Archive TEST_PLAN_POSTGRES_MIGRATION.md

---

## Phase 3: Validation Strategy

### Pre-Removal Baseline
```bash
pytest tests/ -v --tb=no
# Should show: 176 passed, 2 skipped
```

### After Each Phase
```bash
# Run tests
pytest tests/ -v --tb=no

# Verify no imports fail
python -m compileall -q .

# Check for remaining references
grep -r "USE_POSTGRES" . --exclude-dir=.git
grep -r "chromadb" . --exclude-dir=.git --exclude-dir=chroma_db
```

### Final Validation
```bash
# Full test suite
pytest tests/ -v

# Verify app starts
python app.py &
sleep 2
curl http://localhost:5001/
pkill -f "python app.py"
```

---

## Phase 4: Expected Test Changes

### Tests That May Break
1. `test_backend_selection.py` - Likely needs removal (tests the flag)
2. `test_api_compatibility.py` - May need updates
3. Any test checking USE_POSTGRES env var

### Tests That Should Continue Passing
- All PostgreSQL-specific tests
- Unit tests (shouldn't care about database backend)
- Integration tests using test database
- Migration validation tests

---

## Phase 5: Rollback Plan

If issues arise:
```bash
git checkout main
git branch -D remove-chromadb-legacy
# Start over with more careful approach
```

Or:
```bash
git revert <commit-hash>
# Revert specific problematic commits
```

---

## Success Criteria

- ✅ No references to `USE_POSTGRES` in code (except historical docs)
- ✅ No references to `chromadb` in active code
- ✅ No `chroma_db/` or `chroma_storage/` directories
- ✅ All tests still pass (176 passing, 2 skipped)
- ✅ Application starts and runs normally
- ✅ Documentation updated to reflect PostgreSQL-only architecture
- ✅ Cleaner codebase with less conditional logic

---

## Execution Order

### PHASE 0: TEST COVERAGE VALIDATION (NEW)
**CRITICAL**: Ensure adequate test coverage before removal

1. ✅ Verify current test baseline: 176/178 passing
2. Identify coverage gaps for components being removed
3. Add missing tests if needed
4. Document what each test validates

### PHASE 1-10: REMOVAL
1. ✅ Document current state (this file)
2. Remove ChromaDB storage directories
3. Remove legacy model backups
4. Remove feature flag from config
5. Update tests to remove USE_POSTGRES
6. Remove feature flag management scripts
7. Remove postgres_mode.html template
8. Update all documentation
9. Final validation
10. Commit and merge

---

## Notes

- The app still uses ChromaDB/embeddings for RAG (vector search), but that's the new architecture, not the legacy code
- Focus is on removing the **dual-backend** system, not vector embeddings
- Legacy adapters may be kept if they provide useful abstraction for the current PostgreSQL implementation

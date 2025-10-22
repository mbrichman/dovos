# API Snapshot Report

Generated: 2025-10-06T20:52:13.419033

This report contains the baseline API responses captured from the current system.
These responses serve as golden snapshots for regression testing during migration.

## Captured Endpoints

### GET /api/conversations

- **Status Code**: 200
- **Captured At**: 2025-10-06T20:52:08.182464
- **Conversations**: 50

### GET /api/conversation/<id>

- **Status Code**: 200
- **Captured At**: 2025-10-06T20:52:08.187421
- **Messages**: 2

### GET /api/search

- **Status Code**: 200
- **Captured At**: 2025-10-06T20:52:08.208898
- **Results**: 5

### POST /api/rag/query

- **Status Code**: 200
- **Captured At**: 2025-10-06T20:52:12.446001
- **Results**: 3

### GET /api/rag/health

- **Status Code**: 200
- **Captured At**: 2025-10-06T20:52:12.446931
- **Health**: healthy

### GET /api/stats

- **Status Code**: 200
- **Captured At**: 2025-10-06T20:52:13.303502
- **Documents**: 0

### ERROR 404

- **Status Code**: 404
- **Captured At**: 2025-10-06T20:52:13.416602


## Usage

These snapshots can be used in tests to:
1. Validate that migrated API responses match exactly
2. Detect any unintended changes in response structure
3. Ensure frontend compatibility is preserved
4. Benchmark performance against baseline

## Files

- `live_api_snapshots.json` - Full response data
- `snapshot_report.md` - This human-readable report

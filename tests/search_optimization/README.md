# Search Optimization Test Suite

This directory contains tools for testing and optimizing DovOS search quality.

## Overview

The search optimization framework consists of:
1. **Test Query Generator** - Analyzes corpus and creates representative test queries
2. **Thematic Search Catalog** - Deep analysis of conversation themes and patterns
3. **Test Harness** (TODO) - Runs queries and evaluates results
4. **Optimization Loop** (TODO) - Iteratively tunes search parameters

---

## Thematic Search Term Catalog

### Additional Files

- **`search_term_catalog.json`** - Primary catalog containing:
  - 15 major thematic clusters with associated conversations
  - Entity index (people, places, organizations, concepts)
  - 15 predefined test queries with expected results

- **`keyword_frequency.json`** - Frequency analysis including:
  - High-frequency terms by category
  - Named entity frequencies
  - Phrase patterns
  - Search optimization recommendations

- **`test_search_terms.py`** - Pytest module for validating catalog structure

### Thematic Clusters

The corpus is organized into these major themes:

| Cluster | Description | Key Terms |
|---------|-------------|-----------|
| personal_transformation | Identity work, career shifts | sovereignty, values, Mark to Dov |
| grief_and_healing | Divorce recovery, loss processing | grief, attachment, healing |
| relationships_and_dating | Dating patterns, connections | CG, TG, TOTGA, dating |
| family_dynamics | Mother/father relationships | mother, Gary, caregiving |
| financial_sovereignty | Investment, crypto, retirement | Bitcoin, 401k, assets |
| mexico_and_relocation | Puerto Vallarta, expat life | PV, Mexico, condo |
| technology_and_ai | Sovereign AI, MCP, LLMs | AI, LM Studio, ChromaDB |
| work_and_career | iManage, compliance | FedRAMP, CMMC, team topologies |
| zero_knowledge_and_privacy | ZK proofs, cryptography | ZK, verification, privacy |
| politics_and_society | Trump, American decline | Trump, collapse, empire |
| rpg_and_gaming | Tabletop RPGs | Night's Black Agents, D&D |
| language_learning | Spanish, Hebrew | Spanish, espanol |
| health_and_wellness | Fasting, sleep | ADF, OMAD, temazcal |
| travel | Trip planning | Dublin, VIA Rail, Toronto |
| memoir_and_writing | Personal writing | memoir, writing, feedback |
| legal_tech_vision | DMS innovation | iManage competitor, legal AI |

### Key Entities

**People (Initials)**
- R - Ex-wife
- CG - Former connection
- TG/TOTGA - "The One That Got Away"
- MG - "Lilith Arc"
- Gary - Father

**Places**
- PV/Puerto Vallarta - Primary destination
- Chicago - Current (departing)
- Toronto/Canada - Backstop

---

## Generated Test Queries

### Query Generation

Run the query generator to create test cases based on your corpus:

```bash
PYTHONPATH=/Users/markrichman/projects/dovos python scripts/search_optimization/generate_search_test_queries.py
```

This creates `search_test_queries.json` with diverse test queries.

### Query Types

The generator creates 4 types of queries:

1. **Keyword Queries** (25 queries)
   - Single significant terms
   - Varying frequency: rare (hard), moderate (medium), common (easy)
   - Example: "songwriting", "callback", "database"

2. **Phrase Queries** (50 queries)
   - Multi-word exact phrases (2-5 words)
   - Based on actual content patterns
   - Example: "spanish translation practice", "without sending"

3. **Semantic Queries** (10 queries)
   - Conceptual/topic-based searches
   - Tests semantic understanding
   - Example: "machine learning models", "API design patterns"

4. **Acronym Queries** (8 queries)
   - Tests synonym expansion
   - Acronyms and their expansions
   - Example: "API" ↔ "application programming interface"

### Difficulty Levels

- **Easy** (14 queries): Common terms, many expected results
- **Medium** (54 queries): Moderate frequency, good discriminative power
- **Hard** (25 queries): Rare terms, few expected results

## Test Query Format

Each test case includes:
```json
{
  "query": "machine learning models",
  "query_type": "semantic",
  "difficulty": "medium",
  "expected_message_ids": ["uuid1", "uuid2", ...],
  "expected_conversation_ids": ["uuid3", "uuid4", ...],
  "notes": "AI/ML discussions"
}
```

## Current Corpus Statistics

- **Total Messages**: 81,713
- **Total Conversations**: 5,297
- **Embeddings**: 81,671 (99.9% coverage)
- **Sample Size**: 10,000 messages analyzed

## Next Steps

### Phase 2: Build Test Harness
Create test runner to:
- Execute queries with different SearchConfig settings
- Calculate quality metrics (Precision@k, MRR, NDCG)
- Compare results against expected outcomes

### Phase 3: Optimization Loop
- Grid search over parameter space
- Agent-driven parameter tuning
- Find optimal SearchConfig

## Tunable Search Parameters

From `SearchConfig` in `db/services/search_service.py`:

### Ranking Weights (must sum to 1.0)
- `vector_weight`: 0.6 (semantic search)
- `fts_weight`: 0.4 (keyword search)

### Quality Thresholds
- `vector_similarity_threshold`: 0.2 (min cosine similarity)
- `fts_rank_threshold`: 0.01 (min FTS rank)

### Result Limits
- `max_results`: 50
- `max_fts_results`: 100
- `max_vector_results`: 100

### Query Processing
- `enable_query_expansion`: True
- `enable_typo_tolerance`: True (not yet implemented)

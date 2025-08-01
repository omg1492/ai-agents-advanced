# Common Errors and Solutions

## RAG System Integration Issues - 2025-08-01

### Environment Variable Loading in Tests

**Problem**: Integration tests failing because `.env` file not loaded in test environment.

**Error Symptoms**:
```
KeyError: 'AZURE_OPENAI_EMBEDDING_API_KEY'
```

**Root Cause**: Tests running in isolated environment without access to application's environment configuration.

**Solution**:
```python
# Add to integration test files
from dotenv import load_dotenv
load_dotenv()  # Add this at module level
```

**Prevention**: Always include dotenv loading in integration tests that require real API/database connections.

---

### SQL Query Execution with SQLAlchemy

**Problem**: Raw SQL strings causing execution failures in SQLAlchemy.

**Error Symptoms**:
```
sqlalchemy.exc.InvalidRequestError: Could not evaluate current criteria
```

**Root Cause**: SQLAlchemy requires explicit text() wrapper for raw SQL queries in modern versions.

**Solution**:
```python
# Before (fails)
result = session.execute(query, {"embedding": embedding_list})

# After (works)
from sqlalchemy import text
result = session.execute(text(query), {"embedding": embedding_list})
```

**Prevention**: Always wrap raw SQL strings with SQLAlchemy's `text()` function.

---

### Vector Dimension Mismatch

**Problem**: Embedding dimension mismatch between model output and database expectations.

**Error Symptoms**:
```
sqlalchemy.exc.DataError: vector dimension 3072 does not match column dimension 2000
```

**Root Cause**: Azure OpenAI text-embedding-3-large defaults to 3072 dimensions, but pgvector was configured for 2000.

**Solution**:
```python
# Limit dimensions in embedding generation
embedding = client.embeddings.create(
    input=text,
    model="text-embedding-3-large",
    dimensions=2000  # Add this parameter
)
```

**Prevention**: Always verify and align embedding dimensions between model configuration and database schema.

---

### Similarity Threshold Tuning

**Problem**: Overly restrictive similarity thresholds returning no results.

**Error Symptoms**: Semantic search queries returning empty results despite relevant data existing.

**Root Cause**: Default similarity threshold (0.7) too high for realistic data distribution.

**Solution**:
```python
# Adjust threshold based on empirical testing
RAG_SIMILARITY_THRESHOLD=0.5  # Reduced from 0.7
```

**Prevention**: Tune similarity thresholds empirically using real data and expected search queries.

---

### Test Environment Contamination

**Problem**: Unit tests failing due to environment variable contamination from other tests.

**Error Symptoms**: Tests passing individually but failing when run as part of full suite.

**Root Cause**: Environment variables from integration tests affecting unit test expectations.

**Solution**:
```python
# Clear both primary and fallback environment variables
with patch.dict(os.environ, {
    "AZURE_OPENAI_EMBEDDING_ENDPOINT": "",
    "AZURE_OPENAI_EMBEDDING_API_KEY": "",
    "AZURE_OPENAI_EMBEDDING_API_VERSION": "",
    # Also clear fallback variables
    "AZURE_OPENAI_ENDPOINT": "",
    "AZURE_OPENAI_API_KEY": "",
    "AZURE_OPENAI_API_VERSION": "",
}, clear=False):
```

**Prevention**: Properly isolate test environments by clearing all relevant environment variables, including fallback options.

---

### Async/Sync Integration Challenges

**Problem**: Mixed async/sync code patterns causing execution issues.

**Common Issues Encountered**:
1. **SQLAlchemy Session Management**: Mixing sync database operations with async FastAPI endpoints
2. **OpenAI Client Usage**: Using sync client in async context without proper handling
3. **Test Framework Confusion**: pytest-asyncio vs standard pytest patterns

**Solutions Applied**:
1. **Consistent Sync Pattern**: Used synchronous SQLAlchemy and OpenAI clients throughout
2. **Proper Session Management**: Created sessions per request, closed explicitly
3. **Clear Test Boundaries**: Separate async integration tests from sync unit tests

**Lessons Learned**:
- Choose async OR sync consistently within a service boundary
- Use async only when genuine concurrency benefits exist
- Avoid mixing patterns unless absolutely necessary
- FastAPI can handle sync route handlers efficiently

**Prevention**: Establish clear async/sync boundaries early in project architecture.

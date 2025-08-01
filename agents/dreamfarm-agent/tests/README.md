# Test Configuration for DreamFarm Agent

## Testing Strategy

This project follows industry best practices for API testing with multiple layers:

### Testing Pyramid

```
        E2E Tests (Manual/Automated Browser)
       /                                    \
      /         Integration Tests           \
     /      (FastAPI TestClient + pytest)   \
    /__________Unit Tests (Mocked)_________\
```

### Test Types

1. **Unit Tests** (`test_*_service.py`)
   - Fast, isolated tests with mocks
   - Test business logic without external dependencies
   - Run frequently during development
   - Examples: `test_thread_service.py`, `test_rag_service.py`, `test_template_service.py`

2. **Integration Tests** (`test_*_integration.py`) 
   - Test API endpoints using FastAPI TestClient
   - Test real functionality with external services
   - **This is the industry standard for API testing**
   - Examples: `test_api_integration.py`, `test_rag_integration.py`

### RAG Testing Strategy

**Unit Tests** (`test_rag_service.py`):
- ✅ Mock OpenAI API calls and database connections
- ✅ Fast execution, no external dependencies
- ✅ Test error handling and business logic
- Run with: `pytest -m unit tests/test_rag_service.py`

**Integration Tests** (`test_rag_integration.py`):
- ✅ Real OpenAI API calls for embeddings
- ✅ Real PostgreSQL database with pgvector
- ✅ End-to-end RAG functionality verification
- ⚠️ Requires environment setup (database, API keys)
- ⚠️ Slower execution, costs money (OpenAI API calls)
- Run with: `pytest -m integration tests/test_rag_integration.py`

## Running Tests

### All Tests
```bash
uv run pytest
```

### Test Categories
```bash
# Unit tests only (fast, no external dependencies)
uv run pytest -m unit -v

# Integration tests only (requires database + API keys)
uv run pytest -m integration -v

# Skip slow/expensive tests
uv run pytest -m "not integration" -v
```

### Specific Services
```bash
# RAG service unit tests (mocked)
uv run pytest tests/test_rag_service.py -v

# RAG service integration tests (real API/DB)
uv run pytest tests/test_rag_integration.py -v

# API integration tests
uv run pytest tests/test_api_integration.py -v

# Thread service unit tests
uv run pytest tests/test_thread_service.py -v
```

### Test Coverage
```bash
uv run pytest --cov=src --cov-report=html
```

### Test with different environments
```bash
# Test with Azure OpenAI
OPENAI_API_TYPE=azure uv run pytest

# Test with OpenAI API
OPENAI_API_TYPE=openai uv run pytest
```

## Industry Standards This Follows

### ✅ FastAPI TestClient
- **Industry Standard**: Uses FastAPI's built-in testing tools
- **Benefits**: Fast, no server startup, consistent environment
- **Used by**: Netflix, Uber, Microsoft for Python APIs

### ✅ pytest Framework
- **Industry Standard**: Most popular Python testing framework
- **Benefits**: Rich plugin ecosystem, fixtures, parametrization
- **Used by**: Google, Dropbox, Mozilla

### ✅ Dependency Injection for Testing
- **Pattern**: Mock external dependencies (OpenAI, databases)
- **Benefits**: Reliable, fast, deterministic tests
- **Standard**: Used in all major tech companies

### ✅ Test Categorization
- **Pattern**: Mark tests by type (unit, integration, e2e)
- **Benefits**: Run different test suites in different environments
- **Standard**: CI/CD pipelines use this approach

## Continuous Integration Integration

### GitHub Actions Example
```yaml
- name: Run Unit Tests
  run: uv run pytest tests/test_*service.py

- name: Run Integration Tests  
  run: uv run pytest tests/test_api_integration.py

- name: Run Manual API Tests (optional)
  run: |
    uv run dreamfarm-agent &
    sleep 5
    uv run python tests/test_api_manual.py
```

### Test Data Management
- Use factories/fixtures for test data
- Reset state between tests
- Use in-memory storage for fast tests

## Advanced Testing (Future Lessons)

1. **Contract Testing** with Pact
2. **Load Testing** with Locust  
3. **Security Testing** with OWASP ZAP
4. **E2E Testing** with Playwright
5. **Mutation Testing** with mutmut

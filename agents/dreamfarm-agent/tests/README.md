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

1. **Unit Tests** (`test_*_service.py`, API tests with mocks)
   - Fast, isolated tests with mocks
   - Test business logic without external dependencies
   - Run frequently during development
  - Examples: `test_rag_service.py`, `test_template_service.py`, `test_api_integration.py`, `test_threads_api_integration.py`

2. **Integration Tests** (`test_*_integration.py`, explicitly marked)
  - Hit real services and infrastructure (OpenAI, PostgreSQL)
  - Examples: `test_api_live_integration.py`, `test_rag_integration.py`

### RAG Testing Strategy

**Unit Tests** (`test_rag_service.py`):
- ✅ Mock OpenAI API calls and database connections
- ✅ Fast execution, no external dependencies
- ✅ Test error handling and business logic
- Run with: `uv run -q pytest -m unit tests/test_rag_service.py`

**Integration Tests**
- `tests/test_api_live_integration.py`: hits real OpenAI/Azure via backend (/threads)
- `tests/test_rag_integration.py`: hits real embeddings + real PostgreSQL (RAG)
- Select with `-m integration`. Tests self‑skip if required env/infra is not available.

## Running Tests

By default, only unit tests run (configured via `pytest.ini: addopts = ... -m unit`). .env is auto‑loaded for all tests.

### Test Categories
```bash
# Unit tests only (fast, no external dependencies)
uv run pytest -m unit -v

# Integration tests only (requires database + API keys)
uv run pytest -m integration -v

# Run everything (unit + integration)
uv run pytest -m "unit or integration" -v
```

### Specific Services
```bash
# RAG service unit tests (mocked)
uv run pytest tests/test_rag_service.py -v

# RAG service integration tests (real API/DB)
uv run pytest tests/test_rag_integration.py -v

# API tests (mocked)
uv run pytest tests/test_api_integration.py -v

# Live API test (real provider)
uv run pytest tests/test_api_live_integration.py -v
```

Azure configuration tips for live test:
- Use OPENAI_BASE_URL with '/openai/v1/' suffix and OPENAI_API_VERSION='preview' (next-gen v1)

PowerShell example to enable and run:
```powershell
$env:RUN_API_INTEGRATION = "true"
$env:OPENAI_API_KEY = "<azure-key>"
$env:OPENAI_BASE_URL = "https://your-resource-name.openai.azure.com/openai/v1/"
$env:OPENAI_API_VERSION = "preview"
$env:OPENAI_MODEL = "gpt-5"
uv run pytest tests/test_api_live_integration.py -v -k live
```

### Test Coverage
```bash
uv run pytest --cov=src --cov-report=html
```

### Test with different environments
Environment setup is documented in the project README; tests automatically load .env.

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

## Continuous Integration

### GitHub Actions Example
```yaml
- name: Run Unit Tests
  run: uv run pytest tests/test_*service.py

- name: Run Integration Tests  
  run: uv run pytest tests/test_api_integration.py

  # Integration tests can be run in a separate job or workflow when envs are available.
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

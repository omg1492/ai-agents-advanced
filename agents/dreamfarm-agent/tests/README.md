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

1. **Unit Tests** (`test_thread_service.py`)
   - Fast, isolated tests with mocks
   - Test business logic without external dependencies
   - Run frequently during development

2. **Integration Tests** (`test_api_integration.py`) 
   - Test API endpoints using FastAPI TestClient
   - Mock external services (OpenAI) but test real HTTP flow
   - Test request/response validation, error handling
   - **This is the industry standard for API testing**

## Running Tests

### All Tests
```bash
uv run pytest
```

### Specific Test Categories
```bash
# Unit tests only
uv run pytest tests/test_thread_service.py -v

# Integration tests only  
uv run pytest tests/test_api_integration.py -v

# Skip integration tests that need real API
uv run pytest -m "not integration"

# Run only integration tests
uv run pytest -m integration
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

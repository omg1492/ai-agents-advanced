# DreamFarm Agent

AI-powered assistant for the Dream Farm marketplace that connects local farmers with customers.

## Overview

This is the main AI agent for the Advanced AI Applications course. It provides a thread-based conversation system that allows customers to interact with an AI assistant about farm products and local produce.

## Features

- **Thread-based Conversations**: Each conversation is managed as a separate thread with message history
- **Dual OpenAI Support**: Works with both Azure OpenAI Service and OpenAI API
- **RAG Capabilities**: Semantic search over farm product database using PostgreSQL + pgvector
- **Jinja2 Template System**: Flexible prompt templating for different scenarios
- **Configuration Management**: Centralized config with environment-based settings
- **Dream Farm Context**: AI assistant specialized in farm marketplace topics
- **RESTful API**: Clean HTTP endpoints for frontend integration
- **In-memory Storage**: Simple storage for Lesson 1 (will be replaced with database in later lessons)

## Quick Start

### Prerequisites

- Python 3.11+
- uv (Python environment manager)

### Setup

1. **Clone and navigate to the agent directory:**
   ```bash
   cd agents/dreamfarm-agent
   ```

2. **Install dependencies:**
   ```bash
   # Install production dependencies
   uv sync
   
   # Install development dependencies (needed for testing)
   uv sync --dev
   ```

3. **Configure environment variables:**
   Copy and edit the `.env` file with your OpenAI credentials:

   **For Azure OpenAI:**
   ```env
   OPENAI_API_TYPE=azure
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_API_KEY=your-api-key
   AZURE_OPENAI_API_VERSION=2024-02-15-preview
   AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
   CORS_ORIGINS=http://localhost:3000
   
   # RAG Configuration (requires PostgreSQL + pgvector)
   ENABLE_RAG=true
   PGHOST=localhost
   PGDATABASE=your-database
   PGUSER=your-username
   PGPASSWORD=your-password
   AZURE_OPENAI_EMBEDDING_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_EMBEDDING_API_KEY=your-embedding-api-key
   AZURE_OPENAI_EMBEDDING_API_VERSION=2024-12-01-preview
   AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-large
   ```

   **For OpenAI API:**
   ```env
   OPENAI_API_TYPE=openai
   OPENAI_API_KEY=your-openai-api-key
   OPENAI_MODEL=gpt-4o
   CORS_ORIGINS=http://localhost:3000
   
   # RAG Configuration (requires PostgreSQL + pgvector)  
   ENABLE_RAG=true
   PGHOST=localhost
   PGDATABASE=your-database
   PGUSER=your-username
   PGPASSWORD=your-password
   # For OpenAI API, use the same key for embeddings
   ```

4. **Run the agent:**
   ```bash
   uv run dreamfarm-agent
   ```
   
   Or alternatively using uvicorn directly:
   ```bash
   uv run uvicorn src.main:app --reload --port 8001
   ```

   The agent will be available at `http://localhost:8001`

### Testing

**Prerequisites for Testing:**
```bash
# Make sure development dependencies are installed
uv sync --dev
```

**Industry Standard Testing (Recommended):**
```bash
# Run all tests
uv run pytest

# Run only unit tests (fast, with mocks)
uv run pytest -m unit

# Run only integration tests (slower, requires real database and API)
uv run pytest -m integration

# Run integration tests for RAG functionality (requires database + OpenAI API)
uv run pytest -m "integration and requires_api" tests/test_rag_integration.py

# Run with coverage report
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_rag_service.py  # Unit tests with mocks
uv run pytest tests/test_rag_integration.py  # Integration tests with real services
```

**Manual/Exploratory Testing:**

1. **HTTP REST Client file** (`tests/api_manual_tests.http`):
   - Use with VS Code REST Client extension
   - Contains comprehensive API test scenarios
   - Best for interactive development and debugging

2. **Manual testing script** (`tests/test_api_manual.py`):
   ```bash
   # Make sure the agent is running first
   uv run dreamfarm-agent
   
   # In another terminal, run manual tests
   uv run python tests/test_api_manual.py
   ```

**See `tests/README.md` for detailed testing strategy and best practices.**

## API Endpoints

### Health Check
- `GET /health` - Check service health

### Thread Management  
- `POST /threads` - Create a new conversation thread
- `GET /threads/{thread_id}` - Get thread information
- `POST /threads/{thread_id}/messages` - Send a message and get AI response  
- `GET /threads/{thread_id}/messages` - Get conversation history

## Example Usage

### Create a thread
```bash
curl -X POST http://localhost:8001/threads \
  -H "Content-Type: application/json" \
  -d '{"title": "Looking for fresh vegetables"}'
```

### Send a message
```bash
curl -X POST http://localhost:8001/threads/{thread_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "What fresh vegetables do you have available this season?"}'
```

## Architecture

- **FastAPI**: Web framework for the REST API
- **Pydantic**: Data validation and serialization
- **OpenAI/Azure OpenAI**: AI response generation
- **PostgreSQL + pgvector**: Vector database for semantic search (RAG)
- **SQLAlchemy**: Database ORM for vector operations
- **Jinja2**: Template engine for dynamic prompt generation
- **In-memory storage**: Thread and message persistence (Lesson 1 only)

## Development

### Project Structure
```
src/
├── __init__.py
├── main.py              # FastAPI application
├── models/
│   ├── __init__.py
│   ├── health.py        # Health check models
│   └── thread.py        # Thread and message models
└── services/
    ├── __init__.py
    ├── openai_service.py # OpenAI/Azure OpenAI integration
    └── thread_service.py # Thread management
tests/
├── test_thread_service.py    # Unit tests (with mocks)
├── test_api_integration.py   # Integration tests (FastAPI TestClient) ⭐
├── api_manual_tests.http     # REST Client test file
├── test_api_manual.py        # Manual testing script
├── README.md                 # Testing strategy and best practices
└── pytest.ini               # Test configuration
```

⭐ **`test_api_integration.py` is the industry standard for API testing**

### Adding New Features

1. Add new Pydantic models in `models/`
2. Implement business logic in `services/`
3. Add API endpoints in `main.py`
4. Write tests in `tests/`

## Future Enhancements (Later Lessons)

- Database persistence for threads/messages (PostgreSQL)
- MCP tool integration
- User authentication
- Multi-agent orchestration

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure you've run `uv sync` to install dependencies
2. **OpenAI API errors**: Check your API keys and endpoints in `.env`
3. **CORS issues**: Verify `CORS_ORIGINS` includes your frontend URL
4. **Port conflicts**: Ensure port 8001 is available

### Logs

The application logs to stdout with INFO level. Check logs for detailed error information.

## Contributing

Follow the project coding standards:
- Use docstrings for all public methods
- Add type hints
- Write tests for new functionality
- Update this README for significant changes

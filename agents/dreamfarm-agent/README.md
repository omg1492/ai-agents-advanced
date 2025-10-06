# DreamFarm Agent

AI-powered assistant for the Dream Farm marketplace that connects local farmers with customers.

## Overview

This is the main AI agent for the Advanced AI Applications course. It provides a simple /chat endpoint powered by OpenAI Responses API with server-side conversation state.

## Features

- **Server-side Conversation State**: Uses Responses API with `store` and `previous_response_id` for continuity
- **Dual OpenAI Support**: Works with both Azure OpenAI Service and OpenAI API
- **RAG Capabilities**: Semantic search over farm product database using PostgreSQL + pgvector
- **Jinja2 Template System**: Flexible prompt templating for different scenarios
- **Configuration Management**: Centralized config with environment-based settings
- **Dream Farm Context**: AI assistant specialized in farm marketplace topics
- **RESTful API**: Clean HTTP endpoints for frontend integration
- **In-memory Storage**: Simple storage for Lesson 1 (will be replaced with database in later lessons)
- **JWT Authentication (Keycloak)**: Optional RS256 validation of access tokens (dev default enabled)
- **Voice Mode**: Speech-to-speech conversations via OpenAI Realtime API (WebSocket-based)
- **Memory & Personalization**: Conversation summaries, memory search, and user profiles

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
   Copy and edit the `.env` file with your OpenAI credentials using the unified scheme:

   **OpenAI (hosted by OpenAI):**
   ```env
   OPENAI_API_KEY=your-openai-api-key
   OPENAI_MODEL=gpt-5
   CORS_ORIGINS=http://localhost:3000

   # RAG Configuration (requires PostgreSQL + pgvector)
   ENABLE_RAG=true
   PGHOST=localhost
   PGDATABASE=your-database
   PGUSER=your-username
   PGPASSWORD=your-password
   OPENAI_EMBEDDING_MODEL=text-embedding-3-large
   ```

   **Azure OpenAI (next‑gen v1):**
   ```env
   OPENAI_API_KEY=your-azure-api-key
   OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/
   OPENAI_API_VERSION=preview
   OPENAI_MODEL=your-deployment-name  # use your Azure deployment name
   CORS_ORIGINS=http://localhost:3000

   # RAG Configuration (requires PostgreSQL + pgvector)
   ENABLE_RAG=true
   PGHOST=localhost
   PGDATABASE=your-database
   PGUSER=your-username
   PGPASSWORD=your-password
   OPENAI_EMBEDDING_MODEL=text-embedding-3-large  # Azure deployment name for embeddings
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

### Authentication (Keycloak JWT)

The agent can validate access tokens issued by the local Keycloak realm provisioned via `identity/provision_keycloak.py`.

Environment variables (already present in `.env`):
```env
AUTH_ENABLED=true                  # Toggle auth (all chat/thread endpoints require Bearer token when true)
KEYCLOAK_URL=http://localhost:8080 # Keycloak base URL
KEYCLOAK_REALM=dreamfarm           # Realm name
KEYCLOAK_AUDIENCE=dreamfarm-frontend  # Expected client_id (aud) in tokens
```

Behavior:
- On each protected request the `Authorization: Bearer <access_token>` header is required.
- Token is validated for signature (RS256 via JWKS), issuer (`{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}`) and audience.
- Username + VIP status (realm role `vip`) are extracted and included in request logs.
- If `AUTH_ENABLED=false`, endpoints skip validation (development fallback).

Current scope (dev): No refresh endpoint, no per-route RBAC decisions yet—only identity extraction and logging foundation for later RAG fencing.

### Optional: Remote MCP Tools (Farmer Tools)

Enable a public MCP server as a tool for the model via the Responses API. Configure in `.env`:

```env
# Enable and point to your MCP server URL
FARMER_TOOLS_ENABLED=true
FARMER_TOOLS_MCP_URL=https://farmer-tools.tomasdemo.org/mcp

# Bearer token used as HTTP Authorization header for the MCP server
FARMER_TOOLS_MCP_API_KEY=advancedaiapps2025
# Note: legacy MCP_API_KEY is also accepted as a fallback.
```

When enabled, the backend passes a remote MCP tool named `farmer-tools` to the model with:
`Authorization: Bearer <FARMER_TOOLS_MCP_API_KEY>`.

### Optional: Voice Mode (Speech-to-Speech)

Enable real-time voice conversations via OpenAI Realtime API:

```env
# Enable voice mode WebSocket endpoint
VOICE_ENABLED=true
```

**Requirements:**
- OpenAI account with Realtime API access (gpt-4o-realtime-preview model)
- Modern browser with Web Audio API support (Chrome/Edge recommended)
- Microphone permissions

**Features:**
- Real-time bidirectional audio streaming (24kHz mono PCM16)
- Automatic transcription and persistence with `mode='voice'` flag
- Tool filtering: only `memory_search` enabled by default for low latency
- Optional heavy tools mode via `?enable_heavy_tools=true` query parameter

**Usage:**
1. Start agent with `VOICE_ENABLED=true`
2. Frontend shows voice button in thread UI
3. Click "Start Voice" → Grant mic permission → Speak naturally
4. Transcripts automatically saved to conversation history

**Documentation**: See `docs/voice-mode.md` for detailed guide.

### Testing

**Prerequisites for Testing:**
```bash
# Make sure development dependencies are installed
uv sync --dev
```

**Industry Standard Testing (Recommended):**
```bash
# By default, only unit tests run (see pytest.ini addopts)
uv run pytest

# Explicit: run only unit tests (fast, with mocks)
uv run pytest -m unit

# Run integration tests (slower, requires real database and/or API)
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

### Running Real-API Integration Tests (Optional)

RAG integration tests call real OpenAI embeddings and a real PostgreSQL database. They are skipped unless you explicitly run the integration suite. Use pytest markers to select suites:

```powershell
# OpenAI hosted:
$env:OPENAI_API_KEY = "<openai-key>"
$env:OPENAI_MODEL = "gpt-5"
$env:OPENAI_EMBEDDING_MODEL = "text-embedding-3-large"

# Azure OpenAI (next-gen v1):
$env:OPENAI_API_KEY = "<azure-key>"
$env:OPENAI_BASE_URL = "https://<your-azure-openai>.openai.azure.com/openai/v1/"
$env:OPENAI_API_VERSION = "preview"
$env:OPENAI_MODEL = "<chat-deployment-name>"
$env:OPENAI_EMBEDDING_MODEL = "text-embedding-3-large"  # embedding deployment name

# PostgreSQL
$env:PGHOST = "localhost"; $env:PGPORT = "5432"; $env:PGDATABASE = "aidb"; $env:PGUSER = "admin"; $env:PGPASSWORD = "<password>"

# Run RAG integration tests (database + embeddings)
uv run pytest -m "integration and requires_api" tests/test_rag_integration.py -v

# Live API test for /threads (non-RAG):
uv run pytest -m integration tests/test_api_live_integration.py -v -k live
```

## API Endpoints

### Health Check
- `GET /health` - Check service health

### Chat
- `POST /chat` - Send a message and get AI response
   - Request body: `{ "message": string, "previous_response_id"?: string }`
   - Response body: `{ "response_id": string, "message": string, "timestamp": string }`
   - Use the returned `response_id` as `previous_response_id` on the next request to continue the conversation on the server side.

### Sessions (Lightweight Thread API)
- `POST /threads` - Create a new session handle (thread)
   - Request body: `{ "title"?: string }`
   - Response body: `{ "thread_id": string, "title": string, "created_at": string, "updated_at": string }`
- `GET /threads/{thread_id}` - Get session metadata
- `POST /threads/{thread_id}/messages` - Send a message and get AI response
   - Request body: `{ "message": string }`
   - Response body: `{ "message_id": string, "thread_id": string, "user_message": string, "assistant_response": string, "timestamp": string }`
- `GET /threads/{thread_id}/messages` - Get a lightweight, in-memory message history for UI display (not used for generation)

Notes:
- The backend keeps only the last `response_id` per `thread_id` and passes it as `previous_response_id` to the Responses API to preserve server-side conversation state.

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
- **Responses API**: /chat endpoint using server-managed state; lightweight `/threads` for session handles and UI-only history

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
   └── openai_service.py # OpenAI/Azure OpenAI integration via Responses API
tests/
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
- User authorization & role-based filtering (VIP product fencing)
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

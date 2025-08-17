## 2025-08-16

- Refactored `data/scripts/embeddings_simple_products.py` to use the unified OpenAI SDK configuration consistent with `agents/dreamfarm-agent`:
   - Uses `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_API_VERSION`, and `OPENAI_EMBEDDING_MODEL` only (no legacy fallbacks).
   - Implemented batching (100 items), retries with exponential backoff and respect for `Retry-After` on 429.
   - Reduced third-party loggers to WARNING while keeping our logger at INFO.
   - Saves output to `../processed/simple_products.parquet`.
- Updated `data/scripts/.env.template` to include unified env variables and clarified legacy variables are not used by scripts.
- Updated `data/scripts/README.md` quick start to reference `.env.template` and unified environment variables.

# Implementation Log

## Responses API Migration & session API - 2025-08-16

- Migrated DreamFarm Agent from Chat Completions to Responses API.
   - Async clients (AsyncOpenAI/AsyncAzureOpenAI)
   - Server-side state via `store=True` and `previous_response_id`
   - Enable GPT-5 minimal reasoning `reasoning={"effort": "minimal"}` when model starts with `gpt-5`.
- Added `POST /chat` endpoint using Responses API.
- Reintroduced lightweight `/threads` endpoints to manage client session handles while keeping conversation state in the provider via `previous_response_id`.
- Removed deprecated `ThreadService`; replaced with minimal session handling directly in `main.py`. `models/thread.py` now provides minimal Pydantic models used by the endpoints.
- Updated tests:
   - Added mocked integration tests for `/chat` using FastAPI TestClient.
   - Skipped old ThreadService tests.
   - Marked any real-API integration tests as skipped by default.
- Upgraded `openai` package to `>=1.99.0,<2.0.0` in `pyproject.toml`.
- Updated README to reflect new API and usage.

## Unified OpenAI/Azure client via Responses API - 2025-08-16

- Refactored OpenAI integration to a single client setup using the next‑gen v1 API style.
   - Use OpenAI SDK with optional `base_url` and `default_query={"api-version": "preview"}` for Azure.
   - Works for both OpenAI-hosted and Azure OpenAI without branching on provider type.
- Updated environment variables to a unified scheme:
   - Required: `OPENAI_API_KEY`, `OPENAI_MODEL`.
   - Azure-specific: `OPENAI_BASE_URL`, `OPENAI_API_VERSION`.
   - Embeddings: `OPENAI_EMBEDDING_MODEL` (deployment name on Azure).
- Maintained backward compatibility by reading legacy Azure envs if unified ones are missing.
- Updated docs (`README.md`, `docs/Design.md`) and `.env.template` accordingly.
- Adjusted tests to the unified configuration.
   - Removed reliance on OPENAI_API_TYPE in tests and config, favoring OPENAI_BASE_URL detection.

## Test simplification and config injection - 2025-08-16

## Template wiring for Responses API - 2025-08-16

- Initialized `TemplateService` during app startup in `src/main.py`.
- Replaced hardcoded instruction strings with rendering of `src/templates/system_prompt.j2` in both `/chat` and `/threads/{id}/messages` endpoints.
- Passed optional RAG context from `RAGService.get_relevant_context` into the template as `simple_rag`, so it appears under `<relevant_products>`.
- Added DEBUG logs to output the rendered system prompt for verification when `LOG_LEVEL=DEBUG`.

- Simplified test selection: removed RUN_* env gates (e.g., RUN_RAG_INTEGRATION, RUN_API_INTEGRATION).
   - Default: unit tests selected via pytest marker in pytest.ini (`-m unit`).
   - Integration tests are explicitly selected with `-m integration` and self‑skip only when required env/infra is missing.
- OpenAI configuration injection:
   - `OpenAIService` now accepts `OpenAIConfig` from `ConfigService` (env fallback preserved).
   - `main.py` injects the config: `OpenAIService(config_service.get_openai_config())`.
   - Tests that patch `OpenAIService` continue to work unchanged.

## RAG System Integration & Testing Success - 2025-08-01

### RAG System Implementation Complete

**Major Achievement**: Successfully implemented and tested end-to-end RAG (Retrieval-Augmented Generation) system with real database and API integration.

#### Final Test Results ✅
- **50 tests passing** (100% success rate)
- **1 test skipped** (OpenAI conversation flow requiring different API setup)
- **0 tests failing**

#### RAG System Architecture Decisions

1. **Vector Database Integration**:
   - **Decision**: PostgreSQL + pgvector for semantic search
   - **Implementation**: Cosine similarity search with configurable thresholds
   - **Benefits**: Production-ready vector database, SQL familiarity, excellent performance

2. **Embedding Strategy**:
   - **Decision**: Azure OpenAI text-embedding-3-large model with 2000 dimensions
   - **Rationale**: Optimal balance between quality and pgvector compatibility
   - **Configuration**: Environment-driven with fallback support

3. **Testing Architecture**:
   - **Unit Tests**: Comprehensive mocking for fast isolated testing (16 tests)
   - **Integration Tests**: Real API and database connections for end-to-end validation (8 tests)
   - **Separation**: Clear boundaries between fast unit tests and slower integration tests

#### Technical Implementation Highlights

**RAG Service Features**:
- Dynamic embedding generation with dimension control
- Configurable similarity thresholds (optimized to 0.5 for realistic results)
- Proper SQL query execution with SQLAlchemy text() wrapper
- Graceful error handling and service availability checking
- Environment-based enable/disable functionality

**Real Search Results Demonstrated**:
- "organic vegetables" → Cosmic Carrots, Baby Carrots, Organic Broccoli (scores: 0.524-0.526)
- "tomatoes" → Roma Tomatoes, San Marzano varieties (scores: 0.565-0.573)  
- "cheese" → Various artisanal cheeses (scores: 0.512-0.518)

#### Lessons Learned

**Critical Issues Resolved**:
1. Environment variable loading in test isolation
2. SQL query execution with raw strings vs SQLAlchemy text()
3. Vector dimension alignment between training and inference
4. Similarity threshold tuning based on actual data distribution
5. Test environment contamination and proper mocking strategies

**Best Practices Established**:
- Always load environment variables in integration tests using python-dotenv
- Use SQLAlchemy text() wrapper for raw SQL queries
- Match embedding dimensions between model and database constraints
- Tune similarity thresholds empirically with real data
- Isolate test environments to prevent variable contamination

## Code Structure Review & Template System - 2025-08-01

### Architecture Enhancement

1. **Jinja2 Template System Implementation**:
   - **Decision**: Added dedicated `TemplateService` for managing AI prompts with Jinja2 templates
   - **Structure**: Created `src/templates/` directory for organized prompt management
   - **Benefits**:
     - Separation of prompt logic from business logic
     - Dynamic prompt generation with context injection
     - Better maintainability and reusability of prompts
     - Template validation and error handling

2. **Configuration Service Implementation**:
   - **Decision**: Centralized configuration management with `ConfigService`
   - **Features**: Environment-based config, validation, type safety with dataclasses
   - **Benefits**: 
     - Single source of truth for configuration
     - Better error messages for missing config
     - Environment-specific settings support

3. **Utility Module Addition**:
   - **Decision**: Added `src/utils/` package for shared utility functions
   - **Functions**: Input sanitization, error formatting, safe nested access
   - **Benefits**: Reusable helper functions, consistent error handling

### Template Structure
- `system_prompt.j2`: Main AI assistant system prompt with context variables
- `product_recommendation.j2`: Specialized prompt for product recommendations
- Templates support dynamic content injection (user location, preferences, available products)

## Lesson 1: DreamFarm Agent Implementation

### 2025-07-28 - Initial Implementation

#### Architecture Decisions Made

1. **Import Strategy**: 
   - **Decision**: Use absolute imports (`from src.models.health import...`) instead of relative imports (`from .models.health import...`)
   - **Rationale**: 
     - Absolute imports are clearer and more explicit
     - Easier to run files directly for testing/debugging
     - Better IDE support and tooling compatibility
     - Follows Python best practices for application code
     - Avoids "attempted relative import with no known parent package" errors

2. **Package Structure**:
   - **Decision**: Use `src/` layout with absolute imports
   - **Benefits**: 
     - Clear separation between source code and other files
     - Standard Python packaging convention
     - Better testing isolation
     - Easier deployment and distribution

3. **Entry Points**:
   - **Decision**: Use `[project.scripts]` in pyproject.toml for clean CLI interface
   - **Implementation**: `dreamfarm-agent = "src.main:main"`
   - **Benefits**: Clean `uv run dreamfarm-agent` command

#### Technical Implementation

**Core Components Implemented:**
- ✅ FastAPI application with CORS support
- ✅ Thread-based conversation management (in-memory storage)
- ✅ Dual OpenAI provider support (Azure OpenAI + OpenAI API)
- ✅ Pydantic models for data validation
- ✅ Health check endpoint
- ✅ Comprehensive error handling and logging
- ✅ Dream Farm domain-specific system prompt

**API Endpoints:**
- `GET /health` - Health check
- `POST /threads` - Create conversation thread
- `GET /threads/{thread_id}` - Get thread info
- `POST /threads/{thread_id}/messages` - Send message + get AI response
- `GET /threads/{thread_id}/messages` - Get conversation history

**Environment Configuration:**
- Support for both Azure OpenAI and OpenAI API
- CORS configuration for frontend integration
- Example `.env` file for easy setup

#### Project Structure

```
agents/dreamfarm-agent/
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + routes
│   ├── models/
│   │   ├── __init__.py
│   │   ├── health.py        # Health check models
│   │   └── thread.py        # Thread/message models
│   └── services/
│       ├── __init__.py
│       ├── openai_service.py # OpenAI integration
│       └── thread_service.py # Thread management
├── tests/
│   └── test_thread_service.py
├── .env.example
├── .env                     # (gitignored)
├── pyproject.toml
└── README.md
```

#### Testing Strategy

**Decision**: Implement comprehensive testing following industry best practices
**Approach**: Multi-layer testing pyramid with appropriate tools for each layer

**Testing Layers Implemented:**

1. **Unit Tests** (`test_thread_service.py`)
   - ✅ Fast, isolated tests with mocks
   - ✅ Test business logic without external dependencies
   - ✅ Use pytest fixtures and async testing

2. **Integration Tests** (`test_api_integration.py`) - **Industry Standard**
   - ✅ FastAPI TestClient for realistic API testing
   - ✅ Mock external services (OpenAI) but test real HTTP flow
   - ✅ Test request/response validation, error handling
   - ✅ No server startup required - fast and reliable
   - **This is what Netflix, Uber, Microsoft use for Python APIs**

3. **Manual/Exploratory Tests**
   - ✅ HTTP REST Client file for interactive development
   - ✅ Automated script for manual testing against real server
   - ✅ Useful for debugging but not for CI/CD

**Testing Configuration:**
- ✅ pytest.ini with proper markers and configuration
- ✅ Test categorization (unit, integration, manual)
- ✅ Comprehensive test documentation in tests/README.md

**Benefits:**
- **Fast Feedback**: Unit tests run in milliseconds
- **Reliable**: Integration tests don't depend on external services
- **Comprehensive**: Multiple testing approaches for different needs
- **Industry Standard**: Uses FastAPI TestClient (the recommended approach)
- **CI/CD Ready**: Tests can run in automated pipelines

**Why FastAPI TestClient > Manual HTTP Testing:**
- ❌ Manual HTTP tests: Require server startup, slower, flaky, hard to debug
- ✅ TestClient: Fast, consistent, better error messages, no network dependencies

## 2025-08-17 - Streaming responses end-to-end

- Backend: added `POST /threads/{thread_id}/messages/stream` which streams plain text tokens using OpenAI Responses streaming context manager. It builds the same Jinja2 system prompt and optional RAG context as non-streaming, yields deltas, and updates in-memory history and `previous_response_id` at completion.
- Frontend: added `dreamFarmAPI.sendMessageStream()` returning a ReadableStream and updated `DreamFarmChatAdapter.run` to be an async generator that reads from the stream and yields progressively to assistant-ui, so tokens appear as they arrive.
- Kept existing non-streaming endpoint for compatibility. No breaking API changes.

## 2025-08-17 - Design doc API/schema alignment

- Updated `docs/Design.md` to fully reflect current API and models:
   - Added missing `POST /chat` endpoint section with `ChatRequest`/`ChatResponse` shapes.
   - Fixed `GET /threads/{thread_id}/messages` response example to include required `thread_id` inside each message item.
   - Aligned Pydantic snippets with code: `Thread.message_count` required, `Message.role` as `str` union, added Chat models section.
   - Kept environment and RAG sections unchanged, only clarified SQL schema fields already present in data scripts.

   ## 2025-08-17 - Design doc project structure alignment

   - Updated `docs/Design.md` Project Structure section to match current repository layout:
      - Reflected top-level folders: agents, data, deploy, docs, frontend, lessons, scripts.
      - Expanded `agents/dreamfarm-agent` key subfolders: src/{models, services, templates, utils}, tests, docs, scripts.
      - Added `data/processed`, `data/scripts`, and `data/source_json`.
      - Included `deploy/{azure,kubernetes,local}` and `frontend/{public,src,scripts}`.

   ## 2025-08-17 - Design doc structure simplification

   - Simplified `Project Structure` section per guidance:
      - Do not list files or root-level files; only main folders and key subfolders.
      - Do not enumerate lesson subfolders; added a comment that lessons contain instructions for individual lessons.
      - Kept docs listed as a main folder without enumerating contents.

      ## 2025-08-17 - Design doc database schema simplification

      - Replaced raw SQL in `Database Schema` with a concise description of the `simple_products` table and its columns.
      - Added notes about HNSW vector index (cosine) and supporting btree indexes for lookups.
      - Ensured column names and types match the `data/scripts/sql/tables/01_create_simple_products.sql` script.

      ## 2025-08-17 - Design doc DB schema table formatting

      - Reformatted the brief `simple_products` schema into a Markdown table for readability while retaining index notes.

      ## 2025-08-17 - Dev utility: lesson branches cherry-pick helper

      - Added `scripts/cherry_pick.py` and documented it in `scripts/README.md`.
      - Automates cherry-picking the latest commit from main into all lesson branches matching `Lxx-teacher`, `Lxx-student-starter`, `Lxx-student-end`.
      - Uses git CLI via subprocess for reliability; no extra dependencies added.
      - Provides interactive confirmation, progress output, conflict abort/continue behavior, and a summary report.
      - Enhancement: script now automatically pushes updated branches to the remote (sets upstream when missing) — no flags required.
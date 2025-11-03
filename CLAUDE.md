# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

This is an **educational course repository** for building production-grade AI applications. The project demonstrates a virtual farmers marketplace called "Dream Farm" with an intelligent AI assistant. The course is structured in 10 lessons, taught in Czech language (docs) with code in English.

**Branch Structure:**
- `Lxx-student` - Student starting points with exercises
- `Lxx-teacher` - Complete solutions for instructors
- `main` - Full production version

Always check the current branch to understand which lesson context you're working in.

## Development Commands

### Local Development Setup (Lesson 1+)

```bash
# 1. Start PostgreSQL
cd deploy/local
docker-compose up -d postgres

# 2. Configure database (creates extensions: pgvector, age)
cd ../../data/scripts
uv sync
uv run configure_postgresql.py

# 3. Import product data with embeddings (L01)
uv run import_simple_products.py

# 4. Start agent (terminal 1)
cd ../../agents/dreamfarm-agent
uv sync
uv run uvicorn src.main:app --reload --port 8001

# 5. Start frontend (terminal 2)
cd ../../frontend
npm install
npm run dev  # Port 3000
```

### Testing

```bash
cd agents/dreamfarm-agent

# Unit tests only (fast, default)
uv run pytest

# Integration tests (requires DB + OpenAI API)
uv run pytest -m integration

# Specific integration tests
uv run pytest -m "integration and requires_api" tests/test_rag_integration.py

# With coverage
uv run pytest --cov=src --cov-report=html

# Manual API testing
uv run python tests/test_api_manual.py
```

**Test Markers:**
- `unit` - Fast tests with mocks
- `integration` - Requires database or external services
- `requires_api` - Requires OpenAI API key

### Data Pipeline

```bash
cd data/scripts

# Generate sample data (optional)
uv run gen_basic_data.py

# Create embeddings from JSON (L01)
uv run prepare_simple_products.py  # → processed/simple_products.parquet

# Import to PostgreSQL
uv run import_simple_products.py
```

## Architecture Overview

### Current State (Lesson 1)
```
React Frontend (port 3000)
    ↓ HTTP/REST
FastAPI Agent (port 8001)
    ↓ OpenAI API
Azure OpenAI / OpenAI
    ↓ Embeddings (2000 dimensions)
PostgreSQL + pgvector (port 5432)
```

### Technology Stack
- **Python:** 3.11+, managed with `uv` (NEVER use pip)
- **Backend:** FastAPI with Uvicorn, SQLAlchemy, Pydantic
- **Database:** PostgreSQL 17 with pgvector (vectors) and Apache AGE (graphs)
- **Frontend:** React 18+, TypeScript, Vite, assistant-ui
- **AI:** OpenAI GPT-5 / Azure OpenAI, text-embedding-3-large (2000 dim)
- **Infrastructure:** Docker, Kubernetes (AKS), Helm, Terraform

### Key Directories
- `agents/dreamfarm-agent/` - Main FastAPI agent (port 8001)
  - `src/main.py` - FastAPI app entry
  - `src/services/` - Business logic (OpenAI, RAG)
  - `src/templates/` - Jinja2 prompt templates
  - `tests/` - pytest unit/integration tests
- `data/scripts/` - Data pipeline scripts (uv managed)
- `frontend/` - React UI
- `docs/` - Comprehensive architecture docs
- `lessons/` - Lesson-specific materials
- `deploy/local/` - Docker Compose for local dev

## Important Development Guidelines

### Code Quality (from AGENTS.md)

1. **Documentation:**
   - Use docstrings for all public functions (no progress/status comments)
   - Update `docs/ImplementationLog.md` for architectural decisions
   - Update component README for operational changes
   - NO inline progress, migration, or "previous implementation" comments

2. **Python Standards:**
   - Package manager: **`uv`** exclusively (never pip)
   - Virtual env: `uv venv` + `source .venv/bin/activate`
   - Dependencies: `uv sync`
   - Type hints required
   - Pydantic models for data validation
   - Python logging (no print statements in production)

3. **Testing:**
   - Use pytest with markers (`unit`, `integration`, `requires_api`)
   - Unit tests with mocks (fast)
   - Integration tests for DB/API (slower)
   - Convert ad-hoc findings into proper tests

4. **Disposable Artifacts:**
   - Test scripts: `adhoc_test_*.py` or `adhoc_*.py`
   - Temporary docs: `ADHOC_*.md`
   - **Must be deleted** after insights extracted

5. **Refactoring:**
   - Opportunistic simplifications encouraged
   - Low-risk cleanups: proceed directly
   - Architectural shifts: surface rationale first

### Configuration

**Environment Variables (.env):**
```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Azure OpenAI (alternative)
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/
OPENAI_API_VERSION=preview

# PostgreSQL
PGHOST=localhost
PGPORT=5432
PGDATABASE=aidb
PGUSER=admin
PGPASSWORD=your-password

# Agent
CORS_ORIGINS=http://localhost:3000
ENABLE_RAG=true
RAG_SIMILARITY_THRESHOLD=0.3
RAG_MAX_RESULTS=3
```

## Database Schema

### Current (Lesson 1): simple_products
- `product_id` (UUID)
- `producer_name` (varchar)
- `product_name` (varchar)
- `product_description` (text)
- `combined_text` (text)
- `embedding` (vector[2000]) - pgvector index

Created via `data/scripts/import_simple_products.py`

### Future Lessons
- `products` - Full catalog with full-text search (FTS)
- `stock` - Inventory management
- `semantic_cache` - Query acceleration
- `concept_embeddings` - Knowledge graph nodes
- `conversations_raw` - Chat history
- `memory_store` - User preferences

See `docs/DataSchemas.md` for complete schemas.

## API Endpoints

### DreamFarm Agent (port 8001)

**Health:**
- `GET /health` - Health check

**Responses API:**
- `POST /chat` - Send message with server-side state
  - Request: `{ "message": string, "previous_response_id"?: string }`
  - Response: `{ "response_id": string, "message": string, "timestamp": string }`

**Thread-based API:**
- `POST /threads` - Create conversation thread
- `GET /threads/{thread_id}` - Get thread metadata
- `POST /threads/{thread_id}/messages` - Send message
- `GET /threads/{thread_id}/messages` - Get message history

See `docs/APIReference.md` for complete specifications.

## Common Issues & Solutions

### Embedding Dimensions
- pgvector indexes limited to **2000 dimensions**
- Must cap embeddings: `embedding[:2000]` when using text-embedding-3-large

### OpenAI Rate Limiting
- Implement exponential backoff for 429 errors
- Use retry logic in embedding generation scripts

### Database Connection
- Ensure PostgreSQL is running: `docker-compose ps`
- Check extensions installed: `SELECT * FROM pg_extension;`
- Required extensions: `vector`, `age`

### Testing Failures
- Integration tests require `.env` with valid `OPENAI_API_KEY`
- Database tests need PostgreSQL running with proper schema
- Use markers to skip: `pytest -m "not integration"`

See `docs/CommonErrors.md` for comprehensive troubleshooting.

## Lesson Progression

Each lesson builds incrementally:

1. **L01** - Basic RAG with semantic search
2. **L02** - Tool usage (MCP, web search, APIs)
3. **L03** - Multi-format knowledge base (docs, images, videos)
4. **L04** - Agentic search, knowledge graphs, authentication
5. **L05** - Voice chat, long-term memory, multimodality
6. **L06** - Code interpreter, dynamic visualizations
7. **L07** - Workflow orchestration (Temporal)
8. **L08** - Multi-agent systems (LangGraph)
9. **L09** - Security, red teaming, evaluation
10. **L10** - Observability, K8s deployment, CI/CD

See `docs/Agenda.md` and lesson-specific folders in `lessons/` for details.

## Documentation References

- `docs/Design.md` - System architecture
- `docs/RetrievalArchitecture.md` - RAG and hybrid search
- `docs/ToolSpecifications.md` - AI tools and MCP servers
- `docs/Observability.md` - OpenTelemetry tracing
- `docs/ConfigurationReference.md` - Environment variables
- `docs/ImplementationLog.md` - Implementation history
- `AGENTS.md` - Detailed development guidelines

## Key Constraints

1. **Package Management:** Always use `uv`, never pip
2. **Code Comments:** Only for non-obvious logic, never for progress/history
3. **Test Artifacts:** Delete `adhoc_` scripts after validation
4. **Logging:** Use Python logging module with appropriate levels
5. **Type Safety:** Type hints required for all functions
6. **Data Validation:** Pydantic models for all data contracts
7. **Simplicity:** KISS principle - simplest solution that works

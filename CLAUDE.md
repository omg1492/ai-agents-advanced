# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Dream Farm AI Platform** - A production-grade AI-powered virtual farmers marketplace demonstrating advanced AI application development including RAG, multi-agent systems, knowledge graphs, and enterprise deployment patterns. This is a 10-lesson course progressing from basic chat to sophisticated AI systems.

**Tech Stack:**
- **Backend**: Python 3.11+ with FastAPI, managed by `uv` package manager
- **Frontend**: React + TypeScript with assistant-ui library
- **Database**: PostgreSQL with pgvector (embeddings), full-text search, Apache AGE (knowledge graph)
- **AI**: OpenAI GPT-5, embeddings, RAG, multi-agent systems, voice interaction
- **Deployment**: Docker, Kubernetes (AKS), Terraform, Helm
- **Auth**: Keycloak (OAuth2/OIDC)

---

## Quick Start Commands

### Initial Setup

```bash
# 1. Start infrastructure (PostgreSQL + Keycloak)
cd deploy/local
docker-compose up -d postgres keycloak

# 2. Setup database and import data
cd ../../data/scripts
uv sync
uv run configure_postgresql.py
uv run import_all.py

# 3. Provision Keycloak
cd ../../identity
uv sync
uv run provision_keycloak.py

# 4. Start backend agent
cd ../agents/dreamfarm-agent
uv sync
cp .env.template .env
# Edit .env with OpenAI credentials
uv run uvicorn src.main:app --reload --port 8001

# 5. Start frontend
cd ../../frontend
npm install
# Edit public/config.js with backend URL
npm run dev
```

**Access:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8001/docs
- Keycloak: http://localhost:8080

---

## Common Development Commands

### Backend (Python/FastAPI)

```bash
# ALWAYS use uv (NEVER pip)
uv sync                      # Install dependencies
uv sync --dev                # Include dev dependencies
uv add <package>             # Add new dependency

# Run agent
uv run dreamfarm-agent       # Using project script
uv run uvicorn src.main:app --reload --port 8001  # With hot reload

# Testing
uv run pytest                # Unit tests only (default)
uv run pytest -m integration # Integration tests
uv run pytest -m "integration and requires_api"  # Full tests with OpenAI
uv run pytest --cov=src --cov-report=html  # With coverage
uv run pytest tests/test_rag_service.py    # Specific test file
```

### Frontend (React/TypeScript)

```bash
npm install                  # Install dependencies
npm run dev                  # Start dev server (hot reload)
npm run build                # Production build
npm run preview              # Preview production build
npm run lint                 # Lint code
```

### Data Pipeline

```bash
cd data/scripts
uv sync

# Database setup
uv run configure_postgresql.py   # Setup schema and extensions
uv run import_all.py             # Import all data

# Individual operations
uv run gen_basic_data.py         # Generate sample data
uv run embeddings_products.py    # Generate embeddings
uv run import_products.py        # Import products
uv run import_graph_age.py       # Import knowledge graph

# Content processing
uv run process_pdfs.py           # Process PDFs for knowledge base
uv run process_images.py         # Process images
uv run process_videos.py         # Process videos (requires FFmpeg)
```

### Deployment

```bash
# Docker build
cd agents/dreamfarm-agent
docker build -t dreamfarm-agent .

# Kubernetes deployment
cd deploy/charts/demo
helm install dreamfarm . --values values.yaml

# Terraform infrastructure
cd deploy/azure/infrastructure
terraform init
terraform plan
terraform apply
```

---

## Architecture Overview

### System Components

```
┌─────────────────┐
│  React Frontend │ (assistant-ui, port 3000)
└────────┬────────┘
         │ REST/WebSocket
┌────────▼────────────────────┐
│  DreamFarm Agent (FastAPI)  │ (port 8001)
│  - RAG & Retrieval          │
│  - Tool Orchestration       │
│  - Memory & Personalization │
│  - Voice Interaction        │
└────────┬────────────────────┘
         │
    ┌────┴─────┬──────────────┬────────────┐
┌───▼────┐ ┌──▼──────┐  ┌────▼────┐  ┌───▼─────┐
│PostgreSQL│ │OpenAI   │  │MCP Tools│  │Keycloak │
│+pgvector │ │/Azure   │  │Servers  │  │(OAuth2) │
│+AGE Graph│ │         │  │         │  │         │
└──────────┘ └─────────┘  └─────────┘  └─────────┘
```

### Project Structure

```
agents/dreamfarm-agent/     # FastAPI backend
├── src/
│   ├── main.py             # App entry point
│   ├── services/           # Business logic (RAG, search, memory, voice)
│   ├── models/             # Pydantic models
│   ├── templates/          # Jinja2 prompt templates
│   └── utils/              # Shared utilities
├── tests/                  # Unit & integration tests
└── pyproject.toml          # uv project config

frontend/                   # React UI
├── src/
│   ├── components/         # UI components (thread, thread-list, etc.)
│   ├── services/           # API client & chat adapter
│   └── App.tsx
└── public/config.js        # Runtime configuration

data/                       # Data layer
├── scripts/                # ETL & data pipelines
│   ├── sql/tables/         # SQL schema definitions
│   └── *.py                # Import/processing scripts
├── source_json/            # Source data files
├── processed/              # Generated embeddings & artifacts
└── PDFs/images/videos/     # Knowledge base content

tools/                      # External tools
├── mcp_public_farmer_tools/  # MCP server
└── api_stock/              # Stock API service

deploy/                     # Deployment configs
├── local/docker-compose.yml   # Local dev
├── azure/                  # Azure + Terraform
└── charts/demo/            # Helm charts

docs/                       # Documentation
├── Design.md               # Architecture
├── APIReference.md         # API specs
├── DataSchemas.md          # Database schemas
├── RetrievalArchitecture.md  # RAG details
└── CommonErrors.md         # Troubleshooting

lessons/                    # Course materials (L01-L10)
```

### Component Responsibilities

**Backend Agent:**
- REST & WebSocket endpoints (`POST /chat`, `WS /voice/{thread_id}`)
- RAG with hybrid search (semantic + keyword + graph)
- Tool orchestration (function calling, MCP servers)
- Memory & personalization (user profiles, conversation summaries)
- Voice interaction via OpenAI Realtime API
- JWT authentication & feature flags

**Database (PostgreSQL):**
- **pgvector**: HNSW indexes for semantic search
- **Full-Text Search**: GIN indexes for keyword search
- **Apache AGE**: Knowledge graph (taxonomy, products, relationships)
- Tables: products, producers, conversations, user_profiles, semantic_cache

**Frontend:**
- ChatGPT-like UI with streaming responses
- OIDC authentication (Keycloak PKCE flow)
- Thread management and history
- Voice capture/playback
- File upload for code interpreter

---

## Key Patterns & Conventions

### 1. Package Management

**Python - ALWAYS use `uv` (NEVER pip):**
```bash
uv sync              # Install deps
uv add package       # Add dependency
uv run script.py     # Run in venv
```

**JavaScript - Use `npm`:**
```bash
npm install          # Install deps
npm run dev          # Dev server
```

### 2. Configuration Management

**Unified OpenAI Client (works for both OpenAI and Azure):**
```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),  # Optional, Azure only
)
```

**Feature Flags (.env):**
- `ENABLE_RAG` - Semantic search
- `AGENTIC_SEARCH_ENABLED` - Tool-based retrieval
- `GRAPH_SEARCH_ENABLED` - Knowledge graph queries
- `MEMORY_SEARCH_ENABLED` - Conversation memory
- `USER_PROFILE_ENABLED` - User personalization
- `VOICE_ENABLED` - Voice interaction
- `AUTH_ENABLED` - Authentication

### 3. Backend Service Organization

All business logic in `services/`:
- `config_service.py` - Centralized configuration
- `openai_service.py` - LLM interactions
- `rag_service.py` - Vector search
- `agentic_search.py` - Tool-based search
- `graph_search_service.py` - Knowledge graph
- `memory_search_service.py` - Conversation memory
- `user_profile_service.py` - User profiles
- `voice_service.py` - Realtime API
- `auth_service.py` - JWT validation

### 4. Testing Strategy

**Pytest Markers:**
```python
@pytest.mark.unit           # Fast tests with mocks (default)
@pytest.mark.integration    # Tests with TestClient
@pytest.mark.requires_api   # Needs real OpenAI API
@pytest.mark.slow           # Tests > 1 second
```

**Running Tests:**
```bash
uv run pytest                                    # Unit tests only
uv run pytest -m integration                     # Integration tests
uv run pytest -m "integration and requires_api"  # Full tests with API
```

**Test Organization:**
- `tests/test_*_unit.py` - Unit tests with mocks
- `tests/test_*_integration.py` - Integration tests
- `tests/api_manual_tests.http` - Manual REST client tests

### 5. Database Patterns

**Vector Search (pgvector):**
```sql
CREATE INDEX idx_products_embedding ON products
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Full-Text Search:**
```sql
CREATE INDEX idx_products_fts ON products
USING gin(to_tsvector('english', fts_document));
```

**Knowledge Graph (Apache AGE):**
```cypher
SELECT * FROM cypher('dreamfarm', $$
  MATCH (c:Category)<-[:HAS_CATEGORY]-(p:Product)
  WHERE c.name = 'Organic'
  RETURN p.name, p.price
$$) as (name agtype, price agtype);
```

### 6. API Design

**Streaming with Meta Events:**
The backend uses a custom meta-event format in SSE streams:
```
DF_META: {"type": "tool_call", "name": "semantic_search", "args": {...}}
Regular assistant response text...
DF_META: {"type": "retrieval", "sources": [...]}
```

**Main Endpoints:**
- `POST /chat` - Single-turn chat
- `POST /threads` - Create thread
- `POST /threads/{thread_id}/messages` - Send message
- `GET /threads/{thread_id}/messages` - Get history
- `WS /voice/{thread_id}` - Voice WebSocket

### 7. Documentation Guidelines (from AGENTS.md)

**DO:**
- Add docstrings to all public functions/classes
- Comment non-obvious logic or critical nuances
- Use `docs/ImplementationLog.md` for decisions and history
- Update relevant docs when making changes

**DON'T:**
- Add progress logs or migration notes in code
- Keep "previous implementation" commentary
- Commit ad-hoc test scripts (prefix with `adhoc_`, delete after use)

### 8. Branch Strategy

- **`main`** - Production-ready with all features
- **`Lxx-teacher`** - Complete lesson implementation
- **`Lxx-student`** - Student starting point
- **`Lxx-teacher-my`** - Your working branch

Current branch: `L05-teacher-my` (Lesson 5: Memory & Voice)

---

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Verify .env settings (use 'localhost' for local dev, not 'postgres')
PGHOST=localhost
PGPORT=5432
PGDATABASE=advanced_ai_db
PGUSER=admin
PGPASSWORD=admin123
```

### OpenAI API Errors

```bash
# Verify credentials in .env
OPENAI_API_KEY=sk-...

# For Azure OpenAI, also set:
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/
OPENAI_API_VERSION=preview
```

### Frontend Can't Connect to Backend

```javascript
// Edit public/config.js
window.APP_CONFIG = {
  BACKEND_URL: 'http://localhost:8001',  // Match backend port
  API_VERSION: 'v1'
};
```

```bash
# Check CORS settings in backend .env
CORS_ORIGINS=http://localhost:3000
```

### Vector Search Returns No Results

```bash
# Ensure embeddings are imported
cd data/scripts
uv run embeddings_products.py
uv run import_products.py

# Verify HNSW index exists (connect to database)
SELECT indexname FROM pg_indexes WHERE tablename = 'products';
```

### Authentication Failures

```bash
# Ensure Keycloak is running
docker-compose ps keycloak

# Provision Keycloak realm
cd identity
uv run provision_keycloak.py

# Verify frontend config matches backend
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=dreamfarm
KEYCLOAK_CLIENT_ID=dreamfarm-frontend
```

### Debug Mode

```bash
# Backend - Set in .env
LOG_LEVEL=DEBUG
uv run uvicorn src.main:app --log-level debug

# Frontend - Add to public/config.js
window.APP_CONFIG = { ..., DEBUG: true };
```

---

## Additional Resources

**Documentation:**
- Architecture: [docs/Design.md](docs/Design.md)
- API Reference: [docs/APIReference.md](docs/APIReference.md)
- Database Schemas: [docs/DataSchemas.md](docs/DataSchemas.md)
- RAG Architecture: [docs/RetrievalArchitecture.md](docs/RetrievalArchitecture.md)
- Common Errors: [docs/CommonErrors.md](docs/CommonErrors.md)
- Agent Guidelines: [AGENTS.md](AGENTS.md)

**Course Materials:**
- Lesson agendas: [docs/Agenda.md](docs/Agenda.md)
- Individual lessons: `lessons/L01_*/`, `lessons/L02_*/`, etc.

**Deployment:**
- Local: [deploy/local/README.md](deploy/local/README.md)
- Azure: [deploy/azure/README.md](deploy/azure/README.md)
- Kubernetes: `deploy/kubernetes/`

**Tools:**
- MCP Servers: [tools/mcp_public_farmer_tools/README.md](tools/mcp_public_farmer_tools/README.md)
- Stock API: [tools/api_stock/README.md](tools/api_stock/README.md)

---

## Key Development Principles (from AGENTS.md)

1. **Simplicity First** - KISS principle, choose simplest solution
2. **Refactor Over Addition** - Clean up rather than layer new code
3. **Clean Code** - Maintainability above all else
4. **SOLID Principles** - Follow design patterns for robust code
5. **Test Code Hygiene** - Remove test code after validation unless explicitly kept
6. **Documentation** - Use docstrings, update docs, minimal inline comments
7. **No Ad-Hoc Artifacts** - Prefix with `adhoc_`, delete after use

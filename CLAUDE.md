# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**Dream Farm AI Platform** - A production-grade AI marketplace demonstrating advanced AI capabilities including RAG, multi-agent systems, graph databases, voice interaction, workflow orchestration, and enterprise observability. Built as a 10-lesson intensive course on Advanced AI Applications.

This is a multi-component monorepo with Python backends (FastAPI), React frontend, PostgreSQL with extensions (pgvector, Apache AGE), and Kubernetes deployment.

## Architecture & Key Concepts

### High-Level System Architecture

```
Frontend (React + assistant-ui)
    ↓ REST/WebSocket
Agent Backends (FastAPI)
    ↓ Multiple channels
├─→ LLM (OpenAI/Azure OpenAI)
├─→ PostgreSQL (pgvector + AGE + FTS)
├─→ MCP Servers (Model Context Protocol tools)
└─→ External Services (Keycloak, Temporal)
```

### Critical Design Principles

1. **Grounded Generation** - All product claims must originate from retrieved, fenced data
2. **Feature Flags** - Each capability independently enabled (see ConfigurationReference.md)
3. **Provider-Agnostic LLM** - Unified OpenAI/Azure client abstraction
4. **Security-by-Default** - Row-level VIP fencing at SQL layer
5. **Explainability** - Structured meta events (`DF_META`) for transparency

### Multi-Agent Architecture

This platform uses the **Agent-as-Tool pattern**:
- **DreamFarm Agent** (`agents/dreamfarm-agent`) - Main marketplace agent
- **Chef Agent** (`agents/chef-agent`) - Culinary services specialist
- Agents communicate via HTTP function calling (independent FastAPI services)

### Retrieval Architecture (RAG)

The system supports multiple retrieval strategies (see `docs/RetrievalArchitecture.md`):
- **Simple RAG**: Vector similarity with prompt injection
- **Hybrid Retrieval**: Semantic + keyword + RRF fusion
- **Agentic Search**: LLM-orchestrated multi-tool retrieval
- **Graph Traversal**: BFS taxonomy expansion, DFS similarity (Apache AGE)
- **Semantic Caching**: First-turn acceleration for common queries

### Database Architecture

PostgreSQL with three extensions:
- **pgvector**: Product/concept embeddings (2000 dimensions), semantic cache
- **Apache AGE**: Knowledge graph (taxonomy, relationships, Cypher queries)
- **Full-Text Search**: GIN indexes on `fts_document` column for keyword search

Key tables: `simple_products`, `products`, `stock`, `conversations_raw`, `conversation_summaries`, `user_profiles`, `semantic_cache`, `concept_embeddings`, plus AGE graph nodes/edges.

## Development Commands

### Environment Setup

**Python (all Python components use `uv`):**
```bash
cd <component-directory>
uv venv
source .venv/bin/activate  # or .venv/bin/activate on Windows
uv sync                     # Install production dependencies
uv sync --dev              # Include development dependencies
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev                # Development server (port 3000)
npm run build             # Production build
npm run lint              # ESLint
```

### Running the System Locally

**1. Start PostgreSQL with extensions:**
```bash
cd deploy/local
docker-compose up -d postgres
```

**2. Configure Database:**
```bash
cd data/scripts
cp .env.template .env      # Configure OpenAI + PostgreSQL credentials
uv sync
uv run configure_postgresql.py
```

**3. Generate and Import Data:**
```bash
# Basic pipeline (Lesson 1)
uv run gen_basic_data.py
uv run embeddings_simple_products.py
uv run import_simple_products.py

# Full pipeline (all lessons)
uv run embeddings_products.py
uv run import_products.py
uv run import_stock.py
uv run import_graph_age.py
uv run gen_graph_taxonomy.py
uv run import_taxonomy_age.py
uv run embeddings_concepts.py
uv run import_concept_embeddings.py
uv run gen_qna.py
uv run embeddings_qna.py
uv run import_qna.py
```

**4. Run DreamFarm Agent:**
```bash
cd agents/dreamfarm-agent
cp .env.template .env      # Configure OpenAI, PostgreSQL, features
uv sync --dev
uv run dreamfarm-agent     # Runs on port 8001
# OR: uv run uvicorn src.main:app --reload --port 8001
```

**5. Run Frontend:**
```bash
cd frontend
npm run dev                # Access at http://localhost:3000
# Edit public/config.js to configure BACKEND_URL if needed
```

### Testing Strategy

**Python (pytest) - All components:**
```bash
cd <component-directory>
uv sync --dev

# Default: unit tests only (fast, with mocks)
uv run pytest

# Explicit: unit tests
uv run pytest -m unit

# Integration tests (requires real DB/API)
uv run pytest -m integration

# Integration tests requiring API
uv run pytest -m "integration and requires_api"

# With coverage
uv run pytest --cov=src --cov-report=html

# Specific test file
uv run pytest tests/test_rag_service.py
```

**Test markers:**
- `@pytest.mark.unit` - Fast tests with mocks (default)
- `@pytest.mark.integration` - Real database/services required
- `@pytest.mark.requires_api` - OpenAI API calls (costs money)

**Running a single test:**
```bash
uv run pytest tests/test_api_integration.py::TestChatEndpoint::test_chat_basic
```

**Manual API testing:**
- REST Client file: `tests/api_manual_tests.http` (VS Code REST Client extension)
- Manual script: `uv run python tests/test_api_manual.py`

### Data Pipeline Commands

All data scripts are in `data/scripts/`:

```bash
cd data/scripts
uv sync

# Core pipeline
uv run configure_postgresql.py      # Setup DB schema + extensions
uv run gen_basic_data.py            # Generate sample data
uv run embeddings_simple_products.py # Generate embeddings
uv run import_simple_products.py    # Import to DB

# Graph operations
uv run import_graph_age.py          # Populate AGE graph
uv run import_graph_age.py --reset  # Rebuild graph from scratch
uv run import_graph_age.py --batch-size 500  # Custom batch size

# Taxonomy generation (resumable)
uv run gen_graph_taxonomy.py
uv run gen_graph_taxonomy.py --rebuild-concepts  # Force regenerate
uv run import_taxonomy_age.py
uv run import_taxonomy_age.py --reset-taxonomy  # Reset taxonomy only

# Semantic cache
uv run gen_qna.py                   # Generate Q&A pairs
uv run embeddings_qna.py            # Embed questions
uv run import_qna.py                # Import to semantic_cache

# Multimodal processing
uv run process_pdfs.py              # Extract from PDFs
uv run process_images.py            # Process images
uv run process_video.py             # Process videos (requires ffmpeg)
```

### Code Quality

**Python:**
```bash
# Linting (ruff)
ruff check .
ruff check --fix .

# Type checking (mypy)
mypy src/

# Formatting (black)
black src/ tests/
```

**Frontend:**
```bash
cd frontend
npm run lint
```

## Project Structure

```
├── agents/                      # AI agent backends (FastAPI)
│   ├── dreamfarm-agent/         # Main marketplace agent
│   │   ├── src/                 # Source code
│   │   │   ├── main.py          # FastAPI app
│   │   │   ├── models/          # Pydantic models
│   │   │   ├── services/        # Business logic
│   │   │   └── routes/          # API endpoints
│   │   ├── tests/               # pytest tests
│   │   ├── pyproject.toml       # uv dependencies
│   │   └── .env.template        # Config template
│   └── chef-agent/              # Culinary services agent (similar structure)
├── data/                        # Data pipeline
│   ├── scripts/                 # ETL, import scripts (uv projects)
│   │   ├── pyproject.toml
│   │   └── *.py                 # Standalone data scripts
│   ├── source_json/             # Generated sample data
│   ├── processed/               # Parquet embeddings + artifacts
│   └── PDFs/images/videos/      # Multimodal inputs
├── frontend/                    # React UI
│   ├── src/                     # React components
│   ├── public/config.js         # Runtime config (build once, deploy anywhere)
│   ├── package.json             # npm dependencies
│   └── vite.config.ts           # Vite build config
├── tools/                       # MCP servers + APIs
│   ├── mcp_public_farmer_tools/ # Utility MCP server
│   ├── mcp_visualization_generator/ # Dynamic UI MCP
│   └── api_stock/               # Stock REST API
├── deploy/                      # Deployment configs
│   ├── local/                   # Docker Compose
│   ├── azure/                   # Terraform IaC + Docker build
│   └── charts/                  # Helm charts for Kubernetes
├── orchestration/               # Temporal workflows
│   └── complaint_workflow/      # Complaint handling workflow
├── identity/                    # Keycloak provisioning scripts
├── postgresql/                  # Dockerfile for PostgreSQL with extensions
├── docs/                        # Comprehensive documentation
│   ├── Design.md                # High-level architecture
│   ├── APIReference.md          # REST/WebSocket specs
│   ├── DataSchemas.md           # Database schemas
│   ├── RetrievalArchitecture.md # RAG strategies
│   ├── ToolSpecifications.md    # All AI tools
│   ├── Observability.md         # OpenTelemetry setup
│   ├── ConfigurationReference.md # Environment variables
│   ├── CommonErrors.md          # Troubleshooting
│   └── ImplementationLog.md     # Implementation history
└── lessons/                     # Course materials (L01-L10)
    └── Lxx_*/README.md          # Lesson-specific instructions
```

### Key Files to Check

- **Architecture**: `docs/Design.md` - Start here for system overview
- **Configuration**: `.env.template` files in each component
- **API Contracts**: `docs/APIReference.md`
- **Database**: `docs/DataSchemas.md`, `data/scripts/sql/`
- **Development Standards**: `AGENTS.md` (project-wide conventions)

## Configuration Management

### Unified OpenAI Configuration

All components use the same environment variables:

```env
# Required
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-5
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Azure-specific (optional)
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/
OPENAI_API_VERSION=preview
```

### PostgreSQL Configuration

Standard `PG*` environment variables:

```env
PGHOST=localhost
PGPORT=5432
PGDATABASE=aidb
PGUSER=admin
PGPASSWORD=your-password
```

### Feature Flags (DreamFarm Agent)

Key feature toggles in `.env`:

```env
# RAG & Search
ENABLE_RAG=true                  # Vector search
ENABLE_KEYWORD_SEARCH=true       # Full-text search
ENABLE_HYBRID_SEARCH=true        # Semantic + keyword fusion
GRAPH_SEARCH_ENABLED=true        # Apache AGE graph tools
SEMANTIC_CACHE_ENABLED=true      # First-turn Q&A cache

# Memory & Personalization
CONVERSATION_STORE_ENABLED=true  # Store conversations
MEMORY_SEARCH_ENABLED=true       # Semantic memory search
USER_PROFILE_ENABLED=true        # User profile management

# Tools & Integrations
FARMER_TOOLS_ENABLED=true        # MCP farmer tools
TAVILY_ENABLED=true              # Web search
CHEF_AGENT_ENABLED=true          # Multi-agent delegation
ENABLE_CODE_INTERPRETER=true     # Code execution

# Voice & Advanced
VOICE_ENABLED=true               # Realtime API
AUTH_ENABLED=true                # Keycloak JWT validation

# Observability
OTEL_SERVICE_NAME=dreamfarm-agent
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_INSTRUMENTATION_PROVIDER=openinference  # or "opentelemetry"
```

See `docs/ConfigurationReference.md` for complete reference.

## Important Development Patterns

### Pydantic Models

All request/response/internal schemas use Pydantic models in `models/` directories:

```python
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: str | None = None
```

### Service Layer Pattern

Business logic in `services/`, routes in `main.py` or `routes/`:

```python
# services/rag_service.py
class RAGService:
    async def semantic_search(self, query: str, limit: int = 5):
        # Implementation
        pass

# main.py
@app.post("/chat")
async def chat(request: ChatRequest):
    rag_service = RAGService()
    results = await rag_service.semantic_search(request.message)
```

### Unified OpenAI Client Pattern

All agents use the same initialization:

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),  # Optional for Azure
)
```

### OpenTelemetry Instrumentation

DreamFarm agent has comprehensive tracing. Two providers available:

1. **OpenInference** (current default) - Supports Responses API streaming NOW
2. **Standard OpenTelemetry** - Use when PR #3396 merges (better ecosystem support)

Configure via `OTEL_INSTRUMENTATION_PROVIDER=openinference` or `opentelemetry`.

Business dimensions automatically added: `user_id`, `is_vip`, `thread_id`, `agent_type`, `experiment`.

### Database Connections

Use standard `psycopg2` + environment variables:

```python
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv("PGHOST"),
    port=os.getenv("PGPORT"),
    database=os.getenv("PGDATABASE"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
)
```

### Apache AGE Graph Queries

Cypher queries executed via AGE SQL wrapper:

```python
cursor.execute("""
    SELECT * FROM ag_catalog.cypher('dreamfarm', $$
        MATCH (p:Producer)-[:PRODUCES]->(prod:Product)
        WHERE prod.name = $product_name
        RETURN p.name, prod.name
    $$, '{"product_name": "Organic Honey"}') as (producer agtype, product agtype);
""")
```

## Branch Structure

- **`main`** - Complete production version (all lessons done)
- **`Lxx-teacher`** - Instructor solution for lesson xx (fully functional)
- **`Lxx-student`** - Starting point for lesson xx (with TODO challenges)

When working on course materials, students start from `Lxx-student` and progress toward `Lxx-teacher`.

## Deployment

### Local Development (Docker Compose)

```bash
cd deploy/local
docker-compose up -d
```

Services: PostgreSQL (with extensions), Keycloak (optional)

### Production (Azure Kubernetes)

```bash
# 1. Infrastructure
cd deploy/azure/infrastructure
terraform init
terraform apply

# 2. Build & Push Images
cd ../docker_build
cp .env.template .env  # Configure ACR credentials
uv sync
uv run build_and_push.py

# 3. Deploy Services
cd ../../charts/demo
helm install dreamfarm . -f values.yaml

# 4. Configure Identity
cd ../../../identity
uv run provision_keycloak.py

# 5. Setup Database & Import Data
cd ../data/scripts
uv run configure_postgresql.py
uv run import_all.py  # Runs all import scripts in order
```

## Common Pitfalls & Solutions

### Embedding Dimension Mismatch

**Symptom**: `ERROR: expected 2000 dimensions, got 3072`

**Solution**: Always specify `dimensions=2000` when calling OpenAI embeddings:

```python
response = client.embeddings.create(
    model="text-embedding-3-large",
    input=texts,
    dimensions=2000  # CRITICAL for pgvector HNSW compatibility
)
```

### Apache AGE Connection Issues

**Symptom**: `ERROR: graph "dreamfarm" does not exist`

**Solution**: Run initialization script:

```bash
cd data/scripts
uv run configure_postgresql.py  # Runs sql/tables/04_init_age_graph.sql
```

### OpenTelemetry Not Tracing

**Symptom**: No traces in Grafana/Langfuse

**Solution**: Check configuration:

```env
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317  # Must be valid
OTEL_TRACES_EXPORTER=otlp                                # Not "none"
OTEL_INSTRUMENTATION_PROVIDER=openinference              # For Responses API streaming
```

For local testing: `kubectl port-forward svc/otel-collector 4317:4317`

### MCP Server Connection Failures

**Symptom**: Tool calls timing out or returning errors

**Solution**: Verify MCP server is running and accessible:

```bash
# Check server
curl -X POST https://farmer-tools.tomasdemo.org/mcp \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'

# Check .env configuration
FARMER_TOOLS_ENABLED=true
FARMER_TOOLS_MCP_URL=https://farmer-tools.tomasdemo.org/mcp
FARMER_TOOLS_MCP_API_KEY=<valid-key>
```

### Voice Mode WebSocket Disconnect

**Symptom**: Voice session disconnects immediately

**Solution**: Ensure Realtime API access and correct model:

```env
VOICE_ENABLED=true
VOICE_MODEL=gpt-4o-realtime-preview  # Must have access
```

Check browser console for WebSocket errors.

## Documentation Philosophy (AGENTS.md)

The project follows strict documentation standards defined in `AGENTS.md`:

1. **Docstrings First** - Update docstrings when code changes
2. **No Progress Comments** - Never add inline progress/migration notes
3. **Controlled Documentation** - Update `docs/ImplementationLog.md` for decisions, `docs/CommonErrors.md` only after user confirmation
4. **Tests Over Scripts** - Validate via `pytest`, not throwaway scripts
5. **Ad-Hoc Naming** - Temporary scripts must be prefixed `adhoc_` and deleted after use

## Technology Stack Summary

| Layer | Technology |
|-------|-----------|
| Backend Language | Python 3.11+ |
| Package Manager | **uv** (NOT pip) |
| API Framework | FastAPI |
| Data Validation | Pydantic |
| LLM | OpenAI API / Azure OpenAI (unified client) |
| Embeddings | text-embedding-3-large (2000 dims) |
| Database | PostgreSQL 16 |
| Vector Search | pgvector (HNSW indexes) |
| Graph Database | Apache AGE (Cypher queries) |
| Full-Text Search | PostgreSQL GIN indexes |
| Frontend | React 18 + TypeScript |
| UI Components | assistant-ui, Tailwind CSS |
| Build Tool | Vite |
| Authentication | Keycloak (OAuth2/OIDC) |
| Observability | OpenTelemetry + Grafana Tempo + Langfuse |
| Workflow Engine | Temporal |
| Tool Protocol | MCP (Model Context Protocol) |
| Containerization | Docker + Docker Compose |
| Orchestration | Kubernetes (Azure AKS) |
| IaC | Terraform (azurerm + azapi) |
| CI/CD | GitHub Actions |

## Quick Reference: Common Tasks

### Adding a New Agent Endpoint

1. Define Pydantic models in `src/models/`
2. Implement service logic in `src/services/`
3. Add route in `src/main.py`
4. Write tests in `tests/test_*.py`
5. Update `docs/APIReference.md`

### Adding a New RAG Tool

1. Implement tool function in agent's `services/` directory
2. Add tool definition to Responses API tool list
3. Update `docs/ToolSpecifications.md`
4. Write unit tests with mocks (`@pytest.mark.unit`)
5. Write integration tests (`@pytest.mark.integration`)

### Modifying Database Schema

1. Create SQL migration in `data/scripts/sql/tables/`
2. Update `configure_postgresql.py` to run migration
3. Update `docs/DataSchemas.md`
4. Update import scripts if needed
5. Run tests to verify

### Adding a New Feature Flag

1. Add environment variable to `.env.template`
2. Document in `docs/ConfigurationReference.md`
3. Load in agent's config/settings
4. Add conditional logic in relevant services
5. Update README with feature description

### Debugging LLM Calls

1. Enable OpenTelemetry tracing (see above)
2. Check Grafana: https://grafana.dreamfarm.tomasdemo.org
3. Filter by `user_id`, `thread_id`, or `experiment`
4. Inspect spans for token counts, latency, prompts
5. For local: `kubectl port-forward svc/otel-collector 4317:4317`

## Links to Key Documentation

- **Architecture**: [`docs/Design.md`](docs/Design.md)
- **API Reference**: [`docs/APIReference.md`](docs/APIReference.md)
- **Database Schemas**: [`docs/DataSchemas.md`](docs/DataSchemas.md)
- **Retrieval Architecture**: [`docs/RetrievalArchitecture.md`](docs/RetrievalArchitecture.md)
- **Tool Specifications**: [`docs/ToolSpecifications.md`](docs/ToolSpecifications.md)
- **Observability**: [`docs/Observability.md`](docs/Observability.md)
- **Configuration**: [`docs/ConfigurationReference.md`](docs/ConfigurationReference.md)
- **Troubleshooting**: [`docs/CommonErrors.md`](docs/CommonErrors.md)
- **Development Standards**: [`AGENTS.md`](AGENTS.md)
- **Main README**: [`README.md`](README.md)

---

**Note**: This is a comprehensive course project with 10 lessons. Each lesson builds incrementally. Check individual `lessons/Lxx_*/README.md` files for lesson-specific instructions and objectives.

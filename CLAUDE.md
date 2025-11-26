# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a course repository for **Advanced AI Applications** - a 10-lesson intensive course teaching production-grade AI application development. The codebase implements **Dream Farm**, a virtual farmer marketplace with AI assistant capabilities including RAG, multi-agent systems, workflow orchestration, and enterprise features.

The repository uses a **lesson-based branching strategy**:
- `main` - Complete production implementation
- `Lxx-teacher` - Full solution for lesson xx
- `Lxx-student` - Starting point with TODO challenges for lesson xx

## Project Structure

- `agents/` - AI agents (DreamFarm Agent, Chef Agent) implemented as FastAPI backends
- `data/` - Database schemas, data ingestion pipelines, import scripts
- `frontend/` - React UI with @assistant-ui components
- `tools/` - MCP servers (farmer tools, visualization, stock API)
- `deploy/` - Kubernetes Helm charts, Docker configs, Terraform IaC
- `orchestration/` - Temporal workflow definitions
- `lessons/` - Lesson-specific materials and exercises
- `identity/` - Keycloak provisioning scripts
- `docs/` - Complete architecture and API documentation

## Technology Stack

### Backend (Python)
- **Package Manager**: `uv` (NEVER use pip)
- **Framework**: FastAPI with uvicorn
- **Python Version**: 3.12+
- **Dependencies**: Managed via `pyproject.toml` (no `requirements.txt`)

### Database
- **Primary**: PostgreSQL with extensions:
  - `pgvector` - Vector embeddings for semantic search
  - `Apache AGE` - Graph database for knowledge graphs
  - Full-text search with GIN indexes

### Frontend
- **Framework**: React + TypeScript
- **UI Components**: @assistant-ui/react
- **Build Tool**: Vite
- **Styling**: Tailwind CSS

### AI/LLM
- **Platforms**: Azure OpenAI and OpenAI Platform (switchable via env config)
- **Models**: GPT-5 (chat/reasoning), text-embedding-3-large (embeddings)
- **APIs**: Responses API, Realtime API (voice)
- **Orchestration**: Temporal for durable workflows

## Development Commands

### Backend (Agents & Services)

All Python services use `uv` for dependency management:

```bash
# Setup virtual environment and install dependencies
uv sync

# Run DreamFarm agent
cd agents/dreamfarm-agent/src
uv run main.py
# Runs on http://localhost:8001

# Run Chef agent
cd agents/chef-agent/src
uv run main.py
# Runs on http://localhost:8002

# Run Stock API tool
cd tools/api_stock
uv run main.py
# Runs on http://localhost:8011

# Run MCP servers
cd tools/mcp_public_farmer_tools
uv run python main.py
# Runs on http://localhost:8012

cd tools/mcp_visualization_generator
uv run python main.py
# Runs on http://localhost:8013
```

### Testing

The project uses pytest with two test categories (configured via markers):

```bash
# Run unit tests only (fast, mocked dependencies) - DEFAULT
cd agents/dreamfarm-agent
uv run pytest -m unit -v

# Run integration tests (requires database + API keys)
uv run pytest -m integration -v

# Run all tests
uv run pytest -m "unit or integration" -v

# Run specific test file
uv run pytest tests/test_rag_service.py -v

# Run with coverage
uv run pytest --cov=src --cov-report=html
```

**Important**: Tests auto-load `.env` file. Integration tests self-skip if required infrastructure is unavailable.

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
# Runs on http://localhost:5173

# Build for production
npm run build

# Lint
npm run lint
```

### Database

```bash
# Start local PostgreSQL with extensions
cd deploy/local
docker-compose up -d
# PostgreSQL on localhost:5432, Keycloak on localhost:8080

# Configure database (install extensions, create schemas)
cd data/scripts
uv run configure_postgresql.py

# Import all data
uv run import_all.py

# Import specific datasets
uv run import_simple_products.py
uv run import_documents.py
```

### Data Pipeline Scripts

```bash
cd data/scripts

# Generate sample data
uv run gen_basic_data.py

# Process documents (PDF, images, videos)
uv run process_document.py <file_path>
uv run process_video.py <file_path>

# Create embeddings from CSV
uv run prepare_simple_products.py
```

### Temporal Orchestration

```bash
# Start Temporal dev server (separate terminal)
temporal server start-dev
# Web UI: http://localhost:8233

# Run complaint workflow demo
cd orchestration/complaint_workflow
uv run python demo.py

# Run production worker
uv run python worker.py
```

### Terraform Infrastructure

```bash
cd deploy/azure/infrastructure

# Initialize Terraform
terraform init

# Plan infrastructure changes
terraform plan

# Apply infrastructure
terraform apply

# Deploy to Azure
cd deploy/azure/docker_build
uv run build_and_push.py

cd deploy/charts/demo
helm install dreamfarm .
```

## Configuration

### Environment Variables

All services use a unified `.env` file at the repository root. Key variables:

```bash
# OpenAI Configuration (works for both Azure and OpenAI Platform)
OPENAI_API_KEY=<your-key>
OPENAI_MODEL=gpt-5
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# For Azure OpenAI, add:
OPENAI_BASE_URL=https://<resource>.openai.azure.com/openai/v1/
OPENAI_API_VERSION=preview

# PostgreSQL (standard PG env vars)
PGHOST=localhost
PGPORT=5432
PGDATABASE=aidb
PGUSER=admin
PGPASSWORD=<password>

# Keycloak (for auth features)
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=admin

# Feature Flags (in agent .env)
RAG_ENABLED=true
TOOLS_ENABLED=true
MEMORY_ENABLED=true
VOICE_ENABLED=true
```

**Note**: Switching between Azure OpenAI and OpenAI Platform only requires changing `OPENAI_BASE_URL` and `OPENAI_API_KEY`.

## Architecture Notes

### Agent Backend Structure

The main agent is a **monolithic FastAPI application** (`agents/dreamfarm-agent/src/main.py`) that includes:
- REST endpoints: `/chat`, `/threads`, `/files`, `/voice`, `/artifacts`
- RAG with hybrid retrieval (semantic + keyword + graph)
- Tool orchestration (MCP servers + function calling)
- Memory injection (personalization)
- Semantic caching
- Feature flags for incremental capabilities

### Multi-Agent Communication

- **Pattern**: Agent-as-Tool (one agent calls another via HTTP)
- **Protocol**: MCP for external tools, REST for inter-agent communication
- Example: DreamFarm Agent calls Chef Agent for catering services

### Data Flow

1. **Ingestion**: Raw data (JSON, PDFs, images, videos) → Processing scripts → Structured DB + embeddings
2. **Retrieval**: User query → Embeddings → Hybrid search (semantic + keyword + graph) → Top-k documents
3. **Generation**: Context + user query → LLM → Response with citations
4. **Streaming**: Server-Sent Events with `DF_META` metadata for transparency

### Testing Strategy

```
        E2E Tests (Manual/Automated Browser)
       /                                    \
      /         Integration Tests           \
     /      (FastAPI TestClient + pytest)   \
    /__________Unit Tests (Mocked)_________\
```

- **Unit tests**: Mocked OpenAI/DB, fast, isolated
- **Integration tests**: Real services, marked with `@pytest.mark.integration`
- Configured in `pytest.ini` with default marker filtering

### Documentation Organization

Architecture is documented across specialized files:
- `docs/Design.md` - High-level system architecture
- `docs/DataSchemas.md` - Database schemas and indexes
- `docs/APIReference.md` - REST/WebSocket API specs
- `docs/RetrievalArchitecture.md` - RAG and hybrid search
- `docs/ToolSpecifications.md` - All AI tools and MCP servers
- `docs/Observability.md` - OpenTelemetry tracing
- `docs/ImplementationLog.md` - Implementation decisions
- `docs/CommonErrors.md` - Troubleshooting guide

### External Reference Documentation

When answering questions about Temporal workflows, activities, or orchestration:
- Reference `docs/temporal-docs.txt` - Complete Temporal documentation (from https://docs.temporal.io/llms-full.txt)
- This file contains comprehensive guidance on workflow patterns, activities, testing, versioning, and best practices
- Use this documentation to provide accurate, official answers about Temporal features and implementation details

## Important Development Practices

### Code Organization (from AGENTS.md)

1. **Documentation via Docstrings**: Every public class/function must have docstrings (purpose, params, returns, exceptions)
2. **No Progress Comments**: Never use inline comments for implementation history or "TODO" notes - use `docs/ImplementationLog.md`
3. **Ad-Hoc Scripts**: Name throwaway test scripts `adhoc_test_*.py` or `adhoc_*.py` - delete after insights integrated
4. **Logging**: Use Python `logging` module with appropriate levels, never `print()` in production
5. **Pydantic Models**: Use for all request/response validation, place in `models/` subdirectories

### Testing Hygiene

- Write tests when adding new features or fixing bugs
- Use mocks for unit tests (OpenAI, DB connections)
- Mark integration tests with `@pytest.mark.integration`
- Tests must be runnable from service root with `uv run pytest`

### Terraform Practices

- Use `azurerm` for standard resources, `azapi` for preview features
- Segment by resource type: `networking.tf`, `service_bus.tf`, etc.
- Always include rich variable descriptions with examples
- No progress comments or change logs in `.tf` files

### Feature Flags

The agent uses environment-based feature flags (see `docs/ConfigurationReference.md`):
- Each capability can be toggled independently
- Flags control: RAG, tools, memory, voice, caching, VIP filtering
- Check flags before assuming features are enabled

## Common Workflows

### Starting from a Lesson Branch

```bash
# Check out student branch for lesson
git checkout L01-student

# Start infrastructure
cd deploy/local
docker-compose up -d

# Configure and import data
cd ../../data/scripts
uv run configure_postgresql.py
uv run import_simple_products.py

# Run agent
cd ../../agents/dreamfarm-agent/src
uv run main.py

# Run frontend (separate terminal)
cd ../../../frontend
npm run dev
```

### Adding a New Tool

1. Create tool in `tools/<tool-name>/`
2. Implement with FastMCP or FastAPI
3. Add to agent's tool registry in `main.py`
4. Document in `docs/ToolSpecifications.md`
5. Add tests (unit + integration)

### Processing New Data

1. Add source data to `data/source_json/` or `data/user_upload/`
2. Create processing script in `data/scripts/`
3. Generate embeddings with OpenAI API
4. Store in PostgreSQL with pgvector
5. Update relevant indexes (FTS, graph)

### Deploying to Azure

1. Provision infrastructure: `terraform apply` in `deploy/azure/infrastructure/`
2. Build and push containers: `uv run build_and_push.py` in `deploy/azure/docker_build/`
3. Deploy with Helm: `helm install dreamfarm .` in `deploy/charts/demo/`
4. Configure Keycloak: `uv run identity/provision_keycloak.py`
5. Initialize database: `uv run data/scripts/configure_postgresql.py`
6. Import data: `uv run data/scripts/import_all.py`

## Ports Reference

- **5173**: Frontend (Vite dev server)
- **8001**: DreamFarm Agent
- **8002**: Chef Agent
- **8011**: Stock API
- **8012**: MCP Farmer Tools
- **8013**: MCP Visualization Generator
- **5432**: PostgreSQL
- **8080**: Keycloak
- **8233**: Temporal Web UI

## Notes

- This is a **teaching repository** - code prioritizes clarity and learning over production optimization
- **ALWAYS use `uv`** for Python dependency management, never pip
- The project supports both Azure OpenAI and OpenAI Platform with the same codebase
- Most agents are single-file FastAPI apps (`main.py`) for simplicity
- See individual lesson READMEs for specific learning objectives and challenges
- The `samples/` folder (if present) contains reference code - not part of the main solution
- Check `AGENTS.md` for detailed agent development guidelines and conventions

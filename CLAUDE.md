# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Advanced AI Applications is a production-grade AI platform demonstrating a virtual farmers marketplace (Dream Farm) that connects farmers with customers through an AI assistant. The project serves as the foundation for a 10-lesson course on building production AI applications. Features include RAG, multi-agent systems, knowledge graphs, voice interaction, workflow orchestration, MCP tools integration, and enterprise-grade deployment.

**Repository Branch Structure:**
- `Lxx-teacher` - Complete implementation for instructor demonstrations
- `Lxx-student` - Starting point with challenges for students
- `main` - Full production version with all features and CI/CD

## High-Level Architecture

The platform consists of three main layers:

1. **Frontend Layer**: React + TypeScript with assistant-ui components, Vite build system
2. **Agent Layer**: Python FastAPI backends (DreamFarm agent, Chef agent) with OpenAI GPT-5 integration
3. **Data Layer**: PostgreSQL with pgvector (embeddings), full-text search, Apache AGE (knowledge graph)

**Key Integrations:**
- MCP (Model Context Protocol) servers for external tools (farmer tools, web search, stock API)
- OpenAI Responses API for streaming, tool use, and reasoning
- Temporal for workflow orchestration
- Keycloak for authentication
- OpenTelemetry for observability

## Common Commands

### Local Development Setup

**Prerequisites:**
- Docker & Docker Compose
- Python 3.11+ with `uv` package manager
- Node.js 18+
- OpenAI or Azure OpenAI API credentials

**Initial Setup:**

```bash
# 1. Start infrastructure (PostgreSQL + Stock API)
cd deploy/local
export DOCKER_DEFAULT_PLATFORM=linux/amd64
docker compose up -d postgres api-stock

# 2. Configure database and import data
cd ../../data/scripts
uv sync
uv run configure_postgresql.py
uv run import_simple_products.py
uv run import_stock.py

# 3. Start DreamFarm agent
cd ../../agents/dreamfarm-agent
uv sync
uv run dreamfarm-agent
# Default port: 8001 (uvicorn with --reload)

# 4. Start frontend
cd ../../frontend
npm install
npm run dev
# Access at http://localhost:3000
```

### Running Tests

**Python Tests (pytest):**
```bash
# Run all tests in an agent
cd agents/dreamfarm-agent
uv run pytest

# Run specific test file
uv run pytest tests/test_rag_service.py

# Run specific test function
uv run pytest tests/test_rag_service.py::test_search_products

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=src
```

**Frontend Tests:**
```bash
cd frontend
npm run lint
npm run build  # Type checking via tsc
```

### Data Pipeline

```bash
cd data/scripts

# Generate sample data (producers, products, stock)
uv run gen_basic_data.py

# Generate embeddings for products
uv run embeddings_simple_products.py

# Import processed data into PostgreSQL
uv run import_simple_products.py
uv run import_stock.py
```

### Docker Operations

```bash
# Start all services
cd deploy/local
docker compose up -d

# View logs
docker compose logs -f postgres
docker compose logs -f api-stock

# Stop services
docker compose down

# Restart specific service
docker compose restart postgres
```

### Kubernetes Deployment (Production)

```bash
# 1. Deploy infrastructure
cd deploy/azure/infrastructure
terraform init
terraform plan
terraform apply

# 2. Build and push containers
cd ../docker_build
uv run build_and_push.py

# 3. Deploy with Helm
cd ../../kubernetes
helm install dreamfarm ./charts/dreamfarm

# 4. Get ingress URL
kubectl get ingress
```

## Architecture Highlights

### Python Agent Structure

Agents follow FastAPI service-oriented architecture:

```
agents/dreamfarm-agent/
├── src/
│   ├── main.py              # FastAPI app entry point
│   ├── routes/              # API route handlers
│   │   ├── chat_routes.py   # Chat endpoints
│   │   └── thread_routes.py # Thread management
│   ├── services/            # Business logic
│   │   ├── openai_service.py    # LLM integration
│   │   ├── rag_service.py       # Retrieval logic
│   │   ├── template_service.py  # Prompt templating
│   │   └── thread_service.py    # Thread persistence
│   ├── models/              # Pydantic data models
│   ├── config/              # Configuration management
│   └── utils/               # Helper utilities
└── tests/                   # pytest test suite
```

**Key Design Patterns:**
- Service layer isolates business logic from routes
- Pydantic models for all request/response validation
- Template system (Jinja2) for prompts in `prompts/` directory
- Feature flags control tool availability (RAG, MCP, Tavily, etc.)

### RAG Implementation

Hybrid retrieval combining three approaches:
1. **Semantic search**: pgvector cosine similarity on 2000-dimensional embeddings
2. **Keyword search**: PostgreSQL full-text search with tsvector
3. **Graph traversal**: Apache AGE for knowledge graph queries

All retrieval happens via `RAGService` which:
- Generates query embeddings using OpenAI text-embedding-3-large
- Executes similarity search with configurable thresholds
- Returns grounded results to prevent hallucination
- Includes metadata for explainability (DF_META events)

### Tool Integration

Three types of tools:
1. **MCP Tools**: External services via Model Context Protocol (e.g., farmer tools at cloud endpoint)
2. **Function Tools**: Local REST APIs (e.g., stock API at localhost:8011)
3. **Web Search**: Tavily integration for internet queries

Tool definitions are registered in `OpenAIService.get_tools()` based on feature flags in `.env`.

### Frontend Architecture

React with assistant-ui library providing:
- Streaming chat interface with SSE (Server-Sent Events)
- File upload for multimodal inputs
- Voice capture for hands-free mode
- Custom UI components for tool call visualization
- Tailwind CSS for styling

Key files:
- `src/App.tsx` - Main app component
- `src/lib/chatApi.ts` - Backend API integration
- `src/components/` - Reusable UI components

## Environment Configuration

Agents use `.env` files with these critical variables:

**OpenAI Configuration:**
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
```

**Database:**
```env
PGHOST=localhost
PGPORT=5432
PGDATABASE=aidb
PGUSER=admin
PGPASSWORD=Admin12345678
```

**Feature Flags:**
```env
ENABLE_RAG=true
STOCK_TOOL_ENABLED=true
FARMER_TOOLS_ENABLED=true
TAVILY_ENABLED=true
```

**Tool Endpoints:**
```env
STOCK_API_URL=http://localhost:8011
FARMER_TOOLS_MCP_URL=https://farmer-tools.tomasdemo.org/mcp/
TAVILY_API_KEY=tvly-...
```

See `.env.template` files in each component directory for full reference.

## Data Flow

**User Query → Agent Processing:**
1. Frontend sends query to `/chat` endpoint
2. Agent processes via OpenAIService using Responses API
3. If RAG enabled: RAGService retrieves relevant products
4. If tools called: Agent executes function/MCP calls
5. Response streamed back to frontend via SSE
6. UI displays messages with metadata (DF_META events)

**Data Import Pipeline:**
```
gen_basic_data.py → JSON files
    ↓
embeddings_simple_products.py → Parquet with vectors
    ↓
configure_postgresql.py → Database schema
    ↓
import_simple_products.py → Populated tables
```

## Key Documentation Files

- [Design.md](docs/Design.md) - Complete architecture overview
- [APIReference.md](docs/APIReference.md) - REST and WebSocket specs
- [DataSchemas.md](docs/DataSchemas.md) - Database tables and indexes
- [RetrievalArchitecture.md](docs/RetrievalArchitecture.md) - RAG implementation details
- [ToolSpecifications.md](docs/ToolSpecifications.md) - All tool definitions
- [AGENTS.md](AGENTS.md) - Agent development guidelines and conventions
- [CommonErrors.md](docs/CommonErrors.md) - Troubleshooting guide

## Important Conventions

From [AGENTS.md](AGENTS.md):

1. **Documentation**: Use docstrings for code documentation, not inline comments for progress/history
2. **Experiments**: Prefix disposable scripts with `adhoc_` and delete after insights are integrated
3. **Package Management**: Use `uv` for Python (never pip), `npm` for frontend
4. **Testing**: pytest for Python with unit tests (mocks) and integration tests (real DB/API)
5. **Logging**: Use Python `logging` module with appropriate levels (DEBUG/INFO/WARNING/ERROR)
6. **Port Assignments**: Each service uses distinct ports to avoid collisions
7. **Refactoring**: Encouraged for simplifications; discuss architectural changes first

## Troubleshooting

**PostgreSQL connection errors:**
- Verify container is running: `docker compose ps`
- Check `.env` database credentials match docker-compose.yml
- Ensure pgvector extension is installed: Run `configure_postgresql.py`

**Embedding dimension errors:**
- Embeddings must be exactly 2000 dimensions
- Check OpenAI API configuration includes `dimensions=2000`

**MCP tool errors:**
- Verify MCP server URL is accessible from agent
- Check API key is correctly set in `.env`
- Review agent logs for connection details

**Import failures:**
- Run scripts in order: configure → embeddings → import
- Check data files exist in `data/source_json/` and `data/processed/`

## Lesson-Specific Notes

Each lesson builds incrementally:
- **L01**: Basic RAG chatbot with semantic search
- **L02**: Tool integration (MCP, web search, stock API)
- **L03**: Multi-format ingestion (docs, images, videos), hybrid search
- **L04**: Agentic search, knowledge graph, authentication
- **L05+**: Voice, memory, code interpreter, workflows, multi-agent, security, observability

See `lessons/Lxx/README.md` for lesson-specific setup and concepts.

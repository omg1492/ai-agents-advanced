# Configuration Reference

This document provides a complete reference for all environment variables and configuration options in the Dream Farm AI platform.

> **Note**: For deployment-specific configuration, see [DeploymentGuide.md](./DeploymentGuide.md). For feature-specific details, see respective documentation files.

---

## Table of Contents

- [Quick Start Templates](#quick-start-templates)
- [Core LLM Configuration](#core-llm-configuration)
- [Database Configuration](#database-configuration)
- [Retrieval & Search](#retrieval--search)
- [Memory & Personalization](#memory--personalization)
- [Voice & Realtime](#voice--realtime)
- [Knowledge Graph](#knowledge-graph)
- [Authentication & Security](#authentication--security)
- [Tool Integration](#tool-integration)
- [Code Execution](#code-execution)
- [Observability](#observability)
- [Development & Debugging](#development--debugging)

---

## Quick Start Templates

### Minimal Development Configuration (.env)

```bash
# Core LLM (OpenAI)
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-5
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Database
PGHOST=localhost
PGPORT=5432
PGDATABASE=aidb
PGUSER=admin
PGPASSWORD=your-password

# Basic Features
ENABLE_RAG=true
AGENTIC_SEARCH_ENABLED=true
CONVERSATION_STORE_ENABLED=true
AUTH_ENABLED=false

# CORS
CORS_ORIGINS=http://localhost:3000
```

### Full Production Configuration (.env)

```bash
# Core LLM (Azure OpenAI)
OPENAI_API_KEY=your-azure-api-key
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/
OPENAI_API_VERSION=preview
OPENAI_MODEL=your-azure-deployment-name
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Database
PGHOST=your-postgres-server.postgres.database.azure.com
PGPORT=5432
PGDATABASE=aidb
PGUSER=admin
PGPASSWORD=your-secure-password

# Retrieval Features
ENABLE_RAG=true
RAG_SIMILARITY_THRESHOLD=0.3
RAG_MAX_RESULTS=3
AGENTIC_SEARCH_ENABLED=true
AGENTIC_SEARCH_MAX_RESULTS=10

# Graph Search
GRAPH_SEARCH_ENABLED=true
AGE_GRAPH_NAME=dreamfarm
GRAPH_DFS_MAX_RESULTS=10

# Memory & Personalization
CONVERSATION_STORE_ENABLED=true
MEMORY_SEARCH_ENABLED=true
USER_PROFILE_ENABLED=true
MEMORY_CONVERSATION_RETENTION_DAYS=7
USER_PROFILE_MAX_TOKENS=500

# Semantic Cache
SEMANTIC_CACHE_ENABLED=true
SEMANTIC_CACHE_SIMILARITY_THRESHOLD=0.8

# Voice
VOICE_ENABLED=true
VOICE_MODEL=gpt-4o-realtime-preview

# Authentication
AUTH_ENABLED=true
KEYCLOAK_URL=https://keycloak.yourdomain.com
KEYCLOAK_REALM=dreamfarm
KEYCLOAK_AUDIENCE=account

# MCP Tools
FARMER_TOOLS_ENABLED=true
TAVILY_ENABLED=true
TAVILY_API_KEY=your-tavily-key

# Stock API
STOCK_TOOL_ENABLED=true
STOCK_API_URL=http://api-stock:8011

# Multi-Agent
CHEF_AGENT_ENABLED=true
CHEF_AGENT_URL=http://chef-agent:8002

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=dreamfarm-agent

# CORS
CORS_ORIGINS=https://yourdomain.com

# Logging
LOG_LEVEL=INFO
```

---

## Core LLM Configuration

### OpenAI Provider

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | ✅ Yes | - | OpenAI or Azure OpenAI API key |
| `OPENAI_MODEL` | ✅ Yes | gpt-5 | Model name (OpenAI) or deployment name (Azure) |
| `OPENAI_BASE_URL` | Azure only | - | Azure OpenAI endpoint: `https://<resource>.openai.azure.com/openai/v1/` |
| `OPENAI_API_VERSION` | Azure only | preview | Azure API version (e.g., `2025-04-01-preview`) |
| `OPENAI_EMBEDDING_MODEL` | ✅ Yes | text-embedding-3-large | Embedding model for vectors |

**Notes:**
- For **OpenAI**: Only set `OPENAI_API_KEY` and `OPENAI_MODEL`
- For **Azure OpenAI**: Set all four variables (KEY, MODEL, BASE_URL, API_VERSION)
- The same client abstraction works for both providers seamlessly

**Example (OpenAI):**
```bash
OPENAI_API_KEY=sk-proj-xxx
OPENAI_MODEL=gpt-5
```

**Example (Azure OpenAI):**
```bash
OPENAI_API_KEY=abc123...
OPENAI_BASE_URL=https://my-resource.openai.azure.com/openai/v1/
OPENAI_API_VERSION=preview
OPENAI_MODEL=gpt-5-deployment
```

---

## Database Configuration

### PostgreSQL Connection

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PGHOST` | ✅ Yes | localhost | PostgreSQL server hostname |
| `PGPORT` | No | 5432 | PostgreSQL server port |
| `PGDATABASE` | ✅ Yes | aidb | Database name |
| `PGUSER` | ✅ Yes | admin | Database user |
| `PGPASSWORD` | ✅ Yes | - | Database password |

**Notes:**
- Requires PostgreSQL with extensions: pgvector, Apache AGE, fuzzystrmatch
- Connection pooling handled by psycopg2 or SQLAlchemy
- SSL mode can be configured via connection string if needed

---

## Retrieval & Search

### Basic RAG (Retrieval-Augmented Generation)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_RAG` | No | true | Enable semantic vector search |
| `RAG_SIMILARITY_THRESHOLD` | No | 0.3 | Minimum cosine similarity (0.0-1.0, higher = stricter) |
| `RAG_MAX_RESULTS` | No | 3 | Maximum products to retrieve for RAG context |

**Usage:**
- When enabled, injects `<relevant_products>` block into prompt
- Threshold controls quality vs. recall tradeoff
- Max results controls context size

See [RetrievalArchitecture.md#simple-semantic-rag](./RetrievalArchitecture.md) for details.

---

### Agentic Search (Tool-Based Retrieval)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AGENTIC_SEARCH_ENABLED` | No | true | Enable function-call based search tools |
| `AGENTIC_SEARCH_MAX_RESULTS` | No | 10 | Max results per tool call |

**Tools Enabled:**
- `semantic_search(text)` - Vector similarity
- `keyword_search(keywords[])` - Full-text search

**Notes:**
- Model orchestrates multiple tool calls and integrates results
- VIP fencing enforced at SQL layer for each tool
- Replaces backend hybrid fusion when enabled

See [ToolSpecifications.md#internal-function-tools](./ToolSpecifications.md) for tool specs.

---

### Semantic Cache

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SEMANTIC_CACHE_ENABLED` | No | true | Enable first-turn question cache |
| `SEMANTIC_CACHE_SIMILARITY_THRESHOLD` | No | 0.8 | High similarity threshold (≥0.80-0.95) |

**Usage:**
- Only applies to first user message in conversation
- Bypasses LLM call on cache hit
- Answers must be generic and time-insensitive

See [RetrievalArchitecture.md#semantic-caching](./RetrievalArchitecture.md) for details.

---

## Memory & Personalization

### Conversation Storage

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CONVERSATION_STORE_ENABLED` | No | true | Persist conversations to database |
| `MEMORY_CONVERSATION_RETENTION_DAYS` | No | 7 | Days to retain raw conversation logs |

**Storage:**
- Raw conversations in `conversations_raw` table (JSONB messages array)
- Auto-deletion after retention period expires
- Summaries retained indefinitely unless separate retention configured

---

### Memory Search

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MEMORY_SEARCH_ENABLED` | No | true | Enable semantic memory recall |
| `MEMORY_SUMMARY_RETENTION_DAYS` | No | unlimited | Days to retain conversation summaries |

**Features:**
- `memory_search(query, k)` tool available to LLM
- Vector similarity over user's own conversation summaries
- Hard user_id constraint (no cross-user leakage)

---

### User Profiles

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `USER_PROFILE_ENABLED` | No | true | Enable user profile management |
| `USER_PROFILE_MAX_TOKENS` | No | 500 | Max tokens for `<user_profile>` block in prompt |
| `MEMORY_AUDIT_ENABLED` | No | false | Track profile changes in audit table |

**Features:**
- `memory_write_profile(patch)` tool for incremental updates
- Structured profile fields: diet, allergens, liked_products, goals, notes
- Token budget with smart field priority (drop low-priority fields if over limit)

See [MemoryPersonalization.md](./MemoryPersonalization.md) for complete specification.

---

## Voice & Realtime

### Voice Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VOICE_ENABLED` | No | false | Enable voice/realtime API |
| `VOICE_MODEL` | No | gpt-4o-realtime-preview | Realtime model (OpenAI) or deployment (Azure) |

**Features:**
- WebSocket endpoint: `/voice/{thread_id}`
- Bidirectional PCM16 audio (24kHz, mono)
- Server-side VAD (voice activity detection)
- Turn detection and interruption support
- Transcripts persisted, audio ephemeral

**Tool Restrictions:**
- Minimal tool set for low latency: `memory_search` + optional lightweight product search
- Heavy graph tools excluded by default

**Azure Nuances:**
- Omit unsupported session fields (e.g., `output_modalities`)
- Client code auto-detects provider

See [VoiceInteraction.md](./VoiceInteraction.md) for architecture details.

---

## Knowledge Graph

### Apache AGE Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GRAPH_SEARCH_ENABLED` | No | false | Enable graph traversal tools |
| `AGE_GRAPH_NAME` | No | dreamfarm | Apache AGE graph name |
| `GRAPH_DFS_MAX_RESULTS` | No | 10 | Max similar products in DFS search |

**Tools Enabled:**
- `graph_bfs_taxonomy_search` - Breadth-first concept expansion
- `graph_dfs_similarity_search` - Depth-first trait overlap

---

### BFS Taxonomy Search Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GRAPH_BFS_CONCEPT_TOP_K_PER_TYPE` | No | 5 | Max semantic matches per concept type |
| `GRAPH_BFS_MIN_SIMILARITY` | No | 0.75 | Min similarity to accept concept |
| `GRAPH_BFS_GLOBAL_MAX_CONCEPTS` | No | 15 | Absolute cap after merging types |
| `GRAPH_BFS_TYPE_WEIGHTS` | No | `{"category":1.0,"cuisine":1.0,"certification":0.6,"allergen":0.5}` | JSON map of concept type weights |
| `GRAPH_BFS_NEGATIVE_ENFORCE` | No | true | Exclude products violating negative constraints |
| `GRAPH_BFS_NEGATIVE_PENALTY` | No | 0.8 | Soft penalty for constraint violations |
| `GRAPH_BFS_PRODUCT_DIVERSITY_PENALTY` | No | 0.15 | Penalize concept overrepresentation |
| `GRAPH_BFS_SCORE_NORMALIZE` | No | true | Normalize final product scores to 0..1 |

See [KnowledgeGraph.md#bfs-configuration](./KnowledgeGraph.md) for algorithm details.

---

### Taxonomy Generation Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TAXONOMY_CATEGORY_TARGET` | No | 50 | Target number of categories |
| `TAXONOMY_CUISINE_TARGET` | No | 20 | Target number of cuisines |
| `TAXONOMY_MIN_CONFIDENCE` | No | 0.55 | Minimum confidence for assignment |
| `TAXONOMY_MODEL` | No | (main model) | LLM model for taxonomy generation |
| `TAXONOMY_BATCH_SIZE` | No | 50 | Products per classification batch |
| `TAXONOMY_VERSION` | No | v1 | Artifact version tag |

**Usage:**
- Used by `data/scripts/` taxonomy generation pipelines
- Not runtime agent configuration
- Controls offline ETL processes

See [DataSchemas.md#taxonomy-enrichment](./DataSchemas.md) for details.

---

## Authentication & Security

### Keycloak (OIDC)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AUTH_ENABLED` | No | false | Enable JWT authentication |
| `KEYCLOAK_URL` | If auth enabled | - | Keycloak server URL (e.g., `http://localhost:8080`) |
| `KEYCLOAK_REALM` | If auth enabled | dreamfarm | Realm name |
| `KEYCLOAK_AUDIENCE` | If auth enabled | account | Expected audience in JWT |

**Security Model:**
- JWT verification middleware (issuer, audience, signature)
- `user_id` extracted from `sub` claim
- VIP status from role membership or `is_vip` claim
- All endpoints protected except `/health` when auth enabled

See [SecurityModel.md](./SecurityModel.md) for complete security architecture.

---

### VIP Fencing

No explicit configuration variables. VIP enforcement is:
- Implicit via user JWT claims (role membership)
- Enforced at SQL query layer for all retrieval tools
- Never delegated to LLM filtering

**SQL Pattern:**
```sql
WHERE (is_vip = false OR :user_is_vip = true)
```

---

## Tool Integration

### MCP Servers

#### Farmer Tools (Utility MCP)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FARMER_TOOLS_ENABLED` | No | true | Enable public farmer utility tools |
| `FARMER_TOOLS_MCP_URL` | No | (local stdio) | MCP server URL for remote deployment |
| `FARMER_TOOLS_MCP_API_KEY` | No | - | API key for remote MCP server |

**Tools:** `get_current_time`, `get_seasonal_tips`, `get_weather` (mocked data)

---

#### Visualization Generator (MCP)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VISUALIZATION_MCP_ENABLED` | No | false | Enable custom HTML visualization generator |
| `VISUALIZATION_MCP_URL` | If enabled | - | MCP server URL |
| `VISUALIZATION_MCP_API_KEY` | No | - | API key |
| `UI_GENERATOR_MODEL` | No | gpt-4o | Model for HTML generation |
| `HTML_SANITIZER_STRICT` | No | true | Strict HTML sanitization |
| `MAX_CUSTOM_UI_SIZE_KB` | No | 200 | Max artifact size in KB |

**Tool:** `generate_infographic` - Dynamic HTML dashboard/card generation

---

#### Tavily Web Search (Remote MCP SaaS)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TAVILY_ENABLED` | No | false | Enable Tavily web search |
| `TAVILY_API_KEY` | If enabled | - | Tavily API key |

**Tools:** `tavily-search`, `tavily-extract`

**Note:** Disabled by default to keep flows deterministic. Enable for real-time web augmentation.

---

### Stock API

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `STOCK_TOOL_ENABLED` | No | true | Enable stock quantity lookup tool |
| `STOCK_API_URL` | No | http://localhost:8011 | Stock API service URL |

**Tool:** `get_stock(productIds[])` - Returns current stock levels

---

### Multi-Agent (Chef Agent)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CHEF_AGENT_ENABLED` | No | false | Enable Chef Agent delegation |
| `CHEF_AGENT_URL` | If enabled | http://localhost:8002 | Chef Agent service URL |

**Tool:** `query_chef_services(query)` - Delegate culinary queries to Chef Agent

See [MultiAgentArchitecture.md](./MultiAgentArchitecture.md) for details.

---

## Code Execution

### Code Interpreter

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_CODE_INTERPRETER` | No | false | Enable Azure OpenAI code interpreter |
| `CODE_INTERPRETER_CONTAINER_TYPE` | No | auto | Container lifecycle management |

**Features:**
- Sandboxed Python environment for data analysis
- File upload (max 30MB): CSV, Excel, JSON, images, PDF
- Automatic chart/visualization generation
- Generated files proxied via `/files/{file_id}/content`

**Pricing Note:** Additional charges beyond token costs (per container-hour)

See [CodeExecution.md#code-interpreter](./CodeExecution.md) for details.

---

## Observability

### OpenTelemetry

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OTEL_SERVICE_NAME` | No | (varies by service) | Service name in traces (e.g., `dreamfarm-agent`, `chef-agent`, `mcp-chef-services`) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | - | OTel Collector endpoint (gRPC, e.g., `http://otel-collector:4317`). Leave empty to disable tracing. |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | No | grpc | Export protocol (grpc or http) |
| `OTEL_TRACES_EXPORTER` | No | otlp | Trace exporter type (otlp, console, none) |
| `OTEL_LOGS_EXPORTER` | No | otlp | Logs exporter type (otlp, console, none). Sends structured logs with trace correlation to Loki. |
| `OTEL_METRICS_EXPORTER` | No | otlp | Metrics exporter type (otlp, console, none). Sends application metrics to Prometheus. |
| `OTEL_EXPERIMENT` | No | production | Custom experiment/environment tag for filtering traces |
| `OTEL_RESOURCE_ATTRIBUTES` | No | - | Additional resource attributes (e.g., `experiment=production`) |

**Auto-Instrumentation:**
- FastAPI (HTTP requests, including custom metrics)
- SQLAlchemy / Psycopg2 (database)
- OpenAI SDK (LLM calls with gen_ai.* semantic conventions)
- Structured logging with trace correlation (trace_id, span_id automatically injected)

**Custom Metrics:**
- HTTP request duration and count (per service)
- LLM request count and token usage
- Cache hit rate (semantic cache)
- Active connections and session count
- Database query duration

**Business Dimensions:**
- `user_id`, `is_vip`, `thread_id`, `agent_type`, `experiment`
- Propagated through all spans via middleware

**Backends:**
- Grafana Tempo (distributed tracing)
- Loki (structured logs with trace correlation)
- Prometheus (metrics and alerting)
- Langfuse (LLM-specific analytics)

See [Observability.md](./Observability.md) for complete observability strategy.

---

### OpenAI Instrumentation Provider

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OTEL_INSTRUMENTATION_PROVIDER` | No | opentelemetry | OpenAI instrumentation provider (`opentelemetry` or `openinference`) |
| `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` | No | true | Capture full prompt/completion content in traces |

**Providers:**
- **opentelemetry**: Standard GenAI semantic conventions (ideal for Langfuse)
- **openinference**: Custom conventions with Responses API streaming support (interim solution)

---

## Development & Debugging

### Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | INFO | Python logging level (DEBUG, INFO, WARNING, ERROR) |

**Structured Logging:**
- Key-value format: `INFO search_tool=semantic_search count=5 elapsed_ms=45`
- DEBUG level includes Cypher queries (parameterized, no sensitive data)

---

### CORS

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CORS_ORIGINS` | No | http://localhost:3000 | Allowed CORS origins (comma-separated) |

**Example:**
```bash
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
```

---

### Reasoning Effort (o3 Model)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REASONING_EFFORT` | No | low | Reasoning effort for o3 model (low, medium, high) |

**Notes:**
- Only applies to `o3` models
- Higher effort = longer latency + higher quality
- Not applicable to gpt-4o, gpt-5, etc.

---

### Debug Endpoints

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEBUG_ENDPOINTS_ENABLED` | No | false | Enable debug endpoints (e.g., `/debug/user-profile/{user_id}`) |

**Security:** Only enable in development. Production should use `AUTH_ENABLED=true` with admin role checks.

---

## Frontend Runtime Configuration

The frontend uses runtime configuration via `public/config.js` (not environment variables at build time).

### Docker Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REACT_APP_BACKEND_URL` | No | http://localhost:8001 | DreamFarm Agent URL |
| `REACT_APP_API_VERSION` | No | v1 | API version identifier |

**Mechanism:**
1. Build Docker image once with config template
2. Startup script generates `config.js` from environment variables at container startup
3. React app reads `window.APP_CONFIG` at runtime

**Local Development:**
Manually edit `frontend/public/config.js`:
```javascript
window.APP_CONFIG = {
  BACKEND_URL: 'http://localhost:8001',
  API_VERSION: 'v1'
};
```

See [DeploymentGuide.md#frontend-runtime-config](./DeploymentGuide.md) for details.

---

## Related Documentation

- [Design.md](./Design.md) - High-level architecture overview
- [DeploymentGuide.md](./DeploymentGuide.md) - Docker Compose and Kubernetes deployment
- [SecurityModel.md](./SecurityModel.md) - Authentication and authorization
- [ToolSpecifications.md](./ToolSpecifications.md) - All tool configurations
- [RetrievalArchitecture.md](./RetrievalArchitecture.md) - RAG and search configuration
- [MemoryPersonalization.md](./MemoryPersonalization.md) - Memory and profile configuration
- [KnowledgeGraph.md](./KnowledgeGraph.md) - Graph search configuration
- [Observability.md](./Observability.md) - Tracing and monitoring configuration
- [CodeExecution.md](./CodeExecution.md) - Code interpreter configuration

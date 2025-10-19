# Dream Farm AI Platform – Architecture & Design Overview

This document provides a **high-level overview** of the Dream Farm AI platform architecture. For detailed specifications, refer to the specialized documentation files linked throughout this document.

## Documentation Structure

This architecture is documented across multiple specialized files for easier navigation and maintenance:

### Core Architecture
- **[Design.md](./Design.md)** (this file) - High-level overview and system architecture
- **[DataSchemas.md](./DataSchemas.md)** - Complete database schemas, tables, and indexes
- **[APIReference.md](./APIReference.md)** - REST and WebSocket API specifications
- **[ConfigurationReference.md](./ConfigurationReference.md)** - All environment variables and feature flags

### Retrieval & AI
- **[RetrievalArchitecture.md](./RetrievalArchitecture.md)** - RAG, hybrid search, semantic caching
- **[ToolSpecifications.md](./ToolSpecifications.md)** - All AI tool definitions and MCP servers
- **[Observability.md](./Observability.md)** - OpenTelemetry tracing and monitoring

### Reference Documentation
- **[ImplementationLog.md](./ImplementationLog.md)** - Implementation history and decisions
- **[CommonErrors.md](./CommonErrors.md)** - Troubleshooting guide

---

## Table of Contents

- [1. Purpose \& Vision](#1-purpose--vision)
- [2. Core Architectural Principles](#2-core-architectural-principles)
- [3. High-Level Architecture](#3-high-level-architecture)
- [4. System Components](#4-system-components)
- [5. Key Features](#5-key-features)
- [6. Technology Stack](#6-technology-stack)
- [7. Development Workflow](#7-development-workflow)
- [8. Further Reading](#8-further-reading)




---

## 1. Purpose & Vision

Dream Farm is a virtual marketplace connecting local farmers with customers via an AI assistant that provides:

**Core Capabilities:**
- ✅ Product search with semantic understanding and grounding in current catalog
- ✅ Multi-modal retrieval (semantic, keyword, graph traversal)
- ✅ Tool integration (MCP servers, web search, internal APIs)
- ✅ Privacy-preserving memory and personalization
- ✅ Voice interaction (hands-free mode via realtime API)
- ✅ Multi-agent delegation (specialized agents for different domains)
- ✅ Workflow orchestration for complex business processes

**Key Non-Functional Goals:**
- Transparency (explainable retrieval and reasoning via `DF_META` events)
- Extensibility (plugin architecture for tools and agents)
- Security (VIP fencing, per-user data isolation)
- Reproducibility (deterministic data pipelines)
- Minimal hallucination (grounded generation enforced)

---

## 2. Core Architectural Principles

1. **Grounded Generation First** – All product claims originate from retrieved, fenced data
2. **Separation of Concerns** – Retrieval, reasoning, memory, tools are isolated
3. **Incremental Feature Flags** – Each capability enabled independently (see [ConfigurationReference.md](./ConfigurationReference.md))
4. **Provider-Agnostic LLM** – Unified OpenAI/Azure client abstraction
5. **Explainability** – Structured meta events (`DF_META`) for UI & logging
6. **Security-by-Default** – Row-level fencing at SQL layer (see [SecurityModel.md](#security-model))
7. **Lean Prompts** – Token budgets for profile + memory + retrieval
8. **Deterministic Pipelines** – Versioned artifacts (taxonomy, embeddings, summaries)

---

## 3. High-Level Architecture

```mermaid
graph TD
  FE[React Frontend<br/>assistant-ui] -->|REST/WebSocket| AG[DreamFarm Agent Backend]
  AG -->|LLM API| LLM[OpenAI / Azure OpenAI]
  AG -->|SQL / Vector| PG[(PostgreSQL + pgvector + AGE)]
  AG -->|HTTP / MCP| TOOLS[MCP & REST Tools]
  PG -->|Embeddings & FTS| AG
  PG -->|Graph (AGE)| AG
  AG -->|Streaming DF_META| FE
```

**Key Layers:**
- **Frontend**: React + assistant-ui with streaming, file upload, voice capture
- **Agent Backend**: FastAPI with tool orchestration, RAG, memory injection
- **Data Layer**: PostgreSQL with pgvector (embeddings), FTS (keyword search), Apache AGE (graph)
- **Tool Ecosystem**: MCP servers + REST APIs for external capabilities

**Deployment:**
- Local: Docker Compose
- Production: Kubernetes on Azure (AKS + managed services)

See [DeploymentGuide](#deployment-guide) for deployment architecture details.

---

## 4. System Components

### 4.1. Frontend (React + assistant-ui)
- Chat interface with streaming token rendering
- Authentication via OIDC PKCE (Keycloak)
- Runtime config (`public/config.js` - build once, deploy anywhere)
- Voice capture UI (WebSocket singleton, Strict Mode safe)
- File upload for code interpreter

### 4.2. Agent Backend (FastAPI)
- Endpoints: `/chat`, `/threads`, `/files`, `/voice`, `/artifacts`
- Orchestrates: RAG, tool calls, semantic cache, memory injection
- Emits `DF_META` events for transparency
- Feature flags control enabled capabilities

**For complete API specification, see [APIReference.md](./APIReference.md)**

### 4.3. Data Layer (PostgreSQL + Extensions)
- **pgvector**: Product/concept embeddings, semantic cache
- **Full-Text Search**: GIN indexes on `fts_document`
- **Apache AGE**: Knowledge graph (taxonomy, relationships)
- **Retention policies**: Configurable for conversations and summaries

**For database schemas, see [DataSchemas.md](./DataSchemas.md)**

### 4.4. Tool Ecosystem
- **Internal tools**: semantic_search, keyword_search, graph tools, memory tools
- **MCP servers**: farmer tools, visualization generator, Tavily web search
- **External APIs**: Stock API, Chef Agent

**For tool specifications, see [ToolSpecifications.md](./ToolSpecifications.md)**

### 4.5. Authentication & Authorization
- Keycloak OIDC with JWT verification
- VIP enforcement at SQL layer (row-level security)
- Per-user memory fencing

**For security details, see [Security Model](#security-model) section below**

### 4.6. Observability
- Streaming meta events (`DF_META`)
- OpenTelemetry distributed tracing (Grafana Tempo + Langfuse)
- Auto-instrumentation: FastAPI, SQLAlchemy, PostgreSQL, OpenAI
- Business dimensions: user_id, is_vip, thread_id, agent_type

**For complete observability architecture, see [Observability.md](./Observability.md)**

---

## 5. Key Features

### 5.1. Retrieval & Search
- **Simple RAG**: Vector similarity with prompt injection
- **Hybrid Retrieval**: Semantic + keyword + RRF fusion
- **Agentic Search**: LLM-orchestrated multi-tool retrieval
- **Graph Traversal**: BFS taxonomy expansion, DFS similarity
- **Semantic Caching**: First-turn acceleration

**For complete retrieval architecture, see [RetrievalArchitecture.md](./RetrievalArchitecture.md)**

### 5.2. Memory & Personalization
- **Conversation Storage**: Raw transcripts with retention policies
- **Semantic Memory**: Vector search over conversation summaries
- **User Profiles**: Structured personalization (diet, preferences, goals)
- **Privacy-Preserving**: Hard user_id constraints, no cross-user leakage

**For memory architecture details, see [Memory & Personalization](#memory--personalization) section below**

### 5.3. Tool Integration
- **Internal Tools**: Semantic search, keyword search, graph tools, memory tools
- **MCP Servers**: Standardized protocol for external capabilities
- **External APIs**: Stock lookups, multi-agent delegation

**For tool specifications, see [ToolSpecifications.md](./ToolSpecifications.md)**

### 5.4. Multi-Agent Architecture
- **Agent-as-Tool Pattern**: Specialized agents callable as tools
- **Chef Agent**: Culinary services (chef search, catering, pricing)
- **HTTP-based Delegation**: Independent agent services

**For multi-agent details, see [Multi-Agent Architecture](#multi-agent-architecture) section below**

### 5.5. Voice Interaction
- **Realtime API**: WebSocket bidirectional audio (PCM16, 24kHz)
- **Server-Side VAD**: Turn detection and interruption
- **Transcript Persistence**: Text stored, audio ephemeral
- **Minimal Tool Set**: Latency-optimized subset

**For voice details, see [Voice Interaction](#voice-interaction) section below**

### 5.6. Knowledge Graph
- **Apache AGE**: Cypher-based graph traversal
- **Taxonomy**: Categories, cuisines, certifications, allergens
- **Concept Embeddings**: Semantic concept selection
- **Dual Retrieval**: BFS concept expansion + DFS similarity

**For graph architecture, see [Knowledge Graph](#knowledge-graph) section below**

### 5.7. Code Execution
- **Code Interpreter**: Azure OpenAI sandboxed Python environment
- **File Upload**: CSV, Excel, JSON, images (max 30MB)
- **Dynamic Visualizations**: Chart generation, data analysis
- **Artifact System**: Secure file serving with token validation

**For code execution details, see [Code Execution](#code-execution) section below**

### 5.8. Workflow Orchestration
- **Temporal Workflows**: Durable, stateful business processes
- **Complaint Handling**: Multi-step resolution with LLM decision points
- **Policy-Driven**: Company policy embedded in prompts
- **Structured Outputs**: JSON schemas for all workflow steps

**For workflow details, see [Workflow Orchestration](#workflow-orchestration) section below**

---

## 6. Technology Stack

### Core Technologies
- **Backend**: Python 3.11+, FastAPI, Pydantic
- **Frontend**: React 18, TypeScript, assistant-ui, Tailwind CSS
- **Database**: PostgreSQL 16 with pgvector, Apache AGE, fuzzystrmatch
- **LLM**: OpenAI API / Azure OpenAI (gpt-5, gpt-4o, o3)
- **Embeddings**: text-embedding-3-large (2000 dimensions)

### Key Libraries & Frameworks
- **Package Management**: uv (Python), npm (JavaScript)
- **Authentication**: Keycloak (OIDC), JWT verification
- **Tool Integration**: MCP (Model Context Protocol)
- **Observability**: OpenTelemetry, Grafana Tempo, Langfuse
- **Workflow**: Temporal (durable workflows)
- **Deployment**: Docker, Kubernetes, Terraform

**For complete configuration reference, see [ConfigurationReference.md](./ConfigurationReference.md)**

---

## 7. Development Workflow

### Local Development Setup
1. **Backend (DreamFarm Agent)**:
   ```bash
   cd agents/dreamfarm-agent
   uv venv
   source .venv/bin/activate
   uv pip install -e .
   cp .env.template .env  # Configure API keys
   uv run python -m uvicorn src.main:app --reload --port 8001
   ```

2. **Frontend**:
   ```bash
   cd frontend
   npm install
   # Edit public/config.js for backend URL
   npm run dev  # Runs on port 3000
   ```

3. **Database**:
   ```bash
   docker-compose up -d postgres
   # Run migrations/init scripts from data/scripts/
   ```

### Testing Strategy
- **Unit Tests**: pytest for business logic
- **Integration Tests**: Database, MCP servers, multi-agent
- **Evaluation**: DeepEval (quality), PyRIT (security)
- **E2E**: Manual testing of critical flows

### Code Quality
- **Linting**: ruff (Python), eslint (JavaScript)
- **Type Checking**: mypy (Python), TypeScript
- **Formatting**: black (Python), prettier (JavaScript)

---

## 8. Further Reading

### Detailed Technical Documentation

#### Data & API
- **[DataSchemas.md](./DataSchemas.md)** - Complete database schemas, tables, indexes, retention policies
- **[APIReference.md](./APIReference.md)** - REST endpoints, WebSocket protocols, request/response models
- **[ConfigurationReference.md](./ConfigurationReference.md)** - All environment variables, feature flags, quick-start templates

#### Retrieval & AI
- **[RetrievalArchitecture.md](./RetrievalArchitecture.md)** - RAG strategies, hybrid search, semantic caching, VIP fencing
- **[ToolSpecifications.md](./ToolSpecifications.md)** - Internal tools, MCP servers, external APIs, observability
- **[Observability.md](./Observability.md)** - OpenTelemetry tracing, Grafana Tempo, Langfuse, auto-instrumentation

#### Reference
- **[ImplementationLog.md](./ImplementationLog.md)** - Implementation history, architectural decisions, migrations
- **[CommonErrors.md](./CommonErrors.md)** - Troubleshooting guide, common pitfalls, solutions

### Advanced Topics

The following sections provide high-level overviews of advanced features. For implementation details, refer to the codebase and inline documentation.

---

## Memory & Personalization

**Overview**: Three-layer memory system for personalization and context recall.

**Layers:**
1. **Raw Conversations** (`conversations_raw`) - Full JSON transcripts, 7-day retention
2. **Summaries** (`conversation_summaries`) - Semantic search over past conversations
3. **User Profiles** (`user_profiles`) - Structured personalization data

**Key Features:**
- Vector similarity search over summaries (`memory_search` tool)
- Incremental profile updates (`memory_write_profile` tool with patch semantics)
- Hard user_id constraints (no cross-user leakage)
- Token-bounded profile injection (<500 tokens, field priority drop)
- Batch summarization with LLM-based enrichment

**Privacy & Security:**
- Raw logs purged after retention period
- Summaries retained indefinitely (unless configured otherwise)
- User_id fencing at SQL layer
- Optional audit trail for profile changes

**Configuration:**
- `CONVERSATION_STORE_ENABLED`, `MEMORY_SEARCH_ENABLED`, `USER_PROFILE_ENABLED`
- `MEMORY_CONVERSATION_RETENTION_DAYS`, `USER_PROFILE_MAX_TOKENS`

---

## Knowledge Graph

**Overview**: Apache AGE graph database for taxonomy, relationships, and multi-hop traversal.

**Graph Schema:**
- **Vertices**: Producer, Product, Category, Cuisine, Certification, Allergen
- **Edges**: PRODUCES, HAS_CATEGORY, HAS_CUISINE, HAS_CERTIFICATION, CONTAINS_ALLERGEN, RELATED

**Retrieval Tools:**
1. **BFS Taxonomy Search** (`graph_bfs_taxonomy_search`)
   - Semantic concept embedding → BFS expansion to products
   - Concept types: Category, Cuisine, Certification, Allergen
   - Scoring by concept matches + trait coverage + diversity

2. **DFS Similarity Search** (`graph_dfs_similarity_search`)
   - Given product → trait overlap scoring
   - Weights: Categories (1.0), Cuisines (0.8), Allergens (0.5), Producer (0.3)

**Concept Embeddings:**
- Relational table with HNSW index for semantic concept selection
- Bridges relational (pgvector) and graph (Apache AGE) layers

**Configuration:**
- `GRAPH_SEARCH_ENABLED`, `AGE_GRAPH_NAME`, `GRAPH_DFS_MAX_RESULTS`
- BFS tuning: `GRAPH_BFS_CONCEPT_TOP_K_PER_TYPE`, `GRAPH_BFS_MIN_SIMILARITY`

---

## Multi-Agent Architecture

**Overview**: Agent-as-tool pattern enabling specialized domain agents.

**Implementation:**
- **DreamFarm Agent**: Main marketplace agent
- **Chef Agent**: Culinary services specialist (chef search, catering, pricing, booking)
- **HTTP-Based Delegation**: Independent FastAPI services

**Integration Pattern:**
1. DreamFarm Agent detects culinary intent
2. Calls `query_chef_services(query)` tool
3. Chef Agent processes via its own MCP tools
4. Returns structured response
5. DreamFarm Agent synthesizes with product recommendations

**Configuration:**
- `CHEF_AGENT_ENABLED`, `CHEF_AGENT_URL`

**Status**: Phase 4 complete, all tests passing (88 total: 32 Chef + 56 DreamFarm)

---

## Voice Interaction

**Overview**: Low-latency bidirectional speech via OpenAI/Azure Realtime API.

**Architecture:**
- **WebSocket**: `/voice/{thread_id}` endpoint
- **Audio Format**: PCM16, 24kHz, mono, base64-encoded
- **Server-Side VAD**: Turn detection, interruption support
- **Transcripts**: Persisted as normal messages, audio ephemeral

**Tool Restrictions:**
- Minimal tool set for low latency (memory_search + optional lightweight product search)
- Heavy graph tools excluded by default

**Configuration:**
- `VOICE_ENABLED`, `VOICE_MODEL`

---

## Code Execution

**Overview**: Azure OpenAI code interpreter for data analysis and visualization.

**Features:**
- Sandboxed Python environment (pandas, matplotlib, numpy, scipy)
- File upload (max 30MB): CSV, Excel, JSON, images, PDF
- Chart generation with automatic serving via `/files/{file_id}/content`
- Artifact system for generated visualizations

**Security:**
- Container isolation (no access to agent host)
- Execution timeouts
- File scope limited to uploaded files

**Configuration:**
- `ENABLE_CODE_INTERPRETER`, `CODE_INTERPRETER_CONTAINER_TYPE`

**Pricing Note**: Additional charges beyond token costs (per container-hour)

---

## Workflow Orchestration

**Overview**: Temporal-based durable workflows for complex business processes.

**Complaint Handling Workflow (Implemented):**
1. Complaint Receipt & Classification (LLM)
2. Structured Data Extraction (LLM)
3. User Profile Fetch (mocked with deterministic hash)
4. Policy-Based Decision (LLM with 6 few-shot examples)
5. Resolution Generation (LLM)
6. Actions: VALID (refund/replacement), NOT_VALID (explanation), HUMAN_REVIEW (escalation)

**Characteristics:**
- Deterministic workflow code with side-effects in activities
- Policy-driven decision making
- Structured outputs (JSON schemas, Pydantic validation)
- Observability via `ORCH_PHASE` logging

**Status**: Production-ready, all 6 phases implemented and tested

---

## Security Model

**Authentication:**
- Keycloak OIDC with JWT verification (issuer, audience, signature)
- PKCE flow for frontend
- user_id from `sub` claim, VIP from role membership

**Authorization:**
- VIP fencing at SQL layer: `WHERE (is_vip = false OR :user_is_vip)`
- Memory isolation: Hard `user_id` constraints
- Never rely on LLM to self-filter sensitive data

**Data Protection:**
- Conversation retention policies (configurable, default 7 days)
- Summary-based recall (raw logs purged)
- Token budgets for profile injection
- DF_META excludes PII/secrets

**Configuration:**
- `AUTH_ENABLED`, `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_AUDIENCE`

---

## Deployment Guide

**Local Development:**
- Docker Compose with: frontend, agent, PostgreSQL (+extensions), Keycloak, tools

**Production (Azure):**
- **AKS**: Managed Kubernetes cluster
- **Azure Container Registry**: Private registry for images
- **Azure Database for PostgreSQL**: Flexible Server with pgvector + AGE
- **Azure AI Services**: OpenAI-compatible endpoint
- **Ingress**: Nginx with cert-manager + Let's Encrypt
- **Observability**: OTel Collector, Grafana Tempo, Langfuse

**Terraform Infrastructure:**
- AKS cluster with CNI networking
- Managed PostgreSQL with extensions
- Static public IP + DNS zone integration
- Secrets management via Kubernetes secrets

**Helm Deployment:**
- Single chart (`deploy/charts/demo`) for all services
- Centralized `values.yaml` with runtime config injection
- HPA for all services (CPU-based scaling)
- Liveness/readiness probes for rolling updates

---

## Evaluation & Safety

**Manual Evaluation Framework:**
- **DeepEval**: LLM-as-judge metrics (Faithfulness, Relevance, Context Recall, Toxicity)
- **PyRIT**: Red teaming campaigns (prompt injection, data exfiltration, toxic content)

**Scope:**
- On-demand quality + safety assurance
- No CI gates or runtime sampling in Phase 1
- Manual sign-off process

**Datasets:**
- `gold_qa_v1.json`: Curated Q&A pairs
- `adversarial_v1.json`: Edge cases (VIP fencing, allergen safety)
- `redteam_baseline_v1.json`: Seed prompts for PyRIT

**Thresholds:**
- Faithfulness median ≥0.80
- Answer Relevance mean ≥0.85
- Toxicity batch avg ≤0.10

**Configuration:**
- `EVAL_ENABLED`, `SECURITY_REDTEAM_ENABLED`, `PYRIT_CAMPAIGN_PROFILE`

---

## Future Enhancements

**Roadmap (Prioritized):**
1. **Advanced Graph Analytics**: Centrality measures, community detection, hierarchical categories
2. **Multi-Agent Expansion**: Nutritionist Agent, Logistics Agent, Supplier Agent
3. **Enhanced Observability**: Runtime drift detection, A/B testing harness, quality metrics
4. **Persistent Code Execution**: Long-running analysis containers, notebook-style interactions
5. **Collaborative Features**: Shared threads, team workspaces, collaborative analysis
6. **Enhanced Security**: PII detection, audit logging, compliance reporting
7. **Production Hardening**: Auto-scaling, blue-green deployments, disaster recovery
8. **Evaluation Automation**: Scheduled extended suites, trend graphs, regression diffs

---

## Project Structure

```
advanced-ai-applications/
├── agents/                    # AI agents
│   ├── dreamfarm-agent/       # Main marketplace agent
│   └── chef-agent/            # Culinary services agent
├── data/                      # Data pipelines & sources
│   ├── processed/             # Generated artifacts (embeddings, taxonomy)
│   ├── scripts/               # ETL, import scripts
│   └── source_json/           # Sample source data
├── deploy/                    # Deployment configurations
│   ├── azure/                 # Terraform (AKS, PostgreSQL, networking)
│   └── local/                 # Docker Compose
├── frontend/                  # React application
│   ├── src/                   # React components & services
│   └── public/                # Runtime config (config.js)
├── docs/                      # Documentation (this directory)
├── orchestration/             # Temporal workflows
│   └── complaint_workflow/    # Complaint handling workflow
├── postgresql/                # PostgreSQL Dockerfile with extensions
└── tools/                     # AI tools (MCP servers, APIs)
    ├── api_stock/             # Stock REST API
    ├── mcp_public_farmer_tools/   # Utility MCP server
    └── mcp_visualization_generator/ # Dynamic UI MCP server
```

---

## Appendix: Key Terms

| Term | Definition |
|------|------------|
| RAG | Retrieval-Augmented Generation – augment LLM with external context |
| VIP Fencing | Pre-LLM row-level filtering of restricted catalog rows |
| HyDE | Hypothetical Document Embedding for improved semantic recall |
| BFS Taxonomy | Breadth-first product expansion through concept nodes |
| DFS Similarity | Depth-first trait overlap exploration from seed product |
| Semantic Cache | High-similarity first-turn Q&A shortcut |
| MCP | Model Context Protocol - standardized tool integration |
| DF_META | Structured metadata events for transparency (tool calls, reasoning) |
| Code Interpreter | Sandboxed Python execution environment |
| Temporal | Durable workflow engine for stateful business processes |

---

**End of Design Overview**

For implementation details, refer to the specialized documentation files linked throughout this document and the inline code documentation in the repository.

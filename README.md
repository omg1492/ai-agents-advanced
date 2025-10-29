# Advanced AI Applications - Dream Farm AI Platform

**Dream Farm** is a (almost) production-grade AI platform demonstrating a virtual farmers marketplace that connects local farmers with customers through an intelligent AI assistant. The platform showcases advanced AI capabilities including RAG (Retrieval-Augmented Generation), multi-agent systems, knowledge graphs, voice interaction, workflow orchestration, and enterprise-grade observability and deployment.

**Key Features:** Semantic product search, tool integration (MCP servers, web search, internal APIs), hybrid retrieval (semantic + keyword + graph), personalized memory, voice chat, code interpreter with visualizations, multi-agent collaboration, workflow automation, authentication (Keycloak), OpenTelemetry observability and Red Teaming, and deployment to Kubernetes.

📖 **[Read full architecture documentation →](docs/Design.md)**

---

## Course: Advanced AI Applications (10 Evening Lessons)

This repository is the foundation for an intensive 10-lesson course teaching how to design, implement, and deploy production AI applications. The course follows an incremental, hands-on approach where each lesson builds on the previous one, evolving from a basic RAG chatbot to a sophisticated multi-agent system with enterprise features.

**Course Format:** 10 consecutive evening lessons (up to 2 hours each) with live coding using GitHub Copilot. Students actively implement features alongside instructor demonstrations.

📚 **[Full course details →](docs/README.md)**

---

## Lessons Overview

1. **Business Requirements & Basic RAG Chatbot** - Product descriptions with semantic search
2. **Tool Usage: Web Search, API, MCP** - Integration of MCP servers, function calling, web search
3. **Knowledge Base from Documents, Images, Videos** - Multi-format ingestion, hybrid search, semantic caching
4. **Agentic Search, Knowledge Graph & RAG Fencing** - Tool-based retrieval, graph traversal, VIP filtering, authentication
5. **Multimodality, Memory & Real Voice Chat** - Voice interaction, long-term personalization
6. **Code Interpreter & Dynamic UI** - Data analysis, visualization generation, MCP visualization server
7. **AI Workflow Orchestration** - Automated complaint handling with Temporal
8. **Multi-Agent Systems** - Collaboration between specialized agents (farmer marketplace + chef services)
9. **Security & Evaluation** - Red teaming, LLM-as-judge, evaluation framework
10. **Observability & Scalable Deployment** - OpenTelemetry, Kubernetes, CI/CD, IaC

🎯 **[Detailed lesson agenda with concepts & technologies →](docs/Agenda.md)**

---

## Repository Branches

- **`Lxx-teacher`** - Complete implementation for instructor demonstration (each lesson)
- **`Lxx-student`** - Starting point with challenges for students to implement (each lesson)
- **`main`** - Full production version with all features, tests, and CI/CD

Students start from `Lxx-student` branch and work towards the solution shown in `Lxx-teacher` branch.

---

## How to Run
Here we describe final stage of development with all features implemented. Follow instructor and individual lessons for more instructions as we go.

### Azure/Kubernetes Deployment (final stage)

1. Deploy infrastructure: `cd deploy/azure/infrastructure && terraform apply`
2. Build and push containers: `cd deploy/azure/docker_build && uv run build_and_push.py`
3. Deploy services: `cd deploy/charts/demo && helm install dreamfarm .`
4. Configure Keycloak: `uv run identity/provision_keycloak.py`
5. Configure database: `uv run data/scripts/configure_postgresql.py`
6. Import data: `uv run data/scripts/import_all.py`
7. Access via Ingress URL (provided by `kubectl get ingress`)

### Local Development (final stage)

**Prerequisites:**
- Docker & Docker Compose (eg. Rancher Desktop)
- Python 3.11+
- Node.js 18+ (for frontend)
- MCP servers accessible via public endpoint (we use Azure Container Apps, shared for whole group)

**Steps:**

1. **Configure PostgreSQL:**
   ```bash
   docker-compose up -d postgres
   uv run data/scripts/configure_postgresql.py
   ```

2. **Import data:**
   ```bash
   uv run data/scripts/import_all.py
   ```

3. **Start infrastructure services:**
   ```bash
   docker-compose up -d keycloak postgres
   ```

4. **Configure Keycloak:**
   ```bash
   uv run identity/provision_keycloak.py
   ```

5. **Start agents:**
   ```bash
   # Terminal 1 - DreamFarm Agent
   cd agents/dreamfarm-agent
   uv run uvicorn src.main:app --reload --port 8001

   # Terminal 2 - Chef Agent
   cd agents/chef-agent
   uv run uvicorn src.main:app --reload --port 8002
   ```

6. **Start frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

7. **Access application:** http://localhost:3000

**Note:** MCP servers must be accessible from Internet (called from Responses API in cloud). 

---

## Technology Stack

**AI & LLM:** OpenAI GPT-5, Azure OpenAI, Embeddings (text-embedding-3-large)  
**Backend:** Python, FastAPI, SQLAlchemy, Pydantic  
**Database:** PostgreSQL, pgvector (vectors), Apache AGE (knowledge graph)  
**Frontend:** React, TypeScript, assistant-ui, Vite  
**Tools:** MCP protocol, function calling, Tavily search  
**Orchestration:** Temporal (workflows)
**Authentication:** Keycloak, OAuth2/OIDC  
**Observability:** OpenTelemetry, Langfuse, Grafana Tempo  
**Deployment:** Docker, Kubernetes (AKS), Helm, Terraform, GitHub Actions

---

## Project Structure

- `agents/` - AI agents (DreamFarm, Chef) with FastAPI backends
- `data/` - Database schemas, data pipelines, import scripts
- `frontend/` - React UI with assistant-ui components
- `tools/` - MCP servers (farmer tools, visualization, stock API)
- `deploy/` - Kubernetes charts, Docker configs, Terraform IaC
- `docs/` - Comprehensive architecture and API documentation
- `lessons/` - Lesson-specific materials and exercises
- `identity/` - Keycloak provisioning scripts

---

## Documentation

- **[Design.md](docs/Design.md)** - Architecture overview and system design
- **[APIReference.md](docs/APIReference.md)** - Complete REST and WebSocket API specs
- **[DataSchemas.md](docs/DataSchemas.md)** - Database schemas and indexes
- **[RetrievalArchitecture.md](docs/RetrievalArchitecture.md)** - RAG, hybrid search, semantic caching
- **[ToolSpecifications.md](docs/ToolSpecifications.md)** - All AI tools and MCP servers
- **[Observability.md](docs/Observability.md)** - OpenTelemetry tracing and monitoring
- **[CommonErrors.md](docs/CommonErrors.md)** - Troubleshooting guide 
## Implementation Log (consolidated)

This log is streamlined to capture key decisions, architecture changes, and durable insights. Details that don’t inform future work have been removed.

## 1) API and conversation architecture

- Migrated DreamFarm Agent to the Responses API with unified OpenAI/Azure client (2025-08-16).
   - Server-side state via `store=True` and `previous_response_id`.
   - Single SDK setup supports OpenAI and Azure by configuring `base_url` and `api-version`.
   - Minimal reasoning enabled when using GPT‑5 family.
- Endpoints finalized: `POST /chat`, lightweight `/threads` for session handles (state remains with provider).
- Jinja2 prompt templates integrated across chat endpoints; optional RAG context injected into the system prompt.
- Streaming added (2025-08-17): `POST /threads/{thread_id}/messages/stream` streams token deltas; history and `previous_response_id` updated on completion.

Why it matters: unified config reduces branching; provider-side state simplifies scaling; streaming improves UX without breaking existing APIs.

## 2) Retrieval and data pipeline

- RAG architecture delivered end-to-end (2025-08-01): PostgreSQL + pgvector (cosine), empirically tuned similarity threshold, robust error handling, and availability checks.
- Embeddings: Azure OpenAI text-embedding-3-large (2000 dims); ensured dimension alignment with DB.
- SQL artifacts (2025-08-17):
   - `stock` table, `products` table (vector + FTS + triggers), AGE graph init; HNSW/GIN indexes documented.
   - Import pipeline for `stock.json` with validation and batching.
- Postgres image (2025-08-17): custom `postgresql/Dockerfile` with pgvector + Apache AGE; GHCR workflow for on-demand builds.
- Data scripts (2025-08-16): unified OpenAI SDK usage, batched embeddings with retries, consistent logging, outputs to Parquet.

Why it matters: production-ready retrieval stack with clear schema, reproducible image, and resilient ETL.

## 3) Tooling and auxiliary services

- `tools/api_stock` service (2025-08-18): FastAPI with `POST /stock`, `GET /health`; psycopg2 pool, UUID array filter; integration tests included.
- Consolidation (2025-08-18): simplified to a single `main.py`; fixed prior syntax issues; health endpoint is tz-aware.
- Containerization & CI (2025-08-18): Added `tools/api_stock/Dockerfile`; GH Actions workflow `build-api-stock.yml` builds and publishes GHCR image on dispatch and changes under `tools/api_stock/**`; local `docker-compose.yml` includes `api-stock` service referencing `ghcr.io/<repo>/api-stock:latest`.
- MCP tools (2025-08-18): Added `tools/mcp_public_farmer_tools` using FastMCP 2.0 with minimal tools (`echo`, `list_produce`, `server_time`), single-file server, Dockerfile, and GH Actions workflow to publish `mcp-public-farmer-tools` image.
      - Testing approach revised (2025-08-18): Removed low-level pytest/httpx harness. We'll adopt a higher-level MCP testing framework (e.g., pytest-mcp or MCP Testing Framework) in CI to validate protocol and tool behavior without bespoke HTTP code.
   - Auth fix (2025-08-18): Adjusted custom TokenVerifier to construct `AccessToken` with required fields (`token`, `client_id`, `scopes`) and made `verify_token` async to satisfy FastMCP bearer middleware awaiting behavior.
- Dev utility (2025-08-17): `scripts/cherry_pick.py` to sync lesson branches; interactive flow and auto-push.

Why it matters: stable read-only stock API for demos/integration; maintenance scripts reduce branch drift.

## 4) Documentation and design

- `docs/Design.md` aligned with current API and models (2025-08-17): added `/chat`, corrected thread message shape, clarified Pydantic fields.
- Project structure simplified in docs; focused on main folders and key subfolders.
- Database schema docs: concise `simple_products` table summary and Markdown tables for readability.
- Production data/graph design captured with SQL-first retrieval and optional AGE traversal.
- Planned AI tools section (2025-08-18): MCP tools, `api_stock`, and Tavily remote MCP with integration guidance.

Why it matters: the docs now reflect reality and guide contributors with compact, actionable references.

## 5) Testing and configuration

- Test selection simplified: default `-m unit`; opt-in `-m integration` with self-skip when env/infra missing.
- Config: centralized `ConfigService`; `OpenAIService` receives `OpenAIConfig` via injection; unified env variables for OpenAI/Azure and data scripts.
- Upgraded `openai` to `>=1.99.0,<2.0.0`.

Why it matters: faster, clearer CI runs and fewer environment surprises.

## Milestones (timeline)

- 2025-08-18: Planned AI tools; `api_stock` released and consolidated.
- 2025-08-17: Streaming chat; design docs aligned; SQL schema + AGE init; Postgres image; stock import; cherry-pick utility.
- 2025-08-16: Responses API migration; unified OpenAI/Azure client; template integration; data embeddings refactor.
- 2025-08-01: RAG system end-to-end validated; template and config services in place.
- 2025-07-28: DreamFarm Agent initial implementation (FastAPI, threads, health, absolute imports, `src/` layout, scripts entry point).
## 2025-12-09

### Updated Agenda Documentation for Lesson 04 Implementation

**Background**: The agenda documentation (agenda.md, final_agenda.md, technický_plán.md) needed to be aligned with the actual implementation of Lesson 04 - Agentic Search, Knowledge Graph & RAG Fencing.

**Changes Made**:
1. **Updated lesson title**: Changed from "Deep Research & Knowledge Graph" to "Agentic Search, Knowledge Graph & RAG Fencing" to better reflect the actual implementation
2. **Corrected concepts**: Added missing key concepts like:
   - Agentic search with function calling
   - VIP fencing and RAG security
   - OAuth2/OIDC authentication with Keycloak
   - HyDE (Hypothetical Document Embedding)
   - BFS/DFS graph traversal algorithms
   - Feature flags for progressive enablement
3. **Updated technologies**: Corrected the technology stack to match actual implementation:
   - Apache AGE (instead of Neo4j/Memgraph as originally planned)
   - OpenAI function calling (instead of LangGraph for this lesson)
   - Keycloak for OAuth2/OIDC
   - FastAPI backend with tool integration
   - React frontend with authentication flow
4. **Enhanced practical exercises**: Updated to reflect the actual hands-on components implemented
5. **Aligned learning objectives**: Ensured the "Umím..." (I can...) outcomes match what was actually built

**Architecture Decision Context**: 
- Chose Apache AGE over standalone graph databases (Neo4j/Memgraph) to maintain unified PostgreSQL infrastructure
- Implemented direct OpenAI function calling instead of LangGraph framework for simpler, more controlled tool execution
- Added comprehensive VIP fencing at application layer before LLM prompt processing

### Added Stock Custom Tool (Local REST Proxy)

Implemented a local custom tool `StockService` that proxies to the `api_stock` REST service.
Reason: Stock API cannot be registered as a remote MCP tool; we fetch data locally and inject summarized stock context (`<stock_info>`) into the system prompt when UUID-like product IDs are detected in user messages.

Key points:
- Configured via `STOCK_TOOL_ENABLED` and `STOCK_API_URL` (added to ConfigService & .env.template)
- Non-intrusive: if disabled or URL missing it silently skips
- Regex-based UUID extraction (capped to 20 IDs per request) to avoid excessive calls
- Added integration test `test_stock_tool_integration.py` (skips when tool not configured)
- Updated `system_prompt.j2` to include optional `<stock_info>` section

## 2025-08-19

### Graph Search Service - AGE Compatibility Issues Resolved

**Background**: Attempted to implement graph traversal search functionality using Apache AGE for BFS taxonomy searches and DFS similarity searches.

**Issues Encountered**:
1. `function cypher(unknown, unknown) does not exist` - solved with `ag_catalog.cypher` qualification
2. SQLAlchemy parameter binding conflicts with AGE - resolved with `exec_driver_sql` direct execution
3. Agtype value extraction with embedded quotes - resolved with `_extract_agtype_value` helper
4. Mysterious `@>` operator errors even with simplified cypher queries
5. AGE syntax limitations: no ORDER BY support, limited WHERE clause compatibility

**Resolution Strategy**: 
- Implemented graceful degradation by disabling both `bfs_taxonomy` and `dfs_similarity` methods
- Methods now return empty results with appropriate warning logs
- Service interface preserved for future re-enablement when AGE is upgraded
- Hybrid architecture remains viable: PostgreSQL for complex queries, AGE for simple relationships

**Architecture Decision**: Keep graph infrastructure but disable complex traversal until AGE syntax limitations are resolved. This maintains system stability while preserving the foundation for future graph functionality.

**Next Steps**: Monitor Apache AGE updates for ORDER BY and advanced cypher support.

---

- agents/dreamfarm-agent: Updated `RAGService.format_search_results` to a clearer block format and included `product_id` in the output. Adjusted unit and integration tests to match the new labels and headers. Added docstring to the method.

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
   - Tool alignment (2025-08-18): Renamed tools to match design spec: `server_time` → `get_current_time`, `list_produce` → `get_seasonal_tips`; added `get_weather(country, city)` mocked endpoint with deterministic daily values.
    - Remote tool integration (2025-08-18): DreamFarm Agent now passes Farmer Tools as a remote MCP tool to Responses API.
       - Config: `FARMER_TOOLS_ENABLED`, `FARMER_TOOLS_MCP_URL`, `FARMER_TOOLS_MCP_API_KEY` (fallback to `MCP_API_KEY`).
       - Auth: HTTP Authorization header `Bearer <FARMER_TOOLS_MCP_API_KEY>`.
       - Applied to both normal and streaming calls.
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

## 6) MCP meta streaming UX and bugfixes (2025-08-18)

- Backend: Fixed a scoping error in `agents/dreamfarm-agent/src/main.py` where `tools` was referenced before assignment in the streaming endpoint. Tools are now resolved once prior to opening the stream and passed into the generator. Also enriches DF_META with `server_label`, `tool_name`, and an `arguments_preview` (truncated to 200 chars).
- Frontend: Improved meta events UI in `frontend/src/components/thread.tsx`.
   - Meta panel moved above assistant text.
   - Collapsible with a Show/Hide toggle and total count.
   - Scrollable container (auto-scroll to bottom) so the latest ~5 items stay visible; older entries available via scrolling.
   - Clear titles like `Tool: <name> (farmer-tools)` when available.

Why it matters: makes tool usage and reasoning transparent during streaming while keeping the primary answer readable.

## 7) Streaming markdown formatting + simplified DF_META (2025-08-18)

- Frontend: Fixed loss of newlines in streamed text in `frontend/src/services/chatAdapter.ts`.
   - When splitting the stream by lines to detect `DF_META:`, we now re-insert `\n` for non-meta lines and preserve blank lines.
   - Result: final assistant output renders Markdown correctly (headings, lists, paragraphs).
- Backend: Simplified DF_META for tool events to only include `{ kind, event_type, tool_name, arguments }`.
   - Removed IDs (id, item_id, call_id), server_label, and internal fields; arguments are aggregated from deltas.
   - Failures still include the same minimal fields and thus remain readable.

Why it matters: cleaner Activity panel and correctly formatted answers.

## 8) Strict RAG grounding for product mentions (2025-08-19)

- System prompt updated (`agents/dreamfarm-agent/src/templates/system_prompt.j2`) with a STRICT grounding policy:
   - Any product-related claims (availability, price, farmer, certification) must be grounded in `<relevant_products>`.
   - Zero-hit behavior: do not invent products; state unavailability, offer alternatives only from RAG, or switch to general non-stock info.
   - Clear decision flow for product vs. general queries; response style tightened to avoid implicit availability claims.

Why it matters: prevents hallucinated inventory when RAG returns no results (e.g., “peaches” case) and keeps recommendations trustworthy.

### 8.1) Prompt tools overview (2025-08-19)
- Added a concise "Available tools & data" section to the system prompt to orient the model about:
   - RAG catalog as sole source for concrete product info
   - Read-only stock API usage
   - Mocked Farmer Tools for general guidance (non-inventory)
   - Web search for recipes/facts without implying availability

## Milestones (timeline)

- 2025-08-18: Planned AI tools; `api_stock` released and consolidated.
- 2025-08-17: Streaming chat; design docs aligned; SQL schema + AGE init; Postgres image; stock import; cherry-pick utility.
- 2025-08-16: Responses API migration; unified OpenAI/Azure client; template integration; data embeddings refactor.
- 2025-08-01: RAG system end-to-end validated; template and config services in place.
- 2025-07-28: DreamFarm Agent initial implementation (FastAPI, threads, health, absolute imports, `src/` layout, scripts entry point).

### 2025-08-22 Function Tool Integration (Stock) Refactor

- Removed earlier approach of injecting stock data into system prompt via `<stock_info>` tags (risk of stale or overlong prompts).
- Implemented proper function calling for local Stock API as `get_stock` tool registered alongside remote MCP tools in `OpenAIService.get_tools()`.

### 2025-09-06 AGE Graph Data Import Script

- Added `data/scripts/import_graph_age.py` to populate Apache AGE graph `dreamfarm` with nodes: Producer, Product, Certification, Allergen and edges: PRODUCES, HAS_CERTIFICATION, CONTAINS_ALLERGEN.
- Idempotent MERGE pattern; optional `--reset` flag drops & recreates graph (dev only) mirroring earlier `04_init_age_graph.sql` intent.
- Product node keeps only id/name/description subset to prevent duplication of large relational attributes (embedding, VIP) inside graph.
- Summary queries (counts + top producers) printed post-run for quick validation.
 - 2025-09-06 Update: Added batching (`--batch-size`, default 1000) committing after each batch to avoid a single long-running transaction (~15k MERGEs) and to emit progress logs (percentage + batch count). Function `_execute_cypher_batches` replaces previous single-transaction executor. Default 1000 chosen as a balance between commit overhead and lock duration; configurable for tuning.

### 2025-09-06 Taxonomy Enrichment Pipeline Design Spec

- Added comprehensive taxonomy & cuisine enrichment section to `docs/Design.md` detailing generation of ~50 categories and ~20 cuisines, description summaries, multi-label classification, artifact versioning (JSON + Parquet), and Apache AGE graph import strategy.
- Defined environment-driven configuration (`TAXONOMY_*` variables), confidence thresholding, batch classification approach, and version-aware MERGE semantics for edges (storing confidence + version properties).
- Included operational safeguards (atomic artifact writes, optional human review gate, dry-run import, logging metrics) plus extensibility roadmap (hierarchies, dietary tags, feedback loop, seasonal concepts).
- Rationale: Removes ambiguity from Lesson 4 plan checkbox; provides executable blueprint enabling parallel implementation of generation, classification, and import scripts.

### 2025-09-06 Taxonomy Generation Script (gen_graph_taxonomy.py)

- Added `data/scripts/gen_graph_taxonomy.py` implementing resumable taxonomy enrichment pipeline.
- Concept synthesis: single structured JSON call producing ~50 categories & ~20 cuisines (code, name, description) with enforced schema + deterministic product sample (seed=42).
- Classification: batched product assignment (default 40 products) mapping each product to 1–3 categories and 0–2 cuisines; truncates descriptions for context efficiency.
- Resumability: `taxonomy_state.json` tracks concepts, completed_batches, total_batches, batch_size, product_ids, and cumulative token usage; safe restarts skip completed work.
- Artifacts: `taxonomy_concepts.parquet`, `taxonomy_assignments.parquet` for downstream AGE import script; parquet chosen for compactness & schema evolution.
- Token accounting aggregated per stage (concept_generation, assignment) logging prompt/completion/total; ETA estimation after each batch.
- CLI flags: `--rebuild-concepts`, `--batch-size`; env overrides `TAXONOMY_BATCH_SIZE`, `TAXONOMY_STATE_PATH`.
- Defensive design: atomic state writes (temp file swap), deterministic ordering, context size guards (truncate long descriptions), fallback to existing products parquet or simple_products.
- Next step (separate script): import taxonomy nodes & edges into AGE with MERGE + optional versioning & confidence.

### 2025-09-08 Taxonomy Graph Import Script (import_taxonomy_age.py)

- Added `data/scripts/import_taxonomy_age.py` to ingest taxonomy artifacts into AGE graph.
- Reads `taxonomy_concepts.parquet` & `taxonomy_assignments.parquet` produced by generation pipeline.
- Creates / updates `Category` & `Cuisine` nodes (code, name, description) plus edges:
   - `(Product)-[:IN_CATEGORY]->(Category)`
   - `(Product)-[:IN_CUISINE]->(Cuisine)`
- Pure MERGE approach (idempotent). Missing product nodes result in skipped edges via MATCH pattern without creation.
- Optional `--reset-taxonomy` flag removes existing taxonomy nodes/edges only (non-destructive to Producer/Product graph core).
- Batch execution pattern mirrors earlier graph import script (`--batch-size`, default 1000) with progress percentage.
- Apostrophe normalization reused to avoid Cypher quoting pitfalls; long descriptions truncated (<=800 chars) for node property hygiene.
- Pre-flight validation of required parquet columns with explicit error if schema drifts.

## 2025-08-24 Semantic Cache Service Integration

- Added `SemanticCacheService` (`agents/dreamfarm-agent/src/services/semantic_cache_service.py`) implementing high-threshold vector lookup against `semantic_cache` table.
- Configuration via new env vars: `SEMANTIC_CACHE_ENABLED` (default true) and `SEMANTIC_CACHE_SIMILARITY_THRESHOLD` (default 0.93). Optional `SEMANTIC_CACHE_EMBEDDING_MODEL` falls back to `OPENAI_EMBEDDING_MODEL`.
- Integrated into `main.py` for `/threads/{thread_id}/messages` and streaming variant only on the FIRST user turn (after user message appended, history length==1).
- On cache hit: immediate response returned, no LLM call, INFO log emitted ("Semantic cache hit").
- Conversation state handling: because Responses API lacks an endpoint to inject a synthetic assistant turn without model generation, we seed only local in-memory history; subsequent model call starts a fresh chain (no `previous_response_id`). Documented rationale + future option in service docstring.
- Added seeding helper `seed_history_with_hit` to append synthetic assistant message with timestamp.
- Updated `.env` and `.env.template` with semantic cache variables; updated `ConfigService` with `SemanticCacheConfig` dataclass.
- Implementation decisions documented here and in service docstring to avoid ambiguity about state continuity and token accounting trade-off.

### 2025-08-24 Semantic Cache Testing

- Added unit tests (`test_semantic_cache_unit.py`) mocking embeddings + DB engine to cover hit and miss paths without network/DB.
- Added integration tests (`test_semantic_cache_integration.py`) exercising real PostgreSQL `semantic_cache` table + real embeddings:
   - Positive case: query "Hello!" expected hit (seed from Q&A import) with similarity >= threshold.
   - Negative case: random string ("jsdovnfjepsd") expected miss.
- Integration test auto-skips when required env vars, API key, or `semantic_cache` table absent (mirrors RAG integration style).
- Ensures threshold logic respected and guards against false positives.
- Added guarded two-iteration tool loop in `generate_response` to resolve synchronous function calls and resubmit outputs via `submit_tool_outputs`.
- Extraction helper `_extract_function_calls` isolates `function_call` items from Responses API output list; resilient to malformed entries.
- Ensures graceful no-op when stock tool disabled while model attempts a call (returns empty items array).
- Updated logging for initialization to include `stock_tool_enabled` state.

Rationale: Aligns with OpenAI Responses API function calling pattern, reduces prompt size, and lets model request only needed stock data.

Follow‑up Correction (2025-08-22): Removed residual `stock_context` prompt injection from all endpoints once function calling path was verified. Stock data now flows strictly through `get_stock` tool events (model asks → tool executes → `submit_tool_outputs` → model continues reasoning). Added backward-compatible argument parsing (`productIds` preferred, `product_ids` accepted).

### GPT-5 Reasoning with Streaming Function Calls Implementation (2025-08-22)

**Critical Discovery**: Successfully implemented continuous reasoning with function calls for GPT-5 models in streaming mode after resolving complex API item pairing requirements.

**The Challenge**: Initial streaming function call implementations failed with `400 Bad Request` errors indicating function call items were "provided without their required reasoning item." Multiple approaches were attempted:

1. **Inline Submission During Streaming**: Attempted to call `submit_tool_outputs` while stream was active → OpenAI SDK limitations prevented this approach
2. **Event Replay Pattern**: Tried to replay tool events after stream completion → Lost reasoning context and broke continuous thought chain
3. **Simple Loop Pattern**: Implemented basic loop but only captured function call items → Missing paired reasoning items caused API rejection

**The Solution**: Implemented proper GPT-5 reasoning item pairing in the streaming loop:

```python
# Key insight: GPT-5 generates reasoning items (rs_*) paired with function calls (fc_*)
current_reasoning_item = None

# Capture both item types in correct order
if item_type == "reasoning":
    current_reasoning_item = item
    input_messages.append(item)  # Reasoning explains the decision
    
elif item_type == "function_call":
    input_messages.append(item)  # Function call follows reasoning
    # Execute tool and prepare output for next iteration
```

**Technical Architecture**:
- **Loop-based streaming**: Continuous `while True` loop following Tomáš Kubica's proven pattern
- **Item pairing preservation**: Maintains reasoning→function_call→output sequence
- **Tool execution**: Functions execute during streaming, outputs queued for next iteration
- **Context continuity**: Full conversation history maintained across reasoning steps

**Why This Matters**:
- Enables true continuous reasoning where model can chain multiple tool calls
- Maintains GPT-5's reasoning capabilities while providing real-time streaming
- Allows model to ask for stock data, process results, and continue reasoning seamlessly
- Provides foundation for complex multi-step AI agent workflows

**Performance Benefits**:
- Real-time token streaming during reasoning phases
- Efficient tool execution without breaking reasoning chains
- Proper reasoning→action→reflection cycles for AI agent behavior

This implementation represents a significant breakthrough in GPT-5 reasoning model integration, enabling sophisticated AI agent capabilities with streaming UX.

## 2025-08-23 PDF Processing Utility

- Added `data/scripts/process_pdfs.py` single-file tool to extract Markdown from PDFs using `markitdown` and summarize product metadata via unified OpenAI Responses API.
- Configurable via env (`PDF_INPUT_DIR`, defaults to `../PDFs` relative to script). Reuses existing unified OpenAI env vars.
- Structured response with Pydantic `ProductSummary` ensuring consistent output (product_name + short_description).
- Added `markitdown` dependency to `data/scripts/pyproject.toml`.
- Console output uses clear delimiter blocks (PROCESSING, MARKDOWN EXTRACT, LLM SUMMARY, ERROR) for readability during batch runs.

## 2025-08-23 Image Processing Utility

- Added `data/scripts/process_images.py` to generate product name & description from images using vision-capable model via unified OpenAI client.
- Supports env `IMAGES_INPUT_DIR` (default `../images`).
- Structured outputs with Pydantic `ImageProductSummary`; consolidated summary printed at end (mirrors PDF script UX).

## 2025-08-23 Video Processing Utility (Frame Sampling Prototype)

- Added `data/scripts/process_video.py` implementing product summarization for videos.
- Current approach samples up to 3 representative frames (start/mid/end) via OpenCV and sends them as multiple image parts to the same vision model (fallback while native `input_video` support stabilizes).

## 2025-08-23 Hybrid RAG (Semantic + FTS + RRF)

- Extended `RAGService` with keyword extraction (Responses API structured output via Pydantic `ExtractedKeywords`).
- Added full‑text search path over `fts_combined` using extracted OR tsquery.
- Implemented Reciprocal Rank Fusion (k=60) to merge semantic + FTS results; fused score stored in `similarity_score` for formatting.
- Logging (INFO): semantic count, extracted keyword count, FTS count, fusion summary.
- Design doc updated (concise hybrid architecture section). Unit tests patched to mock new keyword/FTS branches.
- Structured Pydantic `VideoProductSummary` mirrors image + PDF scripts for consistency.
- Added `VIDEOS_INPUT_DIR` env var to `.env.template` and `.env`.
- Clear TODO marker to switch to direct video ingestion once generally available in the Python SDK.

## 2025-08-23 Full-Text Search for simple_products

- Added FTS column `fts_combined` (unaccent + simple config) with trigger-based maintenance (initial generated column attempt failed: "generation expression is not immutable").
- Created GIN index `idx_simple_products_fts_combined`.
- Added extension script `03_install_unaccent.sql` to enable `unaccent`.
- Updated `Design.md` (notes trigger approach & table column constraints).

Rationale: enables hybrid (semantic + lexical) retrieval with explicit trigger logic; foundation for future rank fusion.

## 2025-08-24 Semantic Cache Seed Generation

- Added `data/scripts/gen_qna.py` producing exactly 50 structured generic first-turn Q&A pairs (greetings, capability inquiries, broad help, onboarding) using GPT‑5 Responses API + Pydantic schema.
- Ensures no specific product / farmer / price / stock / certification mentions; answers are neutral (1–3 sentences) and encourage follow-up specificity.
- Design doc updated with `semantic_cache` table schema (question, answer, embedding) and first-turn-only retrieval rationale + workflow.
- Enforces uniqueness & size (raises if != 50) and basic heuristic guards against leakage of disallowed specifics.
- Temperature kept low (0.4) for stability while preserving phrasing diversity.

Why it matters: reduces cost & latency for extremely frequent cold-start user intents while preserving strict grounding for any catalog-related queries.

### 2025-08-24 Semantic Cache Import Script Simplification

- Simplified `data/scripts/import_qna.py` after successful initial import:
   - Removed conditional (try/except) numpy import; direct dependency already declared.
   - Dropped `# pragma: no cover` markers to reflect real coverage and reduce noise.
   - Generalized embedding sequence detection to accept any non-string `Sequence` (list/tuple/ndarray) without special‑casing numpy.
   - Removed unused import after refactor; leaner path for row preparation and clearer debug logs.
- Result: smaller script surface, fewer conditional branches, and clearer diagnostics if future imports skip rows.

### 2025-08-24 Semantic Cache Pipeline (End-to-End) Summary

End of session snapshot of the new semantic cache data pipeline (first‑turn Q&A):

1. Generation (`data/scripts/gen_qna.py`)
   - Produces a generic first‑turn Q&A seed set (no product / price / stock specifics) via Responses API structured output.
   - Exact count enforcement and heuristic filters were later relaxed per requirements to keep the script minimal.

2. Embeddings (`data/scripts/embeddings_qna.py`)
   - Loads `qna.json`, batches questions through `text-embedding-3-large` (2000 dims) and writes `qna_embeddings.parquet`.
   - Mirrors batching + logging style used in existing product embeddings script for consistency.

3. Table DDL (`data/scripts/sql/05_create_semantic_cache.sql`)
   - Idempotent drop/create of `semantic_cache` table with `question`, `answer`, `embedding VECTOR(2000)`, `created_at`.
   - Adds HNSW index for fast similarity on cold‑start lookups.

4. Import (`data/scripts/import_qna.py`)
   - Truncates table (dev overwrite) then batch inserts from `qna_embeddings.parquet`.
   - Initial zero‑row import issue traced to strict embedding type check; resolved by accepting any non‑string `Sequence`.
   - Simplified after validation (removed conditional numpy import, coverage pragmas) → leaner maintenance footprint.

Result: We now have a reproducible, one‑command path from synthetic Q&A intent seeds to a populated `semantic_cache` table ready for first‑turn retrieval logic integration in the agent service.

## 2025-08-25 Products VIP Fencing Foundation

- Added `is_vip BOOLEAN NOT NULL DEFAULT false` column to `products` table DDL (`03_create_products.sql`) plus index `idx_products_is_vip` and column comment. Purpose: enable search/result fencing so non‑VIP users cannot access VIP‑flagged products.
- Created `data/scripts/embeddings_products.py` generating enriched products parquet (`products.parquet`) with:
   - Flattened producer/product data from `producers.json` (product + producer IDs/names/descriptions)
   - Deterministic VIP assignment (~10%, configurable via `PRODUCT_VIP_RATIO`, seeded RNG) in `is_vip` column
   - 2000‑dim embeddings over a structured `combined_text` field
   - Unified OpenAI/Azure client + batched resilient embedding requests (tenacity retry policy)
- Created `data/scripts/import_products.py` to load parquet into `products`:
   - Truncates table for dev repeatability
   - Converts embedding arrays to pgvector literal strings `[v1,v2,...]`
   - Preserves `is_vip` flag and validates embedding dimensionality
- Updated ImplementationLog to document rationale: forms basis for forthcoming RAG / tool fencing (filter automatically by user VIP status) without modifying existing simple RAG path yet.

### 2025-08-25 Standardized Product Embedding Dimension

- Simplified `embeddings_products.py` to always request embeddings with explicit `dimensions=2000` (removed env override & fallback path) to guarantee alignment with `products.embedding vector(2000)` and avoid import skips.
- Added post-generation sanity check logging error if returned dimension diverges (defensive guard against model/config drift).

Next (not implemented here): integrate VIP filtering into RAG queries and tool-based agentic search once those layers are added.

## 2025-08-25 Keycloak Service Added (Local Dev Auth Foundation)

- Added `keycloak` service to `deploy/local/docker-compose.yml` using `quay.io/keycloak/keycloak:25.0`.
- Runs against existing Postgres instance (shared DB) via JDBC URL `jdbc:postgresql://postgres:${PGPORT}/${PGDATABASE}` to keep dev stack minimal (acceptable for local; prod should isolate DB/schema).
- Dev credentials parameterized: `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD` with defaults (`admin`/`admin`) for simplicity.
- Started with `start-dev` mode (ephemeral, no TLS) and exposed on port 8080; healthcheck hitting `/health/ready` to coordinate dependent future auth integration work.
- Prepared environment variables for future realm import (comment notes about mounting an import directory and adding `--import-realm`).

Rationale: Provides immediate OIDC provider so upcoming tasks (demo users, JWT extraction, VIP fencing) can proceed incrementally without waiting for realm automation. Future steps: create realm (e.g., `dreamfarm`), client for frontend (public w/ PKCE), roles or group mapping for `vip`, and scripted user bootstrap.

### 2025-08-25 Keycloak Provisioning Script

- Added provisioning script (later moved to `identity/provision_keycloak.py`) to automate local Keycloak setup: creates (idempotently) realm, VIP role, public frontend client (Auth Code + PKCE), and three demo users (`user1`, `user2`, `vipuser` with last assigned `vip`).
- Environment-driven; dedicated env moved to `identity/.env*` (`KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_DEMO_CLIENT_ID`, `KEYCLOAK_DEMO_REDIRECT_URIS`, `KEYCLOAK_DEMO_USERS`, `KEYCLOAK_VIP_ROLE`).
- Uses simple deterministic passwords `<username>123` for dev only; sets user attribute `is_vip` plus realm role membership for VIP user.
- Script is safe to re-run; updates client redirect URIs and skips existing entities.
  
Next: integrate JWT validation middleware reading `vip` role (or `is_vip` attr if we map to a claim) in the agent and implement frontend OIDC flow.

## 2025-08-25 Frontend OIDC (Keycloak) Basic Integration

- Added runtime config keys to `frontend/public/config.js` (+ template): `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_REDIRECT_URI` with Docker env counterparts (`REACT_APP_*`).
- Implemented minimal dependency-free PKCE Authorization Code flow in `frontend/src/services/auth.ts` (login redirect, code exchange, token storage, user parsing, logout).
- Updated `App.tsx` to gate UI: unauthenticated users see welcome + login button; authenticated users see username avatar + logout.
- API client (`api.ts`) now attaches bearer token automatically if present and not expired.
- Added `identity/register_app.py` helper for future additional client registrations (idempotent create/update) – not required for main flow but scaffolds future needs.
- Documented auth variables & behavior in `frontend/README.md` (explicit dev‑only caveats, no silent refresh yet).

Deferred (future work): refresh token rotation, silent renew, backend JWT validation & role/VIP claim consumption, fine-grained route protection.

### 2025-08-26 Keycloak Demo User Profile Auto-Population

- Updated `identity/provision_keycloak.py` so demo users are created (or updated) with deterministic `email`, `firstName`, `lastName`, and `emailVerified=True` to suppress the initial Keycloak profile completion screen during local demos.
- Added `ensure_user_profile` helper invoked on every provision run to backfill missing fields for pre-existing users (idempotent). VIP user gets last name `VIP`; others get `User` for quick visual distinction.
- Rationale: streamline developer/testing flow (one-click login) without manual profile edits; strictly dev-only convenience (would not auto-verify email in production).

### 2025-08-26 Frontend VIP Badge

- Parsed `vip` realm role from access token (`realm_access.roles`) plus fallbacks to prospective custom claims.
- Added purple "VIP" badge beside username in header when role present.
- README updated (Authentication section) documenting indicator logic.

### 2025-08-26 Backend JWT Auth (Keycloak)

- Added JWT auth to dreamfarm-agent: new `AuthConfig` + `AuthService` with JWKS-based RS256 verification.
- Protected chat/thread endpoints via `_require_user` dependency; logs now include `user` and `vip` status.
- VIP detection mirrors frontend logic (realm role `vip` or fallback claims).
- Environment toggled (`AUTH_ENABLED`, defaults true). Minimal verification (issuer/audience/signature) suitable for dev.
  
### 2025-08-26 Test Auth Override

- Added pytest session-scoped dependency override in `agents/dreamfarm-agent/tests/conftest.py` to bypass JWT validation during tests.
- Rationale: Keep new auth enforcement from breaking existing fast unit/integration tests (Option A from analysis). Provides synthetic user `test-user` (non‑VIP) so behavior relying on user identity remains consistent.
- Cleanup performed after session; production runtime unchanged.

### 2025-09-11 Graph Search Cypher Invocation Stabilization

- Simplified `GraphSearchService` to always use the 2‑argument Apache AGE form with explicit casts: `cypher((:graph)::name, $$...$$::cstring)`.
- Removed dynamic signature detection (pg_proc introspection + 3‑arg fallback) to reduce surface for errors and eliminate extra connection queries.
- Added early smoke test in `__init__` executing `MATCH (n) RETURN 1` to fail fast if extension/search_path not applied to pooled connections.
- Motivation: Persistent `function cypher(unknown, unknown)` errors indicated argument type inference issues; explicit `name` + `cstring` casting stabilizes resolution after `LOAD 'age'; SET search_path=ag_catalog, public;` hook.
- Next: validate BFS & DFS end‑to‑end and then update `docs/CommonErrors.md` to reflect the simplified guidance.

### 2025-09-11 Graph Search Finalization & Logging (Update)

- Removed the previously described explicit `::name` / `::cstring` casting – empirical tests showed the **pure 2‑arg form** (`cypher(:graph, $$...$$)`) is the only stable variant; casts were unnecessary once the body was fully dollar‑quoted and only `:graph` remained as a bind.
- Deleted all dynamic / probing logic in favor of a single helper `_build_cypher_sql` returning the fixed pattern (reduction in complexity + fewer failure branches).
- Rewrote `docs/CommonErrors.md` Cypher section: deprecated 3‑arg guidance, added smoke test + concise troubleshooting matrix, emphasized isolation of colon tokens inside the dollar block.
- Enhanced observability for agentic transparency:
   - DFS: structured INFO log with `raw_rows`, `kept`, `skipped_vip`, `technique=graph_dfs_similarity`.
   - BFS: concept selection log (total + per‑type counts) and final metrics (`raw_candidates`, `scored`, `kept`, `skipped_vip`, `technique=graph_bfs_taxonomy`).
- Chose flat key=value format (single log line) to simplify downstream parsing / potential structured log ingestion without adding a dependency.
- Rationale: removes ambiguity for future maintainers, prevents regressions to unsupported signatures, and surfaces enough metrics for debugging empty / sparse graph results.

### 2025-09-13 Unified Design Document Restructure

Refactored `docs/Design.md` from lesson-centric narrative into a thematic architecture document:
- Introduced top-level sections: Purpose, Principles, Architecture, Components, Configuration, Security, Conversation Management, Tool Strategy, Grounding & Retrieval, Knowledge Graph, Memory, Voice, Schemas, API Surface, Tools, Observability, Deployment, Roadmap, Glossary.
- Consolidated previously scattered lesson 5 memory & voice additions under Memory & Voice chapters.
- Preserved all technical content (schemas, env vars, tool definitions, retrieval algorithms) while removing “Lesson X” headings for improved maintainability.
- Added roadmap & glossary for onboarding clarity.
No functional code changes; documentation-only refactor improving discoverability.
### 2025-09-14 Conversations Raw Table (Memory Foundation Step 1)

- Added `07_create_conversations_raw.sql` creating `conversations_raw` table (raw transcript storage) with:
   - `thread_id` (unique), `user_id`, `messages JSONB`, lifecycle fields (`summary_status`, `summary_attempts`, `error_last`, `locked_at`)
   - Retention column `expires_at` (default now()+7 days) to allow scheduled purge of raw logs post-summarization
   - Touch trigger maintaining `updated_at` on any row change
   - Indexes on `user_id`, `expires_at`, and `summary_status` (batch summarization pickup)
- Purpose: Foundation for memory pipeline (subsequent steps: summaries, profile enrichment, memory search tools).
- Design choices: `user_id` stored as TEXT for IdP portability; lightweight status enum via CHECK constraint instead of custom type for simpler migrations.
      - 2025-09-14 Update: Simplified schema per request—removed `locked_at`, `summary_attempts`, and later `error_last` columns; batch summarizer will rely solely on `summary_status` plus age-based retry (no explicit locking / attempt counters / per-row error field).

### 2025-09-14 Unified Data Import Orchestrator

- Added `data/scripts/import_all.py` to discover and execute all `import_*.py` scripts in a deterministic order.
- Preferred order encodes soft dependencies: embeddings/tables first, then graph base, then taxonomy enrichment.
- Features: `--dry-run`, `--only`, `--exclude`, `--pattern`, `--stop-on-error`, and `--list`.
- Provides concise success/failure summary; isolates each script in its own subprocess for clean logging.
- Rationale: One-command developer convenience to rebuild demo dataset reliably without memorizing individual script names.

### 2025-09-14 Conversation Persistence (Memory Step 2)

- Implemented `ConversationStore` service using SQLAlchemy for `conversations_raw` table writes.
- Upserts after EACH individual message (user and assistant) to survive disconnects between turns.
- Message JSON shape: {role, content, created_at, mode} aligned with future summarization pipeline expectations.
- Integrated into `/threads/{id}/messages` (normal + streaming) endpoints; errors are non-fatal (logged, continue in-memory).
- Added DELETE `/threads/{thread_id}` endpoint to remove both in-memory structures and persisted transcript (foundation for user-initiated deletion).
- Added unit test `test_conversation_store_unit.py` validating append + delete behavior.
- Added integration test `test_conversation_persistence_integration.py` (skips gracefully if DDL not applied) verifying DB insert & delete lifecycle.
- Design choice: JSONB array concatenation via `messages || :append::jsonb` for atomic append; avoids race conditions of fetch/merge/write with separate SELECT.
 - 2025-09-14 Fix: Replaced `:param::jsonb` cast style with `CAST(:param AS jsonb)` in `ConversationStore` due to psycopg2/SQLAlchemy tokenization quirk on Windows that left `:append` / `:messages` unbound causing `syntax error at or near ":"`. Logic unchanged (still UPDATE then conditional INSERT) but now portable across dev environments.
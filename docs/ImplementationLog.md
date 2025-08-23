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
- Structured Pydantic `VideoProductSummary` mirrors image + PDF scripts for consistency.
- Added `VIDEOS_INPUT_DIR` env var to `.env.template` and `.env`.
- Clear TODO marker to switch to direct video ingestion once generally available in the Python SDK.
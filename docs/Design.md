# Advanced AI Applications - Design Document

## Overview

This document describes the architecture and design of our advanced AI applications project - **Dream Farm**, a virtual farmers' marketplace that connects local farmers with customers through AI-powered assistance.

## Current Phase: Lesson 1 - Basic Architecture

### Business Requirements

- Create a basic chatbot interface for the Dream Farm marketplace
- Allow customers to interact with an AI assistant about farm products
- Provide a foundation for future enhancements (RAG, tools, multimodal features)

### Architecture Overview

**Lesson 1 - Simple Architecture with RAG:**
```mermaid
graph LR
    A[React Frontend<br/>assistant-ui] -->|HTTP/REST| B[DreamFarm<br/>Agent]
    B -->|OpenAI API| C[Azure OpenAI<br/>or OpenAI]
    B -->|SQL Query| D[PostgreSQL<br/>with pgvector]
    D -->|Product Data<br/>+ Embeddings| B
```

**Lesson 2+ - MCP Tool Integration:**
```mermaid
graph TD
    A[React Frontend<br/>assistant-ui] -->|HTTP/REST| B[DreamFarm<br/>Agent]
    B -->|OpenAI API| C[Azure OpenAI<br/>or OpenAI]
    B -->|MCP Protocol| D[MCP Gateway<br/>Routing]
    D -->|MCP Protocol| E[RAG MCP Server]
    D -->|MCP Protocol| F[Web Search MCP<br/>Server]
    D -->|MCP Protocol| G[Knowledge Graph<br/>MCP Server]
```

**Lesson 8+ - Multi-Agent Architecture:**
```mermaid
graph TD
    A[React Frontend<br/>assistant-ui] -->|HTTP/REST| B[DreamFarm<br/>Agent<br/>Orchestrator]
    B -->|HTTP/REST + MCP| C[Chef Agent]
    B -->|HTTP/REST + MCP| D[Other Agents]
    B -->|MCP| E[MCP Tools]
```

**Optional: nginx/Envoy for Production (Lesson 10):**
For production deployment, you can add nginx or Envoy for load balancing, SSL, and static files - but not as a custom service, just as infrastructure.

### Technical Stack

**Backend:**
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Environment Management**: uv (for virtual environments and packages)
- **Configuration**: python-dotenv for environment variables
- **AI Service**: Azure OpenAI Service or OpenAI API
- **Data Validation**: Pydantic models
- **Testing**: pytest

**Frontend:**
- **Framework**: React
- **UI Library**: assistant-ui (for chat interface)
- **Build Tool**: Vite (recommended for React projects)
- **Runtime Configuration**: JavaScript file for environment-specific settings

**Development Tools:**
- **Package Management**: pyproject.toml (no requirements.txt)
- **Code Quality**: Follow project coding standards
- **Documentation**: Docstrings for all public methods and classes

### API Design

#### Base Configuration
- **DreamFarm Agent Port**: 8001 (main AI agent, LLM logic, sessions, CORS)
- **Frontend Port**: 3000 (default for React/Vite)
- **Environment**: `.env` file for DreamFarm agent

#### Environment Variables
**DreamFarm Agent (.env) - Unified:**
```
# OpenAI (hosted by OpenAI)
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-5
CORS_ORIGINS=http://localhost:3000

# Azure OpenAI (next-gen v1)
# OPENAI_API_KEY=your-azure-api-key
# OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/
# OPENAI_API_VERSION=preview
# OPENAI_MODEL=your-azure-deployment-name

# RAG Configuration
ENABLE_RAG=true
RAG_SIMILARITY_THRESHOLD=0.7
RAG_MAX_RESULTS=3

# PostgreSQL Configuration
PGHOST=localhost
PGPORT=5432
PGDATABASE=aidb
PGUSER=admin
PGPASSWORD=Admin12345678

# Embeddings (use same unified scheme)
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Authentication / Authorization
REQUIRE_AUTH=false
KEYCLOAK_ISSUER=https://keycloak.local/realms/dreamfarm
KEYCLOAK_AUDIENCE=dreamfarm-frontend

# Agentic Search (function/tool based retrieval)
ENABLE_AGENTIC_SEARCH=false
AGENTIC_MAX_RESULTS=5
```

**Frontend (Runtime Configuration):**
The frontend uses a runtime configuration approach with a `config.js` file:

For **local development**, manually edit `public/config.js`:
```javascript
window.APP_CONFIG = {
  BACKEND_URL: 'http://localhost:8001',  // DreamFarm Agent URL
  API_VERSION: 'v1'
};
```

For **Docker deployment**, environment variables are injected at container startup:
```
REACT_APP_BACKEND_URL=http://your-dreamfarm-agent-url
REACT_APP_API_VERSION=v1
```

The Dockerfile includes a startup script that generates `public/config.js` from environment variables.

### OpenAI Provider Configuration (Unified)

The system supports both Azure OpenAI and OpenAI API with a single client.
Use ``OPENAI_BASE_URL`` and ``OPENAI_API_VERSION`` when talking to Azure; omit them for OpenAI-hosted.
```python
# services/openai_service.py (concept)
import os
from openai import OpenAI

def get_openai_client():
  api_key = os.getenv("OPENAI_API_KEY")
  base_url = os.getenv("OPENAI_BASE_URL")  # e.g., https://<resource>.openai.azure.com/openai/v1/
  default_query = {"api-version": os.getenv("OPENAI_API_VERSION", "preview")} if base_url else None
  return OpenAI(api_key=api_key, base_url=base_url, default_query=default_query)

def get_model_name():
  return os.getenv("OPENAI_MODEL", "gpt-5")
```

This abstraction allows the same codebase to work with both providers seamlessly.

### Retrieval & Search Architecture

The platform provides two complementary retrieval modes:
1. Hybrid RAG (semantic + keyword fusion) – prompt inlined context blocks (internal fusion logic)
2. Agentic tool-based iterative search (function calling) – LLM chooses which retrieval tool(s) to call (no backend fusion)

Planned augmentation (Lesson 4 end):
3. Graph (Cypher) traversal tools – breadth-first taxonomy expansion and depth-first similarity exploration over Apache AGE graph

VIP fencing (row-level filtering) currently applies only to the agentic tool-based retrieval path; hybrid RAG remains unrestricted (shows full catalog) unless extended later.

#### Hybrid RAG (Semantic + Keyword with RRF)

The DreamFarm Agent includes a hybrid RAG system combining semantic + full‑text retrieval:

#### RAG Architecture (Hybrid)
1. **Semantic Pass**: Generate embedding for user query; vector similarity over `simple_products.embedding` (cosine) → ranked list S
2. **Keyword Extraction**: LLM (Responses API structured output) extracts normalized keywords (product names, producer names, salient nouns)
3. **Full‑Text Pass**: Build `to_tsquery` over `fts_combined` from extracted keywords → ranked list K (ts_rank)
4. **Fusion (RRF)**: Apply Reciprocal Rank Fusion score = Σ 1/(k + rank) with k=60 across S and K; produce fused list F (top N = configured `RAG_MAX_RESULTS`)
5. **Prompt Injection**: Format F (same block format) → `<relevant_products>` in system prompt (existing behavior; unchanged downstream)
6. **Logging** (INFO): counts for semantic, keywords, fts, fused

Design Notes
- **Structured Output**: Pydantic `ExtractedKeywords(keywords: List[str])` passed via `response_format` json_schema; deterministic schema for parsing
- **Safety**: Keyword extraction failure → fallback to semantic only; empty keywords skip FTS
- **FTS Query**: OR-joined sanitized keywords (`|`) with `simple` config & `unaccent`; limit = `RAG_MAX_RESULTS` (pre‑fusion diversity kept by fusion step)
- **RRF Justification**: Simple, order‑aware, requires only ranks (not raw scores), robust to heterogeneous scoring scales
- **Score Reporting**: Final `similarity_score` field holds fused score (semantic method unchanged for tests)
- **Extensibility**: Future third signal (graph, stock filters, reranker) can add another ranked list before fusion

#### RAG Components

**RAGService** (`src/services/rag_service.py`):
- Embedding generation
- Keyword extraction via Responses API structured output
- Vector similarity + FTS search
- Reciprocal Rank Fusion (RRF) combiner
- Result formatting + prompt injection
- Feature flags: `ENABLE_RAG`, interplay with `ENABLE_AGENTIC_SEARCH`

#### Agentic Tool-Based Retrieval (Function Calling)
Enabled via `ENABLE_AGENTIC_SEARCH=true`. The LLM receives two retrieval tool schemas and decides dynamically which (and how many times) to invoke; the backend does not merge or rerank across tool outputs—each call returns an independent result set the model can reference in subsequent reasoning.

Tools (JSON schema arguments):
- `semantic_search(text: string)` -> returns `{ results: [ { product_id, product_name, producer_name, score, is_vip } ] }` (semantic vector similarity, HyDE capable)
- `keyword_search(keywords: string[])` -> returns same shape (full‑text search)

Workflow:
1. Model may synthesize a HyDE document for the semantic tool (backend optional heuristic for very short questions).
2. LLM issues tool calls; backend executes and returns raw lists (VIP‑filtered if user not VIP).
3. Model integrates referenced products in final answer; ordering/selection is model decision (no backend fusion).
4. Each call emits a `DF_META` line with counts (requested, returned) and VIP filter stats.

Fallback: If agentic search disabled or model opts not to call tools, system uses Hybrid RAG.

HyDE Meta: When generated, truncated hash + token count emitted in a `DF_META` line with kind `hyde_generation`.

#### VIP Fencing
Applied only in agentic retrieval tool queries:
```
WHERE (products.is_vip = false OR :user_is_vip = true)
```
`user_is_vip` derived from authenticated request context (defaults false if auth disabled). Hybrid RAG path intentionally ignores `is_vip` (shows full catalog) in this phase; policy may evolve later.

**Database Schema (brief):**

simple_products

| Column             | Type          | Constraints           | Description                                      |
|--------------------|---------------|-----------------------|--------------------------------------------------|
| id                 | integer       | primary key           |                                                  |
| product_id         | UUID          | unique, not null      | Product identifier                               |
| producer_name      | varchar(255)  | not null              | Producer name                                    |
| product_name       | varchar(255)  | not null              | Product name                                     |
| product_description| text          | not null              | Product description                              |
| combined_text      | text          | not null              | Preformatted text used for embedding & FTS       |
| embedding          | vector(2000)  |                       | 2000-d embedding (pgvector)                      |
| fts_combined       | tsvector      | trigger-maintained    | Unaccented tsvector over combined_text for FTS   |

Notes
- Vector similarity optimized with an HNSW index on embedding (cosine similarity).
- Additional btree indexes on product_id, producer_name, and product_name for lookups.
- Full-text search enabled via generated column `fts_combined` + GIN index (unaccent + simple config).

#### Full-Text Search (FTS) Enhancement (Lesson 1 Hybrid Add-On)
Hybrid support: `fts_combined` (trigger-maintained due to unaccent immutability) + GIN index for keyword fallback alongside vector search. Extension: `unaccent`.

### Semantic Caching (First-Turn Accelerator)

Purpose: Reduce latency and model cost for extremely common FIRST user turns (greetings, capability questions, generic help requests) by answering from a local cache when the opening user message semantically matches a precomputed canonical question.

Scope & Constraints:
- Only applied to the VERY FIRST user message of a conversation/session (no prior context). Subsequent turns are not cached to avoid misinterpretation without full dialogue history.
- Cache contains only generic, non‑specific Q&A pairs (no concrete product, farmer, stock, price, certification, or allergen references) to avoid stale or hallucinated factual answers.
- Answers are concise, neutral, and encourage the user to proceed with a more specific request if needed.

Data Preparation:
- Generated via `data/scripts/gen_qna.py` using GPT‑5 with structured output (Pydantic) to produce exactly 50 diverse, generic Q&A pairs.
- Output file: `data/source_json/qna.json` with schema:
  ```json
  [ { "question": "...", "answer": "..." }, ... ]
  ```

Database Schema (`semantic_cache`):

| Column      | Type        | Constraints            | Description                                                   |
|-------------|-------------|------------------------|---------------------------------------------------------------|
| id          | serial      | primary key            | Surrogate key                                                 |
| question    | text        | unique, not null       | Canonical generic question (embedding source)                 |
| answer      | text        | not null               | Pre-approved neutral answer                                   |
| embedding   | vector(2000)| not null               | 2000‑d embedding of `question` (text-embedding-3-large)       |
| created_at  | timestamptz | default now()          | Insert timestamp                                              |

Indexes:
- HNSW index on `embedding` (cosine) for fast nearest neighbor match.
- Unique btree on `question` for integrity.

Retrieval Logic (First Turn Only):
1. User sends initial message M (thread has 0 prior messages).
2. Generate embedding for M and run vector similarity against `semantic_cache`.
3. If top similarity >= configured threshold (e.g., 0.90) return cached `answer` immediately (flag response as `cache_hit=true`).
4. Otherwise proceed with normal LLM path (RAG / tools, etc.).

Benefits:
- Cuts cold-start latency for frequent boilerplate intents.
- Reduces token spend for trivial first exchanges.
- Creates deterministic, consistent onboarding tone.

Limitations & Rationale:
- Not applied mid-conversation: meaning shifts with context; risk of incorrect shortcutting.
- No product specifics cached: inventory & catalog are dynamic; those must remain grounded via RAG to avoid stale answers.
- Simple single-table design; future evolutions may add adaptive cache entries from high-frequency production queries plus feedback scoring.

Future Enhancements:
- Add hit/miss telemetry for tuning threshold & pruning low-value entries.
- Periodic regeneration/refinement incorporating anonymized real user phrasing.
- Multi-lingual variant sets keyed by detected language.

### Database and Knowledge Graph Schema (production-ready)

This section specifies the target schema for production, extending the Lesson 1 "simple_products" with a richer `products` table for hybrid search, a `stock` table, and a knowledge graph using Apache AGE.

#### Products (relational, hybrid search)

Purpose: primary product catalog optimized for hybrid retrieval (semantic + keyword) and downstream reranking.

Reasoning/tool telemetry (streamed):
- Backend streams model events from the Responses API (semantic event types such as response.output_text.delta, response.web_search_call.*, response.file_search_call.*, response.function_call_arguments.*, and reasoning-related events).
- Non-answer events are emitted as text lines prefixed with `DF_META:` followed by JSON (e.g., `{kind: "tool_event" | "reasoning", event_type: "...", ...}`), and logged at INFO for observability.
- Frontend parses `DF_META:` lines from the stream and renders them in a separate meta panel, clearly distinguished from the assistant answer body.
Columns

| Column             | Type          | Constraints                | Description                                                                 |
|--------------------|---------------|----------------------------|-----------------------------------------------------------------------------|
| id                 | serial        | primary key                | Surrogate key                                                               |
| product_id         | UUID          | unique, not null           | Stable external product identifier                                          |
| producer_id        | UUID          | not null                   | External producer identifier; correlates with Producer vertex (producerId)  |
| producer_name      | varchar(255)  | not null                   | Redundant for search/sorting                                                |
| product_name       | varchar(255)  | not null                   | Product display name                                                        |
| product_description| text          | not null                   | Rich description                                                            |
| combined_text      | text          | not null                   | Concatenated fields used for embeddings                                     |
| embedding          | vector(2000)  |                            | 2000‑d pgvector embedding (text-embedding-3-large)                          |
| fts_document       | tsvector      | not null                   | Generated from name/producer/description for FTS                            |
| is_vip             | boolean       | not null default false     | True = restricted; visible only to VIP users                                |
| created_at         | timestamptz   | default now()              | Row creation timestamp                                                      |
| updated_at         | timestamptz   | default now()              | Row update timestamp                                                        |

Indexes

- HNSW index on embedding using cosine ops for fast vector similarity
- GIN index on fts_document for full‑text search
- BTREE indexes on product_id, producer_id, producer_name, product_name

Notes

- Maintain `fts_document` via trigger (e.g., to_tsvector('english', ...)).
- Use hybrid scoring for candidate retrieval:
  score = 0.6 * (1 - cosine_distance(embedding, :query_vec)) + 0.4 * ts_rank_cd(fts_document, plainto_tsquery(:q))
- Keep `simple_products` as a minimal seed/training/lesson table; `products` supersedes it for production use.

#### Stock (relational)

Purpose: current stock quantity per product (and producer for provenance).

Columns

| Column       | Type        | Constraints       | Description                              |
|--------------|-------------|-------------------|------------------------------------------|
| producer_id  | UUID        | not null          | Producer that owns the stock entry        |
| product_id   | UUID        | not null          | Product this stock refers to              |
| on_stock     | integer     | not null, default 0 | Current available quantity               |
| updated_at   | timestamptz | default now()     | Last update timestamp                     |

Constraints & Indexes

- Primary key: (producer_id, product_id)
- BTREE indexes on product_id and producer_id (if not covered by PK)

Notes

- Matches generator output in `data/source_json/stock.json` (producerId, productId, onStock).
- If products are unique to a producer, (product_id) could be unique; we keep a composite PK for generality.

#### Knowledge graph (Apache AGE)

Purpose: model rich relationships (producer → product, certifications, allergens, categories) and enable graph traversals for recommendations, explanations, and exploration.

- Graph name: dreamfarm
- Query language: openCypher via AGE’s cypher() SQL function

Vertices (labels and representative properties)

- Producer { producerId: UUID, name: text, description: text }
- Product { productId: UUID, name: text }
- Certification { certificationId: UUID, name: text, description: text }
- Allergen { allergenId: UUID, name: text }
- Category { categoryId: UUID, name: text, description: text }
- Cuisine { cuisineId: UUID, name: text, description: text }

Edges (relationship types)

- PRODUCES (Producer → Product)
- HAS_CERTIFICATION (Producer → Certification)
- CONTAINS_ALLERGEN (Product → Allergen)
- HAS_CATEGORY (Product → Category)
- HAS_CUISINE (Product → Cuisine)
- RELATED (Product ↔ Product) optional, for curated similarity/co‑purchase signals

Relational ↔ Graph integration (recommended pattern)

- Keep `products` as the system of record for product content, embeddings, and FTS.
- Create lightweight Product vertices that carry only a stable external key `productId` (and `name`) to reference relational rows.
- Mirror producer/certification/allergen entities as vertices with their stable IDs from the JSON/ETL.
- Synchronization: populate/refresh the graph from the relational/JSON sources via ETL jobs; only a small subset of product attributes lives in the graph.
- Query pattern:
  1) Do hybrid retrieval in SQL on `products` to get top-N product_ids with scores.
  2) Use those IDs as parameters to a Cypher query for traversals/enrichment (e.g., producers, certifications, similar products) and optionally re‑rank.
  3) Join the `cypher(...)` results with relational tables on the `productId`/`producerId` properties.

Taxonomy Enrichment Pipeline (categories & cuisines):
1. Derive canonical category & cuisine sets (LLM structured output + deterministic review) – target ~50 categories, ~20 cuisines.
2. Generate concise, neutral summaries for every category & cuisine (1–2 sentences) for graph explainability.
3. Multi‑label classify each product to 0..N categories and 0..N cuisines (confidence‑aware; low confidence = unassigned).
4. Persist artifacts (JSON + Parquet) for reproducibility & downstream batch import.
5. Import script MERGEs Category / Cuisine vertices (with description) and HAS_CATEGORY / HAS_CUISINE edges into graph.

#### Detailed Taxonomy & Cuisine Enrichment Specification (Lesson 4)

Goals
- Introduce two higher‑level concept layers (Category, Cuisine) above raw products to enable semantic grouping, faceted exploration, recommendation pivots, and richer natural‑language answers (e.g., "These cheeses fit Italian Mediterranean salads").
- Keep derivation deterministic & auditable (stored artifacts, hash of model prompts, version tags) so future re‑runs can diff changes.

Inputs
- Source product data (relational `products` table or pre‑import parquet) – fields: `product_id`, `product_name`, `producer_name`, `product_description`.
- (Optional) Existing allergens/certifications (can inform category naming for edge cases, but not required for first pass).

LLM Tasks (three sequential phases)
1. Concept Set Generation
  - Prompt model with sampled / summarized product descriptions (NOT entire corpus verbatim) to propose a candidate list of categories (target count configurable) and cuisines.
  - Structured JSON schema with fields: `categories: [{id, name, description}]`, `cuisines: [{id, name, description}]`.
  - Deterministic ID strategy: slug of name (kebab-case) + short hash suffix to avoid collisions (e.g., `fresh-cheese-d4f2`).
2. Concept Refinement (optional human review loop)
  - Script outputs draft set; if `--review` flag provided, write to `processed/taxonomy_concepts.draft.json` and exit for manual edits; otherwise continue automatically.
3. Product Classification
  - Multi‑label assignment using second structured call per batch of products (batch size configurable, default 50) with schema: `assignments: [{product_id, categories: [id], cuisines: [id], confidences: {<id>: float}}]`.
  - Apply local confidence filter (`>= TAXONOMY_MIN_CONFIDENCE`, default 0.55) dropping weak associations.

Artifacts (Versioned)
```
processed/
  taxonomy_concepts.v1.json            # canonical list (categories + cuisines)
  product_taxonomy_assignments.v1.parquet  # columns: product_id, category_ids (array<str>), cuisine_ids (array<str>), meta (JSON)
  product_taxonomy_assignments.v1.json  # (optional) human-readable mirror
```
Versioning Rules: bump minor (v1 -> v1.1) for additive concept descriptions; bump major for structural or ID changes.

Import Workflow
1. Ensure graph exists (`dreamfarm`).
2. Load `taxonomy_concepts.*` → MERGE Category/Cuisine vertices with properties: `{categoryId|cuisineId, name, description, version}`.
3. Load product assignment parquet → for each product edge:
  - MATCH (p:Product {productId}) & (c:Category {categoryId}) MERGE (p)-[:HAS_CATEGORY {version, confidence}]->(c)
  - MATCH (p:Product {productId}) & (cui:Cuisine {cuisineId}) MERGE (p)-[:HAS_CUISINE {version, confidence}]->(cui)
4. Optionally detach & recreate only edges whose version differs to support incremental updates.

Configuration (env vars / flags)
- `TAXONOMY_CATEGORY_TARGET=50`
- `TAXONOMY_CUISINE_TARGET=20`
- `TAXONOMY_MIN_CONFIDENCE=0.55`
- `TAXONOMY_MODEL` (defaults to main chat model)
- `TAXONOMY_BATCH_SIZE=50`
- `TAXONOMY_VERSION=v1`

Planned Scripts (`data/scripts/`)
- `gen_taxonomy_concepts.py` – phases 1–2 (generation + optional review)
- `classify_products_taxonomy.py` – phase 3 (multi‑label classification, parquet + json output)
- `import_taxonomy_graph.py` – graph MERGE of vertices + edges (idempotent, version aware)

Data Models (JSON Schemas – conceptual)
```
// taxonomy_concepts.v1.json
{
  "version": "v1",
  "generated_at": "<iso8601>",
  "categories": [ { "id": "fresh-cheese-d4f2", "name": "Fresh Cheese", "description": "Soft, unripened cheeses..." } ],
  "cuisines":   [ { "id": "italian-78ac", "name": "Italian", "description": "Cuisine featuring regional..." } ],
  "model": {"name": "gpt-5", "embedding": "text-embedding-3-large"},
  "prompt_hash": "sha256:..."
}

// Single assignment row (logical)
{
  "product_id": "<uuid>",
  "categories": ["fresh-cheese-d4f2", "dairy-general-91bf"],
  "cuisines": ["italian-78ac"],
  "confidences": {"fresh-cheese-d4f2": 0.81, "dairy-general-91bf": 0.62, "italian-78ac": 0.74},
  "version": "v1"
}
```

Edge Cases & Safeguards
- Products with extremely short or generic descriptions may yield no assignments (allowed).
- Confidence tie‑breaking: keep all above threshold (no forced top‑k) to avoid premature narrowing.
- Category/Cuisine name collisions collapse via slug+hash; detection logged.
- Re‑run with same input + model should produce same slug IDs (hash includes name only) – descriptions may vary; review gate recommended for stability.

Integration Points
- RAG / Agentic Search Enhancement: allow filtering or boosting by category/cuisine (future flag `ENABLE_TAXONOMY_FILTERS`).
- Answer Generation: graph traversals can fetch sibling products in same category or top categories for a cuisine to enrich recommendations.
- Explanations: surface chain like Product → HAS_CATEGORY → Category.description to justify suggestions.

Observability
- Log counts: total categories/cuisines, mean categories per product, orphan products (0 assignments), duplicate slug collisions.
- Potential metrics table (future): taxonomy_version, run_id, category_count, cuisine_count, coverage_ratio.

Future Extensions
- Add hierarchical Category layering (e.g., Meat -> Poultry -> Chicken) using parent edges.
- Introduce seasonal tags or dietary patterns (vegan, keto) as additional concept layers.
- Feedback loop: capture user selections to refine confidence thresholds.

Security / Safety Considerations
- Human edible example terms only; rely on manual review for sensitive or culturally specific cuisine descriptions.
- All model outputs constrained by schema & max length (truncate/server‑side validation before import).

Failure Handling
- Any phase error aborts before writing partially complete artifacts (write temp file then atomic rename).
- Import script supports `--dry-run` to emit Cypher without executing for review.

This specification operationalizes the high‑level taxonomy bullet so implementation can proceed without further design ambiguity.

Why this split?

- Relational tables excel at hybrid search (pgvector + FTS) and filtering/pagination.
- Graph excels at multi‑hop relationships and explanations (e.g., why is this product recommended?).
- Using `productId`/`producerId` as shared keys keeps the models decoupled but interoperable.

AGE operational notes

- Enable AGE extension and set `search_path = ag_catalog, "$user", public` in sessions that run Cypher.
- Use `SELECT create_graph('dreamfarm');` once, then `cypher('dreamfarm', $$ ... $$)` for DML/queries.
- Store external IDs as vertex properties (e.g., `Product {productId: '...'}`) to bridge to relational tables.

#### RAG Configuration

**Feature Flag**: Set `ENABLE_RAG=true` to enable semantic search
**Similarity Threshold**: `RAG_SIMILARITY_THRESHOLD=0.7` (0.0-1.0, higher = more strict)
**Max Results**: `RAG_MAX_RESULTS=3` (top N similar products to include)

#### RAG Workflow
1. User asks: "I need fresh vegetables for a salad"
2. System generates embedding for the query
3. Cosine similarity search finds relevant products (e.g., lettuce, tomatoes, cucumbers)
4. Top 3 results above threshold are formatted as context
5. System prompt includes: `<relevant_products>Product info...</relevant_products>`
6. AI assistant responds with knowledge of available products

#### Benefits
- **Semantic Understanding**: Finds products by meaning, not just keywords
- **Real-time Context**: Always uses current product database
- **Configurable**: Can be enabled/disabled and tuned via environment variables
- **Scalable**: Uses PostgreSQL with proper indexing for performance

### Thread/Session Management Strategy

For Lesson 1, we implement a simple session API consumed by the frontend while keeping conversation state on the provider via the Responses API:

#### Session Lifecycle
1. **Create Session**: Frontend calls `POST /threads` to get a session handle (`thread_id`)
2. **Send Messages**: Frontend sends messages via `POST /threads/{thread_id}/messages`
3. **Server-side State**: Backend calls OpenAI Responses API with `store=True` and remembers only the last `response_id` per `thread_id` to continue with `previous_response_id` on the next turn
4. **History (Optional)**: Backend maintains a lightweight in-memory message list for UI display only; content is not used to generate responses
5. **Persistence**: In-memory for Lesson 1; later lessons may add DB/Redis for durability

#### Data Storage (Lesson 1)
```python
# In-memory storage for simplicity
threads: Dict[str, Thread] = {}
messages: Dict[str, List[Message]] = {}  # thread_id -> messages (display only)
last_response_id: Dict[str, str] = {}    # thread_id -> last response_id for Responses API continuity

# Later lessons will replace with:
# - PostgreSQL for persistent storage
# - Redis for session caching
# - User authentication and authorization
```

#### Benefits of Hybrid Session API
- **Stateless**: Each request is independent, easier to scale
- **Provider State**: Uses Responses API server-side state via `previous_response_id`
- **OpenAI Compatible**: Aligns with Responses API conversation model
- **Frontend Friendly**: Easy for React to manage conversation state
- **Future Ready**: Can easily add user sessions, persistence, sharing
- **Debugging**: Easy to inspect conversation history

#### API Endpoints

**Base URL**: `http://localhost:8001`

##### POST /chat
Single-endpoint chat using server-side conversation state.

Uses Responses API with `store=true` and `previous_response_id` for continuity.

**Request Body:**
```json
{
  "message": "string",
  "previous_response_id": "string (optional)"
}
```
- The stream may include meta lines prefixed with `DF_META:` containing JSON entries that describe tool usage or reasoning summaries. Clients should treat those as telemetry, not as assistant text, and display them separately if desired.

**Response:**
```json
{
  "response_id": "string",
  "message": "string",
  "timestamp": "string (ISO 8601)"
}
```

##### POST /threads
Create a new conversation thread.

**Request Body:**
```json
{
  "title": "string (optional)"
}
```

**Response:**
```json
{
  "thread_id": "string (UUID)",
  "title": "string",
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)"
}
```

##### GET /threads/{thread_id}
Get thread information.

**Response:**
```json
{
  "thread_id": "string (UUID)",
  "title": "string",
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)",
  "message_count": "integer"
}
```

##### POST /threads/{thread_id}/messages
Send a message in a conversation thread.

**Request Body:**
```json
{
  "message": "string"
}
```

**Response:**
```json
{
  "message_id": "string (UUID)",
  "thread_id": "string (UUID)",
  "user_message": "string",
  "assistant_response": "string",
  "timestamp": "string (ISO 8601)"
}
```

##### POST /threads/{thread_id}/messages/stream
Send a message and stream the assistant response tokens progressively.

Response is a streamed text/plain body with chunks of assistant text as they arrive.

Notes:
- Maintains server-side conversation state using Responses API (store + previous_response_id)
- Uses the same prompt template and optional RAG context as the non-streaming route
- Appends final assistant message to in-memory history when stream completes

##### GET /threads/{thread_id}/messages
Get conversation history for a thread.

**Query Parameters:**
- `limit`: integer (optional, default: 50)
- `offset`: integer (optional, default: 0)

**Response:**
```json
{
  "thread_id": "string (UUID)",
  "messages": [
    {
      "message_id": "string (UUID)",
  "thread_id": "string (UUID)",
      "role": "user|assistant",
      "content": "string",
      "timestamp": "string (ISO 8601)"
    }
  ],
  "total_count": "integer"
}
```

##### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "string (ISO 8601)"
}
```

### Data Models

#### Chat (Pydantic)
```python
class ChatRequest(BaseModel):
  message: str
  previous_response_id: Optional[str] = None

class ChatResponse(BaseModel):
  response_id: str
  message: str
  timestamp: str
```

#### Thread (Pydantic)
```python
class Thread(BaseModel):
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int

class CreateThreadRequest(BaseModel):
    title: Optional[str] = None

class CreateThreadResponse(BaseModel):
    thread_id: str
    title: str
    created_at: str
    updated_at: str
```

#### Message (Pydantic)
```python
class Message(BaseModel):
    message_id: str
    thread_id: str
  role: str  # "user" | "assistant"
    content: str
    timestamp: str

class SendMessageRequest(BaseModel):
    message: str

class SendMessageResponse(BaseModel):
    message_id: str
    thread_id: str
    user_message: str
    assistant_response: str
    timestamp: str

class GetMessagesResponse(BaseModel):
    thread_id: str
    messages: List[Message]
    total_count: int
```

#### Health (Pydantic)
```python
class HealthResponse(BaseModel):
    status: str
    timestamp: str
```

### Project Structure

```
advanced-ai-applications/
├── agents/
│   └── dreamfarm-agent/            # Main DreamFarm marketplace agent
│       ├── src/
│       │   ├── main.py             # FastAPI app (routes, CORS)
│       │   ├── models/             # Pydantic models (chat, thread, health)
│       │   ├── services/           # OpenAI, RAG, config, templates
│       │   ├── templates/          # Jinja2 prompts
│       │   └── utils/
│       ├── tests/
│       ├── docs/
│       └── scripts/
├── data/
│   ├── processed/                  # Generated data (e.g., Parquet)
│   ├── scripts/                    # ETL, embeddings, import
│   └── source_json/                # Sample source data
├── deploy/
│   ├── azure/
│   ├── kubernetes/
│   └── local/                      # docker-compose and local setup
├── frontend/
│   ├── public/                     # Runtime config (config.js), assets
│   ├── src/                        # React app (components, services)
│   └── scripts/
├── docs/                           # Design and project docs (contents not listed)
├── lessons/                        # Instructions for individual lessons
├── scripts/                        # Miscellaneous scripts such as cherry pick script
├── postgresql/                     # PostgreSQL database Dockerfile for creating image with extensions binaries
├── tools/                          # AI tools such as MCP servers and APIs
└── (root files not listed)
```

### Service Responsibilities

#### DreamFarm Agent (Port 8001)
**Purpose**: Main AI agent for the Dream Farm marketplace
- **LLM Integration**: Azure OpenAI Service or OpenAI API communication
- **Session API**: Lightweight `/threads` endpoints for session handles; Responses API maintains conversation state
- **Business Logic**: Dream Farm marketplace domain logic
- **MCP Integration**: Tool calling and coordination (Lesson 2+)
- **CORS Handling**: Frontend communication
- **API Endpoints**: All REST endpoints for the Dream Farm application
- **Agent Orchestration**: Coordinate with other agents (Lesson 8+)

#### Future Agents (Later Lessons)
- **Chef Agent** (Lesson 8): Specialized agent for cooking/catering services
- **Other Domain Agents**: Additional specialized agents as business grows

#### Infrastructure (Later Lessons)
- **nginx/Envoy** (Lesson 10): For production load balancing, SSL, static files
- **Authentication**: Can be added as middleware to agents or separate service

### Tool Integration Strategy & Function Interfaces

#### MCP vs REST API Decision

**Use MCP Protocol for:**
- RAG/knowledge base queries (Lesson 3+)
- Web search integration (Lesson 2)
- External API integrations (Lesson 2)
- Data processing tools
- Knowledge graph queries (Lesson 4)
- Multi-agent communication (Lesson 8)

**Use Direct Integration for:**
- Database connections (PostgreSQL with pgvector)
- Authentication/authorization
- Session management
- File uploads/storage
- Core business logic
- Frontend-backend communication

#### Benefits of MCP-First Approach

1. **Standardized Interface**: All tools speak the same protocol
2. **AI-Native Design**: MCP is designed specifically for AI tool integration
3. **Composability**: Easy to add/remove tools without changing core application
4. **Independent Development**: Tools can be developed and deployed separately
5. **Educational Value**: Students learn modern AI application patterns
6. **Future-Proof**: Aligns with emerging AI tooling standards

This approach allows the API Gateway to remain focused on core business logic while delegating specialized tasks to dedicated MCP servers.

#### AI Tools Overview

Tools live under `tools/` (standalone services / MCP servers) or as internal function-call interfaces exposed to the LLM. Scope:

- mcp_public_farmer_tools (MCP, Python)
  - Purpose: simple utility/tooling for the assistant without external dependencies.
  - Implementation: Python using the MCP server library; exposed over stdio for local development and pluggable into the agent (Lesson 2+).
  - Tools
    - get_current_time() -> string current time in ISO 8601
    - get_seasonal_tips() -> list of up to 10 typical seasonal products for the current period (mocked, e.g., strawberries in summer)
    - get_weather(country: string, city: string) -> JSON mock with fields: temperature, humidity, wind, precipitation
  - Notes: returns mock data (no network calls); great for demos and deterministic testing.

- api_stock (HTTP API)
  - Purpose: read-only facade over the relational `stock` table for quick lookups from the assistant or other services.
  - Request: accepts an array of productIds; Response: JSON map/array with each productId’s current on-stock quantity and timestamp.
  - Integration: direct HTTP calls from the DreamFarm Agent. Optionally wrapped as an MCP tool later.
  - Notes: read-only; aligns with `data/source_json/stock.json` shapes (producerId, productId, onStock).

- Tavily Remote MCP (SaaS web search)

#### Internal Function-Call Interfaces (Agentic Retrieval)
- `semantic_search` (arguments: text: string) – semantic vector similarity (HyDE capable) with VIP fence.
- `keyword_search` (arguments: keywords: string[]) – full‑text search over `fts_document` / `fts_combined` with VIP fence.

Return schema (for each call) list of products `[product_id, product_name, producer_name, score, is_vip]`.

No backend fusion: model may call tools multiple times and integrate / compare results itself.

Telemetry: Each invocation emits `DF_META` line (`search_tool_call`) with counts pre/post VIP filter.

#### Graph Traversal Retrieval (Planned – Lesson 4 Final Task)

Objective: Expose the knowledge graph (Apache AGE) as an additional retrieval surface complementary to vector/FTS tools, enabling the LLM to:
- Start from abstract user intent → hypothesize likely higher‑level concepts (categories, cuisines, allergens, certifications) → fan out to candidate products (breadth-first taxonomy expansion).
- Start from a specific product (identified via prior retrieval/tool output or user mention) → walk outward to discover closely related products sharing multiple relationship traits (depth-first similarity traversal).

Feature Flag:
`ENABLE_GRAPH_SEARCH` (default: false). When true and agentic search enabled, two new function-call tools are registered.

Tools (proposed JSON schemas):
1. `graph_bfs_taxonomy_search` arguments:
  - `hypothesis_text: string` – free-form natural language; model may embed conceptual cues (e.g., "looking for mild Italian cheeses without nuts")
  - `max_hops: int` (optional, default 2, max 3) – breadth expansion depth (Category/Cuisine → Product, optionally via Producer)
  - `limit: int` (optional, default 10, max 25) – cap on returned products
  Returns: `{ products: [ { product_id, product_name, producer_name, via: [conceptIds], match_score } ], concepts: [ { id, type, name } ] }`

2. `graph_dfs_similarity_search` arguments:
  - `product_id: string` (UUID – starting product)
  - `max_depth: int` (optional, default 3, max 4) – DFS depth exploring similarity edges (shared Category/Cuisine/Allergen/Certification/Producer)
  - `limit: int` (optional, default 10, max 25)
  Returns: `{ start_product: { product_id, product_name }, similar_products: [ { product_id, product_name, shared_traits: [ { kind, id, name } ], similarity_score } ] }`

##### Clarification: DFS Similarity Tool Rationale
The `graph_dfs_similarity_search` tool intentionally centers on trait overlap (Categories, Cuisines, Certifications, Allergens, Producer) to surface products that are *structurally* similar in the knowledge graph. It does NOT perform semantic embedding similarity itself — that happens earlier (e.g., via semantic product search) and this DFS tool refines or broadens recommendations by relationship structure. Its scoring (weights per trait family) is documented below; no changes needed at this time.

---

### Breadth-First Taxonomy Search (Updated Design: Semantic Concept Matching First)

Earlier draft examples showed ad‑hoc text matching (ILIKE / CONTAINS) against concept names/descriptions. We are replacing that with a semantic concept selection phase to produce more robust recall and nuanced alignment with user intent. This section supersedes any prior LIKE‑based concept matching references.

#### Design Motivation
User queries describing desired attributes (e.g., “mild Italian cheese without nuts certified organic”) combine multiple abstract facets. Literal substring filtering is brittle (pluralization, synonyms, language drift). A semantic embedding layer over higher‑level concept entities (Category, Cuisine, Certification, Allergen) provides resilient matching and ranking before graph expansion.

#### Key Decisions
1. Do **not** store embeddings directly inside AGE vertex properties for similarity search. While AGE lives in PostgreSQL, AGE itself does not expose native vector indexing operators; we instead leverage **pgvector** in dedicated relational tables and then bridge via shared IDs.
2. Maintain a **unified concept embeddings table** covering all supported concept types instead of one table per type to simplify maintenance and multi‑type ranking.
3. Keep graph vertices lean (IDs + minimal display properties) and perform semantic retrieval outside the graph; then pass selected vertex IDs into controlled BFS expansion.
4. Support **negative constraints** (e.g., “without nuts”, “no dairy”) via lightweight structured extraction so we can exclude or penalize conflicting traits early.
5. Provide explicit configurability for per‑type weights and similarity thresholds to tune precision vs. recall.

#### Data Structures (Relational Layer)
`concept_embeddings` (new table – conceptual schema):
| Column | Type | Notes |
| ------ | ---- | ----- |
| concept_type | enum(text) | one of: category, cuisine, certification, allergen |
| concept_id | text/uuid | Matches the corresponding vertex property (e.g., categoryId) |
| name | text | Canonical name |
| description | text | Concise neutral description (same source as graph) |
| normalized_text | text | Preprocessed (lowercased, de-accented) concatenation used for embedding source (name + description) |
| embedding | vector(2000) | pgvector embedding (text-embedding-3-large) |
| created_at | timestamptz | audit |
| updated_at | timestamptz | audit |

Indexes / Performance:
- HNSW index on `embedding` (cosine) for similarity.
- Composite btree on (`concept_type`, `concept_id`).
- Optional partial index for active concepts if future soft deletes are introduced.

#### Environment / Config Additions
| Variable | Purpose | Default |
| -------- | ------- | ------- |
| `GRAPH_BFS_CONCEPT_TOP_K_PER_TYPE` | Max semantic matches kept per type before expansion | 5 |
| `GRAPH_BFS_MIN_SIMILARITY` | Minimum similarity (cosine) to accept a concept | 0.75 |
| `GRAPH_BFS_GLOBAL_MAX_CONCEPTS` | Absolute cap after merging types (pre‑BFS) | 15 |
| `GRAPH_BFS_TYPE_WEIGHTS` | JSON map of weights, e.g. `{"category":1.0,"cuisine":1.0,"certification":0.6,"allergen":0.5}` | (shown) |
| `GRAPH_BFS_NEGATIVE_ENFORCE` | If true, exclude products violating negative constraints | true |
| `GRAPH_BFS_NEGATIVE_PENALTY` | If enforcement is soft, scalar penalty applied | 0.8 |
| `GRAPH_BFS_PRODUCT_DIVERSITY_PENALTY` | Penalize overrepresentation of a single concept | 0.15 |
| `GRAPH_BFS_SCORE_NORMALIZE` | Normalize final product scores to 0..1 | true |

#### Input & Structured Extraction
Tool input: `hypothesis_text` (free form), `max_hops`, `limit`.

Pre‑processing (LLM structured extraction schema conceptually):
```
{
  "positive_cues": ["mild", "Italian", "cheese", "organic"],
  "negative_cues": ["nuts"]
}
```
This step is optional but improves negative constraint handling. If extraction fails, proceed with raw text embedding and skip negative filtering (fail‑open, transparent in telemetry).

#### Semantic Concept Selection Algorithm (Pseudo Steps)
1. Receive `hypothesis_text`.
2. (Optional) Extract positive/negative cues.
3. Generate embedding for `hypothesis_text` (single pass; do **not** split unless text length exceeds model safe window – future optimization).
4. Perform vector similarity search over `concept_embeddings` retrieving top `GRAPH_BFS_CONCEPT_TOP_K_PER_TYPE * (#types)` raw candidates.
5. Group by `concept_type`, apply similarity threshold & per‑type top‑k trimming.
6. Merge groups, apply `GRAPH_BFS_GLOBAL_MAX_CONCEPTS` cap using interleaving for type diversity (round‑robin or weighted).
7. Record telemetry: counts per type, filtered out below threshold, final selected.
8. Produce ordered concept seed list with (concept_id, concept_type, similarity_score, weight = type_weight * similarity_score).

#### BFS Expansion (Concept → Product)
1. Initialize frontier with selected concept vertex IDs (Category/Cuisine/Certification). Allergens appear only if user *explicitly* wants inclusion; otherwise they act mainly as negative constraints (avoidance). We keep allergen vertices optional in frontier to avoid recommending allergen-rich items when user intent is exclusionary.
2. Execute constrained breadth expansion up to `max_hops` (default 2):
   - Hop 1: Concept → Product edges (`HAS_CATEGORY`, `HAS_CUISINE`, `HAS_CERTIFICATION`).
   - Optional Hop 2 (only if room and diversity low): Producer pivot (Concept → Product ← Producer → Product) to widen variety.
3. Collect candidate product IDs with per‑product matched concept set (and path metadata for explainability).
4. Early stop if candidate set exceeds safety bound (e.g., 5 * requested limit) – mark `truncated=true` in telemetry and continue to scoring subset.

#### Product Scoring (Heuristic)
For each candidate product:
```
base_score = Σ (concept_weight for each matched concept)
trait_coverage = matched_concept_count / min(total_selected_concepts, coverage_denominator)
diversity_adjustment = (1 - repetition_factor) * GRAPH_BFS_PRODUCT_DIVERSITY_PENALTY
score = base_score * (0.5 + 0.5 * trait_coverage) + diversity_adjustment
```
Negative constraints:
* If `GRAPH_BFS_NEGATIVE_ENFORCE=true` and product contains excluded allergen → drop.
* Else apply `score *= GRAPH_BFS_NEGATIVE_PENALTY`.
Normalize scores if configured.

Return top `limit` products with:
```
{
  "products": [ { product_id, product_name, producer_name, via: [concept_ids], match_score } ],
  "concepts": [ { id, type, name, similarity_score } ],
  "meta": { truncated, negative_constraints_applied, concept_counts, elapsed_ms }
}
```

#### VIP Filtering Interaction
Apply VIP fencing *after* BFS product scoring but before final truncation: remove VIP products if user not VIP, then re-rank remaining (no score recomputation unless large removals force re-normalization). Telemetry records pre/post counts.

#### Observability & Telemetry
`DF_META` line (kind: `graph_tool_call`) fields:
```
{
  "tool": "graph_bfs_taxonomy_search",
  "concept_candidates": {"category": N1, "cuisine": N2, ...},
  "concept_selected": total_selected,
  "products_expanded": raw_product_count,
  "products_after_vip": filtered_count,
  "negative_constraints": {"count": M, "mode": "enforce|penalize|none"},
  "truncated": bool,
  "elapsed_ms": int
}
```

#### Failure & Fallback Behavior
| Condition | Action |
| --------- | ------ |
| No concept passes threshold | Fallback to hybrid product RAG (semantic + keyword) and note `concept_fallback=true` |
| Empty product expansion | Return empty list (not an error) + suggestion for user clarification |
| Extraction timeout | Skip extraction; proceed with raw text embedding |
| Vector search timeout | Reduce per-type top-k (halve) and retry once; else fallback |

#### Advantages of This Approach
- Robust to synonymy / paraphrasing (“nut-free”, “without nuts”).
- Encourages explainable output (assistant can cite matched concept names and why chosen).
- Clean separation of concerns: semantic retrieval (relational + pgvector) → structural expansion (graph) → heuristic fusion.
- Extensible: new concept layers (Season, DietaryPattern) simply add rows to `concept_embeddings` and graph vertices/edges.

#### Future Enhancements
1. Adaptive threshold: dynamic similarity floor based on distance gap between top and median candidate.
2. Embedding caching: reuse embedding for subsequent refinement turns if user rephrases intent.
3. Per‑concept decay: reduce weight for extremely common concepts (e.g., “organic”) using inverse document frequency style factor.
4. Lightweight learned reranker: train small logistic model on interaction feedback to replace heuristic scoring.
5. Multi‑lingual support: add language column + parallel embeddings; pick embedding space by detected query language.

---

### Summary of Graph Tools After Update
| Tool | Primary Purpose | Similarity Basis | Expansion Mode |
| ---- | ----------------| ---------------- | -------------- |
| `semantic_search` | Product-level semantic retrieval | Vector (products.embedding) | None (direct) |
| `keyword_search` | Product full-text retrieval | FTS rank | None |
| `graph_bfs_taxonomy_search` | Abstract intent → concept semantic match → product breadth | Vector (concept_embeddings) + graph structure | BFS (concept-frontier) |
| `graph_dfs_similarity_search` | Given product → structurally similar products | Graph trait overlap weights | DFS-style trait aggregation |

This updated design removes dependence on ad‑hoc textual LIKE scanning for high‑level concepts and formally introduces a semantic concept retrieval layer feeding the BFS expansion.

Cypher Query Patterns (conceptual):

Breadth-First (taxonomy expansion):
```
-- Pseudocode Cypher (executed through cypher('dreamfarm', $$ ... $$))
// 1) Identify candidate concept vertices by fuzzy/ILIKE matching names/descriptions against tokens derived from hypothesis_text
MATCH (c:Category)
WHERE toLower(c.name) CONTAINS $token OR toLower(c.description) CONTAINS $token
WITH DISTINCT c LIMIT 40
OPTIONAL MATCH (c)<-[:HAS_CATEGORY]-(p:Product)
OPTIONAL MATCH (p)-[:PRODUCES]-(:Producer) // lightweight enrichment
RETURN c.categoryId AS concept_id, c.name AS concept_name, collect(DISTINCT p.productId)[0..$limit] AS product_ids
```
Follow-up: Resolve `product_ids` to relational `products` table for names + ranking heuristic:
`match_score = (#matched_concepts_for_product) + 0.1 * diversity_bonus`.

Depth-First (similarity from a product):
```
// Gather traits of the starting product
MATCH (p:Product {productId: $product_id})
OPTIONAL MATCH (p)-[:HAS_CATEGORY]->(cat:Category)
OPTIONAL MATCH (p)-[:HAS_CUISINE]->(cui:Cuisine)
OPTIONAL MATCH (p)-[:CONTAINS_ALLERGEN]->(alg:Allergen)
OPTIONAL MATCH (p)<-[:PRODUCES]-(prod:Producer)
WITH p, collect(DISTINCT cat) AS cats, collect(DISTINCT cui) AS cuis,
    collect(DISTINCT alg) AS algs, prod
// Find other products sharing traits
MATCH (other:Product)
WHERE other <> p
OPTIONAL MATCH (other)-[:HAS_CATEGORY]->(cat2:Category)
OPTIONAL MATCH (other)-[:HAS_CUISINE]->(cui2:Cuisine)
OPTIONAL MATCH (other)-[:CONTAINS_ALLERGEN]->(alg2:Allergen)
OPTIONAL MATCH (other)<-[:PRODUCES]-(prod2:Producer)
WITH other,
    size([x IN cats WHERE x IN collect(DISTINCT cat2)]) AS cat_overlap,
    size([x IN cuis WHERE x IN collect(DISTINCT cui2)]) AS cui_overlap,
    size([x IN algs WHERE x IN collect(DISTINCT alg2)]) AS alg_overlap,
    CASE WHEN prod2 = prod THEN 1 ELSE 0 END AS same_producer
WITH other,
    (cat_overlap * 1.0) + (cui_overlap * 0.8) + (alg_overlap * 0.5) + (same_producer * 0.3) AS similarity_score,
    cat_overlap, cui_overlap, alg_overlap, same_producer
WHERE similarity_score > 0
ORDER BY similarity_score DESC
LIMIT $limit
RETURN other.productId AS product_id, similarity_score, cat_overlap, cui_overlap, alg_overlap, same_producer
```
Post-processing: build `shared_traits` array by re-matching only required trait vertices for top results.

Scoring Rationale:
- Categories & cuisines express conceptual similarity → higher weights.
- Allergens reflect composition overlap (useful but weaker for recommendation diversity).
- Same producer suggests catalog adjacency (mild boost; avoids monopolizing list).

Security / Fencing:
- VIP filtering applied after relational join (same rules as other tools) unless future policy extends VIP property to graph vertices.
- Depth-first traversal restricts max node/edge expansions (`max_depth`, LIMIT) to avoid runaway cost.

Error Handling & Timeouts:
- Each graph tool call bounded by server-side statement timeout (e.g., 2s) – on timeout: return partial results (if any) with `incomplete=true` meta.
- Empty match gracefully returns empty arrays (never an error unless Cypher failure).

Observability:
- Emit `DF_META` lines with `graph_tool_call` including: tool_name, elapsed_ms, candidate_concepts, expanded_products, post_vip_count, truncated (bool).
- Log raw Cypher (parameterized form) at DEBUG only (no sensitive data) for troubleshooting.

Integration Flow (LLM side):
1. Model may call `semantic_search` first to anchor concrete product(s).
2. Then call `graph_dfs_similarity_search` with a chosen `product_id` to propose related products.
3. Alternatively, model starts with `graph_bfs_taxonomy_search` when the user provides abstract intent lacking explicit product names.
4. Final answer cites concept names or shared traits for explainability (encouraged by tool descriptions).

Future Enhancements:
- Add hybrid reranking (vector similarity + graph similarity) for candidate fusion.
- Introduce precomputed similarity edges (RELATED) from batch analytics to speed DFS queries.
- Cache high-frequency taxonomy BFS expansions keyed by normalized hypothesis tokens.

Testing Strategy:
- Unit tests: mock Cypher responses to validate ranking & post-processing.
- Integration tests (flagged): require running AGE-enabled PostgreSQL; will skip if `ENABLE_GRAPH_SEARCH` false or AGE absent.
- Performance smoke: assert BFS/DFS tool calls complete under threshold on sample dataset.

Documentation: This section formalizes design prior to implementation; code will adhere to schemas & flags above.
  - Purpose: real-time internet search and extraction to augment answers beyond local data.
  - Integration: connect to Tavily’s remote MCP server as an MCP tool in the LLM call. Server URL: `https://mcp.tavily.com/mcp/?tavilyApiKey=<your-api-key>` (requires a Tavily API key).
  - Capabilities: search, extract, map, crawl (we primarily use `tavily-search` and `tavily-extract`).
  - Notes: used only when web context is needed; disabled by default in early lessons to keep flows deterministic.

### Runtime Configuration Pattern

The frontend uses a runtime configuration approach to support different environments without rebuilding the application:

#### Development Flow
1. **Local Development**: Manually edit `public/config.js` with local backend URL
2. **Docker Build**: Application is built once with a config template
3. **Container Start**: Startup script generates `config.js` from environment variables
4. **Application Load**: React app reads configuration from `window.APP_CONFIG`

#### Implementation Details

**Config Template (`public/config.js.template`):**
```javascript
window.APP_CONFIG = {
  BACKEND_URL: '${REACT_APP_BACKEND_URL}',
  API_VERSION: '${REACT_APP_API_VERSION}'
};
```

**Startup Script (`scripts/generate-config.sh`):**
```bash
#!/bin/sh
# Replace environment variables in config template
envsubst < /app/public/config.js.template > /app/public/config.js
# Start the web server
exec "$@"
```

**React Service (`src/services/api.ts`):**
```typescript
// Access runtime configuration
const config = (window as any).APP_CONFIG;
const BACKEND_URL = config?.BACKEND_URL || 'http://localhost:8001';
```

This pattern enables:
- **Build Once, Deploy Anywhere**: Same Docker image works in all environments
- **Runtime Flexibility**: Configure backend URLs without rebuilding
- **Development Simplicity**: Manual config editing for local development

### Development Workflow

1. **DreamFarm Agent Setup** (Start here for Lesson 1):
   - Use `uv` to create virtual environment and install dependencies
   - Configure `.env` file with Azure OpenAI or OpenAI credentials and CORS origins
   - Run with `uv run python -m uvicorn src.main:app --reload --port 8001`

2. **Frontend Setup**:
   - Install Node.js dependencies
   - For local development: configure `public/config.js` with DreamFarm Agent URL (port 8001)
   - Run with development server on port 3000

3. **MCP Tools Setup** (Lesson 2+):
   - Each MCP server runs as separate process/container
   - DreamFarm Agent connects to MCP servers via MCP protocol
   - Tools can be developed and deployed independently

4. **Multi-Agent Setup** (Lesson 8+):
   - Chef Agent runs as separate service
   - DreamFarm Agent orchestrates communication between agents
   - Each agent can have its own MCP tools

5. **Production Deployment** (Lesson 10):
   - Optional: Add nginx/Envoy for load balancing and SSL
   - Deploy to Kubernetes with proper service discovery
   - Use infrastructure as code (Terraform)

### Security Considerations

- Environment variables for sensitive data (API keys, endpoints)
- No hardcoded credentials in source code
- CORS configuration for frontend-backend communication
- Input validation using Pydantic models
- JWT verification (Keycloak) when `REQUIRE_AUTH=true`
- Role / VIP enforcement at data access layer (defense-in-depth; currently only applied to agentic tool queries)

#### Authentication & Authorization
Keycloak provides OIDC tokens with roles; backend middleware validates JWT (issuer & audience), extracts `user_id` (sub) and VIP status (role membership or explicit `is_vip` claim). Frontend performs Authorization Code + PKCE, stores token in memory, attaches Bearer header. Unauthorized or invalid token requests return 401 (when auth required). VIP fencing implemented via SQL predicate; LLM is instructed but not trusted to self‑filter.

### Future Enhancements

This basic architecture will be extended with:
- RAG (Retrieval-Augmented Generation) with PostgreSQL and pgvector
- MCP (Model Context Protocol) for external tools
- Multimodal capabilities (voice, images, documents)
- Knowledge graphs and advanced search
- Multi-agent systems
- Security and evaluation frameworks
- Kubernetes deployment and observability

### Notes

- Start extremely simple - no RAG, no database, just basic chat functionality
- Focus on clean architecture that can be easily extended
- Use established patterns and frameworks
- Document all public APIs and methods
-- Follow project coding standards throughout development
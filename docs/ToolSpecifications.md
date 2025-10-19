# Tool Specifications & Integration Strategy

This document provides complete specifications for all tools (internal functions, MCP servers, external APIs) available to AI agents in the Dream Farm platform.

> **Note**: For high-level tool integration overview, see [Design.md](./Design.md#8-tool-integration-strategy). For retrieval-specific tools, see [RetrievalArchitecture.md](./RetrievalArchitecture.md). For graph tools, see [KnowledgeGraph.md](./KnowledgeGraph.md).

---

## Table of Contents

- [Tool Integration Philosophy](#tool-integration-philosophy)
- [Internal Function Tools](#internal-function-tools)
- [MCP Server Tools](#mcp-server-tools)
- [External API Tools](#external-api-tools)
- [Tool Registration & Feature Flags](#tool-registration--feature-flags)
- [Observability & Telemetry](#observability--telemetry)

---

## Tool Integration Philosophy

### MCP vs REST API Decision

**Use MCP Protocol for:**
- RAG/knowledge base queries
- Web search integration
- External API integrations
- Data processing tools
- Knowledge graph queries
- Multi-agent communication

**Use Direct Integration for:**
- Database connections (PostgreSQL with pgvector)
- Authentication/authorization
- Session management
- File uploads/storage
- Core business logic
- Frontend-backend communication

### Benefits of MCP-First Approach

1. **Standardized Interface**: All tools speak the same protocol
2. **AI-Native Design**: MCP is designed specifically for AI tool integration
3. **Composability**: Easy to add/remove tools without changing core application
4. **Independent Development**: Tools can be developed and deployed separately
5. **Educational Value**: Students learn modern AI application patterns
6. **Future-Proof**: Aligns with emerging AI tooling standards

This approach allows the agent to remain focused on core business logic while delegating specialized tasks to dedicated MCP servers.

---

## Internal Function Tools

These tools are registered directly in the agent's OpenAI function call interface (not via MCP).

### semantic_search

**Purpose**: Semantic vector similarity search over products using embeddings.

**Arguments:**
```json
{
  "text": "string - Natural language query describing desired products"
}
```

**Returns:**
```json
{
  "products": [
    {
      "product_id": "uuid",
      "product_name": "string",
      "producer_name": "string",
      "description": "string",
      "score": "float (0-1 similarity)",
      "is_vip": "boolean"
    }
  ],
  "count": "integer"
}
```

**Features:**
- Uses pgvector cosine similarity on `products.embedding`
- VIP fencing enforced at SQL layer (`WHERE is_vip = false OR :user_is_vip`)
- Optional HyDE (Hypothetical Document Embedding) for improved recall
- Configurable similarity threshold and max results

**Telemetry:**
- Emits `DF_META` with `search_tool_call` type
- Includes: count, VIP-filtered count, threshold, elapsed_ms

**Configuration:**
- `RAG_SIMILARITY_THRESHOLD` (default: 0.3)
- `RAG_MAX_RESULTS` (default: 3)
- `AGENTIC_SEARCH_MAX_RESULTS` (default: 10)

See [RetrievalArchitecture.md#semantic-search](./RetrievalArchitecture.md) for implementation details.

---

### keyword_search

**Purpose**: Full-text search over products using PostgreSQL FTS.

**Arguments:**
```json
{
  "keywords": ["string", "array", "of", "keywords"]
}
```

**Returns:**
```json
{
  "products": [
    {
      "product_id": "uuid",
      "product_name": "string",
      "producer_name": "string",
      "description": "string",
      "score": "float (FTS rank)",
      "is_vip": "boolean"
    }
  ],
  "count": "integer"
}
```

**Features:**
- Uses GIN index on `fts_document` (tsvector)
- VIP fencing enforced at SQL layer
- Ranked by `ts_rank_cd()` relevance
- Fallback when semantic search fails or insufficient results

**Telemetry:**
- Emits `DF_META` with `search_tool_call` type
- Includes: keywords, count, VIP-filtered count

**Configuration:**
- `AGENTIC_SEARCH_MAX_RESULTS` (default: 10)

---

### memory_search

**Purpose**: Semantic search over user's own conversation summaries.

**Arguments:**
```json
{
  "query": "string - What to search for in memory",
  "k": "integer (optional, default: 3) - Number of results"
}
```

**Returns:**
```json
{
  "summaries": [
    {
      "summary_id": "uuid",
      "summary": "string - Summary text",
      "salient_facts": ["array", "of", "facts"],
      "created_at": "ISO 8601 timestamp",
      "score": "float (similarity)"
    }
  ],
  "count": "integer"
}
```

**Features:**
- Hard user_id constraint: `WHERE user_id = :current_user`
- Vector similarity over `conversation_summaries.embedding`
- Privacy-preserving (no cross-user leakage)
- Used for personalization and context recall

**Telemetry:**
- Emits `DF_META` with `memory_search` type
- Includes: k, hits, elapsed_ms

**Configuration:**
- `MEMORY_SEARCH_ENABLED` (default: true)

See [MemoryPersonalization.md#memory-search](./MemoryPersonalization.md) for details.

---

### memory_write_profile

**Purpose**: Write-only personalization patch for user profile.

**Arguments:**
```json
{
  "patch": {
    "set": {"diet": {"vegetarian": true}},
    "append": {"dislikes": ["kozí sýr"]},
    "remove": ["temporary_note"]
  }
}
```

**Merge Rules:**
1. **set**: Deep recursive merge – dict values merged, primitives overwrite
2. **append**: Ensure target is list, append only unique primitives (idempotent)
3. **remove**: Delete listed top-level fields if present

**Returns:**
```json
{
  "applied": true,
  "touched": ["diet", "dislikes"],
  "current": {
    "diet": {"vegetarian": true},
    "dislikes": ["kozí sýr"]
  }
}
```

**Usage Constraints (prompt-enforced):**
- Invoke only for explicit user request ("remember", "save", "pamatuj si")
- No ephemeral / session-only states
- Aggregate multiple changes into one call per turn
- Never transmit entire profile back – only delta

**Safety:**
- Malformed sections ignored (never raises to calling tool loop)
- Future: rate limiting, audit trail, PII filtering

See [MemoryPersonalization.md#profile-management](./MemoryPersonalization.md) for details.

---

### graph_bfs_taxonomy_search

**Purpose**: Abstract intent → concept semantic match → product breadth via graph traversal.

**Arguments:**
```json
{
  "hypothesis_text": "string - Free-form natural language describing desired attributes",
  "max_hops": "integer (optional, default: 2, max: 3) - Breadth expansion depth",
  "limit": "integer (optional, default: 10, max: 25) - Max products returned"
}
```

**Returns:**
```json
{
  "products": [
    {
      "product_id": "uuid",
      "product_name": "string",
      "producer_name": "string",
      "via": ["concept_id1", "concept_id2"],
      "match_score": "float"
    }
  ],
  "concepts": [
    {
      "id": "string",
      "type": "category|cuisine|certification|allergen",
      "name": "string",
      "similarity_score": "float"
    }
  ],
  "meta": {
    "truncated": "boolean",
    "negative_constraints_applied": "integer",
    "concept_counts": {"category": 3, "cuisine": 2},
    "elapsed_ms": "integer"
  }
}
```

**Algorithm:**
1. Generate embedding for `hypothesis_text`
2. Semantic similarity search over `concept_embeddings` (Category, Cuisine, Certification, Allergen)
3. Select top concepts per type (configurable thresholds and weights)
4. BFS expansion from concepts to products via graph edges (`HAS_CATEGORY`, `HAS_CUISINE`, etc.)
5. Score products by concept matches + coverage + diversity
6. Apply VIP filtering and negative constraints
7. Return top products with explainability metadata

**Scoring Heuristic:**
```
base_score = Σ (concept_weight for each matched concept)
trait_coverage = matched_concept_count / min(total_selected_concepts, coverage_denominator)
diversity_adjustment = (1 - repetition_factor) * PRODUCT_DIVERSITY_PENALTY
score = base_score * (0.5 + 0.5 * trait_coverage) + diversity_adjustment
```

**Configuration:**
| Variable | Purpose | Default |
|----------|---------|---------|
| `GRAPH_BFS_CONCEPT_TOP_K_PER_TYPE` | Max semantic matches per concept type | 5 |
| `GRAPH_BFS_MIN_SIMILARITY` | Minimum similarity to accept concept | 0.75 |
| `GRAPH_BFS_GLOBAL_MAX_CONCEPTS` | Absolute cap after merging types | 15 |
| `GRAPH_BFS_TYPE_WEIGHTS` | JSON map of concept type weights | `{"category":1.0,"cuisine":1.0,"certification":0.6,"allergen":0.5}` |
| `GRAPH_BFS_NEGATIVE_ENFORCE` | Exclude products violating negative constraints | true |
| `GRAPH_BFS_NEGATIVE_PENALTY` | Soft penalty for constraint violations | 0.8 |
| `GRAPH_BFS_PRODUCT_DIVERSITY_PENALTY` | Penalize concept overrepresentation | 0.15 |

**Failure Modes:**
- No concept passes threshold → Fallback to hybrid product RAG
- Empty product expansion → Return empty list + suggestion
- Extraction timeout → Skip extraction, proceed with raw text
- Vector search timeout → Reduce per-type top-k, retry once

See [KnowledgeGraph.md#bfs-taxonomy-search](./KnowledgeGraph.md) for full specification.

---

### graph_dfs_similarity_search

**Purpose**: Given a product, find structurally similar products via trait overlap.

**Arguments:**
```json
{
  "product_id": "uuid - Starting product",
  "max_depth": "integer (optional, default: 3, max: 4) - DFS depth",
  "limit": "integer (optional, default: 10, max: 25) - Max products returned"
}
```

**Returns:**
```json
{
  "start_product": {
    "product_id": "uuid",
    "product_name": "string"
  },
  "similar_products": [
    {
      "product_id": "uuid",
      "product_name": "string",
      "shared_traits": [
        {"kind": "category", "id": "uuid", "name": "Fresh Cheese"},
        {"kind": "cuisine", "id": "uuid", "name": "Italian"}
      ],
      "similarity_score": "float"
    }
  ]
}
```

**Scoring Rationale:**
```
similarity_score = (cat_overlap * 1.0) + (cui_overlap * 0.8) + (alg_overlap * 0.5) + (same_producer * 0.3)
```

- **Categories & Cuisines**: Higher weights (conceptual similarity)
- **Allergens**: Composition overlap (weaker for diversity)
- **Same Producer**: Catalog adjacency (mild boost)

**Security:**
- VIP filtering applied after relational join
- Max node/edge expansions restricted by `max_depth` and `LIMIT`
- Statement timeout (e.g., 2s) prevents runaway queries

**Configuration:**
- `GRAPH_DFS_MAX_RESULTS` (default: 10)
- `GRAPH_SEARCH_ENABLED` (master flag)

See [KnowledgeGraph.md#dfs-similarity-search](./KnowledgeGraph.md) for full specification.

---

### query_chef_services

**Purpose**: Delegate culinary service queries to specialized Chef Agent.

**Arguments:**
```json
{
  "query": "string - User's culinary service request (chef recommendation, catering, pricing, etc.)"
}
```

**Returns:**
```json
{
  "response": "string - Chef Agent's structured or natural language response"
}
```

**Implementation:**
- HTTP POST to Chef Agent service: `http://localhost:8002/query`
- Chef Agent processes query using its own MCP tools (chef search, service search, availability, pricing, orders)
- Returns synthesized response for DreamFarm Agent to integrate

**Configuration:**
- `CHEF_AGENT_ENABLED` (default: false)
- `CHEF_AGENT_URL` (default: http://localhost:8002)

**Usage Pattern:**
1. DreamFarm Agent detects culinary service intent
2. Calls `query_chef_services` with user request
3. Chef Agent returns chef/service options
4. DreamFarm Agent synthesizes with product recommendations

See [MultiAgentArchitecture.md#agent-as-tool-pattern](./MultiAgentArchitecture.md) for details.

---

## MCP Server Tools

### mcp_public_farmer_tools

**Purpose**: Simple utility tools for the assistant without external dependencies.

**Server Type**: Python MCP server (stdio for local dev)

**Tools:**

#### get_current_time
Returns current time in ISO 8601 format.

**Arguments:** None

**Returns:**
```json
{
  "current_time": "2025-10-18T19:20:29Z"
}
```

#### get_seasonal_tips
Returns typical seasonal products for the current period (mocked data).

**Arguments:** None

**Returns:**
```json
{
  "season": "summer",
  "tips": ["strawberries", "tomatoes", "lettuce", "cucumbers", "zucchini"]
}
```

**Note**: Up to 10 seasonal products returned.

#### get_weather
Mock weather data for demo purposes.

**Arguments:**
```json
{
  "country": "string",
  "city": "string"
}
```

**Returns:**
```json
{
  "location": "Prague, Czech Republic",
  "temperature": 22,
  "humidity": 65,
  "wind": 10,
  "precipitation": 0,
  "conditions": "partly cloudy"
}
```

**Configuration:**
- `FARMER_TOOLS_ENABLED` (default: true)
- `FARMER_TOOLS_MCP_URL` (for remote deployment)

**Notes:**
- Returns mock data (no network calls)
- Great for demos and deterministic testing
- Intentionally simple for educational purposes

---

### mcp_visualization_generator

**Purpose**: Generate custom HTML visualizations, dashboards, and infographics.

**Server Type**: Python MCP server

**Tool:**

#### generate_infographic

**Arguments:**
```json
{
  "description": "string - Detailed description of desired UI component",
  "data": "object (optional) - Structured data to display",
  "style": "string (optional) - Visual style hint (card|dashboard|infographic|table|chart)"
}
```

**Returns:**
```json
{
  "html": "string - Sanitized, self-contained HTML",
  "type": "custom_ui",
  "metadata": {
    "generator": "llm",
    "model": "gpt-4o",
    "timestamp": "ISO 8601"
  }
}
```

**HTML Generation Constraints:**
- **Allowed**: Inline CSS/JS only, semantic HTML5
- **Forbidden**: External `<script src=...>`, `<link href=...>`, `eval()`, nested iframes, external form actions
- **Required**: Self-contained (no CDN, no external URLs), data URIs for images if needed

**Security Layers:**
1. **Generation**: Prompt constraints forbid external resources and dangerous JS
2. **Backend Validation**: HTML sanitization removes/rejects forbidden tags/attributes
3. **Frontend Sandboxing**: Rendered in `<iframe sandbox="allow-scripts">` with minimal permissions
4. **CSP**: Content Security Policy restricts resource loading

**Configuration:**
- `VISUALIZATION_MCP_ENABLED` (default: false)
- `VISUALIZATION_MCP_URL`
- `UI_GENERATOR_MODEL` (default: gpt-4o)
- `HTML_SANITIZER_STRICT` (default: true)
- `MAX_CUSTOM_UI_SIZE_KB` (default: 200)

See [CodeExecution.md#dynamic-ui-generation](./CodeExecution.md) for details.

---

### Tavily Web Search (Remote MCP)

**Purpose**: Real-time internet search and extraction to augment answers beyond local data.

**Server Type**: Remote MCP SaaS

**Server URL**: `https://mcp.tavily.com/mcp/?tavilyApiKey=<your-api-key>`

**Primary Tools:**

#### tavily-search
Web search with AI-optimized results.

**Arguments:**
```json
{
  "query": "string",
  "max_results": "integer (optional, default: 5)"
}
```

**Returns:**
```json
{
  "results": [
    {
      "title": "string",
      "url": "string",
      "content": "string - Relevant excerpt",
      "score": "float"
    }
  ]
}
```

#### tavily-extract
Extract structured content from URLs.

**Arguments:**
```json
{
  "urls": ["string", "array"],
  "schema": "object (optional) - Extraction schema"
}
```

**Configuration:**
- `TAVILY_ENABLED` (default: false)
- `TAVILY_API_KEY` (required when enabled)

**Notes:**
- Used only when web context needed
- Disabled by default to keep flows deterministic
- Requires API key from Tavily
- Additional capabilities: map, crawl (less commonly used)

---

## External API Tools

### Stock API (api_stock)

**Purpose**: Read-only facade over the relational `stock` table for quick stock lookups.

**Type**: Internal HTTP REST API

**Endpoint**: `POST /stock/check`

**Request:**
```json
{
  "product_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Response:**
```json
{
  "stock": [
    {
      "product_id": "uuid",
      "producer_id": "uuid",
      "on_stock": 42,
      "updated_at": "ISO 8601"
    }
  ]
}
```

**Integration:** Direct HTTP calls from DreamFarm Agent (optionally wrapped as MCP tool later).

**Configuration:**
- `STOCK_TOOL_ENABLED` (default: true)
- `STOCK_API_URL` (default: http://localhost:8011)

**Notes:**
- Read-only access
- Returns current stock quantities from PostgreSQL
- Fast lookup by product IDs

---

## Tool Registration & Feature Flags

Tools are registered conditionally based on feature flags at request time.

### Registration Flow

1. Agent receives request
2. Checks feature flags (environment variables)
3. Builds tool list based on enabled features
4. Passes tool list to OpenAI Responses API
5. Executes tool calls and returns results

### Feature Flag Summary

| Tool | Feature Flag | Default |
|------|--------------|---------|
| semantic_search | `AGENTIC_SEARCH_ENABLED` | true |
| keyword_search | `AGENTIC_SEARCH_ENABLED` | true |
| memory_search | `MEMORY_SEARCH_ENABLED` | true |
| memory_write_profile | `USER_PROFILE_ENABLED` | true |
| graph_bfs_taxonomy_search | `GRAPH_SEARCH_ENABLED` | false |
| graph_dfs_similarity_search | `GRAPH_SEARCH_ENABLED` | false |
| query_chef_services | `CHEF_AGENT_ENABLED` | false |
| get_stock | `STOCK_TOOL_ENABLED` | true |
| farmer tools (MCP) | `FARMER_TOOLS_ENABLED` | true |
| visualization (MCP) | `VISUALIZATION_MCP_ENABLED` | false |
| tavily (MCP) | `TAVILY_ENABLED` | false |

---

## Observability & Telemetry

### DF_META Event Types

Tool executions emit structured telemetry via `DF_META:` lines in streaming responses.

#### search_tool_call
```json
{
  "kind": "search_tool_call",
  "tool": "semantic_search|keyword_search",
  "count": 5,
  "vip_filtered": 2,
  "threshold": 0.3,
  "elapsed_ms": 45
}
```

#### graph_tool_call
```json
{
  "kind": "graph_tool_call",
  "tool": "graph_bfs_taxonomy_search|graph_dfs_similarity_search",
  "concept_candidates": {"category": 8, "cuisine": 5},
  "concept_selected": 7,
  "products_expanded": 25,
  "products_after_vip": 20,
  "negative_constraints": {"count": 1, "mode": "enforce"},
  "truncated": false,
  "elapsed_ms": 156
}
```

#### memory_search
```json
{
  "kind": "memory_search",
  "k": 3,
  "hits": 2,
  "elapsed_ms": 23
}
```

#### hyde_generation
```json
{
  "kind": "hyde_generation",
  "hash": "sha256:abc123...",
  "tokens": 150,
  "elapsed_ms": 350
}
```

### Structured Logging

Tool services log key events with structured format:

```
INFO search_tool=semantic_search count=5 vip_filtered=2 threshold=0.3 user_is_vip=false elapsed_ms=45
INFO graph_tool=bfs_taxonomy concept_selected=7 products=20 elapsed_ms=156
INFO memory_search k=3 hits=2 user_id=user123 elapsed_ms=23
```

### Future Metrics

- Metrics export (Prometheus/OpenTelemetry)
- Tracing spans for each tool invocation
- Tool success/failure rates
- Latency percentiles per tool
- Token usage per tool type

---

## Related Documentation

- [Design.md](./Design.md) - High-level architecture overview
- [RetrievalArchitecture.md](./RetrievalArchitecture.md) - RAG and hybrid retrieval strategies
- [KnowledgeGraph.md](./KnowledgeGraph.md) - Graph traversal algorithms and Cypher queries
- [MemoryPersonalization.md](./MemoryPersonalization.md) - Memory and user profile tools
- [MultiAgentArchitecture.md](./MultiAgentArchitecture.md) - Agent-as-tool pattern and Chef Agent
- [CodeExecution.md](./CodeExecution.md) - Code interpreter and dynamic UI generation
- [ConfigurationReference.md](./ConfigurationReference.md) - All feature flags and environment variables
- [Observability.md](./Observability.md) - Distributed tracing and observability

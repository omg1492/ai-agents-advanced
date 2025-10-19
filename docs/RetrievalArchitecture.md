# Retrieval & Search Architecture

This document provides complete specifications for all retrieval and search strategies in the Dream Farm AI platform, including semantic search, full-text search, hybrid retrieval, graph traversal, and semantic caching.

> **Note**: For high-level data architecture, see [Design.md](./Design.md#9-grounding--retrieval-data-access-stack). For tool specifications, see [ToolSpecifications.md](./ToolSpecifications.md). For graph traversal details, see [KnowledgeGraph.md](./KnowledgeGraph.md).

---

## Table of Contents

- [Overview](#overview)
- [Simple Semantic RAG](#simple-semantic-rag)
- [Hybrid Retrieval (Semantic + Keyword + RRF)](#hybrid-retrieval-semantic--keyword--rrf)
- [Agentic Tool-Based Search](#agentic-tool-based-search)
- [Semantic Caching (First-Turn Accelerator)](#semantic-caching-first-turn-accelerator)
- [VIP Fencing](#vip-fencing)
- [Retrieval Prompt Grounding Policy](#retrieval-prompt-grounding-policy)
- [Performance & Optimization](#performance--optimization)

---

## Overview

The platform provides multiple complementary retrieval modes that can be used independently or in combination:

1. **Simple Semantic RAG** - Vector similarity search with prompt injection
2. **Hybrid RAG** - Semantic + keyword with Reciprocal Rank Fusion (RRF)
3. **Agentic Tool-Based Search** - LLM orchestrates multiple retrieval tools
4. **Graph-Augmented Retrieval** - Knowledge graph traversal (see [KnowledgeGraph.md](./KnowledgeGraph.md))
5. **Semantic Caching** - First-turn question acceleration

**Retrieval Modes by Feature Flag:**

| Mode | Feature Flag | Default | Use Case |
|------|--------------|---------|----------|
| Simple RAG | `ENABLE_RAG=true` | true | Basic semantic retrieval |
| Hybrid RAG | `ENABLE_RAG=true` | true | Enhanced recall (semantic + keyword) |
| Agentic Search | `AGENTIC_SEARCH_ENABLED=true` | true | LLM-orchestrated multi-tool retrieval |
| Graph Search | `GRAPH_SEARCH_ENABLED=true` | false | Concept expansion and similarity |
| Semantic Cache | `SEMANTIC_CACHE_ENABLED=true` | true | First-turn acceleration |

---

## Simple Semantic RAG

### Purpose

Baseline retrieval using vector similarity to find relevant products for user queries.

### Architecture

1. User query → Generate embedding (text-embedding-3-large)
2. Vector similarity search (cosine) over `products.embedding` using pgvector
3. Top N results (similarity ≥ threshold) → Format as `<relevant_products>` block
4. Inject into system prompt
5. LLM generates response grounded in retrieved products

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_RAG` | true | Enable semantic search |
| `RAG_SIMILARITY_THRESHOLD` | 0.3 | Minimum cosine similarity (0.0-1.0, higher = stricter) |
| `RAG_MAX_RESULTS` | 3 | Maximum products to retrieve |

### SQL Query Pattern

```sql
SELECT 
    product_id,
    product_name,
    producer_name,
    product_description,
    1 - (embedding <=> :query_embedding) AS similarity_score
FROM products
WHERE 1 - (embedding <=> :query_embedding) >= :threshold
ORDER BY similarity_score DESC
LIMIT :max_results;
```

### Prompt Injection Format

```
<relevant_products>
Product 1: [name] by [producer]
Description: [description]
Similarity: 0.85

Product 2: [name] by [producer]
Description: [description]
Similarity: 0.72

[... up to RAG_MAX_RESULTS products ...]
</relevant_products>
```

### Performance

- **HNSW Index**: Fast approximate nearest neighbor search
- **Typical Latency**: 10-50ms for top-10 search
- **Accuracy**: Recall@10 typically >95% vs exact search

---

## Hybrid Retrieval (Semantic + Keyword + RRF)

### Purpose

Combine semantic understanding (embeddings) with exact keyword matching (full-text search) to improve recall and relevance.

### Architecture

#### Pipeline

1. **Semantic Pass**: Vector similarity → ranked list **S**
   - Generate embedding for user query
   - Cosine similarity search over `products.embedding`
   - Ranked by similarity score

2. **Keyword Extraction**: LLM structured output
   - Extract normalized keywords (product names, producer names, nouns)
   - Pydantic schema: `ExtractedKeywords(keywords: List[str])`
   - Robust to extraction failure (fallback to semantic only)

3. **Full-Text Pass**: FTS search → ranked list **K**
   - Build `to_tsquery` from extracted keywords
   - Search over `fts_document` (tsvector, unaccent + simple config)
   - Ranked by `ts_rank_cd()`

4. **Fusion (RRF)**: Merge S and K → fused list **F**
   - Reciprocal Rank Fusion (RRF) with k=60
   - Formula: `score = Σ 1/(60 + rank)`
   - Top N = `RAG_MAX_RESULTS`

5. **Prompt Injection**: Format F as `<relevant_products>` block

### Keyword Extraction Schema

```python
class ExtractedKeywords(BaseModel):
    keywords: List[str] = Field(
        description="Normalized keywords: product names, producer names, salient nouns"
    )
```

### RRF Algorithm

**Reciprocal Rank Fusion (RRF)**:
- Simple, order-aware, robust to heterogeneous scoring scales
- Requires only ranks, not raw scores
- Formula for each product:
  ```
  rrf_score = Σ (1 / (k + rank_in_list))
  
  Where:
  - k = 60 (RRF parameter, controls score smoothing)
  - rank_in_list = position in semantic or keyword list (1-indexed)
  - Sum across all lists where product appears
  ```

**Example:**
- Product A: rank 1 in semantic, rank 3 in keyword
  - RRF score = 1/(60+1) + 1/(60+3) = 0.0164 + 0.0159 = 0.0323
- Product B: rank 2 in semantic, not in keyword
  - RRF score = 1/(60+2) = 0.0161

### Full-Text Search Query

```sql
SELECT 
    product_id,
    product_name,
    producer_name,
    ts_rank_cd(fts_document, query) AS fts_rank
FROM products
WHERE fts_document @@ to_tsquery('simple', unaccent(:keywords_query))
ORDER BY fts_rank DESC
LIMIT :max_results;
```

Where `:keywords_query` is OR-joined sanitized keywords: `'cheese | italian | organic'`

### Safety & Resilience

- **Keyword extraction failure**: Fallback to semantic only (no FTS)
- **Empty keywords**: Skip FTS pass
- **FTS query errors**: Catch and log, proceed with semantic results
- **Zero semantic results**: Still attempt FTS if keywords available

### Logging

```
INFO rag_service hybrid_retrieval semantic_count=5 keywords=['cheese','italian'] fts_count=3 fused_count=5 elapsed_ms=67
```

### Configuration

Uses same flags as Simple RAG:
- `ENABLE_RAG=true`
- `RAG_SIMILARITY_THRESHOLD=0.3`
- `RAG_MAX_RESULTS=3`

### Extensibility

Future enhancements can add additional ranked lists before fusion:
- Graph-based expansion (concepts → products)
- Stock availability filters (prioritize in-stock)
- Reranker model (cross-encoder for top-k refinement)

### Implementation

**RAGService** (`src/services/rag_service.py`):
- Embedding generation
- Keyword extraction via Responses API
- Vector similarity search
- FTS search
- RRF combiner
- Result formatting + prompt injection

---

## Agentic Tool-Based Search

### Purpose

Instead of backend fusion, let the LLM orchestrate retrieval by calling multiple tools and integrating results using its reasoning.

### Activation

```bash
AGENTIC_SEARCH_ENABLED=true
```

When enabled, backend **does not** perform hybrid fusion. Instead, LLM receives two tool schemas and decides which to call.

### Tools

#### semantic_search

**Arguments:**
```json
{
  "text": "string - Natural language query"
}
```

**Returns:**
```json
{
  "results": [
    {
      "product_id": "uuid",
      "product_name": "string",
      "producer_name": "string",
      "description": "string",
      "score": "float (0-1 similarity)",
      "is_vip": "boolean"
    }
  ]
}
```

**Features:**
- Vector similarity search (cosine)
- Optional HyDE (Hypothetical Document Embedding)
- VIP fencing enforced
- Configurable max results: `AGENTIC_SEARCH_MAX_RESULTS` (default: 10)

**HyDE Enhancement:**
- For very short queries (<5 words), backend may generate a hypothetical document
- Hypothetical doc embedded instead of raw query
- Improves recall for terse or ambiguous queries
- HyDE generation emits `DF_META` with kind `hyde_generation`, hash, token count

#### keyword_search

**Arguments:**
```json
{
  "keywords": ["string", "array"]
}
```

**Returns:**
Same schema as `semantic_search`.

**Features:**
- Full-text search over `fts_document`
- VIP fencing enforced
- Ranked by `ts_rank_cd()`

### Workflow

1. LLM receives user query
2. LLM may call `semantic_search("fresh Italian cheese")`
3. Backend executes, returns VIP-filtered results
4. LLM may call `keyword_search(["mozzarella", "parmesan"])`
5. Backend executes, returns VIP-filtered results
6. LLM integrates and synthesizes final answer citing specific products

**No Backend Fusion:**
- Each tool call returns independent result set
- LLM handles ordering, deduplication, ranking
- Model reasoning layer integrates results

### Telemetry

Each tool invocation emits `DF_META` line:

```json
{
  "kind": "search_tool_call",
  "tool": "semantic_search",
  "count": 5,
  "vip_filtered": 2,
  "threshold": 0.3,
  "elapsed_ms": 45
}
```

### Fallback Strategy

If `AGENTIC_SEARCH_ENABLED=false` or LLM chooses not to call tools:
- System falls back to Hybrid RAG (backend fusion)
- Transparent to user

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTIC_SEARCH_ENABLED` | true | Enable tool-based retrieval |
| `AGENTIC_SEARCH_MAX_RESULTS` | 10 | Max results per tool call |

---

## Semantic Caching (First-Turn Accelerator)

### Purpose

Reduce latency and model cost for extremely common FIRST user turns (greetings, capability questions, generic help requests) by answering from a local cache.

### Scope & Constraints

**When Applied:**
- ONLY the very FIRST user message of a conversation (no prior context)
- Subsequent turns NOT cached (context-dependent meaning)

**What's Cached:**
- Generic, non-specific Q&A pairs
- No concrete product, farmer, stock, price, certification, or allergen references
- Concise, neutral answers that encourage specific follow-up

**What's NOT Cached:**
- Mid-conversation turns
- Product-specific queries
- Dynamic data (inventory, pricing, availability)

### Data Preparation

**Generation:**
```bash
python data/scripts/gen_qna.py
```

- Uses GPT-5 with structured output (Pydantic)
- Generates exactly 50 diverse, generic Q&A pairs
- Output: `data/source_json/qna.json`

**Schema:**
```json
[
  {
    "question": "What is Dream Farm?",
    "answer": "Dream Farm is a virtual marketplace connecting local farmers with customers..."
  },
  {
    "question": "Can you help me find organic products?",
    "answer": "Yes! I can help you search our catalog. What type of organic products are you looking for?"
  }
]
```

### Database Schema

**Table:** `semantic_cache`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | serial | primary key | Surrogate key |
| question | text | unique, not null | Canonical generic question |
| answer | text | not null | Pre-approved neutral answer |
| embedding | vector(2000) | not null | Question embedding (text-embedding-3-large) |
| created_at | timestamptz | default now() | Insert timestamp |

**Indexes:**
- HNSW index on `embedding` (cosine) for fast nearest neighbor
- Unique btree on `question` for integrity

### Retrieval Logic

```python
def check_semantic_cache(user_message: str, thread_history_length: int):
    # Only for first turn
    if thread_history_length > 0:
        return None
    
    # Generate embedding
    query_embedding = embed(user_message)
    
    # Vector similarity search
    result = db.query("""
        SELECT question, answer, 
               1 - (embedding <=> :query_emb) AS similarity
        FROM semantic_cache
        WHERE 1 - (embedding <=> :query_emb) >= :threshold
        ORDER BY similarity DESC
        LIMIT 1
    """, query_emb=query_embedding, threshold=0.90)
    
    if result:
        log_cache_hit(similarity=result.similarity)
        return result.answer
    
    return None  # Proceed with normal LLM path
```

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SEMANTIC_CACHE_ENABLED` | true | Enable semantic caching |
| `SEMANTIC_CACHE_SIMILARITY_THRESHOLD` | 0.8 | Minimum similarity for cache hit (≥0.80-0.95 recommended) |

**Threshold Tuning:**
- **0.95+**: Very strict, fewer hits, high precision
- **0.90**: Balanced (recommended)
- **0.85**: More hits, risk of slight semantic drift
- **<0.80**: Too permissive, risk of incorrect matches

### Benefits

- **Latency**: ~10-20ms cache lookup vs 500-2000ms LLM call
- **Cost**: Zero tokens consumed on cache hit
- **Consistency**: Deterministic, pre-approved onboarding tone
- **Cold-start**: Improved first impression for new users

### Limitations & Rationale

- **No Mid-Conversation**: Meaning shifts with context; risk of incorrect shortcuts
- **No Product Specifics**: Inventory is dynamic; must remain grounded via RAG
- **Simple Design**: Single-table, no eviction policy (50 entries minimal overhead)

### Telemetry

Cache hit emits `DF_META`:
```json
{
  "kind": "semantic_cache_hit",
  "question": "What can you help me with?",
  "similarity": 0.92,
  "elapsed_ms": 15
}
```

### Future Enhancements

- Hit/miss telemetry for threshold tuning
- Adaptive cache entries from high-frequency production queries
- Feedback scoring to prune low-value entries
- Periodic regeneration incorporating anonymized real phrasing
- Multi-lingual variant sets keyed by detected language

---

## VIP Fencing

### Purpose

Enforce row-level filtering to restrict VIP-only products from non-VIP users.

### Scope

**Currently Applied:**
- ✅ Agentic tool-based retrieval (`semantic_search`, `keyword_search`)
- ✅ Graph traversal tools (post-scoring filter)
- ❌ Hybrid RAG (shows full catalog)

**Future:**
- May extend to Hybrid RAG path
- Policy evolution pending business requirements

### SQL Pattern

All VIP-fenced queries include:

```sql
WHERE (products.is_vip = false OR :user_is_vip = true)
```

**Logic:**
- `is_vip = false`: Product visible to everyone
- `is_vip = true AND user_is_vip = true`: Product visible to VIP user
- `is_vip = true AND user_is_vip = false`: Product EXCLUDED

### User Context Extraction

```python
def get_user_is_vip(request):
    if not AUTH_ENABLED:
        return False
    
    # Extract from JWT claims
    token = verify_jwt(request.headers["Authorization"])
    
    # Check role membership or explicit claim
    return "vip" in token.roles or token.claims.get("is_vip", False)
```

### Telemetry

Tool calls emit VIP filter stats:

```json
{
  "kind": "search_tool_call",
  "tool": "semantic_search",
  "count": 8,
  "vip_filtered": 3,
  "user_is_vip": false
}
```

### Security Philosophy

**Defense in Depth:**
1. **SQL Layer**: Hard enforcement (WHERE clause)
2. **LLM Layer**: Instructed not to reveal VIP products
3. **API Layer**: JWT verification

**Trust Model:**
- SQL WHERE clause is TRUSTED source of truth
- LLM instructions are UNTRUSTED (model could hallucinate or be jailbroken)
- Never rely on LLM to self-filter VIP products

### Database Schema

**`products.is_vip` Column:**
- Type: `boolean`
- Default: `false`
- Indexed: Part of composite index for performance

---

## Retrieval Prompt Grounding Policy

### Grounding Rules

1. **Product-Related Claims**:
   - MUST originate from `<relevant_products>` block or explicit tool results
   - MUST cite product IDs for traceability
   - MUST NOT fabricate product names, producers, or attributes

2. **Zero-Hit Behavior**:
   - Discourage hallucination
   - Suggest alternative phrasing
   - Offer general domain advice without inventory claims
   - Example: "I couldn't find exact matches. Could you describe what you're looking for differently?"

3. **Graph-Derived Expansions**:
   - MUST reference underlying product IDs
   - MUST explain concept matches (e.g., "via Italian cuisine category")
   - Maintain explainability chain

4. **Uncertainty Handling**:
   - Acknowledge when information is incomplete
   - Direct user to refinement tools (filters, categories)
   - Never claim certainty for fuzzy matches

### Prompt Template (Excerpt)

```
You have access to the Dream Farm product catalog via retrieval tools.

GROUNDING REQUIREMENTS:
- All product recommendations MUST come from tool results or <relevant_products>
- NEVER invent product names, producers, or attributes
- When uncertain, ask for clarification rather than guessing
- If no matches found, suggest alternative search terms or broader categories

ZERO-HIT PROTOCOL:
- Acknowledge "I couldn't find products matching that specific request"
- Offer to broaden search or suggest related categories
- Provide general advice WITHOUT claiming specific inventory

VIP POLICY:
- Some products are VIP-only (not visible to you)
- NEVER mention VIP products if user is not VIP
- SQL layer enforces this; do not attempt to work around it
```

---

## Performance & Optimization

### Vector Search Optimization

**HNSW Index Configuration:**
```sql
CREATE INDEX idx_products_embedding 
ON products 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Parameters:**
- `m = 16`: Balance between recall and index size
- `ef_construction = 64`: Build-time accuracy (higher = better recall, slower build)

**Query-Time Tuning:**
```sql
SET hnsw.ef_search = 100;  -- Higher = better recall, slower search
```

**Performance Benchmarks (10k products):**
- Top-10 search: 10-30ms
- Top-100 search: 30-80ms
- Recall@10: >95% vs exact search

### Full-Text Search Optimization

**GIN Index Configuration:**
```sql
CREATE INDEX idx_products_fts 
ON products 
USING gin(fts_document);
```

**Trigger Maintenance:**
```sql
CREATE TRIGGER products_fts_update 
BEFORE INSERT OR UPDATE ON products
FOR EACH ROW EXECUTE FUNCTION
  tsvector_update_trigger(
    fts_document, 
    'pg_catalog.simple',  -- Use 'simple' config for unaccent compatibility
    product_name, 
    producer_name, 
    product_description
  );
```

**Query Optimization:**
- Use `simple` text search configuration with `unaccent` for diacritic-insensitive search
- Limit keyword OR-joins to <20 terms (performance degrades beyond)
- Consider `ts_rank` vs `ts_rank_cd` tradeoff (speed vs quality)

### Caching Strategy

**Application-Level:**
- Embedding cache for repeated queries (in-memory LRU, 1000 entries)
- HyDE document cache (keyed by query hash)

**Database-Level:**
- PostgreSQL shared buffers: 25% of RAM
- Effective cache size: 75% of RAM
- Work mem: 64MB per query (for sorting/aggregation)

### Monitoring

**Key Metrics:**
- Retrieval latency (p50, p95, p99)
- Cache hit rate (semantic cache, embedding cache)
- VIP filter effectiveness (% products filtered)
- Tool call frequency (semantic vs keyword)
- Zero-hit rate (queries with no results)

**Logging:**
```
INFO retrieval mode=hybrid semantic=5 keywords=3 fused=6 elapsed_ms=67
INFO retrieval mode=agentic tool=semantic_search count=8 vip_filtered=3 elapsed_ms=45
INFO semantic_cache hit=true similarity=0.92 elapsed_ms=15
```

---

## Related Documentation

- [Design.md](./Design.md) - High-level architecture overview
- [ToolSpecifications.md](./ToolSpecifications.md) - Tool argument/return schemas
- [KnowledgeGraph.md](./KnowledgeGraph.md) - Graph traversal algorithms
- [DataSchemas.md](./DataSchemas.md) - Database tables and indexes
- [ConfigurationReference.md](./ConfigurationReference.md) - All feature flags and environment variables
- [SecurityModel.md](./SecurityModel.md) - VIP fencing and authentication

# Data Schemas & Database Design

This document provides detailed specifications for all database tables, columns, indexes, and data structures used in the Dream Farm AI platform.

> **Note**: For high-level data architecture, see [Design.md](./Design.md#13-data-schemas-relational-extract). For retrieval strategies, see [RetrievalArchitecture.md](./RetrievalArchitecture.md).

---

## Table of Contents
- [Products Table](#products-table)
- [Stock Table](#stock-table)
- [Semantic Cache](#semantic-cache)
- [Concept Embeddings](#concept-embeddings)
- [Conversations & Memory](#conversations--memory)
- [Knowledge Graph Schema](#knowledge-graph-schema)
- [Taxonomy & Cuisine Enrichment](#taxonomy--cuisine-enrichment)
- [Indexes & Performance](#indexes--performance)

---

## Products Table

**Purpose**: Primary product catalog optimized for hybrid retrieval (semantic + keyword) and downstream reranking.

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | serial | primary key | Surrogate key |
| product_id | UUID | unique, not null | Stable external product identifier |
| producer_id | UUID | not null | External producer identifier; correlates with Producer vertex (producerId) |
| producer_name | varchar(255) | not null | Redundant for search/sorting |
| product_name | varchar(255) | not null | Product display name |
| product_description | text | not null | Rich description |
| combined_text | text | not null | Concatenated fields used for embeddings |
| embedding | vector(2000) | | 2000‑d pgvector embedding (text-embedding-3-large) |
| fts_document | tsvector | not null | Generated from name/producer/description for FTS |
| is_vip | boolean | not null default false | True = restricted; visible only to VIP users |
| created_at | timestamptz | default now() | Row creation timestamp |
| updated_at | timestamptz | default now() | Row update timestamp |

### Indexes

- **HNSW index** on `embedding` using cosine ops for fast vector similarity
- **GIN index** on `fts_document` for full‑text search
- **BTREE indexes** on `product_id`, `producer_id`, `producer_name`, `product_name`

### Notes

- Maintain `fts_document` via trigger (e.g., `to_tsvector('english', ...)`)
- Use hybrid scoring for candidate retrieval:
  ```sql
  score = 0.6 * (1 - cosine_distance(embedding, :query_vec)) 
        + 0.4 * ts_rank_cd(fts_document, plainto_tsquery(:q))
  ```
- Keep `simple_products` as a minimal seed/training/lesson table; `products` supersedes it for production use

---

## Stock Table

**Purpose**: Current stock quantity per product (and producer for provenance).

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| producer_id | UUID | not null | Producer that owns the stock entry |
| product_id | UUID | not null | Product this stock refers to |
| on_stock | integer | not null, default 0 | Current available quantity |
| updated_at | timestamptz | default now() | Last update timestamp |

### Constraints & Indexes

- **Primary key**: `(producer_id, product_id)`
- **BTREE indexes** on `product_id` and `producer_id` (if not covered by PK)

### Notes

- Matches generator output in `data/source_json/stock.json` (producerId, productId, onStock)
- If products are unique to a producer, `(product_id)` could be unique; we keep a composite PK for generality

---

## Semantic Cache

**Purpose**: First-turn question acceleration via high-similarity matching.

### Columns

| Column | Type | Description |
|--------|------|-------------|
| question | text | Normalized user question |
| answer | text | Generic, time-insensitive cached answer |
| embedding | vector(2000) | Question embedding for similarity search |

### Usage

- **Threshold**: High similarity (≥0.90) required for cache hit
- **Scope**: Only first user message in a conversation
- **Strategy**: Answers intentionally generic & time-insensitive

See [RetrievalArchitecture.md#semantic-caching](./RetrievalArchitecture.md) for implementation details.

---

## Concept Embeddings

**Purpose**: Semantic concept selection for graph BFS taxonomy search.

### Columns

| Column | Type | Notes |
|--------|------|-------|
| concept_type | enum(text) | One of: `category`, `cuisine`, `certification`, `allergen` |
| concept_id | text/uuid | Matches the corresponding vertex property (e.g., categoryId) |
| name | text | Canonical name |
| description | text | Concise neutral description (same source as graph) |
| normalized_text | text | Preprocessed (lowercased, de-accented) concatenation used for embedding source |
| embedding | vector(2000) | pgvector embedding (text-embedding-3-large) |
| created_at | timestamptz | Audit timestamp |
| updated_at | timestamptz | Audit timestamp |

### Indexes

- **HNSW index** on `embedding` (cosine) for similarity
- **Composite btree** on `(concept_type, concept_id)`
- Optional **partial index** for active concepts if future soft deletes are introduced

See [KnowledgeGraph.md#concept-embeddings](./KnowledgeGraph.md) for usage in graph traversal.

---

## Conversations & Memory

### conversations_raw

**Purpose**: Store full JSON conversation (7-day retention).

| Column | Type | Description |
|--------|------|-------------|
| thread_id | UUID | Primary key, conversation identifier |
| user_id | text | User identifier from JWT |
| title | text | Conversation title (user-supplied or generated) |
| messages | jsonb | Array of message objects (user/assistant turns) |
| created_at | timestamptz | Thread creation time |
| updated_at | timestamptz | Last message timestamp |
| expires_at | timestamptz | Auto-deletion timestamp (retention policy) |
| summary_status | text | Enum: 'pending', 'completed', 'failed' |

### conversation_summaries

**Purpose**: Summarized + embedded recaps + salient facts.

| Column | Type | Description |
|--------|------|-------------|
| summary_id | UUID | Primary key |
| thread_id | UUID | Foreign key to conversations_raw |
| user_id | text | User identifier (for fencing) |
| summary | text | Structured summary text |
| salient_facts | jsonb | Extracted key facts |
| embedding | vector(2000) | Summary embedding for semantic search |
| created_at | timestamptz | Summary generation time |

### user_profiles

**Purpose**: Stable personalization facts (diet, allergens, preferences).

| Column | Type | Description |
|--------|------|-------------|
| user_id | text | Primary key (from JWT sub claim) |
| profile | jsonb | Structured profile data (diet, allergens, liked_products, goals, notes) |
| created_at | timestamptz | Profile creation time |
| updated_at | timestamptz | Last modification time |

### memory_enrichment_audit (optional)

**Purpose**: Track profile mutation diffs.

| Column | Type | Description |
|--------|------|-------------|
| audit_id | UUID | Primary key |
| user_id | text | User identifier |
| changed_fields | jsonb | List of fields modified |
| old_values | jsonb | Previous values |
| new_values | jsonb | Updated values |
| timestamp | timestamptz | Change timestamp |

See [MemoryPersonalization.md](./MemoryPersonalization.md) for detailed memory architecture.

---

## Knowledge Graph Schema

**Purpose**: Model rich relationships (producer → product, certifications, allergens, categories) and enable graph traversals for recommendations, explanations, and exploration.

### Graph Configuration

- **Graph name**: `dreamfarm`
- **Query language**: openCypher via AGE's `cypher()` SQL function
- **Extension**: Apache AGE (requires `ag_catalog` in search_path)

### Vertices

| Label | Representative Properties |
|-------|--------------------------|
| Producer | `{ producerId: UUID, name: text, description: text }` |
| Product | `{ productId: UUID, name: text }` |
| Certification | `{ certificationId: UUID, name: text, description: text }` |
| Allergen | `{ allergenId: UUID, name: text }` |
| Category | `{ categoryId: UUID, name: text, description: text }` |
| Cuisine | `{ cuisineId: UUID, name: text, description: text }` |

### Edges

| Relationship | Direction | Description |
|--------------|-----------|-------------|
| PRODUCES | Producer → Product | Producer ownership |
| HAS_CERTIFICATION | Producer → Certification | Producer certifications |
| CONTAINS_ALLERGEN | Product → Allergen | Allergen presence |
| HAS_CATEGORY | Product → Category | Product category membership |
| HAS_CUISINE | Product → Cuisine | Cuisine association |
| RELATED | Product ↔ Product | Optional curated similarity/co‑purchase signals |

### Relational ↔ Graph Integration

**Recommended Pattern**:

1. Keep `products` table as system of record for product content, embeddings, and FTS
2. Create lightweight Product vertices carrying only stable external key `productId` (and `name`)
3. Mirror producer/certification/allergen entities as vertices with their stable IDs from JSON/ETL
4. Synchronization: populate/refresh graph from relational/JSON sources via ETL jobs
5. Query pattern:
   - Do hybrid retrieval in SQL on `products` to get top-N product_ids with scores
   - Use those IDs as parameters to Cypher query for traversals/enrichment
   - Join `cypher(...)` results with relational tables on `productId`/`producerId` properties

### AGE Operational Notes

- Enable AGE extension: `CREATE EXTENSION age;`
- Set search path: `SET search_path = ag_catalog, "$user", public;`
- Create graph once: `SELECT create_graph('dreamfarm');`
- Query pattern: `SELECT * FROM cypher('dreamfarm', $$ MATCH ... $$) AS (result agtype);`
- Store external IDs as vertex properties to bridge to relational tables

See [KnowledgeGraph.md](./KnowledgeGraph.md) for detailed graph traversal strategies.

---

## Taxonomy & Cuisine Enrichment

### Goals

- Introduce two higher‑level concept layers (Category, Cuisine) above raw products
- Enable semantic grouping, faceted exploration, recommendation pivots
- Enrich natural‑language answers (e.g., "These cheeses fit Italian Mediterranean salads")
- Keep derivation deterministic & auditable (stored artifacts, hash of model prompts, version tags)

### LLM Tasks (Three Sequential Phases)

#### 1. Concept Set Generation

- Prompt model with sampled / summarized product descriptions to propose candidate lists
- Structured JSON schema with fields: `categories: [{id, name, description}]`, `cuisines: [{id, name, description}]`
- Deterministic ID strategy: slug of name (kebab-case) + short hash suffix (e.g., `fresh-cheese-d4f2`)

#### 2. Concept Refinement (Optional Human Review)

- Script outputs draft set
- If `--review` flag provided, write to `processed/taxonomy_concepts.draft.json` and exit for manual edits
- Otherwise continue automatically

#### 3. Product Classification

- Multi‑label assignment using second structured call per batch of products (batch size configurable, default 50)
- Schema: `assignments: [{product_id, categories: [id], cuisines: [id], confidences: {<id>: float}}]`
- Apply local confidence filter (`>= TAXONOMY_MIN_CONFIDENCE`, default 0.55) dropping weak associations

### Artifacts (Versioned)

```
processed/
  taxonomy_concepts.v1.json            # canonical list (categories + cuisines)
  product_taxonomy_assignments.v1.parquet  # columns: product_id, category_ids (array<str>), cuisine_ids (array<str>), meta (JSON)
  product_taxonomy_assignments.v1.json  # (optional) human-readable mirror
```

**Versioning Rules**: Bump minor (v1 → v1.1) for additive concept descriptions; bump major for structural or ID changes.

### Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `TAXONOMY_CATEGORY_TARGET` | Target number of categories | 50 |
| `TAXONOMY_CUISINE_TARGET` | Target number of cuisines | 20 |
| `TAXONOMY_MIN_CONFIDENCE` | Minimum confidence for assignment | 0.55 |
| `TAXONOMY_MODEL` | LLM model for generation | (main chat model) |
| `TAXONOMY_BATCH_SIZE` | Products per batch | 50 |
| `TAXONOMY_VERSION` | Artifact version tag | v1 |

### Data Models (JSON Schemas)

```json
// taxonomy_concepts.v1.json
{
  "version": "v1",
  "generated_at": "<iso8601>",
  "categories": [ 
    { "id": "fresh-cheese-d4f2", "name": "Fresh Cheese", "description": "Soft, unripened cheeses..." } 
  ],
  "cuisines": [ 
    { "id": "italian-78ac", "name": "Italian", "description": "Cuisine featuring regional..." } 
  ],
  "model": {"name": "gpt-5", "embedding": "text-embedding-3-large"},
  "prompt_hash": "sha256:..."
}

// Single assignment row (logical)
{
  "product_id": "<uuid>",
  "categories": ["fresh-cheese-d4f2", "dairy-general-91bf"],
  "cuisines": ["italian-78ac"],
  "confidences": {
    "fresh-cheese-d4f2": 0.81, 
    "dairy-general-91bf": 0.62, 
    "italian-78ac": 0.74
  },
  "version": "v1"
}
```

### Scripts (Planned in `data/scripts/`)

- `gen_taxonomy_concepts.py` – phases 1–2 (generation + optional review)
- `classify_products_taxonomy.py` – phase 3 (multi‑label classification, parquet + json output)
- `import_taxonomy_graph.py` – graph MERGE of vertices + edges (idempotent, version aware)

### Edge Cases & Safeguards

- Products with extremely short or generic descriptions may yield no assignments (allowed)
- Confidence tie‑breaking: keep all above threshold (no forced top‑k)
- Category/Cuisine name collisions collapse via slug+hash; detection logged
- Re‑run with same input + model should produce same slug IDs
- Review gate recommended for stability

### Failure Handling

- Any phase error aborts before writing partially complete artifacts
- Write temp file then atomic rename
- Import script supports `--dry-run` to emit Cypher without executing

---

## Indexes & Performance

### Vector Indexes (HNSW)

All vector columns use HNSW indexing with cosine distance:

```sql
CREATE INDEX idx_products_embedding 
ON products USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_concept_embeddings_embedding 
ON concept_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_semantic_cache_embedding 
ON semantic_cache USING hnsw (embedding vector_cosine_ops);
```

### Full-Text Search Indexes (GIN)

```sql
CREATE INDEX idx_products_fts 
ON products USING gin(fts_document);

-- Trigger to maintain fts_document
CREATE TRIGGER products_fts_update 
BEFORE INSERT OR UPDATE ON products
FOR EACH ROW EXECUTE FUNCTION
  tsvector_update_trigger(fts_document, 'pg_catalog.english', 
                         product_name, producer_name, product_description);
```

### Standard Indexes (BTREE)

- Primary keys and foreign keys automatically indexed
- Additional indexes on frequently queried columns: `product_id`, `producer_id`, `user_id`, `thread_id`
- Composite indexes for common query patterns: `(concept_type, concept_id)`

### Retention & Cleanup

- `conversations_raw.expires_at`: Indexed for efficient expired conversation cleanup
- Background job scans `WHERE expires_at < NOW()` and deletes in batches
- Summaries retained indefinitely unless `MEMORY_SUMMARY_RETENTION_DAYS` set

---

## Related Documentation

- [Design.md](./Design.md) - High-level architecture overview
- [RetrievalArchitecture.md](./RetrievalArchitecture.md) - Retrieval strategies and RAG implementation
- [KnowledgeGraph.md](./KnowledgeGraph.md) - Graph traversal algorithms and query patterns
- [MemoryPersonalization.md](./MemoryPersonalization.md) - Memory and user profile implementation
- [ConfigurationReference.md](./ConfigurationReference.md) - All environment variables and feature flags

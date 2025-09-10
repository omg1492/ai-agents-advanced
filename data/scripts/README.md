# Data Scripts

This directory contains standalone utilities that form three groups:

1. **Data pipeline (tabular + embeddings + database import)** – generates sample product data, prepares PostgreSQL (vector + graph), creates embeddings and imports them.
2. **Content understanding utilities (PDF / Image / Video)** – extract or infer structured product metadata (name + short description) from heterogeneous media using OpenAI (PDF/Image) and local Whisper + OpenAI vision (Video).
3. **Semantic cache (first‑turn Q&A)** – generates a generic Q&A seed set, embeds it, creates a dedicated cache table, and imports rows for low‑latency cold‑start responses.

All scripts are intentionally single‑file tools for quick demos and reproducibility. They share a common `.env` using *unified* OpenAI / Azure OpenAI configuration variables.

## Prerequisites

1. **Python environment**: Use `uv` (Python ≥3.12)
2. **PostgreSQL with pgvector + AGE** (for the data pipeline) via `deploy/local/docker-compose.yml`
3. **OpenAI or Azure OpenAI** credentials for embeddings + vision + text
4. **FFmpeg** (optional but recommended) for video audio extraction – required when processing videos
5. **Local Whisper (faster-whisper)** – automatically pulled when you run `uv sync`; used for video transcription to avoid remote speech costs / deployment issues
6. **Environment file**: copy `.env.template` → `.env` and edit

## Quick Start (Data Pipeline + Semantic Cache)

```bash
# 1. Install dependencies
uv sync

# 2. Start PostgreSQL with pgvector
cd ../../deploy/local
docker-compose up -d postgres
cd ../../data/scripts

# 3. Configure environment
# Copy template and set unified OpenAI envs (OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_API_VERSION, OPENAI_EMBEDDING_MODEL)
cp .env.template .env
# Edit .env with your API keys and database settings

# 4. Run the complete pipeline
uv run gen_basic_data.py          # Generate sample data
uv run configure_postgresql.py    # Setup database tables and extensions
uv run embeddings_simple_products.py  # Generate embeddings
uv run import_simple_products.py  # Import data and test queries

# (Optional) Semantic cache seed (generic first‑turn questions)
uv run gen_qna.py                 # Generate generic Q&A pairs (qna.json)
uv run embeddings_qna.py          # Embed questions → qna_embeddings.parquet
# Ensure semantic_cache table exists (sql/tables/05_create_semantic_cache.sql)
uv run import_qna.py              # Import Q&A embeddings into semantic_cache
```

## Scripts Description

### A. Data Pipeline

#### 1. `gen_basic_data.py`
**Purpose**: Generates sample product data with producers, products, and descriptions.

**Output**: Creates JSON files in `../source_json/`:
- `producers.json` - Sample producer and product data
- `allergens.json` - Allergen information
- `certifications.json` - Product certifications
- `stock.json` - Stock levels

**Usage**:
```bash
uv run gen_basic_data.py
```

#### 2. `configure_postgresql.py`
**Purpose**: Sets up PostgreSQL database with pgvector extension and creates tables.

**Features**:
- Installs pgvector extension
- Creates `simple_products` table with vector column
- Creates indexes for fast similarity search
- Handles SQL scripts in organized folders

**Usage**:
```bash
uv run configure_postgresql.py
```

**SQL Scripts Executed** (in order):
- `sql/extensions/01_install_pgvector.sql` - Installs pgvector extension
- `sql/extensions/02_install_age.sql` - Installs and loads Apache AGE
- `sql/tables/01_create_simple_products.sql` - Creates simple seed table with vector index (lesson 1)
- `sql/tables/02_create_stock.sql` - Creates stock table
- `sql/tables/03_create_products.sql` - Creates production products table (hybrid: pgvector + FTS)
- `sql/tables/04_init_age_graph.sql` - Initializes the AGE graph `dreamfarm`

#### 3. `embeddings_simple_products.py`
**Purpose**: Processes product data and generates vector embeddings using OpenAI models.

**Features**:
- Loads data from `producers.json`
- Creates combined text descriptions
- Generates 2000-dimensional embeddings (compatible with pgvector HNSW indexes)
- Parallel processing for fast embedding generation
- Saves results to Parquet format

**Output**: `../processed/simple_products.parquet`

**Usage**:
```bash
uv run embeddings_simple_products.py
```

#### 4. `import_simple_products.py`
**Purpose**: Imports processed data into PostgreSQL and tests vector similarity search.

**Features**:
- Loads data from Parquet file
- Imports into PostgreSQL `simple_products` table
- Replaces existing data (TRUNCATE and re-import)
- Tests cosine similarity search functionality
- Reports import statistics and sample queries

**Usage**:
```bash
uv run import_simple_products.py
```

#### 5. `import_stock.py`
**Purpose**: Imports stock levels from `../source_json/stock.json` into the `stock` table.

**Features**:
- Truncates `stock` table (overwrite existing) before import
- Validates inputs, batches inserts, and logs progress/summary

**Usage**:
```bash
uv run import_stock.py
```

#### 6. `import_graph_age.py`
**Purpose**: Populate Apache AGE graph (`dreamfarm`) with producers, products, certifications and allergens plus edges (PRODUCES, HAS_CERTIFICATION, CONTAINS_ALLERGEN).

**Features**:
- Reads `producers.json`, `allergens.json`, `certifications.json`
- MERGE-based idempotent upserts (safe re-runs)
- Optional `--reset` flag to drop & recreate graph (destructive, dev only)
- Minimal node payloads (avoid embedding / VIP duplication)
- Batched execution with progress logging (default batch size 1000 statements; override via `--batch-size`)
- Prints summary counts + top producers by product count

**Usage**:
```bash
# Default (batch size 1000)
uv run import_graph_age.py

# Custom batch size (e.g. 200) for more frequent commits during debugging
uv run import_graph_age.py --batch-size 200

# Rebuild graph from scratch then import
uv run import_graph_age.py --reset
```

**Why batching?** A single large (~15k) transaction increases lock time and makes restarts expensive on failure. Committing every 1000 statements offers a balance of throughput and safety; tune `--batch-size` based on latency vs. lock considerations.

#### 7. `embeddings_products.py`
**Purpose**: Generate embeddings for the richer `products` dataset (flattened from `producers.json`) and mark a deterministic subset (~10% by default) as VIP (`is_vip=True`).

**Features**:
- Flattens nested producers → products structure (extracts `producer_id`, `producer_name`, `product_id`, names & descriptions)
- Builds `combined_text` field (`PRODUCER | PRODUCT | DESCRIPTION`)
- Deterministic VIP sampling (seeded RNG) via `PRODUCT_VIP_RATIO` (default 0.10)
- Requests 2000‑dim embeddings (compatible with `products.embedding VECTOR(2000)`) using unified OpenAI/Azure config
- Saves Parquet: `../processed/products.parquet`

**Environment**:
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_API_VERSION`, `OPENAI_EMBEDDING_MODEL`
- `PRODUCT_VIP_RATIO` (float, default 0.10)

**Usage**:
```bash
uv run embeddings_products.py
```

#### 8. `import_products.py`
**Purpose**: Import rich product rows (with embeddings + VIP flag) from `products.parquet` into the `products` table.

**Features**:
- Validates embedding dimension (drops malformed rows)
- Truncates table each run (dev‑friendly idempotence)
- Batches inserts with `execute_batch`
- Logs skipped rows & final counts

**Environment**: Standard PostgreSQL connection vars.

**Usage**:
```bash
uv run import_products.py
```

#### 9. `gen_graph_taxonomy.py`
**Purpose**: LLM‑driven enrichment – synthesize Category (~50) & Cuisine (~20) concepts and assign every product to 0‑3 categories and 0‑2 cuisines.

**Key Outputs (../processed/):**
- `taxonomy_concepts.parquet` (kind, code, name, description)
- `taxonomy_assignments.parquet` (product_id, category_codes[list], cuisine_codes[list])
- `taxonomy_state.json` (resumable progress + token usage)

**Resumable Design**:
- Concept generation done once; subsequent runs reuse unless `--rebuild-concepts` or `TAXONOMY_FORCE_REGENERATE_CONCEPTS=true`.
- Product assignments processed in deterministic batches (default 40) – safe resume mid‑way.

**Token Accounting**: Aggregates prompt/completion usage for concept & assignment stages.

**Environment**:
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_API_VERSION`, `OPENAI_MODEL`
- `TAXONOMY_BATCH_SIZE` (default 40)
- `TAXONOMY_STATE_PATH` (override state file location)
- `TAXONOMY_FORCE_REGENERATE_CONCEPTS` (boolean)

**CLI**:
```bash
uv run gen_graph_taxonomy.py                          # resume / normal
uv run gen_graph_taxonomy.py --batch-size 30          # first run only (locks in state)
uv run gen_graph_taxonomy.py --rebuild-concepts       # discard prior concepts
```

#### 10. `import_taxonomy_age.py`
**Purpose**: Import taxonomy concepts + assignments into the Apache AGE graph as `Category` / `Cuisine` nodes and `IN_CATEGORY` / `IN_CUISINE` edges from existing `Product` nodes.

**Features**:
- MERGE‑based idempotent creation / update (safe re-runs)
- Optional selective reset of only taxonomy nodes/edges (`--reset-taxonomy`)
- Batched Cypher execution (`--batch-size`, default 1000)
- Gracefully handles empty / numpy‑backed list columns from Parquet

**Usage**:
```bash
uv run import_taxonomy_age.py
uv run import_taxonomy_age.py --batch-size 500
uv run import_taxonomy_age.py --reset-taxonomy        # drop & rebuild taxonomy layer only
```

**Preconditions**:
1. Base graph initialized (`import_graph_age.py`).
2. Taxonomy parquet files exist (run `gen_graph_taxonomy.py`).

### Additional Environment Variables (beyond earlier sections)

```env
# Rich products embedding pipeline
PRODUCT_VIP_RATIO=0.10

# Taxonomy generation
TAXONOMY_BATCH_SIZE=40
TAXONOMY_STATE_PATH=../processed/taxonomy_state.json
TAXONOMY_FORCE_REGENERATE_CONCEPTS=false
```

### B. Content Understanding Utilities

These scripts infer consistent product metadata (`product_name`, `short_description`) from different modalities. All print clearly delimited console blocks plus a consolidated summary.

| Script | Modality | Core Steps | Model / Engine | Structured Output |
|--------|----------|-----------|----------------|------------------|
| `process_pdfs.py` | PDFs | Convert to Markdown (markitdown) → vision & text prompt (Responses/Chat parse) | OpenAI/Azure (unified client) | `ProductSummary` |
| `process_images.py` | Images (jpg/png/webp/gif) | Base64 embed → vision prompt with structured parse | OpenAI/Azure | `ImageProductSummary` |
| `process_video.py` | Videos (mp4/mov/mkv/webm) | Sample frames (OpenCV) + extract audio (ffmpeg) + local Whisper transcription + vision prompt | OpenAI/Azure (vision) + local `faster-whisper` | `VideoProductSummary` |

### C. Semantic Cache (First‑Turn Q&A)

These scripts create a small semantic cache for extremely common first user turns (greetings, generic capability queries). The agent can attempt a fast embedding similarity lookup before invoking full RAG + tool reasoning. All answers are intentionally generic and avoid specific product / price / stock claims.

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `gen_qna.py` | Generate ~50 generic Q&A pairs (structured Responses API) | OpenAI model | `../source_json/qna.json` |
| `embeddings_qna.py` | Create 2000‑d embeddings for each question | `qna.json` | `../processed/qna_embeddings.parquet` |
| `sql/tables/05_create_semantic_cache.sql` | Define `semantic_cache` table + HNSW index | n/a | DB table/index |
| `import_qna.py` | Import embedded Q&A into `semantic_cache` | Parquet | Populated table |

Planned usage (agent): if first message similarity ≥ threshold (configurable) → return cached answer; else proceed normally.

#### `process_pdfs.py`
Usage:
```bash
uv run process_pdfs.py
```
Behavior: converts each `*.pdf` from `PDF_INPUT_DIR` (default `../PDFs`) to Markdown (no truncation), then prompts the model for structured output.

#### `process_images.py`
Usage:
```bash
uv run process_images.py
```
Behavior: sends one image per request with a grounding prompt; returns structured product name + description.

#### `process_video.py`
Usage:
```bash
uv run process_video.py
```
Pipeline:
1. Enumerate supported videos from `VIDEOS_INPUT_DIR` (default `../videos`).
2. Sample 3 frames (first / mid / last) with OpenCV.
3. Extract mono 16 kHz WAV via ffmpeg (if available).
4. Transcribe audio locally using `faster-whisper` (model + compute type from env) – no remote speech API required.
5. Provide frames (as vision inputs) + full transcript to the OpenAI model for structured output.

Diagnostics blocks printed: FRAME SAMPLING, AUDIO EXTRACTION, TRANSCRIPTION, LLM SUMMARY.

Environment knobs (see below) let you choose Whisper model size and quantization for CPU performance.

## Data Flow (Pipeline Portion)

```
Raw Data Generation → Embedding Creation → Database Import → Search Testing
      ↓                      ↓                    ↓              ↓
gen_basic_data.py → embeddings_simple_products.py → import_simple_products.py
                                                           ↑
                                               configure_postgresql.py

                                             Semantic Cache Flow:
                                             gen_qna.py → embeddings_qna.py → (05_create_semantic_cache.sql) → import_qna.py → first‑turn lookup
```

## Configuration

### Unified Environment Variables (`.env` / `.env.template`)

The project standardizes on the same OpenAI/Azure vars across agents + scripts:

```env
# Required (OpenAI or Azure OpenAI)
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Azure-specific (optional for pure OpenAI)
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/
OPENAI_API_VERSION=preview

# PostgreSQL (used by pipeline scripts)
PGHOST=localhost
PGPORT=5432
PGDATABASE=aidb
PGUSER=admin
PGPASSWORD=your-password

# Media input directories (relative to this folder by default)
PDF_INPUT_DIR=../PDFs
IMAGES_INPUT_DIR=../images
VIDEOS_INPUT_DIR=../videos

# Local Whisper settings (video transcription)
WHISPER_MODEL_SIZE=small        # e.g. tiny, base, small, medium, large-v3
WHISPER_COMPUTE_TYPE=int8       # int8 | int8_float16 | float16 | int16 | float32
WHISPER_BEAM_SIZE=5             # decoding beam size
# WHISPER_LANGUAGE=             # optional force language (e.g. en); empty = auto-detect
```

### Choosing a Whisper configuration

| Goal | Suggested model | Compute type | Notes |
|------|-----------------|-------------|-------|
| Fastest iteration | `tiny` | `int8` | Lowest accuracy but very quick |
| Balanced demo (default) | `small` | `int8` | Good speed/accuracy on CPU |
| Higher accuracy | `medium` | `int8_float16` | Slower cold start |
| Multilingual best | `large-v3` | `int8_float16` | Heavy; consider caching |

Set `OMP_NUM_THREADS` to number of physical cores for better CPU throughput:
```bash
set OMP_NUM_THREADS=8  # PowerShell: $Env:OMP_NUM_THREADS=8
```

### Database Schema

The `simple_products` table contains:
- `id` - Primary key (SERIAL)
- `product_id` - Unique product identifier (UUID)
- `producer_name` - Producer name (VARCHAR)
- `product_name` - Product name (VARCHAR)
- `product_description` - Detailed description (TEXT)
- `combined_text` - Formatted text used for embeddings (TEXT)
- `embedding` - 2000-dimensional vector (VECTOR)
- `created_at`, `updated_at` - Timestamps

## Vector Search (Pipeline)

The system uses cosine similarity for vector search with HNSW indexes for fast approximate nearest neighbor search.

**Example Query**:
```sql
SELECT product_name, producer_name, 
       1 - (embedding <=> '[0.1,0.2,...]'::vector) AS similarity_score
FROM simple_products 
ORDER BY embedding <=> '[0.1,0.2,...]'::vector 
LIMIT 5;
```

## Troubleshooting

### Common Issues

1. **pgvector extension not found**
   - Ensure you're using `pgvector/pgvector:pg17` Docker image
   - Restart PostgreSQL container: `docker-compose restart postgres`

2. **Embedding generation is slow**
   - Check your OpenAI API rate limits
   - Reduce `max_workers` in `embeddings_simple_products.py`

3. **Vector dimension errors**
   - Ensure embeddings are exactly 2000 dimensions
   - Check OpenAI API configuration for `dimensions=2000`

4. **Connection errors**
   - Verify PostgreSQL is running: `docker-compose ps`
   - Check `.env` file configuration
   - Ensure ports are not blocked

### Performance Tips

1. **Embedding Generation**: Use Azure OpenAI for better rate limits
2. **Database Import**: Use batch inserts (implemented by default)
3. **Vector Search**: HNSW indexes provide fast approximate search
4. **Data Size**: Start with smaller datasets for testing

### Video Transcription Issues
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
`AUDIO EXTRACTION Failed: ffmpeg executable not found` | ffmpeg missing | Install ffmpeg & ensure on PATH (Windows: winget install Gyan.FFmpeg) |
`TRANSCRIPTION Failed: Local Whisper error: ...` | Model download interrupted / low memory | Re-run; choose smaller model or different compute type |
No transcript but frames OK | Silent audio track | Expected; model relies purely on frames |

### General
If a script prints a `Fatal error:` line it exits non‑zero; inspect preceding blocks (they include granular diagnostics rather than stack traces for brevity).

## File Structure

```
data/scripts/
├── README.md                          # This file
├── .env.template                      # Environment template
├── pyproject.toml                     # Python dependencies
├── gen_basic_data.py                  # Data generation
├── configure_postgresql.py            # Database setup
├── embeddings_simple_products.py      # Embedding generation (products)
├── embeddings_qna.py                  # Embedding generation (semantic cache Q&A)
├── embeddings_products.py             # Embedding generation (rich products + VIP flag)
├── import_simple_products.py          # Data import and testing (products)
├── import_qna.py                      # Import semantic cache Q&A embeddings
├── import_products.py                 # Import rich products table
├── process_pdfs.py                    # PDF → Markdown → structured summary
├── process_images.py                  # Image → vision structured summary
├── process_video.py                   # Video → frames + local Whisper + vision summary
├── gen_graph_taxonomy.py              # Generate taxonomy concepts + assignments (resumable)
├── import_taxonomy_age.py             # Import taxonomy into AGE graph (Category/Cuisine)
└── sql/                               # SQL scripts
    ├── README.md                      # SQL documentation
    ├── extensions/                    # Database extensions
    │   └── 01_install_pgvector.sql
    │   └── 02_install_age.sql
    └── tables/                        # Table definitions
      ├── 01_create_simple_products.sql
      ├── 02_create_stock.sql
      ├── 03_create_products.sql
   ├── 04_init_age_graph.sql
   └── 05_create_semantic_cache.sql
```
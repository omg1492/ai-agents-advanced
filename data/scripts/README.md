# Data Scripts

This directory contains scripts for data generation, processing, and database management for the Advanced AI Applications project.

## Overview

The scripts work together to create a complete data pipeline from raw data generation to a searchable PostgreSQL database with vector embeddings.

## Prerequisites

1. **Python Environment**: Use `uv` to manage dependencies
2. **PostgreSQL with pgvector**: Use Docker Compose setup in `deploy/local/`
3. **OpenAI API**: Configure Azure OpenAI or OpenAI API credentials
4. **Environment Configuration**: Copy `.env.example` to `.env` and configure

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Start PostgreSQL with pgvector
cd ../../deploy/local
docker-compose up -d postgres
cd ../../data/scripts

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys and database settings

# 4. Run the complete pipeline
uv run gen_basic_data.py          # Generate sample data
uv run configure_postgresql.py    # Setup database tables and extensions
uv run embeddings_simple_products.py  # Generate embeddings
uv run import_simple_products.py  # Import data and test queries
```

## Scripts Description

### 1. `gen_basic_data.py`
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

### 2. `configure_postgresql.py`
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

**SQL Scripts Executed**:
- `sql/extensions/01_install_pgvector.sql` - Installs pgvector extension
- `sql/tables/01_create_simple_products.sql` - Creates main table with indexes

### 3. `embeddings_simple_products.py`
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

### 4. `import_simple_products.py`
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

## Data Flow

```
Raw Data Generation → Embedding Creation → Database Import → Search Testing
      ↓                      ↓                    ↓              ↓
gen_basic_data.py → embeddings_simple_products.py → import_simple_products.py
                                                           ↑
                                               configure_postgresql.py
```

## Configuration

### Environment Variables (.env)

```env
# PostgreSQL Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=aidb
POSTGRES_USER=admin
POSTGRES_PASSWORD=Admin12345678

# Azure OpenAI (recommended)
OPENAI_API_TYPE=azure
AZURE_OPENAI_EMBEDDING_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_EMBEDDING_API_KEY=your-api-key
AZURE_OPENAI_EMBEDDING_API_VERSION=2024-12-01-preview
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-large

# OR OpenAI API
OPENAI_API_TYPE=openai
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
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

## Vector Search

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

## File Structure

```
data/scripts/
├── README.md                          # This file
├── .env.example                       # Environment template
├── pyproject.toml                     # Python dependencies
├── gen_basic_data.py                  # Data generation
├── configure_postgresql.py            # Database setup
├── embeddings_simple_products.py     # Embedding generation
├── import_simple_products.py          # Data import and testing
└── sql/                              # SQL scripts
    ├── README.md                      # SQL documentation
    ├── extensions/                    # Database extensions
    │   └── 01_install_pgvector.sql
    └── tables/                        # Table definitions
        └── 01_create_simple_products.sql
```
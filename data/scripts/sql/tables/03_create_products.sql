-- Create products table for hybrid search (pgvector + FTS)

-- Drop table if it exists (for development convenience)
DROP TABLE IF EXISTS public.products CASCADE;

-- Create products table
CREATE TABLE public.products (
    id                  SERIAL PRIMARY KEY,
    product_id          UUID NOT NULL UNIQUE,
    producer_id         UUID NOT NULL,
    producer_name       VARCHAR(255) NOT NULL,
    product_name        VARCHAR(255) NOT NULL,
    product_description TEXT NOT NULL,
    combined_text       TEXT NOT NULL,
    -- VIP fencing flag: when true, item visible only to VIP users (used in RAG / tool filtering)
    is_vip              BOOLEAN NOT NULL DEFAULT false,
    embedding           vector(2000),
    fts_document        TSVECTOR NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

-- Indexes for lookups
CREATE INDEX idx_products_product_id ON public.products(product_id);
CREATE INDEX idx_products_producer_id ON public.products(producer_id);
CREATE INDEX idx_products_producer_name ON public.products(producer_name);
CREATE INDEX idx_products_product_name ON public.products(product_name);
-- Filtering index (optional selectivity aid for (is_vip=false) predicates in queries)
CREATE INDEX idx_products_is_vip ON public.products(is_vip);

-- HNSW index for vector similarity
CREATE INDEX idx_products_embedding_cosine 
ON public.products 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- GIN index for full-text search
CREATE INDEX idx_products_fts ON public.products USING GIN (fts_document);

-- Trigger to keep fts_document up to date
CREATE OR REPLACE FUNCTION public.products_update_fts()
RETURNS TRIGGER AS $$
BEGIN
  NEW.fts_document :=
    setweight(to_tsvector('english', coalesce(NEW.product_name, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(NEW.producer_name, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(NEW.product_description, '')), 'C');
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_products_update_fts
BEFORE INSERT OR UPDATE OF product_name, producer_name, product_description
ON public.products
FOR EACH ROW
EXECUTE FUNCTION public.products_update_fts();

-- Comments for documentation
COMMENT ON TABLE public.products IS 'Rich product catalog with embeddings and full-text search for hybrid retrieval.';
COMMENT ON COLUMN public.products.embedding IS 'Vector embedding (2000 dims) generated via text-embedding-3-large.';
COMMENT ON COLUMN public.products.fts_document IS 'FTS document built from product/producer/description.';
COMMENT ON COLUMN public.products.is_vip IS 'When true, product is restricted to VIP users (fencing).';

-- Verify table creation
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'products' 
ORDER BY ordinal_position;

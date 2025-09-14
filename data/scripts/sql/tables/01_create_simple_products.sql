-- Create simple_products table for storing product data with embeddings
-- This table stores product information from producers along with their vector embeddings
-- Includes tsvector column (maintained by trigger) for full-text search over combined_text

-- Drop table if it exists (for development)
DROP TABLE IF EXISTS public.simple_products CASCADE;

-- Create simple_products table
CREATE TABLE public.simple_products (
    -- Primary key
    id SERIAL PRIMARY KEY,

    -- Product identification
    product_id UUID NOT NULL UNIQUE,

    -- Producer information
    producer_name VARCHAR(255) NOT NULL,

    -- Product information
    product_name VARCHAR(255) NOT NULL,
    product_description TEXT NOT NULL,

    -- Combined text used for embedding generation & keyword search
    combined_text TEXT NOT NULL,

    -- Vector embedding (using pgvector extension)
    -- Using 2000 dimensions for pgvector HNSW index compatibility
    embedding vector(2000),

    -- Full-text search document (maintained by trigger because unaccent is not IMMUTABLE)
    fts_combined tsvector NOT NULL DEFAULT to_tsvector('simple','')
);

-- Create indexes for better performance
CREATE INDEX idx_simple_products_product_id ON public.simple_products(product_id);
CREATE INDEX idx_simple_products_producer_name ON public.simple_products(producer_name);
CREATE INDEX idx_simple_products_product_name ON public.simple_products(product_name);

-- Create HNSW index for fast cosine similarity search
CREATE INDEX idx_simple_products_embedding_cosine 
ON public.simple_products 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Full-text search GIN index for keyword queries
CREATE INDEX idx_simple_products_fts_combined ON public.simple_products USING GIN (fts_combined);

-- Add table comment
COMMENT ON TABLE public.simple_products IS 'Stores product information with vector embeddings and full-text search for similarity + keyword retrieval';
COMMENT ON COLUMN public.simple_products.embedding IS 'Vector embedding generated using text-embedding-3-large model (2000 dimensions)';
COMMENT ON COLUMN public.simple_products.combined_text IS 'Formatted text used for embedding generation: PRODUCER: [name], PRODUCT: [name], DESCRIPTION: [description]';
COMMENT ON COLUMN public.simple_products.fts_combined IS 'tsvector (unaccent + simple config) over combined_text maintained by trigger';

-- Trigger function and trigger to maintain fts_combined (cannot use GENERATED due to unaccent STABLE immutability constraint)
CREATE OR REPLACE FUNCTION simple_products_fts_trigger()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.fts_combined := to_tsvector('simple', unaccent(coalesce(NEW.combined_text, '')));
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_simple_products_fts
BEFORE INSERT OR UPDATE OF combined_text ON public.simple_products
FOR EACH ROW EXECUTE FUNCTION simple_products_fts_trigger();

-- Verify table creation
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'simple_products' 
ORDER BY ordinal_position;

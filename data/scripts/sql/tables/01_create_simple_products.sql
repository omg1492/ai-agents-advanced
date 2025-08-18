-- Create simple_products table for storing product data with embeddings
-- This table stores product information from producers along with their vector embeddings

-- Drop table if it exists (for development)
DROP TABLE IF EXISTS public.simple_products;

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
    
    -- Combined text used for embedding generation
    combined_text TEXT NOT NULL,
    
    -- Vector embedding (using pgvector extension)
    -- Using 2000 dimensions for pgvector HNSW index compatibility
    embedding vector(2000)
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

-- Add table comment
COMMENT ON TABLE public.simple_products IS 'Stores product information with vector embeddings for similarity search';
COMMENT ON COLUMN public.simple_products.embedding IS 'Vector embedding generated using text-embedding-3-large model (2000 dimensions)';
COMMENT ON COLUMN public.simple_products.combined_text IS 'Formatted text used for embedding generation: PRODUCER: [name], PRODUCT: [name], DESCRIPTION: [description]';

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

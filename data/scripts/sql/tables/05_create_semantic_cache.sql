-- Create semantic_cache table for first-turn Q&A semantic caching
-- Stores generic question/answer pairs with vector embeddings of the question
-- Safe to re-run in development (drops and recreates table)

DROP TABLE IF EXISTS public.semantic_cache CASCADE;

CREATE TABLE public.semantic_cache (
    id          SERIAL PRIMARY KEY,
    question    TEXT NOT NULL UNIQUE,
    answer      TEXT NOT NULL,
    embedding   vector(2000) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- HNSW index for fast cosine similarity search on questions
CREATE INDEX idx_semantic_cache_embedding_cosine 
ON public.semantic_cache 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

COMMENT ON TABLE public.semantic_cache IS 'Generic first-turn Q&A pairs (question embedding for semantic cache lookup).';
COMMENT ON COLUMN public.semantic_cache.embedding IS '2000-d embedding (text-embedding-3-large) of question.';

-- Verification query listing columns
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'semantic_cache'
ORDER BY ordinal_position;

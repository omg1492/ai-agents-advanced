-- Create conversation_summaries table for compact semantic recall of past conversations
-- One summary row per (user_id, thread_id). Raw transcripts live in conversations_raw (short retention).
-- Safe to re-run in development (drops then recreates table). Do NOT run automatically in production without migration planning.

-- Required for gen_random_uuid(); safe if already installed
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DROP TABLE IF EXISTS public.conversation_summaries CASCADE;

CREATE TABLE public.conversation_summaries (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- External stable thread identifier (mirrors conversations_raw.thread_id)
  thread_id   TEXT NOT NULL,
  user_id     TEXT NOT NULL,
  -- Neutral recap (~<= 120 words). No PII, no speculative claims.
  summary     TEXT NOT NULL,
  -- Embedding of summary text for semantic memory search (2000 dims to align with text-embedding-3-large)
  embedding   vector(2000) NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Touch trigger to keep updated_at fresh on row modification
CREATE OR REPLACE FUNCTION public.conversation_summaries_touch()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conversation_summaries_touch ON public.conversation_summaries;
CREATE TRIGGER trg_conversation_summaries_touch
BEFORE UPDATE ON public.conversation_summaries
FOR EACH ROW EXECUTE FUNCTION public.conversation_summaries_touch();

-- Enforce one summary per thread per user
CREATE UNIQUE INDEX idx_conversation_summaries_user_thread ON public.conversation_summaries(user_id, thread_id);

-- Vector similarity index (HNSW) for cosine search over summaries (memory_search)
CREATE INDEX idx_conversation_summaries_embedding_cosine
ON public.conversation_summaries
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- (Optional) Recent summaries by user for recency-biased queries
CREATE INDEX idx_conversation_summaries_user_created_at ON public.conversation_summaries(user_id, created_at DESC);

-- Foreign key (optional). Using ON DELETE CASCADE so deleting a raw conversation removes its summary.
ALTER TABLE public.conversation_summaries
  ADD CONSTRAINT fk_conversation_summaries_thread
  FOREIGN KEY (thread_id) REFERENCES public.conversations_raw(thread_id) ON DELETE CASCADE;

COMMENT ON TABLE public.conversation_summaries IS 'Per-thread conversation summaries (longer retention) used for semantic memory search.';
COMMENT ON COLUMN public.conversation_summaries.summary IS 'Neutral concise recap (<= ~120 words).';
COMMENT ON COLUMN public.conversation_summaries.embedding IS '2000-d embedding of summary (text-embedding-3-large).';

-- Verification query (schema inspection)
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'conversation_summaries'
ORDER BY ordinal_position;

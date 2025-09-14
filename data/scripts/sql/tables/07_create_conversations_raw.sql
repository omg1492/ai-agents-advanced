-- Create conversations_raw table for storing full conversation transcripts (per thread)
-- Raw transcripts retained short-term (default 7 days) before summarization + purge.
-- Summaries & user profile enrichment will operate off this table.
-- Safe to re-run in development (drops then recreates table).

DROP TABLE IF EXISTS public.conversations_raw;

CREATE TABLE public.conversations_raw (
  id             SERIAL PRIMARY KEY,
  -- External conversation / thread identifier (e.g. OpenAI thread_id or app thread UUID)
  thread_id      TEXT NOT NULL UNIQUE,
  -- Authenticated end user identifier (Keycloak subject). Using TEXT for portability across IdP formats.
  user_id        TEXT NOT NULL,
  -- User friendly title stored separately (NOT in messages JSON). Can later be user‑edited or summarizer‑generated.
  title          TEXT NOT NULL DEFAULT 'Untitled conversation',
  -- Array of message objects: {"role":"user|assistant","content":"...","created_at":"ISO","mode":"chat|voice"}
  messages       JSONB NOT NULL,
  -- Summarization workflow status lifecycle: pending -> processing -> done | error (simplified: no attempts/locking)
  summary_status TEXT NOT NULL DEFAULT 'pending' CHECK (summary_status IN ('pending','processing','done','error')),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Expiration timestamp for raw retention window (default 7 days). Summaries persist separately.
  expires_at     TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '7 days')
);

-- Touch trigger to keep updated_at fresh on row modification
CREATE OR REPLACE FUNCTION public.conversations_raw_touch()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conversations_raw_touch ON public.conversations_raw;
CREATE TRIGGER trg_conversations_raw_touch
BEFORE UPDATE ON public.conversations_raw
FOR EACH ROW EXECUTE FUNCTION public.conversations_raw_touch();

-- Indexes
CREATE INDEX idx_conversations_raw_user_id ON public.conversations_raw(user_id);
CREATE INDEX idx_conversations_raw_expires_at ON public.conversations_raw(expires_at);
-- Accelerate batch pickup of pending summaries
CREATE INDEX idx_conversations_raw_summary_status ON public.conversations_raw(summary_status);
-- Optional future JSONB querying (commented until needed)
-- CREATE INDEX idx_conversations_raw_messages_gin ON public.conversations_raw USING GIN (messages jsonb_path_ops);

COMMENT ON TABLE public.conversations_raw IS 'Raw per-thread conversation transcripts (short retention) for memory summarization & profile enrichment.';
COMMENT ON COLUMN public.conversations_raw.title IS 'User supplied or summarizer generated title (separate column for efficient listing).';
COMMENT ON COLUMN public.conversations_raw.messages IS 'Ordered JSON array of message objects (role, content, created_at, mode).';
COMMENT ON COLUMN public.conversations_raw.summary_status IS 'Summarization pipeline status: pending|processing|done|error.';
COMMENT ON COLUMN public.conversations_raw.expires_at IS 'Timestamp after which raw transcript is eligible for purge (configured retention window).';

-- Verification query (schema inspection)
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'conversations_raw'
ORDER BY ordinal_position;

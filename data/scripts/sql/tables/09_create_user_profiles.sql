-- Create user_profiles table to store consolidated per-user memory/profile document
-- Populated by enrichment batch (future): aggregates stable user preferences, goals, dietary constraints, VIP flags, etc.
-- Safe to re-run in development (drops then recreates table). Do NOT auto-run in production without migration plan.

DROP TABLE IF EXISTS public.user_profiles CASCADE;

CREATE TABLE public.user_profiles (
  -- Authenticated end user identifier (Keycloak subject or other IdP subject). TEXT keeps portability.
  user_id     TEXT PRIMARY KEY,
  -- Consolidated profile object (structured JSON). Expected shape evolves; enrichment script owns schema.
  profile     JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Touch trigger to keep updated_at fresh on row modification
CREATE OR REPLACE FUNCTION public.user_profiles_touch()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_profiles_touch ON public.user_profiles;
CREATE TRIGGER trg_user_profiles_touch
BEFORE UPDATE ON public.user_profiles
FOR EACH ROW EXECUTE FUNCTION public.user_profiles_touch();

COMMENT ON TABLE public.user_profiles IS 'Per-user consolidated profile (preferences, constraints, inferred traits) derived from conversation summaries.';
COMMENT ON COLUMN public.user_profiles.profile IS 'JSONB document capturing structured user memory; enrichment job mutates this object atomically.';

-- Verification query (schema inspection)
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'user_profiles'
ORDER BY ordinal_position;

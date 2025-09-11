-- Create table for semantic concept embeddings (categories, cuisines, certifications, allergens)
-- Vector dimension fixed at 2000 to align with other embeddings.
-- Requires pgvector extension.

CREATE TABLE IF NOT EXISTS concept_embeddings (
    concept_type TEXT NOT NULL CHECK (concept_type IN ('category','cuisine','certification','allergen')),
    concept_id   TEXT NOT NULL,
    name         TEXT NOT NULL,
    description  TEXT,
    normalized_text TEXT NOT NULL,
    embedding    VECTOR(2000) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (concept_type, concept_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_concept_embeddings_type_id ON concept_embeddings(concept_type, concept_id);
CREATE INDEX IF NOT EXISTS idx_concept_embeddings_type ON concept_embeddings(concept_type);
CREATE INDEX IF NOT EXISTS idx_concept_embeddings_embedding ON concept_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE OR REPLACE FUNCTION trg_concept_embeddings_touch() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS concept_embeddings_touch ON concept_embeddings;
CREATE TRIGGER concept_embeddings_touch
    BEFORE UPDATE ON concept_embeddings
    FOR EACH ROW EXECUTE FUNCTION trg_concept_embeddings_touch();

COMMENT ON TABLE concept_embeddings IS 'Semantic embeddings for higher-level concepts used in BFS taxonomy search';
COMMENT ON COLUMN concept_embeddings.normalized_text IS 'Lowercased + accent stripped concatenation of name + description (embedding source)';

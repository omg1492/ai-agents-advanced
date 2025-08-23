-- Enable unaccent extension for accent-insensitive full-text search normalization
-- This is used by the simple_products FTS generated column

CREATE EXTENSION IF NOT EXISTS unaccent;

-- Verify installation
SELECT extname, extversion FROM pg_extension WHERE extname = 'unaccent';

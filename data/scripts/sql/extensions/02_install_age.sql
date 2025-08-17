-- Install Apache AGE extension for graph capabilities
-- This enables openCypher via the cypher() SQL function within PostgreSQL

CREATE EXTENSION IF NOT EXISTS age;

-- Load AGE for the session (required before calling cypher())
LOAD 'age';

-- Ensure AGE catalog is accessible in this session
SET search_path = ag_catalog, "$user", public;

-- Verify installation
SELECT extname, extversion FROM pg_extension WHERE extname = 'age';

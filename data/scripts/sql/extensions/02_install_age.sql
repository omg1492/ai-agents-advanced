-- Install Apache AGE extension for graph capabilities
-- This enables openCypher via the cypher() SQL function within PostgreSQL

CREATE EXTENSION IF NOT EXISTS age;

-- Try to load AGE library for the session
-- This is required for local PostgreSQL but will fail gracefully in Azure
-- where AGE must be preloaded via shared_preload_libraries
DO $$
BEGIN
    -- Attempt to load the AGE library
    LOAD 'age';
    RAISE NOTICE 'AGE library loaded successfully';
EXCEPTION
    WHEN OTHERS THEN
        -- If loading fails (e.g., in Azure where it's preloaded), just continue
        RAISE NOTICE 'AGE library already loaded or preloaded: %', SQLERRM;
END
$$;

-- Verify installation
SELECT extname, extversion FROM pg_extension WHERE extname = 'age';

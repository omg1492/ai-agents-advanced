-- Initialize Apache AGE graph for DreamFarm
-- Requires AGE extension to be installed (see extensions/02_install_age.sql)

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

-- Recreate the graph for idempotent development runs
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'dreamfarm') THEN
    PERFORM ag_catalog.drop_graph('dreamfarm', true);
  END IF;
  PERFORM ag_catalog.create_graph('dreamfarm');
END
$$ LANGUAGE plpgsql;

-- Document intended labels and relationships (labels are created implicitly on first use)
-- Vertices: Producer {producerId, name, description}
--           Product {productId, name}
--           Certification {certificationId, name, description}
--           Allergen {allergenId, name}
--           Category {name}
-- Edges:    PRODUCES (Producer -> Product)
--           HAS_CERTIFICATION (Producer -> Certification)
--           CONTAINS_ALLERGEN (Product -> Allergen)
--           HAS_CATEGORY (Product -> Category)
--           RELATED (Product <-> Product)

-- Verification: list graphs
SELECT name, namespace FROM ag_catalog.ag_graph ORDER BY name;

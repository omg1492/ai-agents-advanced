-- Initialize Apache AGE graph for DreamFarm
-- Requires AGE extension to be installed (see extensions/02_install_age.sql)

-- Ensure AGE is loaded and catalog is on search path for this session
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Recreate the graph for idempotent development runs
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'dreamfarm') THEN
    PERFORM drop_graph('dreamfarm', true);
  END IF;
  PERFORM create_graph('dreamfarm');
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

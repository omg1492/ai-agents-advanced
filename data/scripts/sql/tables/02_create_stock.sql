-- Create stock table to track per-producer product quantities

-- Drop table if it exists (for development convenience)
DROP TABLE IF EXISTS public.stock;

-- Create stock table
CREATE TABLE public.stock (
    producer_id UUID NOT NULL,
    product_id  UUID NOT NULL,
    on_stock    INTEGER NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT pk_stock PRIMARY KEY (producer_id, product_id)
);

-- Comments for documentation
COMMENT ON TABLE public.stock IS 'Tracks current stock levels for each (producer, product).';
COMMENT ON COLUMN public.stock.on_stock IS 'Current available quantity for the given producer/product.';

-- Verify table creation
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'stock' 
ORDER BY ordinal_position;

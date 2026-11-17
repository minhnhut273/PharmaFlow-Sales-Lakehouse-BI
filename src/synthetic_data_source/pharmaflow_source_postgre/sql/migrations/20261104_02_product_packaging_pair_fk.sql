-- Versioned additive hardening for a database already bootstrapped to source v2.
-- Existing rows are checked before replacing the single-column FK.
DO $migration$
DECLARE
    pair_unique_exists BOOLEAN;
    pair_fk_exists BOOLEAN;
BEGIN
    IF current_database() <> 'pharmaflow_source_postgre_v2' THEN
        RAISE EXCEPTION 'This migration is restricted to pharmaflow_source_postgre_v2; connected to %.', current_database();
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pos.sales_order_line l
        JOIN catalog.product_packaging pp ON pp.product_packaging_id = l.product_packaging_id
        WHERE l.product_packaging_id IS NOT NULL
          AND l.product_id <> pp.product_id
    ) THEN
        RAISE EXCEPTION 'Product/packaging mismatch exists; no constraint was changed.';
    END IF;

    SELECT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'catalog.product_packaging'::regclass
          AND conname = 'uq_product_packaging_id_product'
    ) INTO pair_unique_exists;

    IF NOT pair_unique_exists THEN
        ALTER TABLE catalog.product_packaging
            ADD CONSTRAINT uq_product_packaging_id_product
            UNIQUE (product_packaging_id, product_id);
    END IF;

    SELECT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'pos.sales_order_line'::regclass
          AND conname = 'fk_sales_line_product_packaging_pair'
    ) INTO pair_fk_exists;

    IF NOT pair_fk_exists THEN
        ALTER TABLE pos.sales_order_line
            DROP CONSTRAINT IF EXISTS sales_order_line_product_packaging_id_fkey;
        ALTER TABLE pos.sales_order_line
            ADD CONSTRAINT fk_sales_line_product_packaging_pair
            FOREIGN KEY (product_packaging_id, product_id)
            REFERENCES catalog.product_packaging(product_packaging_id, product_id);
    ELSE
        ALTER TABLE pos.sales_order_line
            DROP CONSTRAINT IF EXISTS sales_order_line_product_packaging_id_fkey;
    END IF;
END
$migration$;

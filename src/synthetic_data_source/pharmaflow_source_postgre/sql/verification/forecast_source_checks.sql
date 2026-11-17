-- Read-only acceptance queries for the source forecast contract.
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_type = 'BASE TABLE'
  AND table_schema IN ('catalog', 'org', 'pos', 'procurement', 'inventory')
ORDER BY table_schema, table_name;

SELECT source, COUNT(*) AS row_count
FROM pos.sales_order
GROUP BY source
ORDER BY source;

SELECT source, COUNT(*) AS row_count
FROM pos.sales_order_line
GROUP BY source
ORDER BY source;

SELECT source, subject_kind, COUNT(*) AS row_count,
       MIN(period_start) AS first_period, MAX(period_end) AS last_period
FROM pos.sales_observation
GROUP BY source, subject_kind
ORDER BY source, subject_kind;

SELECT source, COUNT(*) AS row_count,
       COUNT(*) FILTER (WHERE latitude IS NULL OR longitude IS NULL) AS missing_coordinates
FROM org.store
GROUP BY source
ORDER BY source;

-- These are expected to return zero. Public catalog/locator evidence must not
-- be represented as POS sales and no sale implies inventory movements.
SELECT COUNT(*) AS public_catalog_sales
FROM pos.sales_order
WHERE source LIKE 'LONGCHAU_PUBLIC_%';

SELECT COUNT(*) AS movements_from_dataset_sales
FROM inventory.inventory_movement m
JOIN pos.sales_order_line l USING (sales_order_line_id)
WHERE l.source IN ('IRPD_PUBLISHER_REPORTED_POS',
                   'SIMULATED_ONYX_DAILY_FACT_TO_POS',
                   'SIMULATED_PHARMA_SALES_ATC_SCALE10');

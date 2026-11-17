\set ON_ERROR_STOP on
-- Versioned fresh-database bootstrap record for forecast source contract v2.
-- This file is intentionally not an in-place upgrade for the old 24-table DB.
-- The canonical DDL is schema_full.sql; this wrapper fails closed unless the
-- selected database has no application tables, then includes that exact file.
DO $bootstrap_guard$
DECLARE
    app_table_count INTEGER;
BEGIN
    SELECT count(*) INTO app_table_count
    FROM information_schema.tables
    WHERE table_type = 'BASE TABLE'
      AND table_schema NOT IN ('pg_catalog', 'information_schema');

    IF app_table_count <> 0 THEN
        RAISE EXCEPTION 'Forecast source v2 bootstrap requires an empty database; found % application tables.', app_table_count;
    END IF;
END
$bootstrap_guard$;

\ir ../../schema_full.sql

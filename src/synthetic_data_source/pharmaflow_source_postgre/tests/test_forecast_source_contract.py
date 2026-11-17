from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import source_db  # noqa: E402
from source_prepare import RUN_ROOT, SOURCE_ORDER, load_yaml, read_csv, source_folder_name  # noqa: E402


RUN_ID = "20261104-forecast-schema-v2"
RUN = RUN_ROOT
BASELINE_SQL = RUN / "baseline" / "schema_full.pre-v2.sql"
CURRENT_SQL = PACKAGE_ROOT / "schema_full.sql"
ALLOWED_CHANGED_TABLES = {
    "catalog.manufacturer",
    "catalog.unit_of_measure",
    "catalog.product_category",
    "catalog.product",
    "catalog.product_category_assignment",
    "catalog.product_source_reference",
    "catalog.product_packaging",
    "org.store",
    "pos.sales_order",
    "pos.sales_order_line",
}


def _table_creates(sql: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for statement in source_db._split_sql(sql):
        match = re.search(r"\bCREATE\s+TABLE\s+([a-z_][\w]*\.[a-z_][\w]*)\s*\(", statement, re.I)
        if match:
            result[match.group(1).lower()] = " ".join(statement.split())
    return result


def _sample_dir(source: str) -> Path:
    return RUN / source_folder_name(source) / "prepared" / "sample"


def _manifest(source: str) -> dict:
    path = RUN / source_folder_name(source) / "manifest.sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_bootstrap_retains_other_domains_and_limits_schema_changes_to_source_contract() -> None:
    baseline = _table_creates(BASELINE_SQL.read_text(encoding="utf-8"))
    current_text = CURRENT_SQL.read_text(encoding="utf-8")
    current = _table_creates(current_text)

    assert len(baseline) == 34
    assert len(current) == 35
    assert set(baseline) <= set(current)
    assert set(current) - set(baseline) == {"pos.sales_observation"}
    assert not re.search(r"\bDROP\s+(TABLE|SCHEMA|DATABASE)\b", current_text, re.I)
    for table, statement in baseline.items():
        if table not in ALLOWED_CHANGED_TABLES:
            assert current[table] == statement, f"Unrelated table changed: {table}"

    product = current["catalog.product"]
    for retained in ("brand_name", "manufacturer_id", "base_uom_code", "is_active", "source"):
        assert re.search(rf"\b{retained}\b", product)
    for removed in ("dosage_form", "active_ingredient_text", "strength_text", "registration_number", "logo"):
        assert not re.search(rf"\b{removed}\b", product)
    assert "fk_sales_line_product_packaging_pair" in current["pos.sales_order_line"]


def test_bounded_sample_manifests_and_source_grains() -> None:
    assert tuple(SOURCE_ORDER) == ("longchau", "irpd", "onyx", "pharma_sales")
    for source in SOURCE_ORDER:
        manifest = _manifest(source)
        assert manifest["validation"]["valid"] is True
        if source != "longchau":
            assert manifest["sample_rule_set"] == "bounded-sample-v2"

    longchau = _manifest("longchau")
    assert longchau["sample_parameters"]["product_count"] == 50
    assert longchau["sample_parameters"]["store_count"] == 20
    assert set(longchau["sample_parameters"]["taxonomy_roots"].values()) == {10}
    assert longchau["prepared_row_counts"]["orders"] == 0
    assert longchau["prepared_row_counts"]["lines"] == 0
    assert longchau["prepared_row_counts"]["observations"] == 0
    if not (_sample_dir("longchau") / "products.csv").exists():
        pytest.skip("Prepared local CSV fixtures are excluded from standalone repository.")
    assert len({r["product_code"] for r in _csv_rows(_sample_dir("longchau") / "products.csv")}) == 50
    assert len({r["store_code"] for r in _csv_rows(_sample_dir("longchau") / "stores.csv")}) == 20

    irpd_full = _csv_rows(RUN / source_folder_name("irpd") / "prepared" / "full" / "orders.csv")
    irpd_sample = _csv_rows(_sample_dir("irpd") / "orders.csv")
    first_seven_dates = sorted({datetime.fromisoformat(row["ordered_at"].replace("Z", "+00:00")).date() for row in irpd_full})[:7]
    sample_dates = {datetime.fromisoformat(row["ordered_at"].replace("Z", "+00:00")).date() for row in irpd_sample}
    assert sample_dates == set(first_seven_dates)
    sample_invoice_ids = {row["order_number"] for row in irpd_sample}
    full_lines = _csv_rows(RUN / source_folder_name("irpd") / "prepared" / "full" / "lines.csv")
    sample_lines = _csv_rows(_sample_dir("irpd") / "lines.csv")
    assert Counter(row["order_number"] for row in sample_lines) == Counter(
        row["order_number"] for row in full_lines if row["order_number"] in sample_invoice_ids
    )

    onyx_rows = _csv_rows(_sample_dir("onyx") / "observations.csv")
    dates_by_store: dict[str, set[str]] = defaultdict(set)
    for row in onyx_rows:
        dates_by_store[row["store_code"]].add(row["period_start"])
    assert len(dates_by_store) == 5
    assert all(len(dates) == 14 for dates in dates_by_store.values())

    pharma_full = _csv_rows(RUN / source_folder_name("pharma_sales") / "prepared" / "full" / "observations.csv")
    pharma_sample = _csv_rows(_sample_dir("pharma_sales") / "observations.csv")
    first_28_observed_days = sorted({row["period_start"] for row in pharma_full})[:28]
    assert sorted({row["period_start"] for row in pharma_sample}) == first_28_observed_days
    assert all(not row["quantity_uom_code"] for row in pharma_sample)

    product_codes: list[str] = []
    for source in ("longchau", "irpd", "onyx"):
        product_codes.extend(row["product_code"] for row in _csv_rows(_sample_dir(source) / "products.csv"))
    assert len(product_codes) == len(set(product_codes)), "Source product identifiers must remain namespaced."


def test_source_mapping_csvs_have_complete_auditable_rows() -> None:
    expected_header = [
        "source_file",
        "source_grain",
        "source_field",
        "target_table_column",
        "transformation",
        "data_class",
        "notes",
    ]
    for source in SOURCE_ORDER:
        path = PACKAGE_ROOT / "config" / "mappings" / f"{source}.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames == expected_header
            rows = list(reader)
        assert rows, source
        assert all(all(row[field].strip() for field in expected_header[:6]) for row in rows), source


@pytest.fixture(scope="module")
def test_database():
    if not source_db.TEST_ENVIRONMENT_ACTIVE:
        pytest.skip("The isolated Neon test branch is retired; its successful acceptance run is preserved as historical evidence.")
    if not os.environ.get("PHARMAFLOW_TEST_DATABASE_URL_UNPOOLED"):
        pytest.skip("Live Neon contract checks require an active isolated test-branch URL.")
    connection = source_db.connect(source_db.TEST_DATABASE)
    try:
        yield connection
    finally:
        connection.close()


def test_test_branch_isolated_and_reconciled(test_database: psycopg.Connection) -> None:
    name = test_database.execute("SELECT current_database()").fetchone()[0]
    assert name == source_db.TEST_DATABASE
    table_count = test_database.execute(
        """SELECT count(*) FROM information_schema.tables
           WHERE table_type='BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema')"""
    ).fetchone()[0]
    assert table_count == 35

    for source in SOURCE_ORDER:
        prepared = _sample_dir(source)
        expected_sources, expected = source_db._expected_sources(prepared)
        actual = source_db._source_counts(test_database, expected_sources)
        assert actual == expected, source
        verified_path = (
            RUN
            / "test"
            / "forecast-validation-20261104"
            / source_folder_name(source)
            / "verified-sample.json"
        )
        assert verified_path.exists(), f"Missing test-branch reconciliation evidence: {source}"

    expected_warehouses = {
        f"SIM_STORE_WH::{source.upper()}::{row['demand_store_code']}": row["demand_store_code"]
        for source in SOURCE_ORDER
        for row in _csv_rows(_sample_dir(source) / "orders.csv")
    }
    actual_warehouses = {
        str(code): str(store_code)
        for code, kind, origin, store_code in test_database.execute(
            """SELECT w.warehouse_code,w.warehouse_kind,w.data_origin,s.store_code
               FROM org.warehouse w JOIN org.store s USING(store_id)
               WHERE w.warehouse_code LIKE 'SIM_STORE_WH::%'"""
        ).fetchall()
        if kind == "STORE" and origin == "SYNTHETIC"
    }
    assert actual_warehouses == expected_warehouses

    untouched = test_database.execute(
        """SELECT
            (SELECT count(*) FROM procurement.purchase_order),
            (SELECT count(*) FROM procurement.goods_receipt),
            (SELECT count(*) FROM inventory.inventory_movement),
            (SELECT count(*) FROM inventory.inventory_balance),
            (SELECT count(*) FROM pos.customer_request)"""
    ).fetchone()
    assert tuple(untouched) == (0, 0, 0, 0, 0)

    invalid_pairs = test_database.execute(
        """SELECT count(*) FROM pos.sales_order_line l
           JOIN catalog.product_packaging pp ON pp.product_packaging_id=l.product_packaging_id
           WHERE l.product_id <> pp.product_id"""
    ).fetchone()[0]
    assert invalid_pairs == 0
    null_optional_fields = test_database.execute(
        "SELECT count(*) FROM pos.sales_order WHERE fulfillment_location_id IS NOT NULL OR sales_channel_id IS NOT NULL"
    ).fetchone()[0]
    assert null_optional_fields == 0
    currency_errors = test_database.execute(
        """SELECT count(*) FROM pos.sales_order_line
           WHERE (line_amount IS NOT NULL OR cost_amount IS NOT NULL OR margin_amount IS NOT NULL)
             AND currency_code IS NULL"""
    ).fetchone()[0]
    assert currency_errors == 0


def test_daily_order_instants_match_store_timezone_and_prepared_source(test_database: psycopg.Connection) -> None:
    expected_orders: dict[str, dict[str, str]] = {}
    for source in SOURCE_ORDER:
        for row in _csv_rows(_sample_dir(source) / "orders.csv"):
            expected_orders[row["order_number"]] = row
    rows = test_database.execute(
        """SELECT o.order_number,o.ordered_at,s.timezone_name
           FROM pos.sales_order o JOIN org.store s ON s.store_id=o.demand_location_id"""
    ).fetchall()
    assert len(rows) == len(expected_orders)
    for order_number, actual, timezone_name in rows:
        expected = datetime.fromisoformat(expected_orders[order_number]["ordered_at"].replace("Z", "+00:00"))
        zone = ZoneInfo(timezone_name)
        assert expected.astimezone(timezone.utc) == actual.astimezone(timezone.utc)
        assert expected.astimezone(zone) == actual.astimezone(zone)


def _expect_constraint_failure(connection: psycopg.Connection, exception_type: type[Exception], sql: str, params: tuple) -> None:
    with connection.transaction():
        with pytest.raises(exception_type):
            with connection.transaction():
                connection.execute(sql, params)


def test_database_constraints_reject_invalid_observation_location_fk_and_packaging(test_database: psycopg.Connection) -> None:
    store_id = test_database.execute("SELECT store_id FROM org.store ORDER BY store_id LIMIT 1").fetchone()[0]
    _expect_constraint_failure(
        test_database,
        psycopg.errors.CheckViolation,
        """INSERT INTO pos.sales_observation(
             store_id,subject_kind,product_id,category_id,period_start,period_end,quantity,source)
           VALUES (%s,'PRODUCT',NULL,NULL,DATE '2026-01-01',DATE '2026-01-01',1,'SIMULATED_TEST')""",
        (store_id,),
    )
    _expect_constraint_failure(
        test_database,
        psycopg.errors.CheckViolation,
        """INSERT INTO org.store(store_code,store_name,latitude,longitude,timezone_name,store_status,source)
           VALUES ('__TEST_LAT_RANGE__','Temporary test',91,0,'Europe/Belgrade','ACTIVE','SIMULATED_TEST')""",
        (),
    )

    candidate = test_database.execute(
        """SELECT product_id,product_packaging_id FROM catalog.product_packaging
           ORDER BY product_id LIMIT 1"""
    ).fetchone()
    other_product = test_database.execute(
        "SELECT product_id FROM catalog.product WHERE product_id <> %s ORDER BY product_id LIMIT 1",
        (candidate[0],),
    ).fetchone()
    order_id = test_database.execute("SELECT sales_order_id FROM pos.sales_order ORDER BY sales_order_id LIMIT 1").fetchone()[0]
    next_line = test_database.execute(
        "SELECT COALESCE(max(line_number),0)+1000 FROM pos.sales_order_line WHERE sales_order_id=%s",
        (order_id,),
    ).fetchone()[0]
    _expect_constraint_failure(
        test_database,
        psycopg.errors.ForeignKeyViolation,
        """INSERT INTO pos.sales_order_line(sales_order_id,line_number,product_id,product_packaging_id,sold_quantity,source)
           VALUES (%s,%s,%s,%s,1,'SIMULATED_TEST')""",
        (order_id, next_line, other_product[0], candidate[1]),
    )


def test_loader_rolls_back_a_failed_source_transaction_and_resume_is_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    if not source_db.TEST_ENVIRONMENT_ACTIVE:
        pytest.skip("The isolated Neon test branch is retired; do not reconnect to a second environment.")
    if not os.environ.get("PHARMAFLOW_TEST_DATABASE_URL_UNPOOLED"):
        pytest.skip("Transactional loader checks require the isolated test-branch URL.")
    sample = _csv_rows(_sample_dir("longchau") / "products.csv")
    product_code = sample[0]["product_code"]
    with source_db.connect(source_db.TEST_DATABASE) as connection:
        original_name = connection.execute("SELECT product_name FROM catalog.product WHERE product_code=%s", (product_code,)).fetchone()[0]
        connection.execute("UPDATE catalog.product SET product_name='__ROLLBACK_SENTINEL__' WHERE product_code=%s", (product_code,))

    original_loader = source_db._load_source_data

    def fail_after_database_writes(connection: psycopg.Connection, source: str, prepared: Path) -> dict[str, int]:
        original_loader(connection, source, prepared)
        raise RuntimeError("injected failure after writes, before commit")

    monkeypatch.setattr(source_db, "_load_source_data", fail_after_database_writes)
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            source_db.load_source("longchau", "sample", source_db.TEST_DATABASE)
        with source_db.connect(source_db.TEST_DATABASE) as connection:
            rolled_back_name = connection.execute(
                "SELECT product_name FROM catalog.product WHERE product_code=%s", (product_code,)
            ).fetchone()[0]
            assert rolled_back_name == "__ROLLBACK_SENTINEL__"
    finally:
        monkeypatch.setattr(source_db, "_load_source_data", original_loader)
        source_db.load_source("longchau", "sample", source_db.TEST_DATABASE)

    with source_db.connect(source_db.TEST_DATABASE) as connection:
        restored_name = connection.execute("SELECT product_name FROM catalog.product WHERE product_code=%s", (product_code,)).fetchone()[0]
        assert restored_name == original_name

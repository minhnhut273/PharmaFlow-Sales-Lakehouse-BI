from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Iterator

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from source_prepare import (
    PACKAGE_ROOT,
    PROJECT_ROOT,
    RUN_ID,
    RUN_ROOT,
    SOURCE_ORDER,
    count_csv_rows,
    load_yaml,
    read_csv,
    sha256_file,
    source_folder_name,
)


PROJECT_CONFIG = load_yaml(PACKAGE_ROOT / "config" / "project.yaml")
TARGET_DATABASE = str(PROJECT_CONFIG["target_database"])
PREVIOUS_DATABASE = str(PROJECT_CONFIG["previous_database"])
PREVIOUS_DATABASE_STATUS = str(PROJECT_CONFIG.get("previous_database_status", "ACTIVE"))
PREVIOUS_DATABASE_BACKUP = PROJECT_CONFIG.get("previous_database_backup", {})
TEST_ENVIRONMENT = PROJECT_CONFIG["test_environment"]
TEST_DATABASE = str(TEST_ENVIRONMENT["database_name"])
TEST_RUN_KEY = str(TEST_ENVIRONMENT["run_key"])
TEST_ENVIRONMENT_ACTIVE = str(TEST_ENVIRONMENT.get("status", "ACTIVE")).upper() == "ACTIVE"
TEST_ROOT = RUN_ROOT / "test" / TEST_RUN_KEY
WRITABLE_DATABASES = {TARGET_DATABASE}

TABLE_CONFIG = {
    "uoms": ("catalog.unit_of_measure", "source"),
    "manufacturers": ("catalog.manufacturer", "source"),
    "categories": ("catalog.product_category", "source"),
    "products": ("catalog.product", "source"),
    "assignments": ("catalog.product_category_assignment", "source"),
    "references": ("catalog.product_source_reference", "source"),
    "packaging": ("catalog.product_packaging", "source"),
    "stores": ("org.store", "source"),
    "observations": ("pos.sales_observation", "source"),
    "orders": ("pos.sales_order", "source"),
    "lines": ("pos.sales_order_line", "source"),
}


def _read_env_file() -> None:
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    with env_file.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            match = re.match(r"^\s*(?:export\s+)?DATABASE_URL_UNPOOLED\s*=\s*(.*?)\s*$", line)
            if not match:
                continue
            value = match.group(1)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if value and not os.environ.get("DATABASE_URL_UNPOOLED"):
                os.environ["DATABASE_URL_UNPOOLED"] = value
            return


def _dsn_for_database(database: str) -> str:
    if database != TARGET_DATABASE:
        raise RuntimeError(_retired_database_message(database))
    _read_env_file()
    dsn = os.environ.get("DATABASE_URL_UNPOOLED")
    if not dsn:
        raise RuntimeError("DATABASE_URL_UNPOOLED is not set and was not found in the repository .env file.")
    try:
        parsed = conninfo_to_dict(dsn)
    except Exception:
        raise RuntimeError("DATABASE_URL_UNPOOLED could not be parsed as a PostgreSQL connection string.") from None
    host = parsed.get("host", "")
    if "pooler" in host.casefold():
        raise RuntimeError("A pooled Neon endpoint was supplied; this loader requires DATABASE_URL_UNPOOLED.")
    return make_conninfo(dsn, dbname=database, application_name="PharmaFlowForecastSourceLoader", connect_timeout=30)


def connect(database: str = TARGET_DATABASE) -> psycopg.Connection:
    if database != TARGET_DATABASE:
        raise RuntimeError(_retired_database_message(database))
    try:
        connection = psycopg.connect(_dsn_for_database(database))
    except Exception as exc:
        raise RuntimeError(f"Could not connect to the configured Neon database ({type(exc).__name__}).") from None
    actual = connection.execute("SELECT current_database()").fetchone()[0]
    if actual != database:
        connection.close()
        raise RuntimeError(f"Connected to {actual!r}, expected {database!r}; refusing to continue.")
    return connection


def _retired_database_message(database: str) -> str:
    if database == TEST_DATABASE:
        return (
            f"Database {database!r} belongs to the retired and deleted Neon test branch; "
            f"only {TARGET_DATABASE!r} is active. Historical acceptance evidence is preserved under {TEST_ROOT}."
        )
    if database == PREVIOUS_DATABASE:
        backup_path = str(PREVIOUS_DATABASE_BACKUP.get("path", "the package backup folder"))
        return (
            f"Database {database!r} was deleted after its verified backup; only {TARGET_DATABASE!r} is active. "
            f"Use the retained archive at {backup_path}."
        )
    return f"Refusing database {database!r}; the only active configured database is {TARGET_DATABASE!r}."


def _split_sql(sql: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    quote: str | None = None
    dollar_tag: str | None = None
    line_comment = False
    block_depth = 0
    index = 0
    while index < len(sql):
        char = sql[index]
        nxt = sql[index + 1] if index + 1 < len(sql) else ""
        if line_comment:
            buffer.append(char)
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_depth:
            buffer.append(char)
            if char == "/" and nxt == "*":
                buffer.append(nxt)
                block_depth += 1
                index += 2
                continue
            if char == "*" and nxt == "/":
                buffer.append(nxt)
                block_depth -= 1
                index += 2
                continue
            index += 1
            continue
        if dollar_tag:
            if sql.startswith(dollar_tag, index):
                buffer.extend(dollar_tag)
                index += len(dollar_tag)
                dollar_tag = None
            else:
                buffer.append(char)
                index += 1
            continue
        if quote:
            buffer.append(char)
            if char == quote:
                if nxt == quote:
                    buffer.append(nxt)
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if char == "-" and nxt == "-":
            buffer.extend((char, nxt))
            line_comment = True
            index += 2
            continue
        if char == "/" and nxt == "*":
            buffer.extend((char, nxt))
            block_depth = 1
            index += 2
            continue
        if char in {"'", '"'}:
            quote = char
            buffer.append(char)
            index += 1
            continue
        if char == "$":
            match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", sql[index:])
            if match:
                dollar_tag = match.group(0)
                buffer.extend(dollar_tag)
                index += len(dollar_tag)
                continue
        if char == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer.clear()
            index += 1
            continue
        buffer.append(char)
        index += 1
    statement = "".join(buffer).strip()
    if statement:
        statements.append(statement)
    return statements


def _artifact_root(database: str) -> Path:
    if database == TEST_DATABASE:
        return TEST_ROOT
    if database == TARGET_DATABASE:
        return RUN_ROOT
    raise RuntimeError(f"No run-artifact location is configured for database: {database}")


def _source_artifact_root(source: str, database: str) -> Path:
    return _artifact_root(database) / source_folder_name(source)


def _require_current_marker(source: str, mode: str, database: str) -> dict[str, Any]:
    evidence_root = _source_artifact_root(source, database)
    marker_path = evidence_root / f"verified-{mode}.json"
    manifest_path = RUN_ROOT / source_folder_name(source) / f"manifest.{mode}.json"
    if not marker_path.exists():
        raise RuntimeError(f"Verify {mode} {source} on {database} before continuing.")
    if not manifest_path.exists():
        raise RuntimeError(f"The prepared {mode} manifest is missing for {source}.")
    marker = json.loads(marker_path.read_text(encoding="utf-8-sig"))
    manifest_sha = sha256_file(manifest_path)
    if marker.get("database") != database or marker.get("manifest_sha256") != manifest_sha:
        raise RuntimeError(f"The {mode} verification marker for {source} is stale or belongs to another database.")
    return marker


def bootstrap_schema(database: str = TARGET_DATABASE) -> dict[str, Any]:
    if database not in WRITABLE_DATABASES:
        raise RuntimeError(f"Schema bootstrap is not allowed on database: {database}")
    with connect(database) as connection:
        existing = connection.execute(
            """SELECT table_schema, table_name FROM information_schema.tables
               WHERE table_type='BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema')
               ORDER BY table_schema, table_name"""
        ).fetchall()
        if existing:
            raise RuntimeError(
                f"Bootstrap requires an empty target database; found {len(existing)} existing tables. No schema changes were applied."
            )
        schema_file = PACKAGE_ROOT / "schema_full.sql"
        sql = schema_file.read_text(encoding="utf-8")
        sql = re.sub(r"(?im)^\s*(?:BEGIN|COMMIT)\s*;\s*$", "", sql)
        statements = _split_sql(sql)
        with connection.transaction():
            for statement in statements:
                connection.execute(statement, prepare=False)
        objects = connection.execute(
            """SELECT count(*) FROM information_schema.tables
               WHERE table_type='BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema')"""
        ).fetchone()[0]
        expected = len(re.findall(r"(?im)^CREATE\s+TABLE\s+[\w.]+", sql))
        if objects != expected:
            raise RuntimeError(f"Bootstrap table count mismatch: expected {expected}, found {objects}.")
    result = {
        "database": database,
        "schema_file": str(schema_file.relative_to(PACKAGE_ROOT)).replace("\\", "/"),
        "schema_sha256": sha256_file(schema_file),
        "statement_count": len(statements),
        "table_count": expected,
        "bootstrapped_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _write_run_json(_artifact_root(database) / "database" / "bootstrap.json", result)
    return result


def apply_migration(migration_name: str, database: str = TARGET_DATABASE) -> dict[str, Any]:
    """Apply an explicitly allowlisted, forward-only migration to the v2 target."""
    allowed = {
        "20261104_02_product_packaging_pair_fk": PACKAGE_ROOT
        / "sql"
        / "migrations"
        / "20261104_02_product_packaging_pair_fk.sql"
    }
    if database != TARGET_DATABASE:
        raise RuntimeError(f"Versioned production migrations are not allowed on database: {database}")
    migration_path = allowed.get(migration_name)
    if migration_path is None:
        raise ValueError(f"Migration is not allowlisted: {migration_name}")
    if not migration_path.is_file():
        raise RuntimeError(f"Migration file not found: {migration_path}")

    statements = _split_sql(migration_path.read_text(encoding="utf-8"))
    with connect(database) as connection:
        with connection.transaction():
            before = connection.execute(
                """SELECT
                     (SELECT count(*) FROM catalog.product_packaging),
                     (SELECT count(*) FROM pos.sales_order_line)"""
            ).fetchone()
            for statement in statements:
                connection.execute(statement, prepare=False)
            constraints = connection.execute(
                """SELECT conname FROM pg_constraint
                   WHERE conrelid IN ('catalog.product_packaging'::regclass,'pos.sales_order_line'::regclass)
                     AND conname IN ('uq_product_packaging_id_product','fk_sales_line_product_packaging_pair')"""
            ).fetchall()
            names = {str(row[0]) for row in constraints}
            expected = {"uq_product_packaging_id_product", "fk_sales_line_product_packaging_pair"}
            if names != expected:
                raise RuntimeError(f"Migration verification failed; found constraints {sorted(names)}")
            after = connection.execute(
                """SELECT
                     (SELECT count(*) FROM catalog.product_packaging),
                     (SELECT count(*) FROM pos.sales_order_line)"""
            ).fetchone()
            if tuple(before) != tuple(after):
                raise RuntimeError("Migration changed source row counts unexpectedly.")

    result = {
        "database": database,
        "migration": migration_name,
        "applied_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "migration_sha256": sha256_file(migration_path),
        "verified_constraints": sorted(names),
        "row_counts_before_after": {"product_packaging": int(before[0]), "sales_order_line": int(before[1])},
        "status": "PASS",
    }
    _write_run_json(RUN_ROOT / "final" / "migrations" / f"{migration_name}.json", result)
    return result


def _write_run_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def _value(value: str | None) -> str | None:
    return value if value not in {"", None} else None


def _decimal(value: str | None) -> Decimal | None:
    value = _value(value)
    return Decimal(value) if value is not None else None


def _integer(value: str | None) -> int | None:
    value = _value(value)
    return int(value) if value is not None else None


def _boolean(value: str | None) -> bool | None:
    value = _value(value)
    if value is None:
        return None
    if value.casefold() in {"true", "1", "yes"}:
        return True
    if value.casefold() in {"false", "0", "no"}:
        return False
    raise ValueError(f"Invalid prepared boolean: {value!r}")


def _timestamp(value: str | None) -> datetime | None:
    value = _value(value)
    return datetime.fromisoformat(value) if value is not None else None


def _ids(connection: psycopg.Connection, table: str, key_column: str, id_column: str) -> dict[str, int]:
    rows = connection.execute(f"SELECT {key_column}, {id_column} FROM {table}").fetchall()
    return {str(key): int(identifier) for key, identifier in rows}


def _need(mapping: dict[str, int], key: str | None, context: str) -> int:
    if key is None or key not in mapping:
        raise RuntimeError(f"Prepared foreign key not found for {context}: {key!r}")
    return mapping[key]


def _executemany(connection: psycopg.Connection, statement: str, rows: Iterable[tuple[Any, ...]]) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(statement, rows)


def _load_dimensions(connection: psycopg.Connection, prepared: Path) -> None:
    _executemany(
        connection,
        """INSERT INTO catalog.unit_of_measure(uom_code,uom_name,uom_kind,source)
           VALUES (%s,%s,%s,%s) ON CONFLICT (uom_code) DO UPDATE SET
           uom_name=excluded.uom_name,uom_kind=excluded.uom_kind,source=excluded.source""",
        ((row["uom_code"], row["uom_name"], row["uom_kind"], row["source"]) for row in _rows(prepared / "uoms.csv")),
    )
    _executemany(
        connection,
        """INSERT INTO catalog.manufacturer(manufacturer_code,manufacturer_name,country_code,source)
           VALUES (%s,%s,%s,%s) ON CONFLICT (manufacturer_code) DO UPDATE SET
           manufacturer_name=excluded.manufacturer_name,country_code=excluded.country_code,source=excluded.source""",
        ((_value(row.get("manufacturer_code")), row["manufacturer_name"], _value(row.get("country_code")), row["source"])
         for row in _rows(prepared / "manufacturers.csv")),
    )

    category_rows = list(_rows(prepared / "categories.csv"))
    category_cache = {
        (str(scheme), str(code)): int(identifier)
        for scheme, code, identifier in connection.execute(
            "SELECT taxonomy_scheme,category_code,category_id FROM catalog.product_category"
        ).fetchall()
    }
    pending = category_rows
    while pending:
        deferred = []
        ready = []
        for row in pending:
            scheme = row["taxonomy_scheme"]
            category_code = row["category_code"]
            parent_code = _value(row.get("parent_category_code"))
            parent_id = None
            if parent_code is not None:
                parent_id = category_cache.get((scheme, parent_code))
                if parent_id is None:
                    deferred.append(row)
                    continue
            ready.append((scheme, category_code, row["category_name"], parent_id,
                          _value(row.get("source_category_path")), row["source"]))
        if not ready:
            unresolved = [(row["taxonomy_scheme"], row["category_code"], row.get("parent_category_code")) for row in deferred[:10]]
            raise RuntimeError(f"Category parent references are missing or cyclic: {unresolved}")
        _executemany(
            connection,
            """INSERT INTO catalog.product_category(
                   taxonomy_scheme,category_code,category_name,parent_category_id,source_category_path,is_active,source)
               VALUES (%s,%s,%s,%s,%s,TRUE,%s)
               ON CONFLICT (taxonomy_scheme,category_code) DO UPDATE SET
                   category_name=excluded.category_name,parent_category_id=excluded.parent_category_id,
                   source_category_path=excluded.source_category_path,is_active=TRUE,source=excluded.source""",
            ready,
        )
        category_cache = {
            (str(scheme), str(code)): int(identifier)
            for scheme, code, identifier in connection.execute(
                "SELECT taxonomy_scheme,category_code,category_id FROM catalog.product_category"
            ).fetchall()
        }
        pending = deferred

    manufacturer_ids = _ids(connection, "catalog.manufacturer", "manufacturer_code", "manufacturer_id")
    def product_values() -> Iterator[tuple[Any, ...]]:
        for row in _rows(prepared / "products.csv"):
            manufacturer_code = _value(row.get("manufacturer_code"))
            manufacturer_id = _need(manufacturer_ids, manufacturer_code, row["product_code"]) if manufacturer_code else None
            yield (row["product_code"], row["product_name"], _value(row.get("brand_name")), manufacturer_id,
                   _value(row.get("base_uom_code")), _boolean(row.get("is_active")), row["source"])

    _executemany(
        connection,
        """INSERT INTO catalog.product(product_code,product_name,brand_name,manufacturer_id,base_uom_code,is_active,source)
           VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (product_code) DO UPDATE SET
           product_name=excluded.product_name,brand_name=excluded.brand_name,manufacturer_id=excluded.manufacturer_id,
           base_uom_code=excluded.base_uom_code,is_active=excluded.is_active,source=excluded.source,updated_at=now()""",
        product_values(),
    )

    product_ids = _ids(connection, "catalog.product", "product_code", "product_id")
    def assignment_values() -> Iterator[tuple[Any, ...]]:
      for row in _rows(prepared / "assignments.csv"):
        product_id = _need(product_ids, row.get("product_code"), "category assignment")
        category_id = category_cache.get((row["taxonomy_scheme"], row["category_code"]))
        if category_id is None:
            raise RuntimeError(f"Prepared assignment category is missing: {row['taxonomy_scheme']}:{row['category_code']}")
        yield (product_id, category_id, row["assignment_status"], row["assignment_basis"], row["source"])

    _executemany(
        connection,
        """INSERT INTO catalog.product_category_assignment(product_id,category_id,assignment_status,assignment_basis,source)
           VALUES (%s,%s,%s,%s,%s) ON CONFLICT (product_id,category_id) DO UPDATE SET
           assignment_status=excluded.assignment_status,assignment_basis=excluded.assignment_basis,
           source=excluded.source,assigned_at=now()""",
        assignment_values(),
    )

    def reference_values() -> Iterator[tuple[Any, ...]]:
      for row in _rows(prepared / "references.csv"):
        product_id = _need(product_ids, row.get("product_code"), "product source reference")
        yield (product_id, row["source"], row["external_product_key"], row["match_status"],
               _value(row.get("match_basis")), _timestamp(row.get("observed_at")))

    _executemany(
        connection,
        """INSERT INTO catalog.product_source_reference(
               product_id,source,external_product_key,match_status,match_basis,observed_at)
           VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (source,external_product_key) DO UPDATE SET
               product_id=excluded.product_id,match_status=excluded.match_status,
               match_basis=excluded.match_basis,observed_at=excluded.observed_at""",
        reference_values(),
    )

    def packaging_values() -> Iterator[tuple[Any, ...]]:
      for row in _rows(prepared / "packaging.csv"):
        product_id = _need(product_ids, row.get("product_code"), "product packaging")
        yield (product_id, row["packaging_code"], row["display_name"], _value(row.get("package_uom_code")),
               _decimal(row.get("quantity_in_base_uom")), _boolean(row.get("is_default_sales_unit")), row["source"])

    _executemany(
        connection,
        """INSERT INTO catalog.product_packaging(
               product_id,packaging_code,display_name,package_uom_code,quantity_in_base_uom,is_default_sales_unit,source)
           VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (product_id,packaging_code) DO UPDATE SET
               display_name=excluded.display_name,package_uom_code=excluded.package_uom_code,
               quantity_in_base_uom=excluded.quantity_in_base_uom,is_default_sales_unit=excluded.is_default_sales_unit,
               source=excluded.source""",
        packaging_values(),
    )

    _executemany(
        connection,
        """INSERT INTO org.store(
                   store_code,store_name,address,city_name,region_name,country_code,latitude,longitude,timezone_name,store_status,source)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (store_code) DO UPDATE SET
                   store_name=excluded.store_name,address=excluded.address,city_name=excluded.city_name,
                   region_name=excluded.region_name,country_code=excluded.country_code,latitude=excluded.latitude,
                   longitude=excluded.longitude,timezone_name=excluded.timezone_name,store_status=excluded.store_status,
                   source=excluded.source""",
        ((row["store_code"], row["store_name"], _value(row.get("address")), _value(row.get("city_name")),
          _value(row.get("region_name")), _value(row.get("country_code")), _decimal(row.get("latitude")),
          _decimal(row.get("longitude")), row["timezone_name"], row["store_status"], row["source"])
         for row in _rows(prepared / "stores.csv")),
    )


def _load_synthetic_store_warehouses(connection: psycopg.Connection, source: str, prepared: Path) -> int:
    """Create a clearly synthetic store-level location row for stores used by prepared orders."""
    store_ids = _ids(connection, "org.store", "store_code", "store_id")
    store_names = {
        str(code): str(name)
        for code, name in connection.execute("SELECT store_code,store_name FROM org.store").fetchall()
    }
    demand_store_codes = sorted({
        (row.get("demand_store_code") or "").strip()
        for row in _rows(prepared / "orders.csv")
        if (row.get("demand_store_code") or "").strip()
    })

    def values() -> Iterator[tuple[Any, ...]]:
        for store_code in demand_store_codes:
            store_id = _need(store_ids, store_code, "synthetic store warehouse")
            yield (
                f"SIM_STORE_WH::{source.upper()}::{store_code}",
                f"{store_names[store_code]} (synthetic store warehouse)",
                store_id,
            )

    _executemany(
        connection,
        """INSERT INTO org.warehouse(
               warehouse_code,warehouse_name,warehouse_kind,store_id,is_active,data_origin)
           VALUES (%s,%s,'STORE',%s,TRUE,'SYNTHETIC')
           ON CONFLICT (warehouse_code) DO UPDATE SET
               warehouse_name=excluded.warehouse_name,warehouse_kind=excluded.warehouse_kind,
               store_id=excluded.store_id,is_active=TRUE,data_origin='SYNTHETIC'""",
        values(),
    )
    return len(demand_store_codes)


def _load_observations(connection: psycopg.Connection, prepared: Path) -> None:
    stores = _ids(connection, "org.store", "store_code", "store_id")
    products = _ids(connection, "catalog.product", "product_code", "product_id")
    categories = {
        (str(scheme), str(code)): int(identifier)
        for scheme, code, identifier in connection.execute(
            "SELECT taxonomy_scheme,category_code,category_id FROM catalog.product_category"
        ).fetchall()
    }
    def values() -> Iterator[tuple[Any, ...]]:
        for row in _rows(prepared / "observations.csv"):
            store_id = _need(stores, row.get("store_code"), "sales observation")
            product_code = _value(row.get("product_code"))
            product_id = _need(products, product_code, "sales observation product") if product_code else None
            category_id = None
            if _value(row.get("category_code")):
                key = (row["taxonomy_scheme"], row["category_code"])
                category_id = categories.get(key)
                if category_id is None:
                    raise RuntimeError(f"Sales observation category missing: {key}")
            yield (
                store_id, row["subject_kind"], product_id, category_id, date.fromisoformat(row["period_start"]),
                date.fromisoformat(row["period_end"]), _decimal(row["quantity"]), _value(row.get("quantity_uom_code")),
                _decimal(row.get("revenue_amount")), _decimal(row.get("cost_amount")), _decimal(row.get("margin_amount")),
                _value(row.get("currency_code")), row["source"],
            )

    _executemany(
        connection,
        """INSERT INTO pos.sales_observation(
               store_id,subject_kind,product_id,category_id,period_start,period_end,quantity,quantity_uom_code,
               revenue_amount,cost_amount,margin_amount,currency_code,source)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (source,store_id,product_id,category_id,period_start,period_end) DO UPDATE SET
               subject_kind=excluded.subject_kind,quantity=excluded.quantity,quantity_uom_code=excluded.quantity_uom_code,
               revenue_amount=excluded.revenue_amount,cost_amount=excluded.cost_amount,
               margin_amount=excluded.margin_amount,currency_code=excluded.currency_code""",
        values(),
    )


def _load_orders_and_lines(connection: psycopg.Connection, prepared: Path) -> None:
    stores = _ids(connection, "org.store", "store_code", "store_id")
    products = _ids(connection, "catalog.product", "product_code", "product_id")
    packages: dict[tuple[str, str], int] = {}
    for product_code, packaging_code, identifier in connection.execute(
        """SELECT p.product_code,pp.packaging_code,pp.product_packaging_id
           FROM catalog.product_packaging pp JOIN catalog.product p USING(product_id)"""
    ).fetchall():
        packages[(str(product_code), str(packaging_code))] = int(identifier)
    order_sources: set[str] = set()

    def order_values() -> Iterator[tuple[Any, ...]]:
        for row in _rows(prepared / "orders.csv"):
            order_sources.add(row["source"])
            demand_store_id = _need(stores, row.get("demand_store_code"), "sales order demand location")
            yield (row["order_number"], demand_store_id, _timestamp(row["ordered_at"]), row["order_status"],
                   _value(row.get("currency_code")), _decimal(row.get("total_amount")), row["source"])

    _executemany(
        connection,
        """INSERT INTO pos.sales_order(
                   order_number,demand_location_id,fulfillment_location_id,sales_channel_id,customer_ref,ordered_at,
                   order_status,currency_code,total_amount,source)
               VALUES (%s,%s,NULL,NULL,NULL,%s,%s,%s,%s,%s)
               ON CONFLICT (order_number) DO UPDATE SET demand_location_id=excluded.demand_location_id,
                   fulfillment_location_id=NULL,sales_channel_id=NULL,customer_ref=NULL,ordered_at=excluded.ordered_at,
                   order_status=excluded.order_status,currency_code=excluded.currency_code,
                   total_amount=excluded.total_amount,source=excluded.source""",
        order_values(),
    )
    order_ids: dict[str, int] = {}
    for source in sorted(order_sources):
        order_ids.update({str(number): int(identifier) for number, identifier in connection.execute(
            "SELECT order_number,sales_order_id FROM pos.sales_order WHERE source=%s", (source,)
        ).fetchall()})

    def line_values() -> Iterator[tuple[Any, ...]]:
        for row in _rows(prepared / "lines.csv"):
            order_id = order_ids.get(row.get("order_number", ""))
            if order_id is None:
                raise RuntimeError(f"Sales line order missing during load: {row.get('order_number')}")
            product_id = _need(products, row.get("product_code"), "sales order line")
            packaging_code = _value(row.get("packaging_code"))
            packaging_id = packages.get((row["product_code"], packaging_code)) if packaging_code else None
            if packaging_code and packaging_id is None:
                raise RuntimeError(f"Sales line packaging missing: {row['product_code']} / {packaging_code}")
            yield (
                order_id, _integer(row["line_number"]), product_id, packaging_id, _decimal(row["sold_quantity"]),
                _value(row.get("sales_uom_code")), _decimal(row.get("unit_price")), _decimal(row.get("line_amount")),
                _decimal(row.get("cost_amount")), _decimal(row.get("margin_amount")), _value(row.get("currency_code")),
                _boolean(row.get("is_promotional")), row["source"],
            )

    _executemany(
        connection,
        """INSERT INTO pos.sales_order_line(
                   sales_order_id,line_number,product_id,product_packaging_id,sold_quantity,sales_uom_code,unit_price,
                   line_amount,cost_amount,margin_amount,currency_code,is_promotional,source)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (sales_order_id,line_number) DO UPDATE SET product_id=excluded.product_id,
                   product_packaging_id=excluded.product_packaging_id,sold_quantity=excluded.sold_quantity,
                   sales_uom_code=excluded.sales_uom_code,unit_price=excluded.unit_price,line_amount=excluded.line_amount,
                   cost_amount=excluded.cost_amount,margin_amount=excluded.margin_amount,currency_code=excluded.currency_code,
                   is_promotional=excluded.is_promotional,source=excluded.source""",
        line_values(),
    )


def _load_source_data(connection: psycopg.Connection, source: str, prepared: Path) -> dict[str, int]:
    _load_dimensions(connection, prepared)
    generated = {"simulated_store_warehouses": _load_synthetic_store_warehouses(connection, source, prepared)}
    _load_observations(connection, prepared)
    _load_orders_and_lines(connection, prepared)
    return generated


def _check_predecessors(source: str, database: str, mode: str) -> None:
    source_index = SOURCE_ORDER.index(source)
    required_mode = "sample" if mode == "sample" else "full"
    for previous in SOURCE_ORDER[:source_index]:
        try:
            _require_current_marker(previous, required_mode, database)
        except RuntimeError as exc:
            raise RuntimeError(f"Source order gate: {exc}") from None


def load_source(source: str, mode: str, database: str = TARGET_DATABASE) -> dict[str, Any]:
    if mode not in {"sample", "full"}:
        raise ValueError("mode must be sample or full")
    if database not in WRITABLE_DATABASES:
        raise RuntimeError(f"Source loading is not allowed on database: {database}")
    if database == TARGET_DATABASE and mode == "sample":
        raise RuntimeError("Sample loads are disabled in the single-environment configuration; the active database accepts full sources only.")
    _check_predecessors(source, database, mode)
    source_root = RUN_ROOT / source_folder_name(source)
    evidence_root = _source_artifact_root(source, database)
    manifest_path = source_root / f"manifest.{mode}.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Prepare {source} {mode} before loading it.")
    if mode == "full":
        try:
            _require_current_marker(source, "sample", TEST_DATABASE)
        except RuntimeError as exc:
            raise RuntimeError(f"Historical bounded-sample acceptance gate: {exc}") from None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("validation", {}).get("valid"):
        raise RuntimeError(f"Prepared {source} {mode} manifest is not marked valid.")
    if mode == "full" and manifest.get("source_name") != source:
        raise RuntimeError("Prepared manifest source mismatch.")
    prepared = source_root / "prepared" / mode
    with connect(database) as connection:
        with connection.transaction():
            generated_records = _load_source_data(connection, source, prepared)
    result = {
        "run_id": RUN_ID,
        "source_name": source,
        "mode": mode,
        "database": database,
        "loaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest_sha256": sha256_file(manifest_path),
        "prepared_directory": str(prepared.relative_to(PACKAGE_ROOT)).replace("\\", "/"),
        "loaded_counts": manifest["prepared_row_counts"],
        "generated_records": generated_records,
    }
    _write_run_json(evidence_root / f"loaded.{mode}.json", result)
    return result


def _source_counts(connection: psycopg.Connection, sources_by_table: dict[str, set[str]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for name, source_values in sources_by_table.items():
        if not source_values:
            result[name] = {}
            continue
        table, _ = TABLE_CONFIG[name]
        counts = connection.execute(
            f"SELECT source,count(*) FROM {table} WHERE source = ANY(%s) GROUP BY source ORDER BY source",
            (sorted(source_values),),
        ).fetchall()
        result[name] = {str(source): int(count) for source, count in counts}
    return result


def _expected_sources(prepared: Path) -> tuple[dict[str, set[str]], dict[str, dict[str, int]]]:
    sources_by_table: dict[str, set[str]] = {}
    expected: dict[str, dict[str, int]] = {}
    for name, (table, _) in TABLE_CONFIG.items():
        path = prepared / f"{name}.csv"
        counter: Counter[str] = Counter()
        if path.exists():
            for row in _rows(path):
                source = _value(row.get("source"))
                if source:
                    counter[source] += 1
        sources_by_table[name] = set(counter)
        expected[name] = dict(counter)
    return sources_by_table, expected


def verify_source(source: str, mode: str, database: str = TARGET_DATABASE) -> dict[str, Any]:
    if mode not in {"sample", "full"}:
        raise ValueError("mode must be sample or full")
    if database not in WRITABLE_DATABASES:
        raise RuntimeError(f"Source verification is not allowed on database: {database}")
    if database == TARGET_DATABASE and mode == "sample":
        raise RuntimeError("Sample reconciliation is disabled in the single-environment configuration; only full-source reconciliation runs on the active database.")
    _check_predecessors(source, database, mode)
    source_root = RUN_ROOT / source_folder_name(source)
    evidence_root = _source_artifact_root(source, database)
    prepared = source_root / "prepared" / mode
    if not (evidence_root / f"loaded.{mode}.json").exists():
        raise RuntimeError(f"Load {source} {mode} before verifying it.")
    source_sets, expected = _expected_sources(prepared)
    with connect(database) as connection:
        actual = _source_counts(connection, source_sets)
    mismatches = []
    for table in TABLE_CONFIG:
        if expected[table] != actual[table]:
            mismatches.append({"table": table, "expected": expected[table], "actual": actual[table]})
    if mismatches:
        raise RuntimeError(f"Neon reconciliation failed for {source} {mode}: {json.dumps(mismatches, ensure_ascii=False)}")
    result = {
        "run_id": RUN_ID,
        "source_name": source,
        "mode": mode,
        "database": database,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest_sha256": sha256_file(source_root / f"manifest.{mode}.json"),
        "source_counts": expected,
        "reconciliation": "PASS",
        "mismatches": [],
    }
    _write_run_json(evidence_root / f"verified-{mode}.json", result)
    return result


def verify_all(database: str = TARGET_DATABASE) -> dict[str, Any]:
    if database not in WRITABLE_DATABASES:
        raise RuntimeError(f"All-source verification is not allowed on database: {database}")
    missing = [source for source in SOURCE_ORDER if not (_source_artifact_root(source, database) / "verified-full.json").exists()]
    if missing:
        raise RuntimeError(f"All-source verification requires verified full loads: {', '.join(missing)}")
    with connect(database) as connection:
        tables = connection.execute(
            """SELECT table_schema,table_name FROM information_schema.tables
               WHERE table_type='BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema')
               ORDER BY table_schema,table_name"""
        ).fetchall()
        row_counts = {}
        for schema, table in tables:
            safe_schema = str(schema).replace('"', '""')
            safe_table = str(table).replace('"', '""')
            row_counts[f"{schema}.{table}"] = int(connection.execute(f'SELECT count(*) FROM "{safe_schema}"."{safe_table}"').fetchone()[0])
        current_database, server_version = connection.execute("SELECT current_database(),current_setting('server_version')").fetchone()
    result = {
        "run_id": RUN_ID,
        "database": current_database,
        "server_version": server_version,
        "table_count": len(tables),
        "row_counts": row_counts,
        "sources_verified_full": list(SOURCE_ORDER),
        "verified_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _write_run_json(_artifact_root(database) / "database" / "final-verification.json", result)
    return result


def database_report(database: str = TARGET_DATABASE) -> dict[str, Any]:
    if database not in WRITABLE_DATABASES:
        raise RuntimeError(f"Database reporting is not allowed on database: {database}")
    with connect(database) as connection:
        tables = connection.execute(
            """SELECT table_schema,table_name FROM information_schema.tables
               WHERE table_type='BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema')
               ORDER BY table_schema,table_name"""
        ).fetchall()
        current_database = connection.execute("SELECT current_database()").fetchone()[0]
        counts = {}
        for schema, table in tables:
            counts[f"{schema}.{table}"] = int(connection.execute(f'SELECT count(*) FROM "{schema}"."{table}"').fetchone()[0])
    result = {
        "database": current_database,
        "table_count": len(tables),
        "row_counts": counts,
        "reported_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _write_run_json(_artifact_root(database) / "database" / "report.json", result)
    return result


def backup_previous_database() -> dict[str, Any]:
    """Refuse to reconnect to the deleted legacy database; its verified archive is retained."""
    if PREVIOUS_DATABASE_STATUS != "ACTIVE":
        archive = PACKAGE_ROOT / str(PREVIOUS_DATABASE_BACKUP.get("path", ""))
        expected_sha = str(PREVIOUS_DATABASE_BACKUP.get("sha256", ""))
        if archive.is_file() and expected_sha and sha256_file(archive) == expected_sha:
            raise RuntimeError(
                f"Cannot create a new backup: {PREVIOUS_DATABASE!r} is marked {PREVIOUS_DATABASE_STATUS}. "
                f"Its verified archive is already retained at {PREVIOUS_DATABASE_BACKUP['path']} (SHA-256 {expected_sha})."
            )
        raise RuntimeError(
            f"Cannot back up {PREVIOUS_DATABASE!r}: it is marked {PREVIOUS_DATABASE_STATUS}; "
            "no Neon connection was attempted. The configured local archive is missing or its checksum differs."
        )
    verify_snapshot_record()
    dump_exe = PACKAGE_ROOT / "tools" / "postgresql-client" / "runtime" / "pgsql" / "bin" / "pg_dump.exe"
    restore_exe = PACKAGE_ROOT / "tools" / "postgresql-client" / "runtime" / "pgsql" / "bin" / "pg_restore.exe"
    if not dump_exe.is_file() or not restore_exe.is_file():
        raise RuntimeError("The package-local PostgreSQL client is incomplete; run scripts/prepare_postgres_client.ps1 first.")

    _read_env_file()
    dsn = os.environ.get("DATABASE_URL_UNPOOLED")
    if not dsn:
        raise RuntimeError("DATABASE_URL_UNPOOLED is not set and was not found in the repository .env file.")
    fields = conninfo_to_dict(dsn)
    host = str(fields.get("host", ""))
    if not host or "pooler" in host.casefold():
        raise RuntimeError("The source backup requires the configured direct, unpooled Neon endpoint.")
    password = fields.get("password")
    if not password:
        raise RuntimeError("The direct Neon connection string has no password; no backup was attempted.")

    with connect(PREVIOUS_DATABASE) as connection:
        current_database, server_version, server_version_num = connection.execute(
            "SELECT current_database(), current_setting('server_version'), current_setting('server_version_num')"
        ).fetchone()
        tables = connection.execute(
            """SELECT table_schema,table_name FROM information_schema.tables
               WHERE table_type='BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema')
               ORDER BY table_schema,table_name"""
        ).fetchall()
        row_counts: dict[str, int] = {}
        for schema_name, table_name in tables:
            schema_ident = str(schema_name).replace('"', '""')
            table_ident = str(table_name).replace('"', '""')
            row_counts[f"{schema_name}.{table_name}"] = int(
                connection.execute(f'SELECT count(*) FROM "{schema_ident}"."{table_ident}"').fetchone()[0]
            )
    if current_database != PREVIOUS_DATABASE:
        raise RuntimeError(f"Refusing backup: connected to {current_database!r}, expected {PREVIOUS_DATABASE!r}.")

    client_version = subprocess.run([str(dump_exe), "--version"], capture_output=True, text=True, check=True).stdout.strip()
    client_match = re.search(r"PostgreSQL\) (\d+)", client_version)
    server_match = re.match(r"(\d+)", str(server_version))
    if not client_match or not server_match or client_match.group(1) != server_match.group(1):
        raise RuntimeError(f"pg_dump major version does not match the source server: {client_version!r} vs {server_version!r}.")

    backup_root = RUN_ROOT / "backup"
    backup_root.mkdir(parents=True, exist_ok=True)
    dump_path = backup_root / "pharmaflow_source_postgre-pre-v2.dump"
    env = os.environ.copy()
    for key in ("DATABASE_URL_UNPOOLED", "DATABASE_URL", "DATABASE_URL_POOLED"):
        env.pop(key, None)
    env["PGPASSWORD"] = str(password)
    env["PGSSLMODE"] = str(fields.get("sslmode") or "require")
    env["PGCONNECT_TIMEOUT"] = str(fields.get("connect_timeout") or "30")
    if fields.get("channel_binding"):
        env["PGCHANNELBINDING"] = str(fields["channel_binding"])

    command = [
        str(dump_exe), "--format=custom", "--compress=9", "--no-owner", "--no-acl", "--no-password",
        "--host", host,
        "--port", str(fields.get("port") or "5432"),
        "--username", str(fields.get("user") or "neondb_owner"),
        "--dbname", PREVIOUS_DATABASE,
        "--file", str(dump_path),
    ]
    process = subprocess.run(command, cwd=str(dump_exe.parent), env=env, capture_output=True, text=True, timeout=900)
    if process.returncode != 0:
        _write_run_json(backup_root / "pg-dump-failure.json", {
            "database": PREVIOUS_DATABASE,
            "failed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pg_dump_exit_code": process.returncode,
            "stderr_tail": process.stderr[-2000:],
            "secret_redaction": "connection credentials are passed only by process environment and are not saved",
        })
        raise RuntimeError(f"pg_dump failed with exit code {process.returncode}; see backup/pg-dump-failure.json.")

    listing = subprocess.run([str(restore_exe), "--list", str(dump_path)], cwd=str(restore_exe.parent), env=env,
                             capture_output=True, text=True, timeout=120)
    if listing.returncode != 0:
        raise RuntimeError(f"pg_restore could not read the generated archive (exit {listing.returncode}).")
    archive_table_count = sum(
        1 for line in listing.stdout.splitlines()
        if re.match(r"^\s*\d+;\s+\d+\s+\d+\s+TABLE\s+\S+\s+\S+\s+\S+\s*$", line)
    )
    if archive_table_count != len(tables):
        raise RuntimeError(f"Backup archive lists {archive_table_count} tables, but the source has {len(tables)}.")

    result = {
        "database": current_database,
        "branch_id": PROJECT_CONFIG["production_branch_id"],
        "format": "pg_dump custom archive",
        "pg_dump_version": client_version,
        "server_version": str(server_version),
        "server_version_num": int(server_version_num),
        "table_count": len(tables),
        "row_counts": row_counts,
        "archive_table_count": archive_table_count,
        "archive_file": str(dump_path.relative_to(PACKAGE_ROOT)).replace("\\", "/"),
        "archive_bytes": dump_path.stat().st_size,
        "archive_sha256": sha256_file(dump_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "snapshot_id": json.loads((RUN_ROOT / "backup" / "neon-snapshot.json").read_text(encoding="utf-8-sig"))["snapshot_id"],
        "credentials_saved": False,
    }
    _write_run_json(backup_root / "logical-backup.json", result)
    return result


def verify_snapshot_record() -> dict[str, Any]:
    path = RUN_ROOT / "backup" / "neon-snapshot.json"
    if not path.exists():
        raise RuntimeError("No recorded Neon branch snapshot found; create a branch snapshot before changing the database.")
    record = json.loads(path.read_text(encoding="utf-8-sig"))
    project = load_yaml(PACKAGE_ROOT / "config" / "project.yaml")
    if record.get("project_id") != project["project_id"] or record.get("branch_id") != project["production_branch_id"]:
        raise RuntimeError("Recorded Neon snapshot project or branch does not match this package.")
    if not record.get("snapshot_id"):
        raise RuntimeError("Recorded Neon snapshot is missing its Neon snapshot ID.")
    try:
        datetime.fromisoformat(str(record["created_at_utc"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("Recorded Neon snapshot is missing a valid creation timestamp.") from None
    return record

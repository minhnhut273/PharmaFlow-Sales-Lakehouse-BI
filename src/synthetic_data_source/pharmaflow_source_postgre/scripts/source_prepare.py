from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import re
import sqlite3
import tempfile
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Iterator
from zoneinfo import ZoneInfo

import yaml
from openpyxl import load_workbook


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[2]
RUN_ID = "20261104-forecast-schema-v2"
RUN_ROOT = PACKAGE_ROOT / "runs" / RUN_ID
SOURCE_ORDER = ("longchau", "irpd", "onyx", "pharma_sales")

CSV_FIELDS: dict[str, tuple[str, ...]] = {
    "uoms": ("uom_code", "uom_name", "uom_kind", "source"),
    "manufacturers": ("manufacturer_code", "manufacturer_name", "country_code", "source"),
    "categories": ("taxonomy_scheme", "category_code", "category_name", "parent_category_code", "source_category_path", "source"),
    "products": ("product_code", "product_name", "brand_name", "manufacturer_code", "base_uom_code", "is_active", "source"),
    "assignments": ("product_code", "taxonomy_scheme", "category_code", "assignment_status", "assignment_basis", "source"),
    "references": ("product_code", "source", "external_product_key", "match_status", "match_basis", "observed_at"),
    "packaging": ("product_code", "packaging_code", "display_name", "package_uom_code", "quantity_in_base_uom", "is_default_sales_unit", "source"),
    "stores": ("store_code", "store_name", "address", "city_name", "region_name", "country_code", "latitude", "longitude", "timezone_name", "store_status", "source"),
    "observations": ("store_code", "subject_kind", "product_code", "taxonomy_scheme", "category_code", "period_start", "period_end", "quantity", "quantity_uom_code", "revenue_amount", "cost_amount", "margin_amount", "currency_code", "source"),
    "orders": ("order_number", "demand_store_code", "ordered_at", "order_status", "currency_code", "total_amount", "source"),
    "lines": ("order_number", "line_number", "product_code", "packaging_code", "sold_quantity", "sales_uom_code", "unit_price", "line_amount", "cost_amount", "margin_amount", "currency_code", "is_promotional", "source"),
    "rejects": ("source_path", "record_key", "reason", "details"),
}


def read_text(path: Path) -> str:
    with _open_path(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _open_path(path: Path, mode: str, **kwargs: Any):
    raw = str(path.resolve())
    if os.name == "nt" and not raw.startswith("\\\\?\\"):
        raw = "\\\\?\\" + raw
    return open(raw, mode, **kwargs)


def json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _open_path(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def csv_writer(path: Path, fields: Iterable[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = _open_path(path, "w", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    return handle, writer


def write_csv(path: Path, fields: Iterable[str], rows: Iterable[dict[str, Any]]) -> int:
    handle, writer = csv_writer(path, fields)
    count = 0
    try:
        for row in rows:
            writer.writerow(row)
            count += 1
    finally:
        handle.close()
    return count


def read_csv(path: Path) -> Iterator[dict[str, str]]:
    with _open_path(path, "r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with _open_path(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_path(relative: str) -> Path:
    return PROJECT_ROOT / Path(relative)


def load_yaml(path: Path) -> dict[str, Any]:
    with _open_path(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value or value.casefold() in {"-", "--", "n/a", "na", "none", "null", "unknown"}:
        return None
    return value


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").casefold()
    ascii_value = re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")
    return ascii_value or "value"


def stable_code(prefix: str, value: str, length: int = 12) -> str:
    return f"{prefix}_{slug(value)[:48]}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:length]}"


def as_decimal(value: Any) -> Decimal:
    text = str(value).strip().replace(",", "")
    if text == "":
        raise ValueError("empty numeric value")
    return Decimal(text)


def number_text(value: Decimal | int | float | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def parse_date(value: Any) -> date:
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    raise ValueError(f"unsupported date format: {text!r}")


def parse_datetime_local(day: Any, clock: Any, tz_name: str) -> datetime:
    parsed_day = parse_date(day)
    parsed_time = datetime.strptime(str(clock).strip(), "%H:%M:%S").time()
    return datetime.combine(parsed_day, parsed_time, tzinfo=ZoneInfo(tz_name))


def iso_timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def capture_time(meta: dict[str, Any]) -> str:
    candidates = [
        (meta.get("crawl") or {}).get("crawled_at"),
        ((meta.get("product") or {}).get("other_public_attributes") or {}).get("observed_at"),
        (meta.get("price_observation") or {}).get("observed_at"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = datetime.fromisoformat(str(candidate).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
        except ValueError:
            continue
    return "2026-10-06T00:00:00+00:00"


def placeholder_reason(code: str, record: str, details: Any) -> dict[str, str]:
    return {
        "source_path": code,
        "record_key": record,
        "reason": "source_record_rejected",
        "details": str(details),
    }


def package_uom(label: str | None) -> tuple[str | None, str | None, str | None]:
    if not label:
        return None, None, None
    folded = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode("ascii").casefold()
    candidates = (
        (("hop", "box", "carton"), "LC_BOX", "Hộp", "PACKAGE"),
        (("vi", "blister"), "LC_BLISTER", "Vỉ", "PACKAGE"),
        (("chai", "bottle"), "LC_BOTTLE", "Chai", "PACKAGE"),
        (("tuyp", "tube"), "LC_TUBE", "Tuýp", "PACKAGE"),
        (("goi", "sachet"), "LC_SACHET", "Gói", "PACKAGE"),
        (("vien", "tablet"), "LC_TABLET", "Viên", "COUNT"),
        (("ong", "ampoule"), "LC_AMPOULE", "Ống", "PACKAGE"),
        (("cai", "piece"), "LC_PIECE", "Cái", "COUNT"),
    )
    for words, code, name, kind in candidates:
        if any(re.search(rf"\b{re.escape(word)}\b", folded) for word in words):
            return code, name, kind
    return None, None, None


def parse_frontmatter(text: str) -> dict[str, Any] | None:
    match = re.match(r"^---\s*\n(.*?)\n---", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None


def product_categories(meta: dict[str, Any]) -> list[dict[str, Any]]:
    taxonomy = meta.get("taxonomy") or {}
    result = taxonomy.get("page_product_categories") or []
    if result:
        return [item for item in result if isinstance(item, dict) and clean_text(item.get("slug"))]
    path = clean_text(taxonomy.get("vault_category_path"))
    if not path:
        return []
    parts = path.split("/")
    categories = []
    built: list[str] = []
    for part in parts:
        built.append(part)
        categories.append({"slug": "/".join(built), "name": part.replace("-", " "), "parent_name": None})
    return categories


def _longchau_note_records() -> tuple[dict[str, dict[str, Any]], int, list[dict[str, str]]]:
    root = source_path("dataset/longchau-knowledge")
    records_by_url: dict[str, dict[str, Any]] = {}
    captures = 0
    rejects: list[dict[str, str]] = []
    for note in root.rglob("*.md"):
        try:
            text = read_text(note)
        except OSError as exc:
            rejects.append(placeholder_reason("LONGCHAU_PUBLIC_PRODUCT_PAGE", note.name, f"note could not be read: {exc}"))
            continue
        meta = parse_frontmatter(text)
        if not meta or meta.get("page_type") != "product_detail":
            continue
        captures += 1
        product = meta.get("product") or {}
        url = clean_text(meta.get("canonical_url") or product.get("canonical_url") or meta.get("source_url"))
        if not url:
            rejects.append(placeholder_reason("LONGCHAU_PUBLIC_PRODUCT_PAGE", note.name, "missing canonical/source URL"))
            continue
        categories = product_categories(meta)
        entry = {
            "meta": meta,
            "product": product,
            "path": str(note.relative_to(root)).replace("\\", "/"),
            "categories": categories,
            "url": url,
            "observed_at": capture_time(meta),
        }
        previous = records_by_url.get(url)
        if previous:
            previous["categories"] = _merge_categories(previous["categories"], categories)
            if entry["observed_at"] >= previous["observed_at"]:
                entry["categories"] = _merge_categories(entry["categories"], previous["categories"])
                records_by_url[url] = entry
        else:
            records_by_url[url] = entry
    return records_by_url, captures, rejects


def _merge_categories(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for item in left + right:
        code = clean_text(item.get("slug"))
        if code:
            found[code] = item
    return [found[key] for key in sorted(found)]


def prepare_longchau(output: Path) -> dict[str, Any]:
    source_cfg = load_yaml(PACKAGE_ROOT / "config" / "sources" / "longchau.yaml")
    records_by_url, capture_count, rejects = _longchau_note_records()
    supplement_path = PACKAGE_ROOT / source_cfg["forecast_mapping_candidate_supplement"]
    supplement_rows = list(read_csv(supplement_path))
    records_by_identity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    no_sku_count = 0
    for entry in records_by_url.values():
        product = entry["product"]
        attrs = product.get("other_public_attributes") or {}
        sku = clean_text(attrs.get("sku"))
        if sku:
            identity = "SKU:" + sku
        else:
            no_sku_count += 1
            identity = "URL:" + hashlib.sha256(entry["url"].encode("utf-8")).hexdigest()[:20]
        entry["sku"] = sku
        records_by_identity[identity].append(entry)

    products: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    packages: list[dict[str, Any]] = []
    manufacturers: dict[str, dict[str, Any]] = {}
    uoms: dict[str, dict[str, Any]] = {}
    categories: dict[str, dict[str, Any]] = {}
    mapping_rows: list[dict[str, Any]] = []
    identity_conflicts = 0

    for identity in sorted(records_by_identity):
        group = records_by_identity[identity]
        latest = max(group, key=lambda entry: entry["observed_at"])
        details = []
        for entry in group:
            product = entry["product"]
            attrs = product.get("other_public_attributes") or {}
            details.append((
                clean_text(product.get("title") or entry["meta"].get("title")),
                clean_text(product.get("brand")),
                clean_text(product.get("manufacturer")),
                clean_text(product.get("unit_or_packing")),
            ))
        if len(set(details)) > 1:
            identity_conflicts += 1
            for entry in group:
                rejects.append(placeholder_reason("LONGCHAU_PUBLIC_PRODUCT_PAGE", identity, "same source SKU/URL identity has conflicting name/brand/manufacturer/package attributes"))
            continue

        product_source = latest["product"]
        meta = latest["meta"]
        title = clean_text(product_source.get("title") or meta.get("title"))
        if not title:
            rejects.append(placeholder_reason("LONGCHAU_PUBLIC_PRODUCT_PAGE", identity, "missing product title in note and product metadata"))
            continue
        sku = latest["sku"]
        if sku:
            product_code = "LC:" + sku
            product_key_basis = "SOURCE_SKU"
        else:
            product_code = "LC:URL:" + hashlib.sha256(latest["url"].encode("utf-8")).hexdigest()[:20]
            product_key_basis = "CANONICAL_URL_NO_SOURCE_SKU"
        brand = clean_text(product_source.get("brand"))
        manufacturer_name = clean_text(product_source.get("manufacturer"))
        manufacturer_code = None
        if manufacturer_name:
            manufacturer_code = stable_code("LC_MFR", manufacturer_name)
            manufacturers[manufacturer_code] = {
                "manufacturer_code": manufacturer_code,
                "manufacturer_name": manufacturer_name,
                "country_code": None,
                "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
            }
        products.append({
            "product_code": product_code,
            "product_name": title,
            "brand_name": brand,
            "manufacturer_code": manufacturer_code,
            "base_uom_code": None,
            "is_active": True,
            "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
        })
        selected_categories: dict[str, dict[str, Any]] = {}
        for entry in group:
            for category in entry["categories"]:
                category_code = clean_text(category.get("slug"))
                if not category_code:
                    continue
                selected_categories[category_code] = category
                current = categories.setdefault(category_code, {
                    "taxonomy_scheme": "LONGCHAU_PUBLIC",
                    "category_code": category_code,
                    "category_name": clean_text(category.get("name")) or category_code.rsplit("/", 1)[-1],
                    "parent_category_code": None,
                    "source_category_path": category_code,
                    "source": "LONGCHAU_PUBLIC_TAXONOMY",
                    "_parent_names": set(),
                })
                parent_name = clean_text(category.get("parent_name"))
                if parent_name:
                    current["_parent_names"].add(parent_name)
        for category_code, category in sorted(selected_categories.items()):
            assignments.append({
                "product_code": product_code,
                "taxonomy_scheme": "LONGCHAU_PUBLIC",
                "category_code": category_code,
                "assignment_status": "VERIFIED",
                "assignment_basis": "saved public product-page taxonomy/category relationship",
                "source": "LONGCHAU_PUBLIC_TAXONOMY",
            })

        package_text = clean_text(product_source.get("unit_or_packing"))
        if package_text:
            uom_code, uom_name, uom_kind = package_uom(package_text)
            if uom_code and uom_name and uom_kind:
                uoms[uom_code] = {"uom_code": uom_code, "uom_name": uom_name, "uom_kind": uom_kind, "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE"}
            packages.append({
                "product_code": product_code,
                "packaging_code": "LC-PACK-" + hashlib.sha256(package_text.casefold().encode("utf-8")).hexdigest()[:12],
                "display_name": package_text,
                "package_uom_code": uom_code,
                "quantity_in_base_uom": None,
                "is_default_sales_unit": False,
                "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
            })

        for entry in sorted(group, key=lambda item: item["url"]):
            url_key = "URL:" + entry["url"]
            references.append({
                "product_code": product_code,
                "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
                "external_product_key": url_key,
                "match_status": "DIRECT",
                "match_basis": product_key_basis,
                "observed_at": entry["observed_at"],
            })
        if sku:
            references.append({
                "product_code": product_code,
                "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
                "external_product_key": "SKU:" + sku,
                "match_status": "DIRECT",
                "match_basis": "SOURCE_SKU",
                "observed_at": latest["observed_at"],
            })
        attrs = product_source.get("other_public_attributes") or {}
        ingredient = clean_text(product_source.get("active_ingredient")) or clean_text(attrs.get("ingredients_from_page"))
        taxonomy_path = clean_text((meta.get("taxonomy") or {}).get("vault_category_path"))
        if ingredient and taxonomy_path and taxonomy_path.startswith("thuoc/"):
            mapping_rows.append({
                "product_code": product_code,
                "source_sku": sku,
                "product_name": title,
                "active_ingredient_evidence": ingredient,
                "taxonomy_path": taxonomy_path,
                "evidence_source_url": latest["url"],
                "evidence_basis": "captured official Long Châu product page with recorded medicine taxonomy",
                "route_form_evidence": clean_text(attrs.get("route_or_dosage_form")),
                "expected_atc_group": "",
                "ingredient_atc_code": "",
            })

    existing_products = {row["product_code"]: row for row in products}
    supplemental_skus_added = 0
    for candidate in supplement_rows:
        sku = clean_text(candidate.get("source_sku"))
        product_name = clean_text(candidate.get("product_name"))
        brand_name = clean_text(candidate.get("brand_name"))
        manufacturer_name = clean_text(candidate.get("manufacturer_name"))
        ingredient = clean_text(candidate.get("active_ingredient_evidence"))
        package_text = clean_text(candidate.get("package_display_name"))
        product_url = clean_text(candidate.get("source_url"))
        observed_at = clean_text(candidate.get("observed_at_utc"))
        if not all((sku, product_name, ingredient, package_text, product_url, observed_at)):
            raise RuntimeError(f"Incomplete Long Châu forecast-candidate supplement row: {candidate}")
        if not product_url.startswith("https://nhathuoclongchau.com.vn/thuoc/"):
            raise RuntimeError(f"Supplement product is not an official Long Châu medicine detail page: {product_url}")
        product_code = "LC:" + sku
        manufacturer_code = stable_code("LC_MFR", manufacturer_name) if manufacturer_name else None
        existing = existing_products.get(product_code)
        if existing:
            if (existing["product_name"], existing["brand_name"], existing["manufacturer_code"]) != (
                product_name, brand_name, manufacturer_code
            ):
                raise RuntimeError(f"Supplement conflicts with captured Long Châu product identity: {product_code}")
            continue
        if manufacturer_code and manufacturer_name:
            manufacturers[manufacturer_code] = {
                "manufacturer_code": manufacturer_code,
                "manufacturer_name": manufacturer_name,
                "country_code": None,
                "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
            }
        products.append({
            "product_code": product_code,
            "product_name": product_name,
            "brand_name": brand_name,
            "manufacturer_code": manufacturer_code,
            "base_uom_code": None,
            "is_active": True,
            "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
        })
        existing_products[product_code] = products[-1]
        package_uom_code, package_uom_name, package_uom_kind = package_uom(package_text)
        if package_uom_code and package_uom_name and package_uom_kind:
            uoms[package_uom_code] = {
                "uom_code": package_uom_code,
                "uom_name": package_uom_name,
                "uom_kind": package_uom_kind,
                "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
            }
        packages.append({
            "product_code": product_code,
            "packaging_code": "LC-PACK-" + hashlib.sha256(package_text.casefold().encode("utf-8")).hexdigest()[:12],
            "display_name": package_text,
            "package_uom_code": package_uom_code,
            "quantity_in_base_uom": None,
            "is_default_sales_unit": False,
            "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
        })
        references.extend((
            {
                "product_code": product_code,
                "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
                "external_product_key": "URL:" + product_url,
                "match_status": "DIRECT",
                "match_basis": "OFFICIAL_LONGCHAU_PRODUCT_PAGE",
                "observed_at": observed_at,
            },
            {
                "product_code": product_code,
                "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
                "external_product_key": "SKU:" + sku,
                "match_status": "DIRECT",
                "match_basis": "SOURCE_SKU",
                "observed_at": observed_at,
            },
        ))
        mapping_rows.append({
            "product_code": product_code,
            "source_sku": sku,
            "product_name": product_name,
            "active_ingredient_evidence": ingredient,
            "taxonomy_path": "",
            "evidence_source_url": product_url,
            "evidence_basis": "curated official Long Châu medicine detail page; taxonomy not inferred",
            "route_form_evidence": clean_text(candidate.get("route_form_evidence")),
            "expected_atc_group": clean_text(candidate.get("atc_group")),
            "ingredient_atc_code": clean_text(candidate.get("ingredient_atc_code")),
        })
        supplemental_skus_added += 1

    # Parent links are resolved only when the page evidence identifies a unique
    # category with the recorded parent name.
    category_name_index: dict[str, set[str]] = defaultdict(set)
    for code, category in categories.items():
        category_name_index[str(category["category_name"]).casefold()].add(code)
    ambiguous_parents: list[str] = []
    for code, category in categories.items():
        parent_names = category.pop("_parent_names")
        if not parent_names:
            continue
        if len(parent_names) != 1:
            ambiguous_parents.append(code)
            continue
        candidates = category_name_index.get(next(iter(parent_names)).casefold(), set())
        if len(candidates) == 1:
            category["parent_category_code"] = next(iter(candidates))
        elif len(candidates) > 1:
            ambiguous_parents.append(code)

    store_path = source_path(source_cfg["store_dataset_path"]) / source_cfg["store_file"]
    stores: list[dict[str, Any]] = []
    store_codes: set[str] = set()
    for row in read_csv(store_path):
        shop_code = clean_text(row.get("shop_code"))
        shop_name = clean_text(row.get("shop_name"))
        latitude = clean_text(row.get("latitude"))
        longitude = clean_text(row.get("longitude"))
        if not shop_code or not shop_name:
            rejects.append(placeholder_reason("LONGCHAU_PUBLIC_STORE_LOCATOR", shop_code or "<missing-code>", "missing shop code or name"))
            continue
        if shop_code in store_codes:
            rejects.append(placeholder_reason("LONGCHAU_PUBLIC_STORE_LOCATOR", shop_code, "duplicate shop_code in location file"))
            continue
        store_codes.add(shop_code)
        if not latitude or not longitude:
            rejects.append(placeholder_reason("LONGCHAU_PUBLIC_STORE_LOCATOR", shop_code, "missing source coordinate"))
            continue
        stores.append({
            "store_code": "LC:" + shop_code,
            "store_name": shop_name,
            "address": clean_text(row.get("address")),
            "city_name": clean_text(row.get("ward_name")),
            "region_name": clean_text(row.get("province_name")),
            "country_code": "VN",
            "latitude": f"{Decimal(latitude):.6f}",
            "longitude": f"{Decimal(longitude):.6f}",
            "timezone_name": "Asia/Ho_Chi_Minh",
            "store_status": "ACTIVE",
            "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
        })

    # The taxonomy names and category paths come from saved page metadata. Any
    # unresolved parent is retained as a category node without a guessed edge.
    counts = {}
    for name, rows in (
        ("uoms", list(uoms.values())),
        ("manufacturers", list(manufacturers.values())),
        ("categories", list(categories.values())),
        ("products", products),
        ("assignments", assignments),
        ("references", references),
        ("packaging", packages),
        ("stores", stores),
        ("observations", []),
        ("orders", []),
        ("lines", []),
        ("rejects", rejects),
    ):
        counts[name] = write_csv(output / f"{name}.csv", CSV_FIELDS[name], rows)
    mapping_fields = ("product_code", "source_sku", "product_name", "active_ingredient_evidence", "taxonomy_path", "evidence_source_url", "evidence_basis", "route_form_evidence", "expected_atc_group", "ingredient_atc_code")
    write_csv(output / "products_for_mapping.csv", mapping_fields, mapping_rows)
    write_csv(output / "rejects.csv", CSV_FIELDS["rejects"], rejects)

    manifest_file = source_path(source_cfg["store_dataset_path"]) / "manifest.json"
    profile = {
        "source_id": source_cfg["source_id"],
        "product_note_captures": capture_count,
        "unique_product_page_urls": len(records_by_url),
        "duplicate_captures_merged": capture_count - len(records_by_url),
        "unique_product_identities": len(records_by_identity),
        "product_identity_fallback_to_url_count": no_sku_count,
        "product_identity_conflict_groups_rejected": identity_conflicts,
        "product_categories": len(categories),
        "category_parent_unresolved_count": len(ambiguous_parents),
        "product_rows": counts["products"],
        "product_mapping_candidates": len(mapping_rows),
        "forecast_candidate_supplement_sha256": sha256_file(supplement_path),
        "forecast_candidate_supplement_rows": len(supplement_rows),
        "forecast_candidate_supplement_skus_added": supplemental_skus_added,
        "store_rows": counts["stores"],
        "source_store_manifest_sha256": sha256_file(manifest_file),
        "store_csv_sha256": sha256_file(store_path),
        "reject_rows": counts["rejects"],
    }
    return {"counts": counts, "profile": profile, "rejects": rejects, "source_id": source_cfg["source_id"]}


def _category_record(scheme: str, value: str, source: str) -> dict[str, Any]:
    code = stable_code(scheme, value, 8)
    return {
        "taxonomy_scheme": scheme,
        "category_code": code,
        "category_name": value,
        "parent_category_code": None,
        "source_category_path": value,
        "source": source,
    }


def _irpd_uom(value: str) -> dict[str, str]:
    code = stable_code("IRPD_UOM", value.casefold(), 8)
    return {"uom_code": code, "uom_name": value, "uom_kind": "OTHER", "source": "IRPD_PUBLISHER_REPORTED_POS"}


def prepare_irpd(output: Path) -> dict[str, Any]:
    source_cfg = load_yaml(PACKAGE_ROOT / "config" / "sources" / "irpd.yaml")
    sales_path = source_path(source_cfg["dataset_path"])
    store_code = source_cfg["location"]["store_code"]
    source = source_cfg["source_id"]
    products: dict[str, dict[str, Any]] = {}
    product_units: dict[str, set[str]] = defaultdict(set)
    product_categories: dict[str, set[str]] = defaultdict(set)
    product_classes: dict[str, set[str]] = defaultdict(set)
    product_manufacturers: dict[str, set[str]] = defaultdict(set)
    manufacturers: dict[str, dict[str, Any]] = {}
    units: dict[str, dict[str, str]] = {}
    categories: dict[tuple[str, str], dict[str, Any]] = {}
    assignments: dict[tuple[str, str, str], dict[str, Any]] = {}
    references: dict[str, dict[str, Any]] = {}
    rejects: list[dict[str, str]] = []
    row_count = 0
    valid_line_count = 0
    invalid_timestamps = 0
    duplicate_invoice_line = 0
    nonpositive_quantities = 0
    timestamp_conflicts = 0
    total_price_subtotal_differences = 0
    missing_line_totals = 0

    temp_root = Path(tempfile.gettempdir())
    with tempfile.TemporaryDirectory(prefix="pharmaflow_irpd_", dir=temp_root) as temporary_directory:
        index_path = Path(temporary_directory) / "invoice-index.sqlite"
        index = sqlite3.connect(index_path)
        index.execute("""
            CREATE TABLE invoice_index (
                order_number TEXT PRIMARY KEY,
                ordered_at TEXT NOT NULL,
                total_amount TEXT,
                total_amount_missing INTEGER NOT NULL DEFAULT 0,
                time_inconsistent INTEGER NOT NULL DEFAULT 0,
                line_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        index.execute("CREATE TABLE line_keys (order_number TEXT NOT NULL, line_number INTEGER NOT NULL, PRIMARY KEY(order_number, line_number)) WITHOUT ROWID")
        line_path = output / "lines.csv"
        line_handle, line_writer = csv_writer(line_path, CSV_FIELDS["lines"])
        try:
            for row in read_csv(sales_path):
                row_count += 1
                record_key = clean_text(row.get("InvoiceNumber")) or f"row:{row_count}"
                drug_code = clean_text(row.get("DrugCode"))
                drug_name = clean_text(row.get("DrugName"))
                if not drug_code or not drug_name:
                    rejects.append(placeholder_reason("IRPD_PUBLISHER_REPORTED_POS", record_key, "missing DrugCode or DrugName"))
                    continue
                product_code = "IRPD:" + drug_code
                product = products.setdefault(product_code, {
                    "product_code": product_code,
                    "product_name": drug_name,
                    "brand_name": None,
                    "manufacturer_code": None,
                    "base_uom_code": None,
                    "is_active": True,
                    "source": "IRPD_PUBLISHER_REPORTED_CATALOG",
                })
                if product["product_name"] != drug_name:
                    rejects.append(placeholder_reason("IRPD_PUBLISHER_REPORTED_POS", drug_code, f"conflicting product names: {product['product_name']!r} vs {drug_name!r}"))
                    continue

                unit = clean_text(row.get("Unit"))
                if not unit:
                    rejects.append(placeholder_reason("IRPD_PUBLISHER_REPORTED_POS", record_key, "missing source sales unit"))
                    continue
                unit_row = _irpd_uom(unit)
                units[unit_row["uom_code"]] = unit_row
                product_units[product_code].add(unit)
                uom_code = unit_row["uom_code"]
                package_code = "IRPD-PACK:" + uom_code

                manufacturer_name = clean_text(row.get("Manufacturer"))
                if manufacturer_name:
                    manufacturer_code = stable_code("IRPD_MFR", manufacturer_name.casefold())
                    manufacturers[manufacturer_code] = {
                        "manufacturer_code": manufacturer_code,
                        "manufacturer_name": manufacturer_name,
                        "country_code": None,
                        "source": "IRPD_PUBLISHER_REPORTED_CATALOG",
                    }
                    product_manufacturers[product_code].add(manufacturer_code)

                for scheme, field, source_value in (
                    ("IRPD_CATEGORY", "Category", "IRPD_PUBLISHER_REPORTED_CLASSIFICATION"),
                    ("IRPD_DRUG_CLASS", "DrugClass", "IRPD_PUBLISHER_REPORTED_CLASSIFICATION"),
                ):
                    value = clean_text(row.get(field))
                    if not value:
                        continue
                    category = _category_record(scheme, value, source_value)
                    categories[(scheme, category["category_code"])] = category
                    assignment_key = (product_code, scheme, category["category_code"])
                    assignments[assignment_key] = {
                        "product_code": product_code,
                        "taxonomy_scheme": scheme,
                        "category_code": category["category_code"],
                        "assignment_status": "VERIFIED",
                        "assignment_basis": f"source field {field} on processed sales rows",
                        "source": source_value,
                    }
                    product_categories[product_code].add(category["category_code"])

                source_date = clean_text(row.get("Date"))
                source_time = clean_text(row.get("Time"))
                try:
                    ordered_at = parse_datetime_local(source_date, source_time, source_cfg["source_timezone"])
                except (ValueError, TypeError):
                    invalid_timestamps += 1
                    rejects.append(placeholder_reason("IRPD_PUBLISHER_REPORTED_POS", record_key, "invalid Date/Time"))
                    continue
                order_number = "IRPD:" + record_key
                line_number_text = clean_text(row.get("RowNumber"))
                try:
                    line_number = int(line_number_text) if line_number_text else 0
                except ValueError:
                    line_number = 0
                if line_number <= 0:
                    rejects.append(placeholder_reason("IRPD_PUBLISHER_REPORTED_POS", record_key, "invalid source RowNumber"))
                    continue
                try:
                    quantity = as_decimal(row.get("Quantity"))
                    if quantity <= 0:
                        nonpositive_quantities += 1
                        rejects.append(placeholder_reason("IRPD_PUBLISHER_REPORTED_POS", record_key, "Quantity must be positive for a sales line"))
                        continue
                    unit_price = as_decimal(row.get("UnitPrice"))
                    subtotal = as_decimal(row.get("Subtotal"))
                    promo_pct = as_decimal(row.get("PromoDiscountPct"))
                    if unit_price < 0 or subtotal < 0 or promo_pct < 0:
                        raise ValueError("unit price, subtotal, and promo discount percentage must be nonnegative")
                    raw_line_total = clean_text(row.get("TotalPrice"))
                    line_total = as_decimal(raw_line_total) if raw_line_total is not None else None
                    if line_total is not None and line_total < 0:
                        raise ValueError("TotalPrice must be nonnegative")
                    if line_total is None:
                        missing_line_totals += 1
                    elif line_total != subtotal:
                        total_price_subtotal_differences += 1
                except Exception as exc:
                    rejects.append(placeholder_reason("IRPD_PUBLISHER_REPORTED_POS", record_key, f"invalid quantity or amount: {exc}"))
                    continue
                try:
                    index.execute("INSERT INTO line_keys(order_number, line_number) VALUES (?, ?)", (order_number, line_number))
                except sqlite3.IntegrityError:
                    duplicate_invoice_line += 1
                    rejects.append(placeholder_reason("IRPD_PUBLISHER_REPORTED_POS", record_key, f"duplicate invoice/RowNumber {line_number}"))
                    continue

                existing = index.execute("SELECT ordered_at, total_amount, total_amount_missing, time_inconsistent FROM invoice_index WHERE order_number=?", (order_number,)).fetchone()
                if existing is None:
                    index.execute(
                        "INSERT INTO invoice_index(order_number, ordered_at, total_amount, total_amount_missing, line_count) VALUES (?, ?, ?, ?, 1)",
                        (order_number, iso_timestamp(ordered_at), number_text(line_total), int(line_total is None)),
                    )
                else:
                    earliest, prior_total, amount_missing, time_bad = existing
                    if earliest != iso_timestamp(ordered_at) and not time_bad:
                        timestamp_conflicts += 1
                    next_time = min(earliest, iso_timestamp(ordered_at))
                    next_amount_missing = int(bool(amount_missing) or line_total is None)
                    if amount_missing or line_total is None:
                        next_total = prior_total
                    else:
                        next_total = number_text(Decimal(prior_total) + line_total)
                    index.execute(
                        "UPDATE invoice_index SET ordered_at=?, total_amount=?, total_amount_missing=?, time_inconsistent=?, line_count=line_count+1 WHERE order_number=?",
                        (next_time, next_total, next_amount_missing, int(bool(time_bad) or earliest != iso_timestamp(ordered_at)), order_number),
                    )

                line_writer.writerow({
                    "order_number": order_number,
                    "line_number": line_number,
                    "product_code": product_code,
                    "packaging_code": package_code,
                    "sold_quantity": number_text(quantity),
                    "sales_uom_code": uom_code,
                    "unit_price": number_text(unit_price),
                    "line_amount": number_text(line_total),
                    "cost_amount": None,
                    "margin_amount": None,
                    "currency_code": "IDR",
                    "is_promotional": promo_pct > 0,
                    "source": "IRPD_PUBLISHER_REPORTED_POS",
                })
                valid_line_count += 1
                if row_count % 100000 == 0:
                    print(f"IRPD profile/prepare: {row_count:,} sales rows read", flush=True)
            index.commit()
        finally:
            line_handle.close()

        order_rows = []
        for order_number, ordered_at, total, amount_missing, _time_inconsistent, _line_count in index.execute(
            "SELECT order_number, ordered_at, total_amount, total_amount_missing, time_inconsistent, line_count FROM invoice_index ORDER BY order_number"
        ):
            order_rows.append({
                "order_number": order_number,
                "demand_store_code": store_code,
                "ordered_at": ordered_at,
                "order_status": "COMPLETED",
                "currency_code": "IDR",
                "total_amount": None if amount_missing else total,
                "source": "IRPD_DERIVED_POS_ORDER_TOTAL_FROM_TOTALPRICE_LINES",
            })
        index.close()

    # Each IRPD unit remains source-specific. It is a transaction sales unit,
    # not an inferred base-unit conversion.
    product_rows = []
    for product_code, product in sorted(products.items()):
        manufacturer_codes = product_manufacturers.get(product_code, set())
        if len(manufacturer_codes) == 1:
            product["manufacturer_code"] = next(iter(manufacturer_codes))
        elif len(manufacturer_codes) > 1:
            rejects.append(placeholder_reason("IRPD_PUBLISHER_REPORTED_CATALOG", product_code, "multiple manufacturer names reported for one DrugCode"))
        product_rows.append(product)

    package_rows = []
    for product_code, source_units in sorted(product_units.items()):
        for unit in sorted(source_units):
            uom_code = _irpd_uom(unit)["uom_code"]
            package_rows.append({
                "product_code": product_code,
                "packaging_code": "IRPD-PACK:" + uom_code,
                "display_name": unit,
                "package_uom_code": uom_code,
                "quantity_in_base_uom": None,
                "is_default_sales_unit": len(source_units) == 1,
                "source": "IRPD_PUBLISHER_REPORTED_POS",
            })
    reference_rows = [
        {
            "product_code": product_code,
            "source": "IRPD_PUBLISHER_REPORTED_CATALOG",
            "external_product_key": "DrugCode:" + product_code.split(":", 1)[1],
            "match_status": "DIRECT",
            "match_basis": "source-provided DrugCode",
            "observed_at": "2026-10-24T00:00:00+00:00",
        }
        for product_code in sorted(products)
    ]
    store = source_cfg["location"]
    location_cfg = load_yaml(PACKAGE_ROOT / "config" / "locations" / "simulated_stores.yaml")["irpd_central_java"]
    latitude, longitude = simulated_coordinates(location_cfg)
    stores = [{
        "store_code": store_code,
        "store_name": store["display_name"],
        "address": None,
        "city_name": store["city_name"],
        "region_name": store["region_name"],
        "country_code": store["country_code"],
        "latitude": latitude,
        "longitude": longitude,
        "timezone_name": store["timezone_name"],
        "store_status": "ACTIVE",
        "source": "IRPD_SIMULATED_LOCATION_CENTRAL_JAVA",
    }]

    rows_by_name = {
        "uoms": list(units.values()),
        "manufacturers": list(manufacturers.values()),
        "categories": list(categories.values()),
        "products": product_rows,
        "assignments": list(assignments.values()),
        "references": reference_rows,
        "packaging": package_rows,
        "stores": stores,
        "observations": [],
        "orders": order_rows,
        "lines": None,
        "rejects": rejects,
    }
    counts = {}
    for name, rows in rows_by_name.items():
        if name == "lines":
            counts[name] = valid_line_count
        elif rows is None:
            continue
        else:
            counts[name] = write_csv(output / f"{name}.csv", CSV_FIELDS[name], rows)
    write_csv(output / "rejects.csv", CSV_FIELDS["rejects"], rejects)
    manifest_file = source_path(source_cfg["provenance_manifest"])
    profile = {
        "source_id": source,
        "sales_processed_sha256": sha256_file(sales_path),
        "manifest_sha256": sha256_file(manifest_file),
        "source_rows": row_count,
        "product_codes": len(products),
        "invoice_numbers": len(order_rows),
        "order_total_rule": "sum valid TotalPrice line values by InvoiceNumber; set NULL if any line TotalPrice is missing",
        "total_price_subtotal_difference_rows": total_price_subtotal_differences,
        "missing_line_total_rows": missing_line_totals,
        "invoice_timestamp_conflicts": timestamp_conflicts,
        "distinct_sales_units": len(units),
        "product_codes_with_multiple_sales_units": sum(len(values) > 1 for values in product_units.values()),
        "source_category_values": sum(1 for scheme, _ in categories if scheme == "IRPD_CATEGORY"),
        "source_drug_class_values": sum(1 for scheme, _ in categories if scheme == "IRPD_DRUG_CLASS"),
        "invalid_timestamps": invalid_timestamps,
        "duplicate_invoice_line_keys": duplicate_invoice_line,
        "nonpositive_quantities": nonpositive_quantities,
        "simulated_store_code": store_code,
        "simulated_coordinates": {"latitude": latitude, "longitude": longitude},
        "stock_source_rows_loaded": 0,
        "reject_rows": len(rejects),
    }
    return {"counts": counts, "profile": profile, "rejects": rejects, "source_id": source}


def _sheet_records(workbook, sheet_name: str) -> Iterator[dict[str, Any]]:
    worksheet = workbook[sheet_name]
    iterator = worksheet.iter_rows(values_only=True)
    headers = next(iterator)
    for values in iterator:
        if values is None or not any(value is not None for value in values):
            continue
        yield {str(key): value for key, value in zip(headers, values)}


def _yes_no(value: Any) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().casefold()
    if text in {"yes", "y", "true", "1"}:
        return True
    if text in {"no", "n", "false", "0"}:
        return False
    return None


def prepare_onyx(output: Path) -> dict[str, Any]:
    source_cfg = load_yaml(PACKAGE_ROOT / "config" / "sources" / "onyx.yaml")
    workbook_path = source_path(source_cfg["dataset_path"])
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    source_id = source_cfg["source_id"]
    countries = {
        "Austria": ("AT", "Europe/Vienna"),
        "Belgium": ("BE", "Europe/Brussels"),
        "France": ("FR", "Europe/Paris"),
        "Germany": ("DE", "Europe/Berlin"),
        "Italy": ("IT", "Europe/Rome"),
        "Netherlands": ("NL", "Europe/Amsterdam"),
        "Poland": ("PL", "Europe/Warsaw"),
        "Spain": ("ES", "Europe/Madrid"),
    }
    stores_by_id: dict[str, dict[str, Any]] = {}
    products_by_id: dict[str, dict[str, Any]] = {}
    categories: dict[str, dict[str, Any]] = {}
    assignments: dict[tuple[str, str], dict[str, Any]] = {}
    references: list[dict[str, Any]] = []
    packages: list[dict[str, Any]] = []
    rejects: list[dict[str, str]] = []
    orders_by_store_date: dict[tuple[str, date], dict[str, Any]] = {}
    observations_handle = None
    observations_writer = None
    line_handle = None
    line_writer = None
    fact_count = 0
    invalid_fact_count = 0
    duplicate_fact_keys = 0
    margin_mismatches = 0
    fact_keys: set[tuple[int, str, str]] = set()
    currencies = set()
    first_date: date | None = None
    last_date: date | None = None
    line_number_by_store_date: dict[tuple[str, date], int] = defaultdict(int)

    try:
        for row in _sheet_records(workbook, source_cfg["pharmacy_sheet"]):
            pharmacy_id = clean_text(row.get("PharmacyID"))
            name = clean_text(row.get("PharmacyName"))
            country_name = clean_text(row.get("Country"))
            city = clean_text(row.get("City"))
            region = clean_text(row.get("Region"))
            if not pharmacy_id or not name or not country_name or country_name not in countries:
                rejects.append(placeholder_reason(source_id, pharmacy_id or "<missing-pharmacy>", "missing location identity or country timezone mapping"))
                continue
            country_code, timezone_name = countries[country_name]
            if country_name == "Spain" and city and city.casefold() in {"las palmas", "santa cruz de tenerife"}:
                timezone_name = "Atlantic/Canary"
            latitude = row.get("Latitude")
            longitude = row.get("Longitude")
            if latitude is None or longitude is None:
                rejects.append(placeholder_reason(source_id, pharmacy_id, "missing source coordinate"))
                continue
            store_code = "ONYX:" + pharmacy_id
            stores_by_id[pharmacy_id] = {
                "store_code": store_code,
                "store_name": name,
                "address": None,
                "city_name": city,
                "region_name": region,
                "country_code": country_code,
                "latitude": f"{Decimal(str(latitude)):.6f}",
                "longitude": f"{Decimal(str(longitude)):.6f}",
                "timezone_name": timezone_name,
                "store_status": "ACTIVE",
                "source": "ONYX_CHALLENGE_LOCATION_DIMENSION_UNVERIFIED",
            }

        for row in _sheet_records(workbook, source_cfg["product_sheet"]):
            product_id = clean_text(row.get("ProductID"))
            name = clean_text(row.get("ProductName"))
            if not product_id or not name:
                rejects.append(placeholder_reason(source_id, product_id or "<missing-product>", "missing ProductID or ProductName"))
                continue
            product_code = "ONYX:" + product_id
            category_name = clean_text(row.get("Category"))
            category_code = None
            if category_name:
                category = _category_record("ONYX_CATEGORY", category_name, "ONYX_CHALLENGE_PRODUCT_DIMENSION")
                category_code = category["category_code"]
                categories[category_code] = category
                assignments[(product_code, category_code)] = {
                    "product_code": product_code,
                    "taxonomy_scheme": "ONYX_CATEGORY",
                    "category_code": category_code,
                    "assignment_status": "VERIFIED",
                    "assignment_basis": "source DimProduct.Category field",
                    "source": "ONYX_CHALLENGE_PRODUCT_DIMENSION",
                }
            brand = clean_text(row.get("Brand"))
            active = _yes_no(row.get("IsDiscontinued")) is not True
            products_by_id[product_id] = {
                "product_code": product_code,
                "product_name": name,
                "brand_name": brand,
                "manufacturer_code": None,
                "base_uom_code": None,
                "is_active": active,
                "source": "ONYX_CHALLENGE_PRODUCT_DIMENSION",
                "category_code": category_code,
            }
            external = "ProductID:" + product_id
            references.append({
                "product_code": product_code,
                "source": "ONYX_CHALLENGE_PRODUCT_DIMENSION",
                "external_product_key": external,
                "match_status": "DIRECT",
                "match_basis": "source-provided ProductID",
                "observed_at": "2026-10-24T00:00:00+00:00",
            })
            pack_label = clean_text(row.get("PackSize"))
            if pack_label:
                packages.append({
                    "product_code": product_code,
                    "packaging_code": "ONYX-PACK-" + hashlib.sha256(pack_label.casefold().encode("utf-8")).hexdigest()[:12],
                    "display_name": pack_label,
                    "package_uom_code": None,
                    "quantity_in_base_uom": None,
                    "is_default_sales_unit": False,
                    "source": "ONYX_CHALLENGE_PRODUCT_DIMENSION",
                })

        uom = {"uom_code": "ONYX_UNIT", "uom_name": "UnitsSold source measure", "uom_kind": "COUNT", "source": "ONYX_CHALLENGE_DAILY_SALES_FACT_UNVERIFIED"}
        observations_handle, observations_writer = csv_writer(output / "observations.csv", CSV_FIELDS["observations"])
        line_handle, line_writer = csv_writer(output / "lines.csv", CSV_FIELDS["lines"])
        date_keys: set[int] = set()
        for row in _sheet_records(workbook, source_cfg["date_sheet"]):
            try:
                date_keys.add(int(row["DateKey"]))
            except (KeyError, TypeError, ValueError):
                continue

        for row in _sheet_records(workbook, source_cfg["fact_sheet"]):
            fact_count += 1
            sales_id = clean_text(row.get("SalesID")) or f"fact-row:{fact_count}"
            pharmacy_id = clean_text(row.get("PharmacyID"))
            product_id = clean_text(row.get("ProductID"))
            if pharmacy_id not in stores_by_id or product_id not in products_by_id:
                invalid_fact_count += 1
                rejects.append(placeholder_reason(source_id, sales_id, "FactSales foreign key missing from dimension"))
                continue
            date_key = row.get("DateKey")
            try:
                day = datetime.strptime(str(int(date_key)), "%Y%m%d").date()
                if int(date_key) not in date_keys:
                    raise ValueError("DateKey is missing from DimDate")
                quantity = as_decimal(row.get("UnitsSold"))
                revenue = as_decimal(row.get("RevenueEUR"))
                cost = as_decimal(row.get("CostEUR"))
                margin = as_decimal(row.get("MarginEUR"))
                if quantity < 0 or revenue < 0 or cost < 0:
                    raise ValueError("UnitsSold, RevenueEUR, and CostEUR must be nonnegative")
            except Exception as exc:
                invalid_fact_count += 1
                rejects.append(placeholder_reason(source_id, sales_id, f"invalid date or quantitative field: {exc}"))
                continue
            key = (int(date_key), pharmacy_id, product_id)
            if key in fact_keys:
                duplicate_fact_keys += 1
                rejects.append(placeholder_reason(source_id, sales_id, "duplicate date/pharmacy/product source grain"))
                continue
            fact_keys.add(key)
            if margin != revenue - cost:
                margin_mismatches += 1
            currencies.add("EUR")
            first_date = day if first_date is None else min(first_date, day)
            last_date = day if last_date is None else max(last_date, day)
            store_code = stores_by_id[pharmacy_id]["store_code"]
            product_code = products_by_id[product_id]["product_code"]
            observations_writer.writerow({
                "store_code": store_code,
                "subject_kind": "PRODUCT",
                "product_code": product_code,
                "taxonomy_scheme": None,
                "category_code": None,
                "period_start": day.isoformat(),
                "period_end": day.isoformat(),
                "quantity": number_text(quantity),
                "quantity_uom_code": "ONYX_UNIT",
                "revenue_amount": number_text(revenue),
                "cost_amount": number_text(cost),
                "margin_amount": number_text(margin),
                "currency_code": "EUR",
                "source": "ONYX_CHALLENGE_DAILY_SALES_FACT_UNVERIFIED",
            })
            order_key = (pharmacy_id, day)
            order_number = f"SIM-ONYX-{pharmacy_id}-{day.strftime('%Y%m%d')}"
            if order_key not in orders_by_store_date:
                orders_by_store_date[order_key] = {"order_number": order_number, "store_code": store_code, "amount": Decimal(0), "line_count": 0}
            order = orders_by_store_date[order_key]
            order["amount"] += revenue
            if quantity > 0:
                line_number_by_store_date[order_key] += 1
                line_number = line_number_by_store_date[order_key]
                line_writer.writerow({
                    "order_number": order_number,
                    "line_number": line_number,
                    "product_code": product_code,
                    "packaging_code": None,
                    "sold_quantity": number_text(quantity),
                    "sales_uom_code": "ONYX_UNIT",
                    "unit_price": None,
                    "line_amount": number_text(revenue),
                    "cost_amount": number_text(cost),
                    "margin_amount": number_text(margin),
                    "currency_code": "EUR",
                    "is_promotional": _yes_no(row.get("PromoFlag")),
                    "source": "SIMULATED_ONYX_DAILY_FACT_TO_POS",
                })
                order["line_count"] += 1
            if fact_count % 20000 == 0:
                print(f"Onyx profile/prepare: {fact_count:,} fact rows read", flush=True)
    finally:
        if observations_handle:
            observations_handle.close()
        if line_handle:
            line_handle.close()
        workbook.close()

    order_rows = []
    for (_pharmacy_id, day), order in sorted(orders_by_store_date.items(), key=lambda item: (item[0][1], item[0][0])):
        if order["line_count"] <= 0:
            continue
        store = stores_by_id[_pharmacy_id]
        local_timestamp = datetime.combine(day, time(12, 0), tzinfo=ZoneInfo(store["timezone_name"]))
        order_rows.append({
            "order_number": order["order_number"],
            "demand_store_code": order["store_code"],
            "ordered_at": iso_timestamp(local_timestamp),
            "order_status": "COMPLETED",
            "currency_code": "EUR",
            "total_amount": number_text(order["amount"]),
            "source": "SIMULATED_ONYX_DAILY_FACT_TO_POS",
        })

    all_uoms = [uom]
    all_categories = list(categories.values())
    all_products = [{key: value for key, value in product.items() if key != "category_code"} for product in products_by_id.values()]
    all_stores = list(stores_by_id.values())
    counts = {}
    rows_by_name: dict[str, Iterable[dict[str, Any]]] = {
        "uoms": all_uoms,
        "manufacturers": [],
        "categories": all_categories,
        "products": all_products,
        "assignments": list(assignments.values()),
        "references": references,
        "packaging": packages,
        "stores": all_stores,
        "orders": order_rows,
        "rejects": rejects,
    }
    for name, rows in rows_by_name.items():
        counts[name] = write_csv(output / f"{name}.csv", CSV_FIELDS[name], rows)
    observation_count = sum(1 for _ in read_csv(output / "observations.csv"))
    line_count = sum(1 for _ in read_csv(output / "lines.csv"))
    counts["observations"] = observation_count
    counts["lines"] = line_count
    profile = {
        "source_id": source_id,
        "workbook_sha256": sha256_file(workbook_path),
        "fact_rows": fact_count,
        "observation_rows": observation_count,
        "synthetic_order_rows": len(order_rows),
        "synthetic_order_line_rows": line_count,
        "source_pharmacies": len(stores_by_id),
        "source_products": len(products_by_id),
        "source_currency": sorted(currencies),
        "first_date": first_date.isoformat() if first_date else None,
        "last_date": last_date.isoformat() if last_date else None,
        "coordinate_provenance": "source dimension coordinates; workbook says they are perturbed; real-versus-synthetic data provenance unverified",
        "invalid_fact_rows": invalid_fact_count,
        "duplicate_fact_keys": duplicate_fact_keys,
        "margin_reconciliation_mismatches": margin_mismatches,
        "reject_rows": len(rejects),
    }
    return {"counts": counts, "profile": profile, "rejects": rejects, "source_id": source_id}


def _normalize_ingredient_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", decomposed.casefold()).strip()


def _ingredient_match(text: str, term: str) -> bool:
    normalized_text = _normalize_ingredient_text(text)
    normalized_term = _normalize_ingredient_text(term)
    return bool(normalized_term and re.search(rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])", normalized_text))


def _mapping_candidate_allowed(atc_code: str, product: dict[str, str]) -> bool:
    path = (product.get("taxonomy_path") or "").casefold()
    name = _normalize_ingredient_text(product.get("product_name") or "")
    if atc_code in {"M01AB", "M01AE"}:
        local_route = ("mieng-dan", "cao-xoa", "thuoc-xit", "gel", "kem-boi", "dung-dich-xit", "vien-ngam-tri-ho-viem-hong")
        if any(token in path for token in local_route) or any(token.replace("-", " ") in name for token in local_route):
            return False
        if re.search(r"\bxit\b", name):
            return False
    if atc_code == "N02BA":
        # The Long Chau aspirin item found by ingredient matching is categorized
        # and described as antiplatelet prevention, not analgesic use.
        if "thuoc-chong-dong-mau" in path or any(term in name for term in ("phong-ngua-dot-quy", "phong-ngua-nhoi-mau")):
            return False
    if atc_code == "R06" and any(token in path for token in ("thuoc-nho-mat", "thuoc-xit-mui")):
        return False
    if atc_code == "R03" and "thuoc-xit-mui" in path:
        return False
    return True


def _mapping_candidate_rank(product: dict[str, str]) -> tuple[int, str]:
    ingredients = [part.strip() for part in (product.get("active_ingredient_evidence") or "").split(";") if part.strip()]
    return (0 if len(ingredients) == 1 else 1, product.get("product_code", ""))


def simulated_coordinates(config: dict[str, Any]) -> tuple[str, str]:
    rng = random.Random(int(config["seed"]))
    center = config["city_center"]
    offset = Decimal(str(config["offset_degrees"]))
    lat = Decimal(str(center["latitude"])) + Decimal(str(rng.uniform(-float(offset), float(offset))))
    lon = Decimal(str(center["longitude"])) + Decimal(str(rng.uniform(-float(offset), float(offset))))
    return f"{lat:.6f}", f"{lon:.6f}"


def _pharma_mapping_candidates() -> tuple[dict[str, list[dict[str, str]]], list[dict[str, str]]]:
    source_cfg = load_yaml(PACKAGE_ROOT / "config" / "mappings" / "pharma_sales_atc_products.yaml")
    product_index = RUN_ROOT / "01-longchau" / "prepared" / "full" / "products_for_mapping.csv"
    if not product_index.exists():
        raise FileNotFoundError("Prepare and validate Long Châu first; it creates products_for_mapping.csv.")
    candidates_by_code: dict[str, list[dict[str, str]]] = {}
    mapping_rows: list[dict[str, str]] = []
    product_rows = list(read_csv(product_index))
    for atc_code, group in source_cfg["groups"].items():
        selected_by_term: dict[str, dict[str, str]] = {}
        for product in product_rows:
            evidence = product.get("active_ingredient_evidence") or ""
            matched = next((term for term in group["ingredient_terms"] if _ingredient_match(evidence, term)), None)
            expected_group = product.get("expected_atc_group") or ""
            if expected_group and expected_group != atc_code:
                continue
            if not matched or not _mapping_candidate_allowed(atc_code, product):
                continue
            prior = selected_by_term.get(matched)
            if prior is None or _mapping_candidate_rank(product) < _mapping_candidate_rank(prior):
                selected_by_term[matched] = product
        selected = [selected_by_term[term] for term in group["ingredient_terms"] if term in selected_by_term]
        selected = list({product["product_code"]: product for product in selected}.values())
        selected = selected[: int(source_cfg["matching"]["maximum_products_per_group"])]
        mapped: list[dict[str, str]] = []
        for product in selected:
            entry = {
                "atc_code": atc_code,
                "atc_name": group["name"],
                "product_code": product["product_code"],
                "source_sku": product.get("source_sku") or "",
                "product_name": product["product_name"],
                "matched_ingredient_term": next(term for term in group["ingredient_terms"] if _ingredient_match(product.get("active_ingredient_evidence", ""), term)),
                "ingredient_evidence": product.get("active_ingredient_evidence", ""),
                "taxonomy_path": product.get("taxonomy_path", ""),
                "evidence_source_url": product.get("evidence_source_url", ""),
                "evidence_basis": product.get("evidence_basis", ""),
                "route_form_evidence": product.get("route_form_evidence", ""),
                "ingredient_atc_code": product.get("ingredient_atc_code", ""),
                "assignment_status": "CANDIDATE",
                "mapping_id": source_cfg["mapping_id"],
            }
            mapped.append(entry)
            mapping_rows.append(entry)
        candidates_by_code[atc_code] = mapped
    return candidates_by_code, mapping_rows


def prepare_pharma_sales(output: Path) -> dict[str, Any]:
    source_cfg = load_yaml(PACKAGE_ROOT / "config" / "sources" / "pharma_sales.yaml")
    location_cfg = load_yaml(PACKAGE_ROOT / "config" / "locations" / "simulated_stores.yaml")["pharma_sales_nis"]
    mapping_cfg = load_yaml(PACKAGE_ROOT / "config" / "mappings" / "pharma_sales_atc_products.yaml")
    source_path_csv = source_path(source_cfg["dataset_path"])
    store_cfg = source_cfg["location"]
    store_code = store_cfg["store_code"]
    latitude, longitude = simulated_coordinates(location_cfg)
    store_rows = [{
        "store_code": store_code,
        "store_name": store_cfg["display_name"],
        "address": None,
        "city_name": store_cfg["city_name"],
        "region_name": store_cfg["region_name"],
        "country_code": store_cfg["country_code"],
        "latitude": latitude,
        "longitude": longitude,
        "timezone_name": store_cfg["timezone_name"],
        "store_status": "ACTIVE",
        "source": "PHARMA_SALES_SIMULATED_LOCATION_NIS",
    }]
    uom_rows = [{
        "uom_code": "SIM_PHARMA_SALES_UNIT",
        "uom_name": "Scaled simulated sales unit from ATC-group source values",
        "uom_kind": "OTHER",
        "source": "SIMULATED_PHARMA_SALES_ATC_SCALE10",
    }]
    category_rows = []
    category_code_by_atc: dict[str, str] = {}
    for atc_code, group in mapping_cfg["groups"].items():
        category_code = atc_code
        category_code_by_atc[atc_code] = category_code
        category_rows.append({
            "taxonomy_scheme": "ATC",
            "category_code": category_code,
            "category_name": group["name"],
            "parent_category_code": None,
            "source_category_path": "ATC/" + atc_code,
            "source": "WHO_ATC_CLASSIFICATION",
        })

    candidates_by_code, mapping_rows = _pharma_mapping_candidates()
    assignment_rows = []
    for atc_code, candidates in candidates_by_code.items():
        for candidate in candidates:
            assignment_rows.append({
                "product_code": candidate["product_code"],
                "taxonomy_scheme": "ATC",
                "category_code": category_code_by_atc[atc_code],
                "assignment_status": "CANDIDATE",
                "assignment_basis": f"explicit active ingredient from referenced Long Châu product page matched ATC group {atc_code}; synthetic SKU allocation; pharmacist review not recorded",
                "source": "PHARMA_SALES_ATC_MAPPING_CANDIDATE",
            })

    observation_handle, observation_writer = csv_writer(output / "observations.csv", CSV_FIELDS["observations"])
    line_handle, line_writer = csv_writer(output / "lines.csv", CSV_FIELDS["lines"])
    order_rows_by_date: dict[date, dict[str, Any]] = {}
    rejects: list[dict[str, str]] = []
    row_count = 0
    observation_count = 0
    simulated_line_count = 0
    zero_group_values = 0
    scaled_group_totals: dict[str, int] = Counter()
    first_day: date | None = None
    last_day: date | None = None
    configured_groups = set(mapping_cfg["groups"])
    try:
        with _open_path(source_path_csv, "r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                row_count += 1
                raw_day = clean_text(row.get("datum"))
                try:
                    day = parse_date(raw_day)
                except (ValueError, TypeError):
                    rejects.append(placeholder_reason("PHARMA_SALES_DAILY_ATC", f"row:{row_count}", "invalid datum"))
                    continue
                first_day = day if first_day is None else min(first_day, day)
                last_day = day if last_day is None else max(last_day, day)
                for atc_code in sorted(configured_groups):
                    try:
                        quantity = as_decimal(row[atc_code])
                    except Exception as exc:
                        rejects.append(placeholder_reason("PHARMA_SALES_DAILY_ATC", f"{day}:{atc_code}", f"invalid source measure: {exc}"))
                        continue
                    if quantity < 0:
                        rejects.append(placeholder_reason("PHARMA_SALES_DAILY_ATC", f"{day}:{atc_code}", "negative source measure"))
                        continue
                    observation_writer.writerow({
                        "store_code": store_code,
                        "subject_kind": "CATEGORY",
                        "product_code": None,
                        "taxonomy_scheme": "ATC",
                        "category_code": category_code_by_atc[atc_code],
                        "period_start": day.isoformat(),
                        "period_end": day.isoformat(),
                        "quantity": number_text(quantity),
                        "quantity_uom_code": None,
                        "revenue_amount": None,
                        "cost_amount": None,
                        "margin_amount": None,
                        "currency_code": None,
                        "source": "PHARMA_SALES_DAILY_ATC",
                    })
                    observation_count += 1
                    if quantity == 0:
                        zero_group_values += 1
                    scaled = int((quantity * Decimal(str(source_cfg["simulation"]["scale"]))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                    scaled_group_totals[atc_code] += scaled
                    mapped = candidates_by_code.get(atc_code, [])
                    if scaled <= 0 or not mapped:
                        continue
                    base, remainder = divmod(scaled, len(mapped))
                    for index, candidate in enumerate(sorted(mapped, key=lambda item: item["product_code"])):
                        split_quantity = base + (1 if index < remainder else 0)
                        if split_quantity <= 0:
                            continue
                        order_number = "SIM-PHARMA-SALES-" + day.strftime("%Y%m%d")
                        if day not in order_rows_by_date:
                            local_timestamp = datetime.combine(day, time(12, 0), tzinfo=ZoneInfo(store_cfg["timezone_name"]))
                            order_rows_by_date[day] = {
                                "order_number": order_number,
                                "demand_store_code": store_code,
                                "ordered_at": iso_timestamp(local_timestamp),
                                "order_status": "COMPLETED",
                                "currency_code": None,
                                "total_amount": None,
                                "source": "SIMULATED_PHARMA_SALES_ATC_SCALE10",
                                "line_number": 0,
                            }
                        order = order_rows_by_date[day]
                        order["line_number"] += 1
                        line_writer.writerow({
                            "order_number": order_number,
                            "line_number": order["line_number"],
                            "product_code": candidate["product_code"],
                            "packaging_code": None,
                            "sold_quantity": split_quantity,
                            "sales_uom_code": "SIM_PHARMA_SALES_UNIT",
                            "unit_price": None,
                            "line_amount": None,
                            "cost_amount": None,
                            "margin_amount": None,
                            "currency_code": None,
                            "is_promotional": None,
                            "source": "SIMULATED_PHARMA_SALES_ATC_SCALE10",
                        })
                        simulated_line_count += 1
    finally:
        observation_handle.close()
        line_handle.close()

    order_rows = []
    for day, order in sorted(order_rows_by_date.items()):
        order_rows.append({key: value for key, value in order.items() if key != "line_number"})
    write_csv(output / "uoms.csv", CSV_FIELDS["uoms"], uom_rows)
    write_csv(output / "manufacturers.csv", CSV_FIELDS["manufacturers"], [])
    write_csv(output / "categories.csv", CSV_FIELDS["categories"], category_rows)
    write_csv(output / "products.csv", CSV_FIELDS["products"], [])
    write_csv(output / "assignments.csv", CSV_FIELDS["assignments"], assignment_rows)
    write_csv(output / "references.csv", CSV_FIELDS["references"], [])
    write_csv(output / "packaging.csv", CSV_FIELDS["packaging"], [])
    write_csv(output / "stores.csv", CSV_FIELDS["stores"], store_rows)
    write_csv(output / "orders.csv", CSV_FIELDS["orders"], order_rows)
    write_csv(output / "rejects.csv", CSV_FIELDS["rejects"], rejects)
    write_csv(output / "atc_candidate_mapping.csv", tuple(mapping_rows[0].keys()) if mapping_rows else ("atc_code", "atc_name", "product_code", "source_sku", "product_name", "matched_ingredient_term", "ingredient_evidence", "taxonomy_path", "evidence_source_url", "evidence_basis", "route_form_evidence", "ingredient_atc_code", "assignment_status", "mapping_id"), mapping_rows)

    per_group_mapping = {code: len(products) for code, products in candidates_by_code.items()}
    profile = {
        "source_id": "PHARMA_SALES_DAILY_ATC",
        "daily_csv_sha256": sha256_file(source_path_csv),
        "source_rows": row_count,
        "observation_rows": observation_count,
        "source_groups": sorted(configured_groups),
        "first_date": first_day.isoformat() if first_day else None,
        "last_date": last_day.isoformat() if last_day else None,
        "zero_group_values_retained": zero_group_values,
        "quantity_unit": None,
        "simulated_atc_mapping_count_by_group": per_group_mapping,
        "unmapped_atc_groups": [code for code, count in per_group_mapping.items() if count == 0],
        "simulated_orders": len(order_rows),
        "simulated_order_lines": simulated_line_count,
        "scale": source_cfg["simulation"]["scale"],
        "scaled_group_totals": dict(scaled_group_totals),
        "simulated_store_code": store_code,
        "simulated_coordinates": {"latitude": latitude, "longitude": longitude},
        "ignored_daily_hour_values": True,
        "reject_rows": len(rejects),
    }
    counts = {
        "uoms": 1,
        "manufacturers": 0,
        "categories": len(category_rows),
        "products": 0,
        "assignments": len(assignment_rows),
        "references": 0,
        "packaging": 0,
        "stores": 1,
        "observations": observation_count,
        "orders": len(order_rows),
        "lines": simulated_line_count,
        "rejects": len(rejects),
    }
    return {"counts": counts, "profile": profile, "rejects": rejects, "source_id": source_cfg["source_id"]}


def source_folder_name(source: str) -> str:
    return {
        "longchau": "01-longchau",
        "irpd": "02-irpd",
        "onyx": "03-onyx",
        "pharma_sales": "04-pharma-sales",
    }[source]


def count_csv_rows(path: Path) -> int:
    with _open_path(path, "r", encoding="utf-8-sig", newline="") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


def validate_prepared(output: Path) -> dict[str, Any]:
    issues: list[str] = []
    products = {row["product_code"] for row in read_csv(output / "products.csv") if row.get("product_code")}
    if output.parent.parent.name == "04-pharma-sales":
        longchau_products = RUN_ROOT / "01-longchau" / "prepared" / "full" / "products.csv"
        if longchau_products.exists():
            products.update(row["product_code"] for row in read_csv(longchau_products) if row.get("product_code"))
    stores = {row["store_code"] for row in read_csv(output / "stores.csv") if row.get("store_code")}
    categories = {(row["taxonomy_scheme"], row["category_code"]) for row in read_csv(output / "categories.csv") if row.get("taxonomy_scheme") and row.get("category_code")}
    uoms = {row["uom_code"] for row in read_csv(output / "uoms.csv") if row.get("uom_code")}
    product_uoms = set()
    category_assignments = set()
    package_keys = set()
    order_keys = set()
    line_keys = set()
    observation_keys = set()
    counts = {name: count_csv_rows(output / f"{name}.csv") for name in CSV_FIELDS if (output / f"{name}.csv").exists()}

    for row in read_csv(output / "categories.csv"):
        parent_code = row.get("parent_category_code")
        if parent_code and (row["taxonomy_scheme"], parent_code) not in categories:
            issues.append(f"category parent missing: {row['taxonomy_scheme']}:{row['category_code']} -> {parent_code}")
    for row in read_csv(output / "products.csv"):
        if row.get("manufacturer_code") and not (output / "manufacturers.csv").exists():
            issues.append(f"manufacturer file missing for {row['product_code']}")
        if row.get("base_uom_code") and row["base_uom_code"] not in uoms:
            issues.append(f"product base UOM missing for {row['product_code']}")
    for row in read_csv(output / "assignments.csv"):
        product_code = row.get("product_code")
        category_key = (row.get("taxonomy_scheme", ""), row.get("category_code", ""))
        if product_code not in products:
            issues.append(f"category assignment product missing: {product_code}")
        if category_key not in categories:
            issues.append(f"category assignment category missing: {category_key}")
        key = (product_code, category_key)
        if key in category_assignments:
            issues.append(f"duplicate product/category assignment: {key}")
        category_assignments.add(key)
    for row in read_csv(output / "references.csv"):
        if row.get("product_code") not in products:
            issues.append(f"source reference product missing: {row.get('product_code')}")
    for row in read_csv(output / "packaging.csv"):
        product_code = row.get("product_code")
        if product_code not in products:
            issues.append(f"packaging product missing: {product_code}")
        if row.get("package_uom_code") and row["package_uom_code"] not in uoms:
            issues.append(f"packaging UOM missing: {product_code}:{row.get('package_uom_code')}")
        key = (product_code, row.get("packaging_code"))
        if key in package_keys:
            issues.append(f"duplicate product packaging: {key}")
        package_keys.add(key)
    for row in read_csv(output / "stores.csv"):
        if row.get("latitude") and not Decimal(row["latitude"]).copy_abs() <= Decimal("90"):
            issues.append(f"invalid latitude for {row.get('store_code')}")
        if row.get("longitude") and not Decimal(row["longitude"]).copy_abs() <= Decimal("180"):
            issues.append(f"invalid longitude for {row.get('store_code')}")
        if bool(row.get("latitude")) != bool(row.get("longitude")):
            issues.append(f"latitude/longitude pair incomplete for {row.get('store_code')}")
    for row in read_csv(output / "orders.csv"):
        if row.get("demand_store_code") not in stores:
            issues.append(f"order demand store missing: {row.get('order_number')}")
        if row.get("order_number") in order_keys:
            issues.append(f"duplicate order number: {row.get('order_number')}")
        order_keys.add(row.get("order_number"))
    for row in read_csv(output / "lines.csv"):
        if row.get("order_number") not in order_keys:
            issues.append(f"sales line order missing: {row.get('order_number')}")
        if row.get("product_code") not in products:
            issues.append(f"sales line product missing: {row.get('product_code')}")
        if row.get("sales_uom_code") and row["sales_uom_code"] not in uoms:
            issues.append(f"sales line UOM missing: {row.get('sales_uom_code')}")
        key = (row.get("order_number"), row.get("line_number"))
        if key in line_keys:
            issues.append(f"duplicate sales line key: {key}")
        line_keys.add(key)
        if not row.get("sold_quantity") or Decimal(row["sold_quantity"]) <= 0:
            issues.append(f"sales line quantity must be positive: {key}")
        if row.get("packaging_code") and (row.get("product_code"), row.get("packaging_code")) not in package_keys:
            issues.append(f"sales line packaging missing: {key}")
    for row in read_csv(output / "observations.csv"):
        if row.get("store_code") not in stores:
            issues.append(f"sales observation store missing: {row.get('store_code')}")
        if row.get("subject_kind") == "PRODUCT":
            if row.get("product_code") not in products or row.get("category_code"):
                issues.append(f"invalid PRODUCT observation subject: {row}")
        elif row.get("subject_kind") == "CATEGORY":
            category_key = (row.get("taxonomy_scheme", ""), row.get("category_code", ""))
            if row.get("product_code") or category_key not in categories:
                issues.append(f"invalid CATEGORY observation subject: {row}")
        else:
            issues.append(f"invalid observation subject kind: {row.get('subject_kind')}")
        natural_key = (row.get("source"), row.get("store_code"), row.get("product_code"), row.get("category_code"), row.get("period_start"), row.get("period_end"))
        if natural_key in observation_keys:
            issues.append(f"duplicate sales observation grain: {natural_key}")
        observation_keys.add(natural_key)
        if Decimal(row["quantity"]) < 0:
            issues.append(f"negative sales observation quantity: {natural_key}")

    report = {
        "prepared_directory": str(output.relative_to(PACKAGE_ROOT)).replace("\\", "/"),
        "row_counts": counts,
        "product_keys": len(products),
        "store_keys": len(stores),
        "category_keys": len(categories),
        "order_keys": len(order_keys),
        "line_keys": len(line_keys),
        "observation_keys": len(observation_keys),
        "issues": issues,
        "valid": not issues,
    }
    json_write(output.parent / "validation.json", report)
    if issues:
        raise ValueError(f"Prepared source validation failed ({len(issues)} issues). See {output.parent / 'validation.json'}")
    return report


def _prepared_source_info(source: str) -> tuple[Path, dict[str, Any]]:
    if source not in SOURCE_ORDER:
        raise ValueError(f"Unknown source {source!r}; expected one of {SOURCE_ORDER}")
    source_root = RUN_ROOT / source_folder_name(source)
    return source_root, source_root / "prepared" / "full"


def ensure_source_predecessors(source: str) -> None:
    index = SOURCE_ORDER.index(source)
    for previous in SOURCE_ORDER[:index]:
        marker = RUN_ROOT / source_folder_name(previous) / "verified-full.json"
        if not marker.exists():
            raise RuntimeError(f"Complete and verify {previous} before starting {source}.")


def prepare_source(source: str) -> dict[str, Any]:
    ensure_source_predecessors(source)
    source_root, output = _prepared_source_info(source)
    output.mkdir(parents=True, exist_ok=True)
    (source_root / "manifest.full.json").unlink(missing_ok=True)
    if source == "longchau":
        result = prepare_longchau(output)
    elif source == "irpd":
        result = prepare_irpd(output)
    elif source == "onyx":
        result = prepare_onyx(output)
    else:
        result = prepare_pharma_sales(output)
    validation = validate_prepared(output)
    prepared_files = {}
    for path in sorted(output.iterdir()):
        if path.is_file():
            prepared_files[path.name] = {"sha256": sha256_file(path), "rows": count_csv_rows(path) if path.suffix.casefold() == ".csv" else None}
    manifest = {
        "run_id": RUN_ID,
        "source_name": source,
        "source_id": result["source_id"],
        "stage": "full",
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_profile": result["profile"],
        "prepared_row_counts": result["counts"],
        "validation": validation,
        "files": prepared_files,
    }
    json_write(source_root / "profile.json", result["profile"])
    json_write(source_root / "manifest.full.json", manifest)
    return manifest


def _filter_csv(source_file: Path, destination: Path, fields: tuple[str, ...], predicate) -> int:
    handle, writer = csv_writer(destination, fields)
    count = 0
    try:
        for row in read_csv(source_file):
            if predicate(row):
                writer.writerow(row)
                count += 1
    finally:
        handle.close()
    return count


def _longchau_sample_product_selection(full: Path, limit: int = 50) -> tuple[set[str], dict[str, int]]:
    products = {row["product_code"] for row in read_csv(full / "products.csv")}
    category_rows = list(read_csv(full / "categories.csv"))
    parent = {
        (row["taxonomy_scheme"], row["category_code"]): row.get("parent_category_code", "")
        for row in category_rows
    }
    root_products: dict[str, set[str]] = defaultdict(set)
    for row in read_csv(full / "assignments.csv"):
        if row["taxonomy_scheme"] != "LONGCHAU_PUBLIC" or row["product_code"] not in products:
            continue
        root = row["category_code"]
        visited: set[str] = set()
        while parent.get(("LONGCHAU_PUBLIC", root)):
            if root in visited:
                raise RuntimeError(f"Long Châu taxonomy parent cycle while selecting sample: {root}")
            visited.add(root)
            root = parent[("LONGCHAU_PUBLIC", root)]
        root_products[root].add(row["product_code"])

    mapping = load_yaml(PACKAGE_ROOT / "config" / "mappings" / "pharma_sales_atc_products.yaml")
    seed_codes = set(mapping.get("matching", {}).get("sample_seed_product_codes", []))
    missing_seeds = sorted(seed_codes - products)
    if missing_seeds:
        raise RuntimeError(f"Configured ATC sample products are absent from the current Long Châu catalog: {missing_seeds}")
    if len(seed_codes) > limit:
        raise RuntimeError(f"Configured ATC sample products exceed the Long Châu SKU sample limit of {limit}.")

    selected_roots = sorted(root_products, key=lambda root: (-len(root_products[root]), root))[:5]
    if len(selected_roots) < 5:
        raise RuntimeError(f"Long Châu sample needs five public taxonomy roots; found {len(selected_roots)}.")
    quota, remainder = divmod(limit, len(selected_roots))
    selected = set(seed_codes)
    for index, root in enumerate(selected_roots):
        target = quota + (1 if index < remainder else 0)
        pool = sorted(root_products[root] - selected)
        selected.update(pool[:max(0, target - len(selected & root_products[root]))])
    if len(selected) < limit:
        selected.update(sorted(products - selected)[:limit - len(selected)])
    if len(selected) != limit:
        raise RuntimeError(f"Long Châu sample expected {limit} unique SKUs, selected {len(selected)}.")
    group_counts = {root: len(selected & root_products[root]) for root in selected_roots}
    if any(count == 0 for count in group_counts.values()):
        raise RuntimeError(f"Long Châu sample did not represent each selected taxonomy root: {group_counts}")
    return selected, group_counts


def _longchau_sample_store_selection(full: Path, limit: int = 20) -> set[str]:
    stores = sorted(read_csv(full / "stores.csv"), key=lambda row: (row.get("region_name", "").casefold(), row["store_code"]))
    selected: list[dict[str, str]] = []
    seen_regions: set[str] = set()
    for row in stores:
        region = row.get("region_name", "").strip().casefold()
        if region and region not in seen_regions:
            selected.append(row)
            seen_regions.add(region)
            if len(selected) == limit:
                break
    if len(selected) < limit:
        selected_codes = {row["store_code"] for row in selected}
        for row in stores:
            if row["store_code"] not in selected_codes:
                selected.append(row)
                selected_codes.add(row["store_code"])
                if len(selected) == limit:
                    break
    if len(selected) != limit:
        raise RuntimeError(f"Long Châu sample expected {limit} stores, selected {len(selected)}.")
    return {row["store_code"] for row in selected}


def _filter_sample_dimensions(
    full: Path,
    sample: Path,
    source: str,
    selected_products: set[str],
    selected_stores: set[str],
    selected_lines: list[dict[str, str]],
    selected_observations: list[dict[str, str]],
) -> dict[str, int]:
    for row in selected_lines:
        if row.get("product_code"):
            selected_products.add(row["product_code"])
    for row in selected_observations:
        if row.get("product_code"):
            selected_products.add(row["product_code"])
        if row.get("store_code"):
            selected_stores.add(row["store_code"])
    selected_stores.update(row["demand_store_code"] for row in read_csv(sample / "orders.csv") if row.get("demand_store_code"))

    product_rows = [row for row in read_csv(full / "products.csv") if row["product_code"] in selected_products]
    existing_products = {row["product_code"] for row in product_rows}
    if source == "pharma_sales":
        longchau_sample_products = RUN_ROOT / "01-longchau" / "prepared" / "sample" / "products.csv"
        canonical_products = {row["product_code"] for row in read_csv(longchau_sample_products)} if longchau_sample_products.exists() else set()
        missing_products = sorted(selected_products - canonical_products)
        if missing_products:
            raise RuntimeError(f"Pharma Sales sample requires Long Châu candidate products outside the bounded catalog sample: {missing_products[:10]}")
    else:
        missing_products = sorted(selected_products - existing_products)
        if missing_products:
            raise RuntimeError(f"Sample facts refer to product codes missing from the source product dimension: {missing_products[:10]}")
    manufacturer_codes = {row["manufacturer_code"] for row in product_rows if row.get("manufacturer_code")}
    uom_codes = {row["base_uom_code"] for row in product_rows if row.get("base_uom_code")}

    packaging_rows = [row for row in read_csv(full / "packaging.csv") if row["product_code"] in selected_products]
    uom_codes.update(row["package_uom_code"] for row in packaging_rows if row.get("package_uom_code"))
    uom_codes.update(row["sales_uom_code"] for row in selected_lines if row.get("sales_uom_code"))
    uom_codes.update(row["quantity_uom_code"] for row in selected_observations if row.get("quantity_uom_code"))

    assignment_rows = [row for row in read_csv(full / "assignments.csv") if row["product_code"] in selected_products]
    category_rows = list(read_csv(full / "categories.csv"))
    category_map = {(row["taxonomy_scheme"], row["category_code"]): row for row in category_rows}
    selected_categories = {(row["taxonomy_scheme"], row["category_code"]) for row in assignment_rows}
    selected_categories.update(
        (row["taxonomy_scheme"], row["category_code"])
        for row in selected_observations
        if row.get("taxonomy_scheme") and row.get("category_code")
    )
    pending = list(selected_categories)
    while pending:
        scheme, code = pending.pop()
        category = category_map.get((scheme, code))
        if category is None:
            raise RuntimeError(f"Sample category is absent from the source taxonomy: {scheme}:{code}")
        parent_code = category.get("parent_category_code", "")
        parent_key = (scheme, parent_code) if parent_code else None
        if parent_key and parent_key not in selected_categories:
            selected_categories.add(parent_key)
            pending.append(parent_key)

    files_to_write = {
        "uoms": lambda row: row["uom_code"] in uom_codes,
        "manufacturers": lambda row: row["manufacturer_code"] in manufacturer_codes,
        "categories": lambda row: (row["taxonomy_scheme"], row["category_code"]) in selected_categories,
        "products": lambda row: row["product_code"] in selected_products,
        "assignments": lambda row: row["product_code"] in selected_products,
        "references": lambda row: row.get("product_code", "") in selected_products,
        "packaging": lambda row: row["product_code"] in selected_products,
        "stores": lambda row: row["store_code"] in selected_stores,
        # Full reject evidence remains with the full source profile; a sample
        # is a bounded row-level fixture, not a resampling of rejected input.
        "rejects": lambda row: False,
    }
    counts: dict[str, int] = {}
    for name, predicate in files_to_write.items():
        source_file = full / f"{name}.csv"
        if source_file.exists():
            counts[name] = _filter_csv(source_file, sample / source_file.name, CSV_FIELDS[name], predicate)
        else:
            counts[name] = write_csv(sample / f"{name}.csv", CSV_FIELDS[name], [])
    return counts


def prepare_sample(source: str) -> dict[str, Any]:
    source_root, full = _prepared_source_info(source)
    if not (source_root / "manifest.full.json").exists():
        raise RuntimeError(f"Prepare {source} full data before creating its sample.")
    sample = source_root / "prepared" / "sample"
    sample.mkdir(parents=True, exist_ok=True)
    (source_root / "manifest.sample.json").unlink(missing_ok=True)
    order_rows: list[dict[str, str]] = []
    line_rows: list[dict[str, str]] = []
    observation_rows: list[dict[str, str]] = []
    selected_products: set[str] = set()
    selected_stores: set[str] = set()
    sample_parameters: dict[str, Any]

    if source == "irpd":
        first_dates = sorted({datetime.fromisoformat(row["ordered_at"]).date().isoformat() for row in read_csv(full / "orders.csv")})[:7]
        date_set = set(first_dates)
        order_rows = [row for row in read_csv(full / "orders.csv") if datetime.fromisoformat(row["ordered_at"]).date().isoformat() in date_set]
        order_codes = {row["order_number"] for row in order_rows}
        line_rows = [row for row in read_csv(full / "lines.csv") if row["order_number"] in order_codes]
        sample_parameters = {
            "invoice_count": len(order_rows), "line_count": len(line_rows), "day_count": len(first_dates),
            "selected_dates": first_dates, "selection": "complete invoices for the first seven source dates with sales",
        }
    elif source == "onyx":
        store_rows = sorted(read_csv(full / "stores.csv"), key=lambda row: (row.get("country_code", ""), row["store_code"]))
        by_country: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in store_rows:
            by_country[row.get("country_code", "")].append(row)
        selected_store_rows = [by_country[country][0] for country in sorted(by_country) if by_country[country]][:5]
        selected_stores = {row["store_code"] for row in selected_store_rows}
        if len(selected_stores) < 5:
            for row in store_rows:
                if row["store_code"] not in selected_stores:
                    selected_stores.add(row["store_code"])
                    selected_store_rows.append(row)
                if len(selected_stores) == 5:
                    break
        if len(selected_stores) != 5:
            raise RuntimeError(f"Onyx sample expected five pharmacies, selected {len(selected_stores)}.")
        days_by_store: dict[str, set[str]] = defaultdict(set)
        for row in read_csv(full / "observations.csv"):
            if row["store_code"] in selected_stores:
                days_by_store[row["store_code"]].add(row["period_start"])
        selected_store_days: set[tuple[str, str]] = set()
        selected_days_by_store: dict[str, list[str]] = {}
        for store_code in sorted(selected_stores):
            selected_days = sorted(days_by_store[store_code])[:14]
            if len(selected_days) != 14:
                raise RuntimeError(f"Onyx store {store_code} has only {len(selected_days)} sample dates; expected 14.")
            selected_days_by_store[store_code] = selected_days
            selected_store_days.update((store_code, day) for day in selected_days)
        observation_rows = [row for row in read_csv(full / "observations.csv") if (row["store_code"], row["period_start"]) in selected_store_days]
        order_rows = [row for row in read_csv(full / "orders.csv") if (row["demand_store_code"], datetime.fromisoformat(row["ordered_at"]).date().isoformat()) in selected_store_days]
        order_codes = {row["order_number"] for row in order_rows}
        line_rows = [row for row in read_csv(full / "lines.csv") if row["order_number"] in order_codes]
        sample_parameters = {
            "store_count": len(selected_stores), "selected_store_codes": sorted(selected_stores),
            "days_per_store": 14, "selected_dates_by_store": selected_days_by_store,
            "daily_order_count": len(order_rows), "selection": "first 14 fact dates for five representative pharmacies",
        }
    elif source == "pharma_sales":
        selected_dates = sorted({row["period_start"] for row in read_csv(full / "observations.csv")})[:28]
        selected_date_set = set(selected_dates)
        observation_rows = [row for row in read_csv(full / "observations.csv") if row["period_start"] in selected_date_set]
        order_rows = [row for row in read_csv(full / "orders.csv") if datetime.fromisoformat(row["ordered_at"]).date().isoformat() in selected_date_set]
        order_codes = {row["order_number"] for row in order_rows}
        line_rows = [row for row in read_csv(full / "lines.csv") if row["order_number"] in order_codes]
        sample_parameters = {
            "date_count": len(selected_dates), "selected_dates": selected_dates,
            "observation_rows": len(observation_rows), "order_count": len(order_rows), "line_count": len(line_rows),
            "selection": "first 28 complete source days at date by ATC-group grain",
        }
    else:
        selected_products, root_counts = _longchau_sample_product_selection(full)
        selected_stores = _longchau_sample_store_selection(full)
        sample_parameters = {
            "product_count": len(selected_products), "selected_product_codes": sorted(selected_products),
            "taxonomy_roots": root_counts, "store_count": len(selected_stores),
            "selected_store_codes": sorted(selected_stores),
            "selection": "50 SKUs across five public taxonomy roots and 20 locations selected across regions; no sales facts",
        }

    write_csv(sample / "orders.csv", CSV_FIELDS["orders"], order_rows)
    write_csv(sample / "lines.csv", CSV_FIELDS["lines"], line_rows)
    write_csv(sample / "observations.csv", CSV_FIELDS["observations"], observation_rows)
    dimension_counts = _filter_sample_dimensions(full, sample, source, selected_products, selected_stores, line_rows, observation_rows)
    for name in ("orders", "lines", "observations"):
        target = sample / f"{name}.csv"
        if not target.exists():
            write_csv(target, CSV_FIELDS[name], [])
    validation = validate_prepared(sample)
    files = {}
    counts = {}
    for path in sorted(sample.glob("*.csv")):
        files[path.name] = {"sha256": sha256_file(path), "rows": count_csv_rows(path)}
        counts[path.stem] = files[path.name]["rows"]
    manifest = {
        "run_id": RUN_ID,
        "source_name": source,
        "stage": "sample",
        "sample_rule_set": "bounded-sample-v2",
        "full_manifest_sha256": sha256_file(source_root / "manifest.full.json"),
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sample_parameters": sample_parameters,
        "dimension_row_counts": dimension_counts,
        "prepared_row_counts": counts,
        "validation": validation,
        "files": files,
    }
    json_write(source_root / "manifest.sample.json", manifest)
    return manifest

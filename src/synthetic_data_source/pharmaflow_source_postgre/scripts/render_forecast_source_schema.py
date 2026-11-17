from __future__ import annotations

from html import escape
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PACKAGE_ROOT / "forecast_source_schema_v2.html"
PAPER = "#f7f8fc"
PAPER_2 = "#eef2ff"
INK = "#1e1b4b"
MUTED = "#475569"
SOFT = "#64748b"
RULE = "#d7dbea"
RULE_SOLID = "#c7c9dc"
ACCENT = "#6366f1"


def field(name: str, sql_type: str, tags: str = "") -> tuple[str, str, str]:
    return name, sql_type, tags


PANELS = [
    {
        "id": "catalog-core",
        "title": "01 · Catalog identity",
        "sub": "Core product identity, its manufacturer reference, and the base unit used when supported.",
        "description": "Three physical tables show the compact product master and its foreign keys to manufacturer and unit of measure.",
        "height": 560,
        "tables": [
            {"name": "catalog.manufacturer", "x": 48, "y": 64, "w": 336, "schema": "catalog", "rows": [
                field("manufacturer_id", "bigint", "PK"), field("manufacturer_code", "text", "UQ"),
                field("manufacturer_name", "text", "NN"), field("country_code", "text"),
                field("source", "text", "NN"), field("created_at", "timestamptz", "NN"),
                field("updated_at", "timestamptz", "NN"),
            ]},
            {"name": "catalog.unit_of_measure", "x": 48, "y": 344, "w": 336, "schema": "catalog", "rows": [
                field("uom_code", "text", "PK"), field("uom_name", "text", "NN"),
                field("uom_kind", "text", "NN"), field("source", "text", "NN"),
                field("created_at", "timestamptz", "NN"),
            ]},
            {"name": "catalog.product", "x": 784, "y": 144, "w": 432, "schema": "catalog", "rows": [
                field("product_id", "bigint", "PK"), field("product_code", "text", "UQ NN"),
                field("product_name", "text", "NN"), field("brand_name", "text"),
                field("manufacturer_id", "bigint", "FK"), field("base_uom_code", "text", "FK"),
                field("is_active", "boolean", "NN"), field("source", "text", "NN"),
            ], "more": 2},
        ],
        "edges": [
            {"points": [(784, 272), (700, 272), (700, 112), (384, 112)], "label": (692, 200, "v")},
            {"points": [(784, 296), (640, 296), (640, 392), (384, 392)], "label": (500, 392, "h")},
        ],
        "note": "Brand and manufacturer are separate attributes. The product table stays semantic; detailed source captures remain in dataset evidence.",
    },
    {
        "id": "taxonomy-source-map",
        "title": "02 · Taxonomy and source mapping",
        "sub": "Many-to-many product classification remains distinct from source-product identity.",
        "description": "Four catalog tables show product assignments to independent taxonomies and compact mapping from source product codes.",
        "height": 720,
        "tables": [
            {"name": "catalog.product", "x": 48, "y": 180, "w": 344, "schema": "catalog", "rows": [
                field("product_id", "bigint", "PK"), field("product_code", "text", "UQ NN"),
                field("product_name", "text", "NN"), field("brand_name", "text"),
                field("manufacturer_id", "bigint", "FK"), field("base_uom_code", "text", "FK"),
                field("is_active", "boolean", "NN"), field("source", "text", "NN"),
            ], "more": 2},
            {"name": "catalog.product_category", "x": 900, "y": 64, "w": 336, "schema": "catalog", "rows": [
                field("category_id", "bigint", "PK"), field("taxonomy_scheme", "text", "NN"),
                field("category_code", "text", "NN"), field("category_name", "text", "NN"),
                field("parent_category_id", "bigint", "FK"), field("source_category_path", "text"),
                field("is_active", "boolean", "NN"), field("source", "text", "NN"),
            ]},
            {"name": "catalog.product_category_assignment", "x": 456, "y": 420, "w": 344, "schema": "catalog", "rows": [
                field("product_id", "bigint", "PK FK NN"), field("category_id", "bigint", "PK FK NN"),
                field("assignment_status", "text", "NN"), field("assignment_basis", "text", "NN"),
                field("source", "text", "NN"), field("assigned_at", "timestamptz", "NN"),
            ]},
            {"name": "catalog.product_source_reference", "x": 48, "y": 444, "w": 344, "schema": "catalog", "rows": [
                field("product_source_reference_id", "bigint", "PK"), field("product_id", "bigint", "FK"),
                field("source", "text", "NN"), field("external_product_key", "text", "NN"),
                field("match_status", "text", "NN"), field("match_basis", "text"),
                field("observed_at", "timestamptz", "NN"),
            ]},
        ],
        "edges": [
            {"points": [(456, 468), (436, 468), (436, 220), (392, 220)], "label": (504, 340, "v")},
            {"points": [(800, 492), (844, 492), (844, 112), (900, 112)], "label": (836, 286, "v")},
            {"points": [(392, 516), (404, 516), (404, 236), (392, 236)], "label": (472, 376, "v")},
        ],
        "note": "`parent_category_id` is a self-reference to `product_category.category_id`; the category tree remains scoped by taxonomy_scheme. Each panel stays within the 5-table / 6-FK budget.",
    },
    {
        "id": "packaging-contract",
        "title": "03 · Packaging-to-product integrity",
        "sub": "A package label is not a verified conversion; every selected sales package must belong to the line product.",
        "description": "Product, package, and sales-line columns show the composite product-packaging foreign key and nullable conversion evidence.",
        "height": 720,
        "tables": [
            {"name": "catalog.product", "x": 48, "y": 144, "w": 344, "schema": "catalog", "rows": [
                field("product_id", "bigint", "PK"), field("product_code", "text", "UQ NN"),
                field("product_name", "text", "NN"), field("brand_name", "text"),
                field("manufacturer_id", "bigint", "FK"), field("base_uom_code", "text", "FK"),
                field("is_active", "boolean", "NN"), field("source", "text", "NN"),
            ], "more": 2},
            {"name": "catalog.product_packaging", "x": 456, "y": 64, "w": 360, "schema": "catalog", "rows": [
                field("product_packaging_id", "bigint", "PK"), field("product_id", "bigint", "FK NN"),
                field("packaging_code", "text", "NN"), field("display_name", "text", "NN"),
                field("package_uom_code", "text", "FK"), field("quantity_in_base_uom", "numeric(18,4)"),
                field("is_default_sales_unit", "boolean", "NN"), field("source", "text", "NN"),
            ]},
            {"name": "pos.sales_order_line", "x": 856, "y": 320, "w": 384, "schema": "pos", "rows": [
                field("sales_order_line_id", "bigint", "PK"), field("sales_order_id", "bigint", "FK NN"),
                field("line_number", "integer", "NN"), field("product_id", "bigint", "FK NN"),
                field("product_packaging_id", "bigint", "FK"), field("sold_quantity", "numeric(18,4)", "NN"),
                field("sales_uom_code", "text", "FK"), field("currency_code", "char(3)"),
            ], "more": 6},
        ],
        "edges": [
            {"points": [(456, 136), (420, 136), (40, 136), (40, 184), (48, 184)], "label": (220, 136, "h")},
            {"points": [(856, 440), (432, 440), (432, 200), (392, 200)], "label": (500, 316, "v")},
            {"points": [(856, 464), (840, 464), (840, 500), (24, 500), (24, 112), (456, 112)], "label": (92, 460, "v")},
        ],
        "note": "`fk_sales_line_product_packaging_pair` references `(product_packaging_id, product_id)` together. Packaging UOM points to `catalog.unit_of_measure` (panel 01); conversion stays NULL unless supported.",
    },
    {
        "id": "pos-transaction",
        "title": "04 · POS transaction and simulated store warehouse",
        "sub": "One header belongs to its demand store; transaction stores get an explicitly synthetic warehouse row. Fulfillment and channel stay nullable.",
        "description": "Five physical tables show demand location, a simulated store warehouse, order header, product line, and the product dimension used by the line.",
        "height": 720,
        "tables": [
            {"name": "org.store", "x": 48, "y": 112, "w": 344, "schema": "org", "rows": [
                field("store_id", "bigint", "PK"), field("store_code", "text", "UQ NN"),
                field("store_name", "text", "NN"), field("country_code", "char(2)"),
                field("latitude", "numeric(9,6)"), field("longitude", "numeric(9,6)"),
                field("timezone_name", "text", "NN"), field("source", "text", "NN"),
            ], "more": 5},
            {"name": "pos.sales_order", "x": 456, "y": 64, "w": 344, "schema": "pos", "rows": [
                field("sales_order_id", "bigint", "PK"), field("order_number", "text", "UQ NN"),
                field("demand_location_id", "bigint", "FK NN"), field("fulfillment_location_id", "bigint", "FK"),
                field("sales_channel_id", "bigint", "FK"), field("ordered_at", "timestamptz", "NN"),
                field("order_status", "text", "NN"), field("currency_code", "char(3)"),
            ], "more": 4},
            {"name": "org.warehouse", "x": 456, "y": 416, "w": 344, "schema": "org", "rows": [
                field("warehouse_id", "bigint", "PK"), field("warehouse_code", "text", "UQ NN"),
                field("warehouse_kind", "text", "NN"), field("store_id", "bigint", "FK"),
                field("data_origin", "text", "NN"),
            ], "more": 2},
            {"name": "pos.sales_order_line", "x": 856, "y": 240, "w": 384, "schema": "pos", "rows": [
                field("sales_order_line_id", "bigint", "PK"), field("sales_order_id", "bigint", "FK NN"),
                field("line_number", "integer", "NN"), field("product_id", "bigint", "FK NN"),
                field("sold_quantity", "numeric(18,4)", "NN"), field("line_amount", "numeric(18,2)"),
                field("currency_code", "char(3)"), field("source", "text", "NN"),
            ], "more": 6},
            {"name": "catalog.product", "x": 48, "y": 440, "w": 344, "schema": "catalog", "rows": [
                field("product_id", "bigint", "PK"), field("product_code", "text", "UQ NN"),
                field("product_name", "text", "NN"), field("source", "text", "NN"),
            ], "more": 6},
        ],
        "edges": [
            {"points": [(456, 160), (392, 160)], "label": (424, 160, "h")},
            {"points": [(856, 312), (824, 312), (824, 112), (800, 112)], "label": (892, 220, "v")},
            {"points": [(856, 360), (832, 360), (832, 624), (416, 624), (416, 488), (392, 488)], "label": (608, 624, "h")},
            {"points": [(456, 440), (416, 440), (416, 340), (392, 340)], "label": (416, 390, "v")},
            {"points": [(700, 316), (700, 400), (640, 400), (640, 416)], "label": (670, 400, "h")},
        ],
        "note": "Synthetic store warehouses are location placeholders; they do not imply stock or receipts. Fulfillment and channel remain NULL when unknown.",
    },
    {
        "id": "sales-observation",
        "title": "05 · Aggregate sales observation",
        "sub": "Keep the source grain intact: store × period × product OR category, with amount and currency only when known.",
        "description": "Four physical tables show aggregate facts attached to one store and exactly one product or category subject.",
        "height": 720,
        "tables": [
            {"name": "org.store", "x": 48, "y": 80, "w": 344, "schema": "org", "rows": [
                field("store_id", "bigint", "PK"), field("store_code", "text", "UQ NN"),
                field("store_name", "text", "NN"), field("country_code", "char(2)"),
                field("latitude", "numeric(9,6)"), field("longitude", "numeric(9,6)"),
                field("timezone_name", "text", "NN"), field("source", "text", "NN"),
            ], "more": 5},
            {"name": "catalog.product", "x": 48, "y": 408, "w": 344, "schema": "catalog", "rows": [
                field("product_id", "bigint", "PK"), field("product_code", "text", "UQ NN"),
                field("product_name", "text", "NN"), field("brand_name", "text"),
                field("manufacturer_id", "bigint", "FK"), field("base_uom_code", "text", "FK"),
                field("is_active", "boolean", "NN"), field("source", "text", "NN"),
            ], "more": 2},
            {"name": "catalog.product_category", "x": 900, "y": 80, "w": 336, "schema": "catalog", "rows": [
                field("category_id", "bigint", "PK"), field("taxonomy_scheme", "text", "NN"),
                field("category_code", "text", "NN"), field("category_name", "text", "NN"),
                field("parent_category_id", "bigint", "FK"), field("source_category_path", "text"),
                field("is_active", "boolean", "NN"), field("source", "text", "NN"),
            ]},
            {"name": "pos.sales_observation", "x": 456, "y": 260, "w": 400, "schema": "pos", "rows": [
                field("sales_observation_id", "bigint", "PK"), field("store_id", "bigint", "FK NN"),
                field("subject_kind", "text", "NN"), field("product_id", "bigint", "FK"),
                field("category_id", "bigint", "FK"), field("period_start", "date", "NN"),
                field("period_end", "date", "NN"), field("quantity", "numeric(18,4)", "NN"),
            ], "more": 6},
        ],
        "edges": [
            {"points": [(456, 332), (440, 332), (440, 128), (392, 128)], "label": (508, 236, "v")},
            {"points": [(456, 380), (416, 380), (416, 456), (392, 456)], "label": (408, 396, "v")},
            {"points": [(856, 404), (1260, 404), (1260, 128), (1236, 128)], "label": (1090, 404, "h")},
        ],
        "note": "CHECK enforces PRODUCT XOR CATEGORY. IRPD transactions and Onyx/Pharma Sales aggregate observations keep their source grain and provenance separate.",
    },
]


def table_height(table: dict) -> int:
    return 36 + 24 * (len(table["rows"]) + (1 if table.get("more") else 0))


def rounded_path(points: list[tuple[int, int]], radius: int = 8) -> str:
    if len(points) < 2:
        raise ValueError("An FK route needs at least two points")
    parts = [f"M {points[0][0]} {points[0][1]}"]
    for index in range(1, len(points) - 1):
        previous, corner, following = points[index - 1], points[index], points[index + 1]
        if previous[0] != corner[0] and previous[1] != corner[1]:
            raise ValueError(f"Non-orthogonal incoming segment: {points}")
        if following[0] != corner[0] and following[1] != corner[1]:
            raise ValueError(f"Non-orthogonal outgoing segment: {points}")
        if previous[0] == corner[0]:
            before = (corner[0], corner[1] - radius if previous[1] < corner[1] else corner[1] + radius)
        else:
            before = (corner[0] - radius if previous[0] < corner[0] else corner[0] + radius, corner[1])
        if following[0] == corner[0]:
            after = (corner[0], corner[1] + radius if following[1] > corner[1] else corner[1] - radius)
        else:
            after = (corner[0] + radius if following[0] > corner[0] else corner[0] - radius, corner[1])
        parts.extend((f"L {before[0]} {before[1]}", f"Q {corner[0]} {corner[1]} {after[0]} {after[1]}"))
    parts.append(f"L {points[-1][0]} {points[-1][1]}")
    return " ".join(parts)


def render_table(table: dict) -> str:
    x, y, w = table["x"], table["y"], table["w"]
    rows = table["rows"]
    more = table.get("more", 0)
    h = table_height(table)
    header_fill = PAPER_2 if table["schema"] == "catalog" else "#f1f3f8"
    out = [f'<g aria-label="{escape(table["name"])}">']
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#ffffff" stroke="{INK}" stroke-width="1"/>')
    out.append(f'<path d="M{x+6} {y}H{x+w-6}V{y+36}H{x+6}Z" fill="{header_fill}"/>')
    out.append(f'<text x="{x+12}" y="{y+23}" class="table-name">{escape(table["name"])}</text>')
    out.append(f'<text x="{x+w-12}" y="{y+22}" text-anchor="end" class="table-tag">TABLE</text>')
    out.append(f'<line x1="{x}" y1="{y+36}" x2="{x+w}" y2="{y+36}" stroke="{RULE}"/>')
    for i, (name, sql_type, tags) in enumerate(rows):
        ry = y + 36 + i * 24
        if i % 2 == 1:
            out.append(f'<rect x="{x+1}" y="{ry}" width="{w-2}" height="24" fill="rgba(30,27,75,0.025)"/>')
        out.append(f'<text x="{x+12}" y="{ry+16}" class="column-name">{escape(name)}</text>')
        if tags:
            out.append(f'<text x="{x+w-144}" y="{ry+16}" class="constraint">{escape(tags)}</text>')
        out.append(f'<text x="{x+w-12}" y="{ry+16}" text-anchor="end" class="sql-type">{escape(sql_type)}</text>')
    if more:
        ry = y + 36 + len(rows) * 24
        out.append(f'<rect x="{x+1}" y="{ry}" width="{w-2}" height="24" fill="#ffffff"/>')
        out.append(f'<text x="{x+12}" y="{ry+16}" class="overflow">+ {more} more columns</text>')
    out.append("</g>")
    return "\n".join(out)


def render_edge(edge: dict, marker_id: str) -> str:
    path = rounded_path(edge["points"])
    x, y, orientation = edge["label"]
    width, height = 60, 12
    if orientation == "v":
        rect_x, rect_y, text_x, text_y = x - width, y - 6, x - width / 2, y + 3
    else:
        rect_x, rect_y, text_x, text_y = x - width / 2, y - 22, x, y - 13
    return "\n".join([
        f'<path d="{path}" fill="none" stroke="{MUTED}" stroke-width="1.3" marker-end="url(#{marker_id})"/>',
        f'<rect x="{rect_x:g}" y="{rect_y:g}" width="{width}" height="{height}" rx="2" fill="#ffffff"/>',
        f'<text x="{text_x:g}" y="{text_y:g}" text-anchor="middle" class="fk-label">NO ACTION</text>',
    ])


def render_panel(panel: dict) -> str:
    slug = panel["id"]
    out = [f'<section aria-labelledby="{slug}-heading">']
    out.append(f'<h2 id="{slug}-heading">{escape(panel["title"])}</h2>')
    out.append(f'<p class="sub">{escape(panel["sub"])}</p>')
    out.append('<div class="diagram-container">')
    out.append(f'<svg viewBox="0 0 1280 {panel["height"]}" role="img" aria-labelledby="{slug}-title {slug}-desc" xmlns="http://www.w3.org/2000/svg">')
    out.append(f'<title id="{slug}-title">{escape(panel["title"])}</title>')
    out.append(f'<desc id="{slug}-desc">{escape(panel["description"])}</desc>')
    marker_id = f"{slug}-arrow"
    out.append(f'<defs><marker id="{marker_id}" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="{MUTED}"/></marker></defs>')
    out.append(f'<rect width="1280" height="{panel["height"]}" fill="#ffffff"/>')
    # Connectors and their masks are painted before the table boxes.
    for edge in panel["edges"]:
        out.append(render_edge(edge, marker_id))
    for table in panel["tables"]:
        out.append(render_table(table))
    note_y = panel["height"] - 28
    out.append(f'<line x1="32" y1="{note_y-18}" x2="1248" y2="{note_y-18}" stroke="{RULE}"/>')
    out.append(f'<text x="40" y="{note_y}" class="panel-note">{escape(panel["note"])}</text>')
    out.append('</svg></div></section>')
    return "\n".join(out)


def render_html() -> str:
    panels = "\n".join(render_panel(panel) for panel in PANELS)
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PharmaFlow forecast source physical schema v2</title>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing:border-box; }}
    :root {{ --paper:{PAPER}; --paper2:{PAPER_2}; --ink:{INK}; --muted:{MUTED}; --soft:{SOFT}; --rule:{RULE}; --rule-solid:{RULE_SOLID}; --accent:{ACCENT}; --sans:'Geist',system-ui,sans-serif; --serif:'Instrument Serif',Georgia,serif; --mono:'Geist Mono',ui-monospace,monospace; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font-family:var(--sans); }}
    main {{ max-width:1320px; margin:0 auto; padding:36px 24px 48px; }}
    .eyebrow {{ color:var(--muted); font:500 11px var(--mono); letter-spacing:.16em; text-transform:uppercase; margin:0 0 8px; }}
    h1 {{ font:400 clamp(32px,4vw,48px)/1.05 var(--serif); letter-spacing:-.02em; margin:0 0 10px; }}
    .intro {{ color:var(--muted); max-width:900px; line-height:1.6; margin:0 0 26px; }}
    section {{ background:#fff; border:1px solid var(--rule); border-radius:8px; padding:20px 20px 14px; margin:18px 0; }}
    h2 {{ font:600 16px var(--sans); margin:0 0 4px; }}
    .sub {{ color:var(--muted); font:12px var(--mono); line-height:1.5; margin:0 0 10px; }}
    .diagram-container {{ width:100%; overflow-x:auto; }}
    svg {{ display:block; width:100%; min-width:1280px; height:auto; }}
    .table-name {{ fill:var(--ink); font:600 12px var(--sans); }}
    .table-tag {{ fill:var(--muted); font:500 8px var(--mono); letter-spacing:.12em; }}
    .column-name {{ fill:var(--ink); font:400 12px var(--sans); }}
    .constraint {{ fill:var(--muted); font:500 8px var(--mono); }}
    .sql-type {{ fill:var(--muted); font:400 9px var(--mono); }}
    .overflow {{ fill:var(--soft); font:400 9px var(--mono); }}
    .fk-label {{ fill:var(--muted); font:400 8px var(--mono); letter-spacing:.04em; }}
    .panel-note {{ fill:var(--muted); font:400 10px var(--sans); }}
    .cards {{ display:grid; grid-template-columns:1.15fr 1fr .9fr; gap:12px; margin-top:20px; }}
    .card {{ background:#fff; border:1px solid var(--rule); border-radius:6px; padding:14px 16px; color:var(--muted); font-size:13px; line-height:1.5; }}
    .card strong {{ color:var(--ink); display:block; margin-bottom:4px; }}
    footer {{ color:var(--soft); font:400 11px/1.5 var(--mono); margin-top:22px; border-top:1px solid var(--rule); padding-top:14px; }}
    @media(max-width:760px) {{ main {{ padding:24px 14px 32px; }} section {{ padding:16px 12px 12px; }} .cards {{ grid-template-columns:1fr; }} }}
    @media print {{ .diagram-container {{ overflow-x:visible; }} svg {{ min-width:0; }} body {{ background:#fff; }} }}
  </style>
</head>
<body><main>
  <p class="eyebrow">PharmaFlow · Source database · Contract 20261104_01 · Migration 20261104_02 applied</p>
  <h1>Forecast source physical schema</h1>
  <p class="intro">Current PostgreSQL source contract for catalog, store geography, synthetic store-warehouse location markers, transaction-shaped source data, and aggregate sales facts. Each SVG is a focused database-schema view with SQL types and key constraints; `+ N more columns` means the full table continues in the canonical DDL. FK labels show PostgreSQL's default <code>NO ACTION</code> behavior where no delete action is declared.</p>
  {panels}
  <div class="cards">
    <div class="card"><strong>Observed facts and simulation are distinct</strong><code>source</code> values and the source manifests distinguish publisher-reported records from generated POS rows.</div>
    <div class="card"><strong>Aggregates keep their grain</strong>Onyx and Pharma Sales observations stay separate from any synthetic order representation.</div>
    <div class="card"><strong>Forecast source only</strong>The schema supports later forecast/KPI work; inventory decisions and logistics are outside this implementation.</div>
  </div>
  <footer>Canonical DDL: schema_full.sql · Versioned migration records: sql/migrations/ · Run evidence: runs/20261104-forecast-schema-v2/ · No downstream forecast module is implemented here.</footer>
</main></body></html>
'''


def validate_panels() -> None:
    def segments(points: list[tuple[int, int]]):
        return list(zip(points, points[1:]))

    def segment_hits_box(segment, table: dict) -> bool:
        (x1, y1), (x2, y2) = segment
        left, top = table["x"], table["y"]
        right, bottom = left + table["w"], top + table_height(table)
        if x1 == x2:
            return left < x1 < right and max(min(y1, y2), top) < min(max(y1, y2), bottom)
        return top < y1 < bottom and max(min(x1, x2), left) < min(max(x1, x2), right)

    def label_rect(edge: dict) -> tuple[float, float, float, float]:
        x, y, orientation = edge["label"]
        width, height = 60, 12
        if orientation == "v":
            return x - width, y - 6, x, y + 6
        return x - width / 2, y - 22, x + width / 2, y - 10

    def segment_hits_rect(segment, rect: tuple[float, float, float, float]) -> bool:
        (x1, y1), (x2, y2) = segment
        left, top, right, bottom = rect
        if x1 == x2:
            return left < x1 < right and max(min(y1, y2), top) < min(max(y1, y2), bottom)
        return top < y1 < bottom and max(min(x1, x2), left) < min(max(x1, x2), right)

    for panel in PANELS:
        if len(panel["tables"]) > 5 or len(panel["edges"]) > 6:
            raise ValueError(f"Diagram complexity budget exceeded in {panel['id']}")
        for table in panel["tables"]:
            if len(table["rows"]) > 8:
                raise ValueError(f"More than eight visible columns in {table['name']}")
            if table_height(table) >= panel["height"] - 48:
                raise ValueError(f"Table leaves no room for panel note: {table['name']}")
        for index, left in enumerate(panel["tables"]):
            for right in panel["tables"][index + 1:]:
                if (left["x"] < right["x"] + right["w"] and right["x"] < left["x"] + left["w"]
                        and left["y"] < right["y"] + table_height(right) and right["y"] < left["y"] + table_height(left)):
                    raise ValueError(f"Overlapping table boxes: {left['name']} and {right['name']}")
        panel_segments = []
        for edge in panel["edges"]:
            rounded_path(edge["points"])
            route_segments = segments(edge["points"])
            for segment in route_segments:
                blockers = [table["name"] for table in panel["tables"] if segment_hits_box(segment, table)]
                if blockers:
                    raise ValueError(f"FK route transits table {blockers}: {edge['points']}")
            x1, y1, x2, y2 = label_rect(edge)
            for table in panel["tables"]:
                if x1 < table["x"] + table["w"] and table["x"] < x2 and y1 < table["y"] + table_height(table) and table["y"] < y2:
                    raise ValueError(f"FK label overlaps table {table['name']}: {edge['label']}")
            panel_segments.append(route_segments)
            if any(segment_hits_rect(segment, (x1, y1, x2, y2)) for segment in route_segments):
                raise ValueError(f"FK label mask overlaps its connector: {edge['label']}")
        for i, left_segments in enumerate(panel_segments):
            for right_segments in panel_segments[i + 1:]:
                for (ax1, ay1), (ax2, ay2) in left_segments:
                    for (bx1, by1), (bx2, by2) in right_segments:
                        if ax1 == ax2 and by1 == by2:
                            x, y = ax1, by1
                            if min(bx1, bx2) < x < max(bx1, bx2) and min(ay1, ay2) < y < max(ay1, ay2):
                                raise ValueError(f"FK routes cross at {(x, y)} in {panel['id']}")
                        elif ay1 == ay2 and bx1 == bx2:
                            x, y = bx1, ay1
                            if min(ax1, ax2) < x < max(ax1, ax2) and min(by1, by2) < y < max(by1, by2):
                                raise ValueError(f"FK routes cross at {(x, y)} in {panel['id']}")
                        elif ay1 == ay2 and by1 == by2 and ay1 == by1:
                            if max(min(ax1, ax2), min(bx1, bx2)) < min(max(ax1, ax2), max(bx1, bx2)):
                                raise ValueError(f"FK routes overlap in {panel['id']}")
                        elif ax1 == ax2 and bx1 == bx2 and ax1 == bx1:
                            if max(min(ay1, ay2), min(by1, by2)) < min(max(ay1, ay2), max(by1, by2)):
                                raise ValueError(f"FK routes overlap in {panel['id']}")


if __name__ == "__main__":
    validate_panels()
    OUTPUT.write_text(render_html(), encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT.relative_to(PACKAGE_ROOT)}")

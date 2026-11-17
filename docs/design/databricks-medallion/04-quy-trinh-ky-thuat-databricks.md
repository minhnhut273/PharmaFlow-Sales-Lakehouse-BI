# 04 — Quy trình kỹ thuật Databricks

Đây là các bước đề xuất. Chưa bước nào được chạy. Tên resource là đề xuất.

## 1. Thành phần Databricks dùng

| Thành phần | Dùng cho |
|---|---|
| Workspace trên AWS `ap-southeast-1` | Cùng region với bucket weather |
| Unity Catalog | Catalog/schema/volume, quyền, lineage |
| Storage credential + External location | Đọc S3 weather (hồ sơ thầu ở S3 platform, không đọc) |
| UC Connection / Secret scope | Thông tin Neon, MongoDB |
| Auto Loader | File S3, file Mongo landing |
| Lakeflow Declarative Pipelines | Bronze → Silver → Gold có expectations |
| Lakeflow Jobs | Điều phối DAG, lịch, retry, cảnh báo |
| Databricks SQL Warehouse | Backend app đọc Gold; dashboard |
| MLflow + Unity Catalog model registry | Model forecast, version, alias `champion` |
| Databricks Asset Bundles | Đóng gói code + job + pipeline theo env, chạy từ CI |
| System tables | Audit, billing, lineage |

## 2. Bố cục code trong repo (đề xuất)

`src/pipeline/` đang là scaffold. Đề xuất:

```text
src/pipeline/databricks/
  databricks.yml                 # Asset Bundle: targets dev/prod
  resources/
    jobs.yml                     # pf_daily, pf_weather_backfill, pf_weekly_retrain
    pipelines.yml                # pf_silver, pf_gold
  src/
    bronze/pg_snapshot.py
    bronze/mongo_snapshots.py
    bronze/weather_autoloader.py
    silver/*.sql                 # Lakeflow SQL
    gold/md01_*.sql ... md05_*.sql
    ml/train_sales.py, score_sales.py, backtest.py
    ops/preflight.py, readiness.py, publish.py
  tests/                         # unit test transform bằng dữ liệu nhỏ
```

## 3. Các bước dựng

### Bước 1 — Workspace và Unity Catalog

```sql
CREATE CATALOG IF NOT EXISTS pharmaflow_dev;
USE CATALOG pharmaflow_dev;
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS bronze_pg;
CREATE SCHEMA IF NOT EXISTS bronze_mongo;
CREATE SCHEMA IF NOT EXISTS bronze_weather;
CREATE SCHEMA IF NOT EXISTS bronze_sim;
CREATE SCHEMA IF NOT EXISTS silver_core;
CREATE SCHEMA IF NOT EXISTS silver_sales;
CREATE SCHEMA IF NOT EXISTS silver_inventory;
CREATE SCHEMA IF NOT EXISTS silver_procurement;
CREATE SCHEMA IF NOT EXISTS silver_logistics;
CREATE SCHEMA IF NOT EXISTS silver_weather;
CREATE SCHEMA IF NOT EXISTS gold_md01_sales;
CREATE SCHEMA IF NOT EXISTS gold_md02_inventory;
CREATE SCHEMA IF NOT EXISTS gold_md03_procurement;
CREATE SCHEMA IF NOT EXISTS gold_md04_distribution;
CREATE SCHEMA IF NOT EXISTS gold_kpi;
CREATE SCHEMA IF NOT EXISTS ml;
CREATE VOLUME IF NOT EXISTS ops.checkpoints;
CREATE VOLUME IF NOT EXISTS bronze_mongo.landing;
CREATE VOLUME IF NOT EXISTS bronze_sim.landing;
-- bronze_app, silver_decision: tạo khi App DB có schema
```

Group UC đề xuất: `pf_data_engineers` (ghi bronze/silver/gold), `pf_ml` (ghi `ml`), `pf_app_reader` (service principal của backend, chỉ SELECT gold + ml.forecast), `pf_analysts` (SELECT silver/gold).

### Bước 2 — Nối S3 weather (chỉ đọc)

1. Tạo IAM role cho Databricks storage credential, trust Databricks UC master role + external ID.
2. Gắn **policy reader weather đã có trong Terraform** (`GetObject` + `ListBucket` theo prefix). Không cấp `PutObject`/`DeleteObject`. Thêm vào `src/infra/terrafrom/environments/dev/`.
3. Trong Databricks:

```sql
CREATE STORAGE CREDENTIAL pf_weather_reader WITH (AWS_IAM_ROLE = 'arn:aws:iam::<acct>:role/pharmaflow-dev-databricks-weather-reader');
CREATE EXTERNAL LOCATION pf_weather_raw
  URL 's3://pharmaflow-dev-weather-raw-<acct>-ap-southeast-1/raw/open_meteo/'
  WITH (STORAGE CREDENTIAL pf_weather_reader) COMMENT 'Open-Meteo raw, read-only';
CREATE EXTERNAL VOLUME bronze_weather.weather_raw
  LOCATION 's3://pharmaflow-dev-weather-raw-<acct>-ap-southeast-1/raw/open_meteo/';
GRANT READ VOLUME ON VOLUME bronze_weather.weather_raw TO pf_data_engineers;
```

### Bước 3 — Nối PostgreSQL Neon

1. Tạo role Neon mới `dbx_reader`: `SELECT` trên 5 schema, `default_transaction_read_only = on`. Không dùng role loader.
2. Lưu thông tin vào secret scope `pf-neon` (`host`, `user`, `password`) hoặc UC Connection type `POSTGRESQL`.
3. Notebook Bronze (pilot full snapshot):

```python
# src/bronze/pg_snapshot.py
from pyspark.sql import functions as F

TABLES = ["catalog.product", "catalog.product_packaging", "org.store", "org.warehouse",
          "pos.sales_order", "pos.sales_order_line", "pos.sales_observation",
          "procurement.purchase_order_line", "procurement.goods_receipt_line",
          "inventory.batch_lot", "inventory.inventory_balance", "inventory.inventory_movement",
          "inventory.stock_transfer", "inventory.stock_transfer_line"]  # + các bảng còn lại

run_id = dbutils.widgets.get("run_id")
opts = dict(host=dbutils.secrets.get("pf-neon", "host"), port="5432",
            database="pharmaflow_source_postgre_v2",
            user=dbutils.secrets.get("pf-neon", "user"),
            password=dbutils.secrets.get("pf-neon", "password"),
            sslmode="require")

for t in TABLES:
    df = (spark.read.format("postgresql").options(**opts).option("dbtable", t).load())
    biz_cols = df.columns
    (df.withColumn("_ingest_run_id", F.lit(run_id))
       .withColumn("_ingested_at", F.current_timestamp())
       .withColumn("_ingest_date", F.current_date())
       .withColumn("_source_system", F.lit("neon:pharmaflow_source_postgre_v2"))
       .withColumn("_source_object", F.lit(t))
       .withColumn("_snapshot_mode", F.lit("FULL"))
       .withColumn("_row_hash", F.sha2(F.to_json(F.struct(*biz_cols)), 256))
       .write.mode("append").partitionBy("_ingest_date")
       .saveAsTable(f"pharmaflow_dev.bronze_pg.{t.replace('.', '__')}"))
```

Bảng lớn (`sales_order_line`, ~715k dòng) thêm `partitionColumn`/`numPartitions`. Ghi số dòng từng bảng vào `ops.ingest_log` để so với `final-verification.json`.

### Bước 4 — Nối MongoDB

- **Cách A (khuyến nghị khi có cluster classic):** cài Maven `org.mongodb.spark:mongo-spark-connector_2.12:10.x` vào job cluster; URI trong secret scope `pf-mongo`. Đọc với pipeline filter `{"provenance.captured_at": {"$gt": <watermark>}}`, lưu toàn document thành `raw_doc`.
- **Cách B (serverless, không cần connector):** chạy `product_knowledge_cli.py prepare` như hiện tại, upload `documents.ejsonl` + `manifest.json` lên `bronze_mongo.landing/<run_id>/`. Auto Loader đọc, kiểm SHA-256 với manifest trước khi ghi Bronze.

### Bước 4b — Dữ liệu MD-03 / MD-04 (theo issue #7, #8)

Việc này làm **ở nguồn**, trước Databricks:

1. Loader CSV sim → PostgreSQL nguồn: kho tổng + 3 kho vùng + kho cho 48 nhà thuốc TP.HCM (`org.warehouse`); gắn 42 SKU sim vào `catalog.product_source_reference`; tồn đầu kỳ (`inventory.batch_lot`, `inventory_balance` từ `inventory_lots_t0.csv`); nhu cầu TP.HCM 24 tháng (`pos.sales_observation`, `source = SIMULATED_MD04_DEMAND`); phiếu điều chuyển lịch sử (`inventory.stock_transfer*`, `inventory_movement`) có mã phiếu; lô bị giữ, recall.
2. Bộ sinh MD-03: NCC, chứng nhận, bảng giá, PO, xác nhận PO, nhận hàng, 12–24 tháng. Mỗi NCC có tham số ẩn (xác suất trễ, tỷ lệ giao đủ, tỷ lệ lô bị giữ); lưu tham số này vào `ops.sim_ground_truth` để Gold kiểm scorecard.
3. Mọi dòng sim: `data_origin = 'SYNTHETIC'` hoặc `source` bắt đầu bằng `SIMULATED_`.
4. Sau khi schema nguồn thêm `supplier_certificate`, `supplier_product_price`, `po_confirmation`, `location_heartbeat`: thêm chúng vào danh sách `TABLES` của `pg_snapshot.py` và vào `ops.source_contract`.

Phía Databricks: upload `travel_matrix.csv`, `service_profiles.csv` vào `bronze_sim.landing/<version>/`, đọc bằng Auto Loader `csv` (header, schema cố định), ghi `bronze_sim.travel_matrix`, `bronze_sim.service_profiles`.

### Bước 5 — Auto Loader weather

Ba stream, mỗi stream một loại file. Silver chỉ lấy file mà `accepted.json` trỏ tới.

```python
# src/bronze/weather_autoloader.py
base = "/Volumes/pharmaflow_dev/bronze_weather/weather_raw"
ckpt = "/Volumes/pharmaflow_dev/ops/checkpoints/weather"

def load(glob, fmt, table, extra=None):
    r = (spark.readStream.format("cloudFiles")
         .option("cloudFiles.format", fmt)
         .option("cloudFiles.schemaLocation", f"{ckpt}/{table}/schema")
         .option("pathGlobFilter", glob)
         .option("recursiveFileLookup", "true"))
    for k, v in (extra or {}).items():
        r = r.option(k, v)
    (r.load(base)
      .selectExpr("*", "_metadata.file_path AS _source_object", "current_timestamp() AS _ingested_at")
      .writeStream.option("checkpointLocation", f"{ckpt}/{table}/cp")
      .trigger(availableNow=True)
      .toTable(f"pharmaflow_dev.bronze_weather.{table}"))

load("accepted.json", "json", "weather_accepted", {"multiLine": "true"})
load("metadata.json", "json", "weather_metadata", {"multiLine": "true"})
load("response.json", "text", "weather_response", {"wholetext": "true"})
```

Silver `weather_snapshot` = `weather_accepted` JOIN `weather_metadata` (theo `metadata_key`) JOIN `weather_response` (theo `response_key`), lọc `sha2(value,256) = raw_sha256`.

### Bước 6 — Silver và Gold bằng Lakeflow Declarative Pipelines

- Pipeline `pf_silver`: đọc Bronze, ghi các schema `silver_*`. Dùng `MATERIALIZED VIEW` cho bảng snapshot (PG full), `STREAMING TABLE` cho weather/mongo (append).
- Dim SCD2: `AUTO CDC ... STORED AS SCD TYPE 2` (tên cũ `APPLY CHANGES`) với key `product_id`, sequence `_ingested_at`.
- Pipeline `pf_gold`: materialized views theo module. Chỉ build module có readiness `READY` trong `ops.module_readiness`.
- Expectations theo mục 6 của tài liệu 02. Kết quả đọc từ event log của pipeline, ghi `ops.dq_result`.

### Bước 7 — ML

1. `train_sales.py`: đọc `ml.trainset_sales_<v>`, chạy baseline (naive, seasonal-naive, moving average) trước, rồi model (ví dụ LightGBM/ETS). Temporal backtest rolling-origin.
2. Log MLflow: params, metrics, `feature_cutoff_at`, `source_snapshot_ids`.
3. Đăng ký model `pharmaflow_dev.ml.sales_forecast`; alias `champion` chỉ gán sau khi Data Admin duyệt (FR-SD-05).
4. `score_sales.py` hằng ngày dùng alias `champion`, ghi `ml.forecast_sales`.
5. `decision_eval` chạy simulation chính sách tồn kho trên forecast, ghi riêng metric quyết định.

### Bước 8 — Job điều phối

```yaml
# src/pipeline/databricks/resources/jobs.yml (trích)
resources:
  jobs:
    pf_daily:
      name: pf_daily
      schedule:
        quartz_cron_expression: "0 30 6 * * ?"
        timezone_id: Asia/Ho_Chi_Minh
      max_concurrent_runs: 1
      email_notifications:
        on_failure: [${var.alert_email}]
      tasks:
        - task_key: preflight
          notebook_task: { notebook_path: ../src/ops/preflight.py }
        - task_key: bronze_pg
          depends_on: [{ task_key: preflight }]
          notebook_task: { notebook_path: ../src/bronze/pg_snapshot.py, base_parameters: { run_id: "{{job.run_id}}" } }
        - task_key: bronze_mongo
          depends_on: [{ task_key: preflight }]
          notebook_task: { notebook_path: ../src/bronze/mongo_snapshots.py }
        - task_key: bronze_weather
          depends_on: [{ task_key: preflight }]
          notebook_task: { notebook_path: ../src/bronze/weather_autoloader.py }
        - task_key: silver
          depends_on: [{ task_key: bronze_pg }, { task_key: bronze_mongo }, { task_key: bronze_weather }]
          pipeline_task: { pipeline_id: ${resources.pipelines.pf_silver.id} }
        - task_key: readiness
          depends_on: [{ task_key: silver }]
          notebook_task: { notebook_path: ../src/ops/readiness.py }
        - task_key: gold
          depends_on: [{ task_key: readiness }]
          pipeline_task: { pipeline_id: ${resources.pipelines.pf_gold.id} }
        - task_key: score_forecast
          depends_on: [{ task_key: gold }]
          notebook_task: { notebook_path: ../src/ml/score_sales.py }
        - task_key: publish
          depends_on: [{ task_key: score_forecast }]
          notebook_task: { notebook_path: ../src/ops/publish.py }
```

Job khác:

| Job | Kích hoạt | Việc |
|---|---|---|
| `pf_weather_backfill` | Thủ công / file arrival trên `historical_*` | Bronze + Silver weather cho dải ngày cũ |
| `pf_weekly_retrain` | CN 22:00 | trainset → train → backtest → chờ duyệt |
| `pf_full_rebuild` | Thủ công | Dựng lại Silver/Gold từ Bronze (full refresh) |

Deploy: `databricks bundle validate -t dev` → `databricks bundle deploy -t dev` → `databricks bundle run pf_daily -t dev`.

### Bước 9 — Phục vụ ứng dụng

- Backend dùng service principal `pf_app_reader`, gọi SQL Warehouse (JDBC/ODBC hoặc SQL Statement Execution API). Chỉ đọc `gold_*`, `ml.forecast_sales`.
- App đọc `ops.product_release` để biết bản mới nhất và hiển thị `as_of_date`.
- Quyết định, duyệt, audit, điều chỉnh forecast ghi vào **app DB**, không ghi vào Gold.
- Khi app DB có, nạp nó vào `bronze_app` (read-only) để đo outcome.

## 4. Preflight và readiness

`ops/preflight.py` kiểm:

1. Kết nối Neon bằng `dbx_reader`, `current_database() = pharmaflow_source_postgre_v2`, session read-only.
2. Đếm 35 bảng + `GROUP BY source/data_origin`; ghi `ops.source_profile`.
3. Mongo ping + đếm `product_snapshots`.
4. List được prefix `raw/open_meteo/daily_forecast/ingest_date=<hôm nay>/`.

`ops/readiness.py` gán `ops.module_readiness`:

| Module | READY khi | Hiện trạng 13/11 |
|---|---|---|
| MD-01 | `pos.sales_order_line` > 0, `catalog.product` > 0 | READY (ID/EU/Serbia); TP.HCM chờ nhu cầu sim 24 tháng |
| MD-02 | `inventory.inventory_balance` > 0 và `batch_lot` > 0 | Chưa: 0 dòng |
| MD-03 | `procurement.purchase_order_line`, `goods_receipt_line`, `supplier` > 0; có `supplier_product_price` và `supplier_certificate` | Chưa: 0 dòng, 3 bảng chưa có |
| MD-04a | `inventory.stock_transfer_line` > 0, `org.warehouse` có `CENTRAL` | Chưa: 0 dòng, chưa có kho tổng |
| MD-04b | `silver_logistics.fact_trip_stop` có mã phiếu; `ref_travel_matrix` > 0 | Chưa: sim có CSV nhưng chưa nạp, thiếu mã phiếu |
| MD-05 | `tender_supply_input` và `tender_sku_reference` có dữ liệu (phụ thuộc MD-02, MD-03) | Chưa: tồn và mua hàng còn 0 dòng |

## 5. Chạy lại và sự cố

| Tình huống | Cách xử lý |
|---|---|
| Bảng nguồn còn rỗng | `readiness` đặt module `NOT_READY`; Gold module đó không build, app hiện "chưa có dữ liệu" |
| Task Bronze fail | Job retry 2 lần; chạy lại từ task fail ("Repair run"). PG append theo `run_id` mới; Silver lấy run mới nhất |
| Weather chưa xong lúc 06:30 | Auto Loader `availableNow` lấy file đã có; lần chạy sau tự lấy phần còn lại. Feature dùng snapshot mới nhất có `retrieved_at <= origin` |
| Silver DQ FAIL | Gold không chạy; app giữ bản publish cũ; xem `ops.dq_result` |
| Cần sửa logic Silver | Sửa code → deploy bundle → full refresh pipeline `pf_silver` (Bronze còn nguyên) |
| Schema nguồn đổi | Auto Loader ghi `_rescued_data`; PG snapshot so cột với `ops.source_contract`, khác → dừng |
| Sai dữ liệu đã publish | Delta `RESTORE TABLE ... TO VERSION AS OF <v>`; ghi `ops.product_release` lùi bản |

## 6. Bảo mật

| Điểm | Quy định |
|---|---|
| Secret | Chỉ trong secret scope / UC connection. Không để trong notebook, log, bundle |
| Nguồn | Role đọc riêng cho Databricks ở Neon, Mongo, S3 |
| S3 | Storage credential chỉ đọc; không cấp `DeleteObject` |
| Quyền UC | Theo group; app chỉ SELECT gold; quyền theo user / scope của MD-06 kiểm ở backend, không đưa tài khoản người dùng vào UC |
| Row filter | `gold_*` theo `location_key` cho Quản lý nhà thuốc/kho vùng (FR-MD04-36, 38) |
| Audit | `system.access.audit` + lineage UC |
| Ghi nguồn | Mọi màn hình weather ghi "Weather data by Open-Meteo.com (CC BY 4.0)" |

## 7. Lộ trình triển khai

| Giai đoạn | Phạm vi | Xong khi |
|---|---|---|
| P0 | Workspace, UC, group, secret, storage credential | Preflight xanh |
| P1 | Bronze 3 nguồn | Số dòng Bronze = nguồn; sha256 weather khớp |
| P2 | Silver core + sales + weather | DQ đạt; reconcile sales với `final-verification.json` |
| P3 | Gold MD-01 + forecast baseline + backtest | Dashboard MD-01 đọc được qua SQL Warehouse |
| P4 | Loader sim vào nguồn; Silver/Gold MD-02, MD-03, MD-04a, MD-04b | Readiness READY, DQ đạt, đủ kịch bản kiểm thử của issue #7 |
| P5 | `bronze_app` + `silver_decision`; decision eval, outcome loop | KPI tỷ lệ chấp nhận đề xuất có số; `ml.decision_eval` có ít nhất GP0 vs 1 policy |
| P6 | Gold MD-05 (`tender_supply_input` …) cho app; đọc lại tender từ `bronze_app` | App MD-05 chạy đủ 4 ca kiểm thử; cam kết tender không bị trừ lặp |

## 8. Checklist nghiệm thu pilot

- [ ] `bronze_pg.*` có 35 bảng, số dòng khớp nguồn tại cùng run.
- [ ] `bronze_mongo.product_snapshots` = 2.481 snapshot (run `lc-longchau-full-20261105-02`) hoặc số mới hơn đã verify.
- [ ] `bronze_weather.weather_accepted` = số `accepted.json` trên S3; 0 sha256 lệch.
- [ ] `silver_sales.fact_sales_line` không có dòng thiếu `provenance_class`.
- [ ] `fact_sales_observation` và `fact_sales_line` không bị cộng chung ở bất kỳ Gold nào.
- [ ] `mart_sales_daily` tổng qty = Silver theo từng `source_code`.
- [ ] Backtest có baseline và model, ghi MAE/RMSE/WAPE/Bias riêng từng fold.
- [ ] Không feature nào dùng weather có `retrieved_at_utc > forecast_origin` trong đánh giá as-of.
- [ ] Service principal app không SELECT được bronze/silver.
- [ ] `mart_po_tracking` có 4 cột lượng riêng (đặt, xác nhận, nhận, đạt QC).
- [ ] `net_purchase_need_input` không trừ phần dư đã giữ chỗ cho điều chuyển.
- [ ] `transfer_candidate_input` không chứa lô bị giữ / thu hồi / hết hạn tại ETA, và không có điểm có heartbeat quá ngưỡng.
- [ ] Scorecard NCC tính lại khớp `ops.sim_ground_truth` trong ngưỡng.
- [ ] Mọi `fact_trip_stop` nối được `fact_transfer_order` qua mã phiếu.
- [ ] Tên SKU và tên điểm trên dashboard lấy từ `dim_product` / `dim_location`.

# PharmaFlow Databricks Lakehouse & ML Pipeline

Phân hệ xử lý dữ liệu tập trung, chuyển đổi Medallion (Bronze – Silver – Gold) cho **PharmaFlow DSS**, được đóng gói theo chuẩn **Databricks Asset Bundles (DABs)** và vận hành trên **Databricks Free Edition** (Serverless) cho môi trường `dev`.

> [!NOTE]
> **Trạng thái hiện tại:** `HYBRID PHASE 1 GOLD MD-01 & WEATHER HISTORICAL COMPLETE (17/11/2026)`
> - **Đã triển khai & kiểm chứng live trên Databricks Free Edition (`pharmaflow_dev`):**
>   - **Bronze PG (Spark JDBC `REPEATABLE READ` + Volume fallback):** [pg_snapshot.py](src/bronze/pg_snapshot.py), [sync_neon_to_volume.py](src/bronze/sync_neon_to_volume.py) — nạp & đối soát 100% cả 12 bảng Neon có dữ liệu (`pos.sales_order_line`: `714.959`, `pos.sales_order`: `393.942`, `pos.sales_observation`: `78.884`, `org.store`: `2.816`, `catalog.product`: `5.674`, v.v.) vào `bronze_pg.latest_*` và `ops.ingest_log`.
>   - **Bronze MongoDB:** [sync_mongo_to_volume.py](src/bronze/sync_mongo_to_volume.py), [mongo_snapshots.py](src/bronze/mongo_snapshots.py) — đối soát SHA-256 & unwrap Extended JSON cho `2.481` Long Châu snapshots từ `lc-longchau-full-20261105-02` vào `bronze_mongo.latest_product_snapshots`.
>   - **Bronze & Silver Weather (Daily + 6.590 task Historical Backfill):** [aws_volume_sync_lambda.py](src/bronze/aws_volume_sync_lambda.py), [sync_s3_to_volume.py](src/bronze/sync_s3_to_volume.py), [weather_autoloader.py](src/bronze/weather_autoloader.py), [silver/weather.sql](src/silver/weather.sql) — đồng bộ `19.902` file S3 → Managed Volume (`0` lỗi) và tạo `silver_weather.weather_daily_metrics` (`92.415` dòng `HISTORICAL_FORECAST_STITCHED` cho `121` cửa hàng + `2.196` dòng `HISTORICAL_ERA5_REANALYSIS` cho Serbia + `624` dòng `FORECAST` daily).
>   - **Silver Core & Silver Sales:** [silver/core.sql](src/silver/core.sql) (`9` bảng dimension/bridge/xref/knowledge, `2.480/2.480` `dim_product_knowledge` map được `product_id`, `2.816` `dim_location`), [silver/sales.sql](src/silver/sales.sql) (`fact_sales_line` `714.959` quy đổi `local_date` theo múi giờ từng cửa hàng và tách riêng `fact_sales_observation` `78.884`, giữ `base_qty = NULL` khi thiếu hệ số quy đổi).
>   - **Gold MD-01 & Atomic Release:** [gold/md01_sales.sql](src/gold/md01_sales.sql), [ops/publish_md01.py](src/ops/publish_md01.py) — `mart_sales_daily` (`474.591` dòng), `mart_sales_observation_period` (`78.884`), `kpi_sales_trend` (`345.664`), `mart_sales_weather_daily` (`474.591` dòng đạt `100%` độ phủ Weather trên `387.021` dòng store `5389`, `62.036` ONYX, `25.534` Serbia), công bố release `ACTIVE` tại `ops.product_release` (`md01-413415570405548`).
> - **Bước tiếp theo (ngoài phạm vi Phase 1 Gold):** **Colab / Local ([src/forecasting/](../../forecasting/))** đọc từ `gold_md01_sales.*` để Data Audit, Calendar Densification và ML Training/Backtesting (ưu tiên `store_id = 5389`), log MLflow về Databricks và ghi dự báo ngược lại `ml.*`.

---

## 📖 Tài liệu thiết kế & Căn cứ kỹ thuật
* **Tài liệu đặc tả thiết kế chi tiết (SDD v1.4):** Xem file [SDD.md](SDD.md).
* **Báo cáo audit độc lập:** Xem [REVIEW.md](../../../artifacts/reviews/2026-11-16-pipeline-sdd/REVIEW.md).
* **Thiết kế Medallion Lakehouse gốc:** Xem [jobs/W9.11/MDD_vKiro/02-thiet-ke-medallion.md](../../../jobs/W9.11/MDD_vKiro/02-thiet-ke-medallion.md).
* **Quy trình kỹ thuật Databricks:** Xem [jobs/W9.11/MDD_vKiro/04-quy-trinh-ky-thuat-databricks.md](../../../jobs/W9.11/MDD_vKiro/04-quy-trinh-ky-thuat-databricks.md).
* **Vòng lặp khép kín với AppDB:** Xem [jobs/W9.11/DBD/01-kien-truc-va-quanhe-databricks.md](../../../jobs/W9.11/DBD/01-kien-truc-va-quanhe-databricks.md).

---

## 🏗 Cấu trúc mã nguồn

```text
src/pipeline/databricks/
├── databricks.yml                      # Asset Bundle (targets: dev Free Edition, prod AWS)
├── SDD.md                              # Software Design Document chi tiết v1.4
├── README.md                           # Tài liệu hướng dẫn này
│
├── resources/                          # Khai báo Workflows & DLT Pipelines (IaC Serverless)
│   ├── jobs.yml                        # Active Serverless jobs (pf_weather_sync, pf_weather_backfill, pf_md01_pipeline)
│   ├── pipelines.yml                   # Active Declarative Pipelines (pf_silver_weather, pf_silver_core, pf_silver_sales, pf_gold_md01)
│   └── planned/                        # Các job/pipeline mở rộng cho Phase 2–3 toàn nền tảng
│       ├── jobs.yml
│       └── pipelines.yml
│
├── src/                                # Mã nguồn logic thực thi
│   ├── common/
│   │   └── workspace.py                # Shared Databricks host sanitizer & Volume helper cho local sync CLIs
│   ├── bronze/
│   │   ├── aws_volume_sync_lambda.py   # AWS Lambda đồng bộ daily S3 -> Volume
│   │   ├── sync_s3_to_volume.py        # CLI local đồng bộ S3 -> Volume với checkpoint
│   │   ├── sync_mongo_to_volume.py     # CLI local kiểm chứng SHA-256 & upload MongoDB EJSONL bundle -> Volume
│   │   ├── sync_neon_to_volume.py      # CLI fallback REPEATABLE READ xuất .jsonl.gz -> Volume
│   │   ├── pg_snapshot.py              # Notebook/CLI Spark JDBC + Volume fallback ingestion 12 bảng Neon
│   │   ├── mongo_snapshots.py          # Notebook/CLI unwrap Extended JSON & nạp bronze_mongo.latest_product_snapshots
│   │   └── weather_autoloader.py       # Notebook/CLI Auto Loader đọc accepted.json + check SHA-256
│   ├── silver/
│   │   ├── weather.sql                 # DLT SQL chuẩn hóa UTC/local_date, store_grid_mapping, weather_daily_metrics
│   │   ├── core.sql                    # DLT SQL 9 bảng dim/bridge/xref/knowledge trong silver_core
│   │   └── sales.sql                   # DLT SQL tách biệt fact_sales_line và fact_sales_observation trong silver_sales
│   ├── gold/
│   │   └── md01_sales.sql              # DLT SQL mart_sales_daily, mart_sales_observation_period, kpi_sales_trend, mart_sales_weather_daily
│   ├── ml/                             # Hợp đồng bảng ml.* (nhận kết quả từ Hybrid Colab/Local)
│   └── ops/
│       └── publish_md01.py             # Đối soát Silver -> Gold và công bố release ACTIVE tại ops.product_release
│
└── tests/
    ├── test_aws_volume_sync_lambda.py  # Unit tests AWS Lambda Volume sync
    ├── test_pg_and_mongo_bronze.py     # Unit tests PG/Mongo Bronze ingestion, Extended JSON unwrap & Volume sync
    ├── test_publish_md01.py            # Unit tests đối soát Silver -> Gold MD-01
    ├── test_volume_sync.py             # Unit tests đồng bộ S3 -> Volume & periodic checkpoint
    └── test_weather_autoloader.py      # Unit tests offline Bronze Weather
```

---

## 🚀 Thao tác nhanh

### 1. Đồng bộ Weather S3 & MongoDB → Databricks Managed Volume (từ máy local)
```powershell
# Kiểm tra dry-run các file Weather chưa sync
.\.venv\Scripts\python.exe src\pipeline\databricks\src\bronze\sync_s3_to_volume.py --mode daily --dry-run

# Đồng bộ daily (hoặc --mode historical cho 6.590 task backfill)
.\.venv\Scripts\python.exe src\pipeline\databricks\src\bronze\sync_s3_to_volume.py --mode daily

# Đồng bộ MongoDB snapshot bundle mới nhất (vd: lc-longchau-full-20261105-02)
.\.venv\Scripts\python.exe src\pipeline\databricks\src\bronze\sync_mongo_to_volume.py --run-id lc-longchau-full-20261105-02
```

### 2. Chạy unit tests offline (từ root repo — chạy riêng 2 suite để tránh trùng namespace `tests`/`src`)
```powershell
.\.venv\Scripts\python.exe -B -m pytest src\pipeline\databricks\tests -v -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest tests\weather -v -p no:cacheprovider
```

### 3. Validate, Deploy & Run với Databricks CLI
```bash
cd src/pipeline/databricks
databricks bundle validate -t dev
databricks bundle deploy -t dev
databricks bundle run pf_md01_pipeline -t dev
databricks bundle run pf_weather_sync -t dev
```

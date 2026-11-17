# AWS Quick BI Serving Bridge (`src/sync_quick/`)

> [!NOTE]
> **BI SERVING LAYER — GOLD MD-01 TO NEON BI MIRROR & AWS QUICK**  
> Phân hệ đồng bộ lát cắt Gold Sales & Weather (`gold_md01_sales.*`) từ Databricks Lakehouse sang Neon PostgreSQL BI Mirror (`landing_datamart_md01`) và tạo sẵn các Analytical Views để **Amazon QuickSight (AWS Quick)** / **Power BI** kết nối trực tiếp qua PostgreSQL SSL connector.

---

## 1. Trạng thái triển khai & Kiểm chứng (17/11/2026)

| Hạng mục | Trạng thái | Chi tiết kiểm chứng thực tế |
|---|---|---|
| **Databricks ↔ AWS Quick trực tiếp** | `BLOCKED (Upstream Connector)` | AWS Quick (`us-east-1`, `SWOVN-QUICK`) dùng OSS Databricks JDBC driver (`databricks331`), chế độ `Password` gửi thiếu credential (`401 Credential was not sent...`), chế độ `3LO` không dùng được vì Databricks Free Edition trả `404` ở `/api/2.0/accounts/oauth2/custom-app-integrations`. |
| **Neon #2 (`landing_datamart_md01`)** | `VERIFIED LIVE` | Project Free riêng (`PostgreSQL 18.7`, `aws-ap-southeast-1`, DB `neondb`), tổng dung lượng sau sync là **`449 MB / 1024 MB`**. Credentials lưu riêng tại `QUICK_NEON_DATABASE_URL` trong `.env`. |
| **Cloud Auto-Sync Job** | `VERIFIED LIVE (Automated)` | Job độc lập **`[aux] quick_gold_md01_sync`** (`job_id`: `216553820375680`, trigger `table_update` trạng thái `UNPAUSED` theo `pharmaflow_dev.ops.product_release`, secret scope riêng `quick-sync-aux`). Lượt chạy ép (`run_id`: `705934393249663`) đạt **`TERMINATED / SUCCESS`** (`sync_mode = databricks_jdbc`). |
| **3 BI Helper Views (`0 MB` thêm)** | `VERIFIED LIVE` | Đã tạo `bi_sales_weather_enriched` (`474.591`), `bi_weather_impact_summary` (`1.172`), `bi_atc_category_monthly` (`560`) cùng `VIEW mart_sales_daily` (`474.591`). |
| **AWS Quick Datasets** | `VERIFIED CONNECTED` | Connector **PostgreSQL (`Public network`, SSL enabled, port `5432`)** validate xanh và đã nạp 4 Datasets (`bi_sales_weather_enriched`, `bi_weather_impact_summary`, `kpi_sales_trend`, `bi_atc_category_monthly`) vào **SPICE**. |
| **Offline Unit Tests** | `6/6 PASSED` | `pytest src/sync_quick/test_sync_quick.py` (`0.04s`). |

---

## 2. Kiến trúc đường phụ (`$0/tháng`)

```text
Databricks Free Edition (pharmaflow_dev.gold_md01_sales.* + ops.product_release)
   │
   ├─ Tự động khi ops.product_release cập nhật:
   │    Job [aux] quick_gold_md01_sync (216553820375680)
   │    Serverless Spark format("postgresql") + fallback psycopg COPY
   └─ Hoặc chạy tay local:
        Statement Execution API (CSV EXTERNAL_LINKS, NULL 'null') -> psycopg COPY
   ▼
Neon Project #2: landing_datamart_md01 (neondb, schema quick_gold_md01, 449 MB)
   │  Atomic staging swap (_stg_* -> live) + VIEW mart_sales_daily + 3 BI views
   ▼
AWS Quick (PostgreSQL connector, Public network, SSL, SPICE / Direct Query)
```

### Lưu ý kỹ thuật đã xử lý trong code
- **Databricks Serverless Write:** Serverless compute chặn `.format("jdbc")` (`UNSUPPORTED_DATA_SOURCE_WRITE`), nên `sync_databricks` dùng `.format("postgresql")` (kèm fallback `psycopg COPY` qua `toLocalIterator()`).
- **Notebook Exit:** Databricks `notebook_task` báo lỗi nếu gọi `raise SystemExit(0)`, nên script chỉ raise `SystemExit` khi exit code `!= 0`.
- **Pooler & Statement API CSV:** Đặt `prepareThreshold=0` / `prepare_threshold=None` để tương thích endpoint `-pooler` của Neon; dùng `NULL 'null'` khi `COPY` CSV từ Databricks Statement Execution `EXTERNAL_LINKS`.

---

## 3. Danh sách đối tượng trong schema `quick_gold_md01` (Neon #2)

| Tên bảng / view | Loại | Số dòng | Mục đích trên AWS Quick |
|---|---|---:|---|
| `mart_sales_weather_daily` | `BASE TABLE` | 474.591 | Bảng Gold daily đã gắn 1:1 thời tiết ngày (62 cột) |
| `mart_sales_daily` | `VIEW` | 474.591 | 29 cột Gold daily gốc đọc qua `mart_sales_weather_daily` (`0` byte trùng lặp) |
| `kpi_sales_trend` | `BASE TABLE` | 345.664 | Tổng hợp `WEEK`/`MONTH` kèm `prev_period_sold_qty` & `sold_qty_pct_change` |
| `mart_sales_observation_period` | `BASE TABLE` | 78.884 | Chuỗi quan sát theo kỳ (8 nhóm ATC Serbia `OBSERVED` + ONYX `UNVERIFIED`) |
| `sync_release_state` | `BASE TABLE` | 1 | Watermark `release_id` (`md01-413415570405548`) chống sync thừa |
| `bi_sales_weather_enriched` | `VIEW` | 474.591 | Bổ sung `dataset_track`, `clean_uom`, `year_month`, `day_of_week`, `is_weekend`, `temp_band`, `rain_regime`, `humidity_band`, `avg_unit_price`, `margin_pct`, `promo_share_pct` |
| `bi_weather_impact_summary` | `VIEW` | 1.172 | Tổng hợp sẵn theo thời tiết × track × cuối tuần (nhẹ cho Direct Query / Quick Chat) |
| `bi_atc_category_monthly` | `VIEW` | 560 | Chuỗi tháng của 8 nhóm thuốc ATC Serbia (`2014–2019`) |

---

## 4. Vận hành & Lệnh nhanh

```powershell
# Kiểm tra unit tests
.\.venv\Scripts\python.exe -B -m pytest src\sync_quick\test_sync_quick.py -v -p no:cacheprovider

# Kiểm tra trạng thái release (không ghi dữ liệu)
.\.venv\Scripts\python.exe src\sync_quick\sync_gold_to_neon.py --mode local --dry-run

# Sync tay từ máy local (thêm --force nếu muốn ép ghi đè dù release_id chưa đổi)
.\.venv\Scripts\python.exe src\sync_quick\sync_gold_to_neon.py --mode local

# Cập nhật script & secret lên Databricks job phụ [aux] quick_gold_md01_sync
.\.venv\Scripts\python.exe src\sync_quick\setup_databricks_aux_sync.py --trigger table
```

---

## 5. Kết nối AWS Quick & Prompts tạo nhanh Dashboard

### Kết nối Data Source (`PostgreSQL`)
- **Connection type:** `Public network` | **Port:** `5432` | **SSL:** `Enabled`
- **Database server / Database name / Username / Password:** lấy từ `QUICK_NEON_DATABASE_URL` trong `.env`.
- **Chế độ:** `Direct query` tự thấy số mới ngay khi Gold sync xong; `SPICE` mượt hơn và tiết kiệm Neon CU-hours (cần bật lịch refresh hoặc bấm *Refresh now* sau khi Gold cập nhật).

### Prompts gợi ý cho nút `✨ Generate` (tạo từng Sheet trong Analysis)
- **Sheet 1 (`bi_sales_weather_enriched` — Tổng quan 1 nhà thuốc Indonesia `5389`):**
  `Create an executive sales monitoring sheet filtered to dataset_track = 'IRPD_ID_OBSERVED' and store_id = 5389 and clean_uom = 'tab'. Include filter controls at the top for clean_uom, year_month, and brand_name. Add KPI cards for total sold_qty, total line_amount, distinct product_id count, and distinct active local_date count. Add a monthly line chart of sum of sold_qty over year_month with forecast enabled, a horizontal bar chart of top 15 product_name by sum of sold_qty, a bar chart of top 10 manufacturer_name by sum of sold_qty, and a detail pivot table by product_name and clean_uom showing sum of sold_qty, sum of line_amount, and average avg_unit_price.`
- **Sheet 2 (`bi_sales_weather_enriched` — Đa yếu tố Thời tiết × Lịch tại `5389`):**
  `Create a multi-factor weather and calendar impact sheet filtered to dataset_track = 'IRPD_ID_OBSERVED' and store_id = 5389 and clean_uom = 'tab'. Add top filter controls for clean_uom, product_name, rain_regime, and temp_band. Show a heatmap with temp_band on rows, rain_regime on columns, and average sold_qty as values. Add a clustered bar chart comparing average sold_qty across rain_regime grouped by is_weekend, a bar chart of sum of sold_qty by day_of_week sorted by day_of_week_num, a bar chart of average sold_qty by humidity_band, and a scatter plot of average temp_mean on x-axis vs average sold_qty on y-axis colored by rain_regime with size by average precip_sum.`
- **Sheet 3 (`bi_sales_weather_enriched` — Đa cửa hàng EU, Khuyến mãi & Biên lợi nhuận):**
  `Create a multi-store commercial and promotion analysis sheet filtered to dataset_track = 'ONYX_EU_SYNTHETIC'. Add top filter controls for country_code, store_name, has_promotion, and year_month. Add KPI cards for total sold_qty, total line_amount, total margin_amount, and average margin_pct. Include a filled map or bar chart of total line_amount and total margin_amount by country_code, a comparison bar chart of average sold_qty and average margin_pct grouped by has_promotion, a bar chart of top 10 store_name by total line_amount, and a monthly trend line chart of total line_amount by country_code over year_month.`
- **Sheet 4 (`bi_atc_category_monthly` — Mùa vụ 8 nhóm thuốc ATC):**
  `Create an ATC therapeutic category seasonality sheet using bi_atc_category_monthly. Add filter controls for year_num and category_name. Include a stacked area chart of sum of total_observed_qty over year_month colored by category_name, a heatmap of category_name on rows vs month_num on columns showing average avg_daily_qty, and a horizontal bar chart ranking category_name by total_observed_qty.`

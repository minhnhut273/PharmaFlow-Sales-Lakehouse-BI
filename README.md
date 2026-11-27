<div align="center">

# 💊 PharmaFlow — Sales & Weather Data Lakehouse (BI Pipeline)

**End-to-End Pharmaceutical Retail Sales & Weather Data Engineering Platform for Business Intelligence**

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Databricks](https://img.shields.io/badge/Databricks-Lakehouse%20%7C%20DABs-FF3621?style=for-the-badge&logo=databricks&logoColor=white)](https://www.databricks.com/)
[![PostgreSQL](https://img.shields.io/badge/Neon-PostgreSQL%2018-00E599?style=for-the-badge&logo=postgresql&logoColor=0F172A)](https://neon.tech/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![AWS](https://img.shields.io/badge/AWS-S3%20%7C%20Lambda%20%7C%20EventBridge-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)](https://aws.amazon.com/)
[![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC?style=for-the-badge&logo=terraform&logoColor=white)](https://www.terraform.io/)
[![AWS QuickSight](https://img.shields.io/badge/BI-AWS%20Quick%20%26%20Power%20BI-8C4FFF?style=for-the-badge&logo=amazon&logoColor=white)](#-bi-serving--analytics-layer-aws-quick--power-bi)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Streamlit%20Cloud-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://pharmaflow-sales-lakehouse-bi-ut7zhiigkcrzqwvz93krzy.streamlit.app/)
[![ML Forecasting](https://img.shields.io/badge/ML%20Forecasting-LightGBM%20%7C%20CQR%20%7C%20SHAP-10B981?style=for-the-badge&logo=scikitlearn&logoColor=white)](#6-chạy-pipeline-ml-dự-báo-nhu-cầu-5-notebooks--1-luồng-thống-nhất)
[![Google Docs](https://img.shields.io/badge/Design%20Docs-Google%20Docs%20(4%20Tabs)-4285F4?style=for-the-badge&logo=googledocs&logoColor=white)](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit)

<p>
  <a href="#-tổng-quan-dự-án">Tổng quan</a> •
  <a href="#-kiến-trúc-hệ-thống-system-architecture">Kiến trúc</a> •
  <a href="#-quy-mô-dữ-liệu-đã-kiểm-chứng">Quy mô dữ liệu</a> •
  <a href="#-cấu-trúc-thư-mục">Cấu trúc thư mục</a> •
  <a href="#-thiết-lập-môi-trường--credentials">Credentials</a> •
  <a href="#-hướng-dẫn-vận-hành">Vận hành</a> •
  <a href="#-tài-liệu--tham-khảo">Tài liệu</a>
</p>

</div>

---

## 🎯 Tổng quan dự án

**PharmaFlow Sales & Weather Data Lakehouse** là hệ thống đường ống dữ liệu (**Data Engineering & Business Intelligence Pipeline**) hoàn chỉnh cho mảng **Phân tích Bán hàng Dược phẩm (Sales Analytics)** trên đa thị trường (Việt Nam, Indonesia, Châu Âu/Serbia).

Dự án giải quyết bài toán tích hợp dữ liệu đa nguồn có cấu trúc khác nhau (Relational POS, Document Product Catalog, External Weather Time-Series) thông qua hạ tầng đám mây **AWS Serverless** (quản lý bằng **Terraform IaC**), xử lý chuẩn hóa qua 3 phân tầng **Medallion Lakehouse (Bronze → Silver → Gold)** trên **Databricks**, và cung cấp Data Mart sẵn sàng cho **Business Intelligence (AWS QuickSight / Power BI)** với mức chi phí vận hành tối ưu (**$0/tháng** trên các tầng Free/Serverless).

### ✨ Điểm nổi bật của hệ thống
- 🔄 **Multi-Source Heterogeneous Ingestion:** Kết hợp đồng thời nguồn quan hệ **Neon PostgreSQL**, nguồn tài liệu bán cấu trúc **MongoDB Atlas** và nguồn API thời tiết **Open-Meteo (ERA5 + GFS)**.
- ☁️ **Production-Grade AWS IaC:** Toàn bộ S3 Bucket, IAM Least-Privilege Policies, DynamoDB Control State, 5 SQS Queues, 4 Lambda Functions và EventBridge Scheduler được quản lý hoàn toàn bằng **Terraform** kèm bộ test `.tftest.hcl`.
- 🧱 **Databricks Asset Bundles (DABs) & Lakeflow DLT:** Triển khai Pipeline khai báo (Declarative SQL + PySpark) với quy tắc kiểm soát chất lượng dữ liệu (*Expectations*), giữ nguyên ngữ nghĩa đơn vị tính (`UOM`), múi giờ địa phương (`local_date`), và phân tách rạch ròi nguồn gốc dữ liệu (`OBSERVED` vs `SYNTHETIC` vs `UNVERIFIED`).
- 🛡️ **Atomic Reconciliation Gate:** Chốt phát hành dữ liệu qua bảng kiểm soát `ops.product_release`, đối soát khớp 100% số lượng và doanh thu giữa tầng Silver và tầng Gold trước khi mở cho tầng BI.
- 📊 **Automated BI Serving Layer:** Đồng bộ tự động Gold Sales Marts sang **Neon BI Mirror** (`landing_datamart_md01`) kèm 3 Analytical Views tối ưu sẵn cho **AWS QuickSight (SPICE / Direct Query)** và **Power BI**.
- 🎛️ **5-Page Vietnamese Streamlit BI Dashboard:** Ứng dụng **Streamlit + Plotly** tại `src/streamlit/` (**[Live Demo](https://pharmaflow-sales-lakehouse-bi-ut7zhiigkcrzqwvz93krzy.streamlit.app/)**) gồm 4 trang BI doanh số/thời tiết/cửa hàng/ATC (**SQL aggregation pushdown** trực tiếp trên PostgreSQL `0.08–0.48s`/query) và **Trang 5 Dự Báo Nhu Cầu ML** (đọc precomputed artifacts `52W/365D`, Split CQR `P10–P90`, `TreeSHAP`, đối chuẩn Paper 2024), hỗ trợ chọn bảng màu, bản đồ Châu Âu và xuất CSV UTF-8.
- 📈 **Demand Forecasting ML & XAI Pipeline (`DATA -> FORECAST`):** Luồng thống nhất **5 Notebooks (`src/ml/01..05_*.ipynb`)** trên dữ liệu `OBSERVED` (`store_id = 5631`, 8 nhóm ATC, `302` tuần & `2,106` ngày) kết hợp **Compact 7-var Open-Meteo ERA5**, chuẩn hóa tốc độ ngày `qty_rate`, **Perturbation Leakage Unit-Test (`max_abs_diff = 0.0`)**, **`AutoRouted Champion`** (đánh bại `Seasonal Naïve` với `DM' p < 0.05` trên **`8/8` nhóm ATC** và vượt MSE của Paper Fourkiotis & Tsadiras 2024 trên **`6/8` nhóm**), hiệu chuẩn bất định **Split CQR `P10–P90`** (`78.8%` độ phủ TB) và giải thích **TreeSHAP** — chạy trọn luồng hết **`166.6 giây`** (~`1,166.9×` nhanh hơn `54h` của Paper 2024). Xem [src/ml/README.md](src/ml/README.md) và [Google Docs (4 Tab)](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit).

---

## 🏗 Kiến trúc hệ thống (System Architecture)

> 🖼️ Mở & chỉnh sửa file nguồn Draw.io trực tiếp tại: [pharmaflow-sales-bi-architecture.drawio](docs/images/pharmaflow-sales-bi-architecture.drawio) *(sơ đồ 5 phân vùng: Data Sources → AWS Cloud IaC → Databricks Medallion → BI Serving & Analytics → ML Forecasting & XAI)*

<div align="center">
  <img src="docs/images/pharmaflow-sales-bi-architecture.png" alt="PharmaFlow Sales & Weather Data Lakehouse — End-to-End BI & ML Architecture" width="100%" />
</div>

### 🔍 Diễn giải luồng dữ liệu theo 5 phân vùng

| Phân vùng | Thành phần chính | Vai trò & Cơ chế hoạt động |
| :--- | :--- | :--- |
| **1. Upstream Data Sources** | 🐘 **Neon PostgreSQL v2**<br/>🍃 **MongoDB Atlas**<br/>🌤️ **Open-Meteo API** | • **PostgreSQL (`pharmaflow_source_postgre_v2`):** Chứa 12/35 bảng Sales/Catalog/Store đang hoạt động (giao dịch bán lẻ IRPD quan sát, dữ liệu tổng hợp Onyx & Pharma Sales).<br/>• **MongoDB (`product_snapshots`):** Lưu 2.481 bản chụp tri thức dược phẩm Long Châu (thành phần, hướng dẫn bảo quản) với chỉ mục SHA-256 duy nhất.<br/>• **Open-Meteo:** Cung cấp chuỗi thời tiết lịch sử (ERA5 `< 2022`, GFS Stitched `≥ 2022`) và dự báo 16 ngày cho **880 điểm lưới** đại diện 2.816 nhà thuốc. |
| **2. AWS Cloud & Terraform IaC** | ⏰ **EventBridge**<br/>⚡ **AWS Lambda (x4)**<br/>📬 **SQS** & 🗄️ **DynamoDB**<br/>🪣 **Amazon S3**<br/>🔐 **AWS SSM** | • **06:00 VN:** EventBridge kích hoạt **Lambda Planner** đọc tọa độ từ Neon (qua `SSM SecureString`), chia cụm lưới `0.111°`, đẩy task vào **SQS**.<br/>• **Lambda Worker:** Điều phối tải từ Open-Meteo (kèm giới hạn quota ở **DynamoDB**), lưu bytes gốc vào **S3** kèm `accepted.json` và `SHA-256`.<br/>• **06:18 VN:** EventBridge kích hoạt **Lambda Volume Bridge** đồng bộ các tệp `accepted.json` mới từ S3 sang **Databricks Managed Volume** qua Files API. |
| **3. Databricks Lakehouse** | 🥉 **Bronze Layer**<br/>🥈 **Silver Layer**<br/>🥇 **Gold Layer**<br/>🛡️ **Ops Control** | • **Bronze:** `bronze_pg` (Spark JDBC `REPEATABLE READ` + Volume fallback), `bronze_mongo` (unwrap Extended JSON), `bronze_weather` (Auto Loader kiểm tra `raw_sha256`).<br/>• **Silver (DLT SQL):** `silver_core` (9 bảng Master Data), `silver_sales` (tách biệt `fact_sales_line` và `fact_sales_observation`, quy đổi `local_date`), `silver_weather` (chuẩn hóa metrics ngày).<br/>• **Gold (MD-01 Marts):** Xuất `mart_sales_daily`, `mart_sales_weather_daily` (join 1:1 thời tiết), `kpi_sales_trend`, `mart_sales_observation_period` và đóng dấu release tại `ops.product_release`. |
| **4. BI Serving & Analytics** | ⚡ **Auto-Sync Job**<br/>🐘 **Neon #2 BI Mirror**<br/>📊 **AWS Quick / Power BI**<br/>🎛️ **Streamlit BI App (5P)** | • Job `[aux] quick_gold_md01_sync` tự động lắng nghe cập nhật từ `ops.product_release`, thực hiện atomic table swap sang schema `quick_gold_md01` trên Neon #2.<br/>• Cung cấp **3 BI Helper Views** không tốn thêm dung lượng (`bi_sales_weather_enriched`, `bi_weather_impact_summary`, `bi_atc_category_monthly`) cho **4 Dashboard Sheets** trên AWS QuickSight / Power BI.<br/>• Ứng dụng **Streamlit Multipage (`src/streamlit/`, 5 trang tiếng Việt)** truy vấn SQL pushdown trực tiếp Neon #2 cho Trang 1–4 và đọc precomputed artifacts cho Trang 5 ML Forecast, hỗ trợ **7 bảng màu** tùy chọn. |
| **5. Demand Forecasting ML & XAI** | 🧠 **5 Notebooks (`src/ml/`)**<br/>🌤️ **Compact ERA5 (`F3`)**<br/>📐 **Split CQR & `TreeSHAP`**<br/>📦 **Artifacts (`artifacts/`)** | • Luồng thống nhất `01 → 05` đọc Gold (`mart_sales_observation_period` + `mart_sales_weather_daily`, `store_id = 5631`, `OBSERVED`) + lịch lễ Serbia.<br/>• Chạy `5` fold tuần × `12` mô hình (`SNaïve`, `Croston-SBA`, `Harmonic_ARIMA`, `Ridge`, `LightGBM`, `AnchorRes`, `Exp-Block OOF Hybrid`, `AutoRouted_Champion`) + `Daily 365D`, `Split CQR P10–P90` và `TreeSHAP` (`DATA -> FORECAST`, không trộn tồn kho/ROP).<br/>• Bàn giao snapshot `.parquet`, bảng đánh giá `.csv`, `model_card.json` và 7 biểu đồ 300 DPI tại `artifacts/forecasting/`. |

---

## 📊 Quy mô dữ liệu đã kiểm chứng

Toàn bộ pipeline đã được triển khai, chạy live trên **Databricks Free Edition (`pharmaflow_dev`)** và **AWS (`ap-southeast-1`)** với các chỉ số thực tế sau:

| Layer / Thành phần | Bảng / Đối tượng chính | Số lượng bản ghi / Tệp | Ghi chú kiểm chứng |
| :--- | :--- | ---: | :--- |
| **Upstream Postgres** | `pos.sales_order_line` / `pos.sales_order` | `714,959` / `393,942` | 100% đối soát khớp giữa source và `bronze_pg` |
| **Upstream Postgres** | `pos.sales_observation` | `78,884` | Chuỗi tổng hợp theo kỳ (ONYX 62,036 + ATC 16,848) |
| **Upstream Postgres** | `catalog.product` / `org.store` | `5,674` / `2,816` | Bao phủ Long Châu VN, IRPD Indonesia, ONYX EU |
| **Upstream MongoDB** | `product_snapshots` | `2,481` | 2,480/2,480 sản phẩm ánh xạ thành công sang `dim_product` |
| **AWS S3 & Weather** | Raw Open-Meteo JSON (`weather_raw`) | `19,902` files | 0 lỗi checksum; hoàn tất 6,590 backfill tasks + P5 grid |
| **Silver Weather** | `silver_weather.weather_daily_metrics` | `95,235` rows | 92,415 GFS Stitched + 2,196 ERA5 + 624 Forecast daily |
| **Gold Sales Mart** | `gold_md01_sales.mart_sales_daily` | `474,591` rows | Doanh số, giá vốn, biên lợi nhuận, khuyến mãi theo ngày |
| **Gold Enriched** | `gold_md01_sales.mart_sales_weather_daily` | `474,591` rows | **100% độ phủ thời tiết** trên toàn bộ dòng bán lẻ |
| **Gold Period KPI** | `gold_md01_sales.kpi_sales_trend` | `345,664` rows | Tổng hợp theo Tuần / Tháng kèm `%` tăng trưởng kỳ trước |
| **BI Mirror (Neon #2)** | `quick_gold_md01.*` + 3 Helper Views | `449 MB` | Sẵn sàng cho AWS QuickSight SPICE & Direct Query |
| **ML Forecasting (`store 5631`)** | `src/ml/01..05_*.ipynb` (`8` ATCs) | `16,848` sales + `2,080` ERA5 | `Leakage = 0.0`; `8/8` thắng SNaïve (`DM' p<0.05`); `6/8` vượt MSE Paper 2024; CQR `78.8%`; `166.6s` |

---

## 📁 Cấu trúc thư mục

```text
.
├── .env.example                            # Mẫu cấu hình biến môi trường (không chứa secret)
├── .gitignore                              # Quy tắc bảo vệ credentials, state Terraform & cache
├── requirements.txt                        # Dependencies Python 3.12+
├── README.md                               # Tài liệu tổng quan dự án
│
├── docs/                                   # 📚 Tài liệu thiết kế, kiến trúc & nghiên cứu
│   ├── images/                             # Sơ đồ kiến trúc tổng quan (.png & .svg)
│   ├── architecture/                       # Tài liệu kiến trúc hệ thống, Data Products & Weather Plan
│   ├── data-model/Relations-DataSource/    # Data Dictionary & sơ đồ EERD của PostgreSQL Source v2
│   ├── design/                             # Tài liệu thiết kế kỹ thuật (Lakehouse & ML Forecasting)
│   │   ├── databricks-medallion/           # Thiết kế chi tiết 3 lớp Bronze/Silver/Gold (MDD_vKiro)
│   │   ├── demand-forecasting-literature-review.md   # Cơ sở khoa học 7 bài báo (2022–2026)
│   │   ├── demand-forecasting-solution.md            # Thiết kế & kết quả thực nghiệm Demand Forecasting
│   │   └── demand-forecasting-colab-step-by-step.md  # Hướng dẫn hiện thực 5 Notebooks (Colab / .venv)
│   ├── domain/sales-and-demand/            # Đặc tả nghiệp vụ Module 01 (UR/FR, Use Case, Activity, Sequence)
│   ├── reviews/                            # Báo cáo kiểm định kiến trúc Pipeline SDD
│   └── references/papers/                  # Tài liệu & 7 bài báo khoa học tham khảo (PDF)
│
├── artifacts/
│   └── forecasting/                        # 📦 Kết quả ML Forecasting (Parquet, CSV metrics, model_card.json, 7 hình 300 DPI)
│
├── scripts/
│   └── weather/                            # 🛠 Scripts đóng gói & deploy AWS Lambda Weather (PowerShell)
│
├── src/
│   ├── synthetic_data_source/              # 🗄️ Tầng chuẩn bị & kiểm chứng Nguồn dữ liệu
│   │   ├── pharmaflow_source_postgre/      # DDL 35 bảng, mapping, CLI nạp & verify Neon PostgreSQL v2
│   │   └── mongodb/                        # Contract validator & importer MongoDB product_snapshots
│   │
│   ├── weather/                            # 🌤️ Engine thu thập thời tiết Open-Meteo (CLI + AWS Lambda)
│   │   ├── config/                         # Cấu hình biến thời tiết ERA5 / GFS v1 & cohorts
│   │   └── *.py                            # Planner, Worker, Reconciler, Grid P5, Validation, S3 Storage
│   │
│   ├── infra/terrafrom/                    # ☁️ Infrastructure as Code (AWS ap-southeast-1)
│   │   ├── bootstrap/                      # Khởi tạo S3 remote state bucket
│   │   ├── modules/private_s3/             # Module bảo mật S3 bucket chuẩn doanh nghiệp
│   │   └── environments/dev/               # S3 bucket, IAM policies, Weather compute & Databricks bridge
│   │
│   ├── pipeline/databricks/                # 🧱 Databricks Asset Bundle (DABs) — Medallion MD-01
│   │   ├── databricks.yml                  # Cấu hình workspace & targets (dev Serverless / prod)
│   │   ├── SDD.md                          # Software Design Document chi tiết
│   │   ├── resources/                      # Định nghĩa Workflows (jobs.yml) & DLT Pipelines (pipelines.yml)
│   │   ├── src/
│   │   │   ├── common/                     # Shared Databricks host sanitizer & Volume helpers
│   │   │   ├── bronze/                     # JDBC/Volume sync, Lambda bridge, Auto Loader weather & mongo
│   │   │   ├── silver/                     # DLT SQL: core.sql, sales.sql, weather.sql
│   │   │   ├── gold/                       # DLT SQL: md01_sales.sql
│   │   │   └── ops/                        # publish_md01.py (đối soát & đóng dấu release)
│   │   └── tests/                          # Unit tests offline cho toàn bộ Databricks logic
│   │
│   ├── streamlit/                          # 🎛️ Dashboard BI Multipage (Streamlit + Plotly, 5 trang tiếng Việt)
│   │   ├── app.py                          # Điểm chạy chính (st.navigation + shared sidebar state)
│   │   ├── requirements.txt                # 6 thư viện gọn nhẹ chỉ dành cho thành viên chạy Streamlit
│   │   ├── analytics.py                    # Logic kỳ so sánh, tăng trưởng MoM tổng, guard ĐVT & nhận xét tự động
│   │   ├── forecast_data.py                # Loader & XAI helper đọc artifacts/forecasting/ cho Trang 5
│   │   ├── config.py                       # Bảng màu tùy chọn, metadata track & bộ ánh xạ tiếng Việt
│   │   ├── queries.py                      # Bộ sinh SQL pushdown tham số hóa an toàn (%s)
│   │   ├── db.py                           # Kết nối Neon (-pooler) qua psycopg + @st.cache_data
│   │   ├── ui.py                           # KPI cards kèm delta, thanh phạm vi lọc, scope strip & xuất CSV
│   │   ├── components/filters.py           # Bộ lọc toàn cục phân tầng đồng bộ (tách biệt bộ lọc Trang 2 & 5)
│   │   └── pages/01..05_*.py               # 5 trang: Cửa Hàng, Cụm CH, Thời Tiết, So Sánh Kỳ & Dự Báo ML
│   │
│   ├── ml/                                 # 📈 Pipeline ML Dự báo Nhu cầu Dược phẩm (5 Notebooks — 1 Luồng)
│   │   ├── README.md                       # Tổng quan ML Lifecycle, kết quả 8 ATCs & hướng dẫn chạy
│   │   └── 01..05_*.ipynb                  # 01 Thu thập -> 02 EDA -> 03 FE/Leakage Test -> 04 Model/CQR -> 05 Eval/SHAP
│   │
│   └── sync_quick/                         # 📊 BI Serving Bridge: Gold MD-01 → Neon #2 → AWS QuickSight
│       ├── sync_gold_to_neon.py            # Sync atomic staging swap & tạo 3 BI Helper Views
│       ├── setup_databricks_aux_sync.py    # Deploy job tự động lắng nghe ops.product_release
│       └── test_sync_quick.py              # Unit tests tầng BI sync
│
└── tests/
    ├── test_streamlit_dashboard.py         # ✅ Bộ 58 unit & AppTest kiểm thử toàn bộ 5 trang Dashboard Streamlit
    └── weather/                            # ✅ Bộ 142 unit tests kiểm thử hệ thống Weather Ingestion
```

---

## 🔐 Thiết lập môi trường & Credentials

### 1. Yêu cầu tiên quyết (Prerequisites)
* **Thành viên chỉ chạy Dashboard Streamlit:** Chỉ cần **Git** và **Python `3.12+`** (không cần AWS CLI, Terraform, Databricks hay MongoDB).
* **Người vận hành / phát triển toàn bộ Pipeline:** Cần thêm **AWS CLI v2** (`aws login` / SSO profile), **Terraform `1.16+`**, và **Databricks CLI (`v1.26+`)**.

### 2. Cài đặt môi trường ảo Python

> **Nếu bạn đã có sẵn môi trường ảo (`venv` / `.venv` dùng chung / `conda`):** Bỏ qua bước `python -m venv .venv`, chỉ cần kích hoạt môi trường hiện có (hoặc gọi thẳng `pip` của môi trường đó) rồi chạy `pip install -r src/streamlit/requirements.txt` (nếu chỉ dùng Dashboard) hoặc `pip install -r requirements.txt` (nếu chạy toàn bộ Pipeline) để đồng bộ các gói còn thiếu.

- **Cách 1 — Nhanh cho thành viên chỉ chạy Streamlit (tạo `.venv` mới, chỉ cài 6 gói nhẹ):**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\pip.exe install -r src\streamlit\requirements.txt
  # macOS/Linux: ./.venv/bin/pip install -r src/streamlit/requirements.txt
  ```
- **Cách 2 — Đầy đủ cho phát triển toàn bộ Pipeline ETL (AWS, Databricks, MongoDB, Streamlit):**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\pip.exe install -r requirements.txt
  # macOS/Linux: ./.venv/bin/pip install -r requirements.txt
  ```
- **Cách 3 — Dùng lại `venv` / `conda` đã có sẵn (không tạo `.venv` mới):**
  ```powershell
  # Kích hoạt venv hoặc conda sẵn có của bạn, rồi cài/cập nhật gói cần thiết:
  pip install -r src\streamlit\requirements.txt   # hoặc: pip install -r requirements.txt
  ```

### 3. Hướng dẫn xin & cấu hình Credentials (`.env`)
Sao chép file mẫu `.env.example` thành `.env` ở thư mục gốc và điền thông tin từ các dịch vụ tương ứng (**tuyệt đối không commit file `.env` hay `.streamlit/secrets.toml`**):

```powershell
Copy-Item .env.example .env
```

> **Phân quyền nhanh cho thành viên trong team:**
> * **Chỉ chạy Dashboard Streamlit (`src/streamlit/app.py`) hoặc notebook phân tích trên Gold:** Chỉ cần **Python `3.12+`**, cài theo `src/streamlit/requirements.txt` và tạo `.env` ở gốc repo (hoặc `src/streamlit/.env`) với **2 biến** `QUICK_NEON_DATABASE_URL` + `QUICK_NEON_SCHEMA=quick_gold_md01` (nên cấp role PostgreSQL **chỉ đọc `SELECT`** trên `quick_gold_md01`).
> * **Vận hành / phát triển toàn bộ Pipeline (Ingestion, Weather, Databricks, Sync):** Cài `requirements.txt` đầy đủ, điền đủ 5 nhóm biến trong `.env`, cài thêm **AWS CLI v2** (`aws login`), **Databricks CLI / PAT**, **Terraform** (nếu chỉnh IaC), và được **whitelist IP** trên **MongoDB Atlas Network Access**.

<details>
<summary><b>📋 Bảng hướng dẫn chi tiết cách lấy từng loại Credential</b></summary>

| Nhóm biến | Dịch vụ | Cách lấy / Cấp quyền |
|---|---|---|
| `DATABASE_URL_UNPOOLED`<br/>`WEATHER_NEON_DSN` | **Neon PostgreSQL #1** | Lấy từ **Neon Console → Connection Details**. `WEATHER_NEON_DSN` nên dùng role chỉ có quyền `SELECT` trên `org.store` (`weather_reader`) để tuân thủ nguyên tắc tối thiểu quyền. |
| `MONGODB_CONNECTION_STRING`<br/>`USERNAME_MONGODB`<br/>`PASSWORD_MONGODB` | **MongoDB Atlas** | Tạo Database User trong **Atlas → Database Access** (quyền `readWrite` trên DB `pharmaflow_product_knowledge`) và lấy SRV URI tại **Connect → Drivers**. |
| `WEATHER_S3_BUCKET`<br/>`WEATHER_S3_ROLE_ARN`<br/>`WEATHER_AWS_PROFILE` | **AWS Cloud** | Đăng nhập AWS CLI bằng `aws login --profile my-aws` (hoặc SSO). Lấy tên bucket và ARN của role `pharmaflow-dev-weather-local-writer` từ lệnh `terraform output` tại `src/infra/terrafrom/environments/dev`. |
| `DATABRICKS_HOST`<br/>`DATABRICKS_TOKEN` | **Databricks** | Lấy Workspace URL (`https://dbc-xxxx.cloud.databricks.com` — không kèm query params) và tạo Personal Access Token (PAT) trong **Databricks User Settings → Developer → Access tokens**. |
| `QUICK_NEON_DATABASE_URL`<br/>`QUICK_NEON_SCHEMA` | **Neon BI Mirror #2** | Tạo một project Neon riêng cho tầng BI (`landing_datamart_md01`), lấy **Pooled connection string** (`-pooler`) để kết nối với Databricks và AWS QuickSight. |

</details>

---

## 🚀 Hướng dẫn vận hành

### 1. Chạy toàn bộ Unit Tests (Offline — không cần kết nối cloud)
```powershell
# 1. Kiểm thử Databricks Lakehouse & Lambda Bridge (17 tests)
.\.venv\Scripts\python.exe -B -m pytest src\pipeline\databricks\tests -v -p no:cacheprovider

# 2. Kiểm thử Weather Ingestion Engine (142 tests)
.\.venv\Scripts\python.exe -B -m pytest tests\weather -v -p no:cacheprovider

# 3. Kiểm thử BI Serving Sync Bridge (6 tests) & Dashboard Streamlit (58 tests)
.\.venv\Scripts\python.exe -B -m pytest src\sync_quick\test_sync_quick.py tests\test_streamlit_dashboard.py -v -p no:cacheprovider

# 4. Kiểm thử Contract nguồn dữ liệu Postgres & MongoDB
.\.venv\Scripts\python.exe -B -m pytest src\synthetic_data_source\mongodb\test_product_knowledge.py -v -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest src\synthetic_data_source\pharmaflow_source_postgre\tests\test_forecast_source_contract.py -v -p no:cacheprovider

# 5. Kiểm thử hạ tầng Terraform IaC (nếu đã cài Terraform)
terraform -chdir=src/infra/terrafrom/environments/dev test
```

### 2. Vận hành Data Sources & Weather Ingestion
```powershell
# Kiểm tra kết nối và đối soát dữ liệu nguồn PostgreSQL
.\.venv\Scripts\python.exe -B src\synthetic_data_source\pharmaflow_source_postgre\scripts\source_cli.py verify all --database pharmaflow_source_postgre_v2

# Kiểm tra kết nối MongoDB Atlas
.\.venv\Scripts\python.exe -B src\synthetic_data_source\mongodb\check_connection.py

# Kiểm tra Weather Preflight & chạy thu thập lên S3
.\.venv\Scripts\python.exe -B -m src.weather.cli preflight --sink s3
```

### 3. Đồng bộ Volume & Chạy Databricks Pipeline (DABs)
```powershell
# Đồng bộ Weather S3 & MongoDB sang Databricks Managed Volume (nếu dùng Free Edition)
.\.venv\Scripts\python.exe -B src\pipeline\databricks\src\bronze\sync_s3_to_volume.py --mode daily
.\.venv\Scripts\python.exe -B src\pipeline\databricks\src\bronze\sync_mongo_to_volume.py --run-id lc-longchau-full-20261105-02

# Validate, Deploy & Trigger Databricks Asset Bundle
cd src/pipeline/databricks
databricks bundle validate -t dev
databricks bundle deploy -t dev
databricks bundle run pf_weather_sync -t dev
databricks bundle run pf_md01_pipeline -t dev
```

### 4. Đồng bộ Gold Marts sang Neon BI Mirror & Kết nối AWS QuickSight
```powershell
# Kiểm tra trạng thái bản phát hành Gold hiện tại (dry-run)
.\.venv\Scripts\python.exe -B src\sync_quick\sync_gold_to_neon.py --mode local --dry-run

# Đồng bộ Gold MD-01 sang Neon BI Mirror (tự động tạo 3 BI Helper Views)
.\.venv\Scripts\python.exe -B src\sync_quick\sync_gold_to_neon.py --mode local
```

Sau khi đồng bộ xong, mở **Amazon QuickSight (AWS Quick)** → **New Dataset → PostgreSQL**:
- **Connection type:** `Public network` | **Port:** `5432` | **SSL:** `Enabled`
- **Datasets khả dụng:** `bi_sales_weather_enriched`, `bi_weather_impact_summary`, `kpi_sales_trend`, `bi_atc_category_monthly`
- Xem chi tiết bộ **4 Prompt tạo Dashboard Sheets tự động** tại [src/sync_quick/README.md](src/sync_quick/README.md).

### 5. Chạy Dashboard Streamlit Multipage (5 Trang Tiếng Việt)

> 🌐 **Trải nghiệm trực tiếp (Live Demo — Streamlit Community Cloud):** https://pharmaflow-sales-lakehouse-bi-ut7zhiigkcrzqwvz93krzy.streamlit.app/

Thành viên chỉ chạy giao diện BI chọn 1 trong 2 cách dưới đây (nhớ tạo file `.env` ở gốc repo hoặc `src/streamlit/.env` gồm `QUICK_NEON_DATABASE_URL` và `QUICK_NEON_SCHEMA=quick_gold_md01`):

- **Trường hợp A — Đã có sẵn `venv` / `conda` (hoặc `.venv` dùng chung ở thư mục cha):** Không cần tạo lại `.venv`, chỉ kích hoạt môi trường sẵn có, cài bổ sung 6 gói nhẹ (nếu chưa có) rồi chạy:
  ```powershell
  # Kích hoạt venv/conda sẵn có của bạn (ví dụ: ..\.venv\Scripts\Activate.ps1 hoặc conda activate <env>)
  pip install -r src/streamlit/requirements.txt
  streamlit run src/streamlit/app.py --server.port 8501
  ```

- **Trường hợp B — Chưa có môi trường ảo (cài mới từ đầu):**
  ```bash
  git clone https://github.com/minhnhut273/PharmaFlow-Sales-Lakehouse-BI.git
  cd PharmaFlow-Sales-Lakehouse-BI
  python -m venv .venv
  ```
  1. **Cài 6 gói cần thiết & khởi chạy:**
     ```powershell
     # Windows (PowerShell)
     .\.venv\Scripts\pip.exe install -r src\streamlit\requirements.txt
     .\.venv\Scripts\streamlit.exe run src\streamlit\app.py --server.port 8501
     ```
     ```bash
     # macOS / Linux
     ./.venv/bin/pip install -r src/streamlit/requirements.txt
     ./.venv/bin/streamlit run src/streamlit/app.py --server.port 8501
     ```

Truy cập `http://localhost:8501` để sử dụng 5 trang (**Cửa Hàng & Mặt Hàng**, **Cụm CH & Bản Đồ**, **Thời Tiết & Mùa Vụ**, **So Sánh Kỳ & Danh Mục**, **Dự Báo Nhu Cầu ML**), chuyển đổi 7 bảng màu giao diện, lọc đa yếu tố thời tiết, xem Fan Chart / TreeSHAP dự báo và tải CSV trực tiếp. Xem hướng dẫn sử dụng & xử lý lỗi chi tiết tại [src/streamlit/README.md](src/streamlit/README.md).

### 6. Chạy Pipeline ML Dự báo Nhu cầu (5 Notebooks — 1 Luồng Thống nhất)
* **Chỉ Notebook 01** cần `.env` với `QUICK_NEON_DATABASE_URL` + `QUICK_NEON_SCHEMA=quick_gold_md01` để trích dữ liệu Gold (`store_id = 5631`); **Notebooks `02 → 05`** chạy hoàn toàn **offline** từ các tệp `.parquet` trong `artifacts/forecasting/`.
* Mở tuần tự `src/ml/01_data_and_feature_collection.ipynb` → `05_evaluation_xai_and_serving.ipynb` trên `.venv` local (cần thêm `lightgbm`, `statsmodels`, `scikit-learn`, `scipy`, `holidays`, `pyarrow`, `matplotlib`, `seaborn`) hoặc Google Colab Pro.
* Xem bảng kết quả 8 ATC, kiểm định `DM'`, `Split CQR P10–P90`, `TreeSHAP` và hướng dẫn chi tiết tại [src/ml/README.md](src/ml/README.md), [demand-forecasting-colab-step-by-step.md](docs/design/demand-forecasting-colab-step-by-step.md) hoặc **[Google Docs 4 Tab](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit)**.

---

## 📖 Tài liệu & Tham khảo

* **Tài liệu Chi tiết ML Dự báo Nhu cầu (Google Docs — 4 Tab đầy đủ):** [Mở Google Docs](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit) — [Tab 1 (7 Bài báo)](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit?tab=t.str8dzlshch7) | [Tab 2 (Kiến trúc & Phương pháp)](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit?tab=t.0) | [Tab 3 (Thiết kế & Kết quả)](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit?tab=t.s40qjatkb5g8) | [Tab 4 (Hướng dẫn 5 Notebooks)](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit?tab=t.3fqlb8ix6shl)
* **Module ML Dự báo Nhu cầu (`DATA -> FORECAST`):** [src/ml/README.md](src/ml/README.md) | [Cơ sở 7 Bài báo](docs/design/demand-forecasting-literature-review.md) | [Tổng Giải pháp & Kết quả](docs/design/demand-forecasting-solution.md) | [Step-by-Step Colab](docs/design/demand-forecasting-colab-step-by-step.md)
* **Hướng dẫn Dashboard Streamlit (5 trang):** [src/streamlit/README.md](src/streamlit/README.md) | [🌐 Live Demo Streamlit Cloud](https://pharmaflow-sales-lakehouse-bi-ut7zhiigkcrzqwvz93krzy.streamlit.app/)

* **Software Design Document (SDD) Databricks Pipeline:** [src/pipeline/databricks/SDD.md](src/pipeline/databricks/SDD.md)
* **Thiết kế 3 tầng Medallion Lakehouse:** [docs/design/databricks-medallion/02-thiet-ke-medallion.md](docs/design/databricks-medallion/02-thiet-ke-medallion.md)
* **Kiến trúc Hệ thống & Data Products:** [docs/architecture/pharmaflow-system-architecture.md](docs/architecture/pharmaflow-system-architecture.md) | [pharmaflow-data-products.md](docs/architecture/pharmaflow-data-products.md)
* **Thiết kế Weather Ingestion (SDD & Runbook):** [src/weather/SDD.md](src/weather/SDD.md) | [src/weather/README.md](src/weather/README.md)
* **Hướng dẫn Hạ tầng AWS Terraform:** [src/infra/terrafrom/README.md](src/infra/terrafrom/README.md)
* **Từ điển dữ liệu Nguồn PostgreSQL v2:** [docs/data-model/Relations-DataSource/README.md](docs/data-model/Relations-DataSource/README.md)
* **Đặc tả nghiệp vụ Sales & Demand (MD-01):** [docs/domain/sales-and-demand/REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md](docs/domain/sales-and-demand/REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md)

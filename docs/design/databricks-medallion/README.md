# PharmaFlow Medallion Design — bản Kiro (14/11/2026, cập nhật theo issue #7, #8)

**Trạng thái:** bản thiết kế đề xuất. Không có workspace, pipeline, bảng Delta hay quyền Databricks nào được tạo trong đợt này. Mọi tên catalog/schema/table là đề xuất, cần nhóm chốt.

Mục tiêu: dựng lakehouse Bronze → Silver → Gold trên Databricks cho DSS PharmaFlow, phục vụ 5 module nghiệp vụ (MD-01…MD-05) và giữ chuỗi `DATA → FORECAST → RISK → DECISION → OPERATIONAL OUTCOME`.

## Đọc theo thứ tự

| # | Tài liệu | Trả lời câu hỏi |
|---|---|---|
| 01 | [Nguồn dữ liệu và 5 module](01-nguon-va-module.md) | Có nguồn gì, grain gì, module nào cần gì, còn thiếu gì |
| 02 | [Thiết kế 3 layer](02-thiet-ke-medallion.md) | Catalog/schema, bảng Bronze/Silver/Gold, cột kỹ thuật, luật chất lượng |
| 03 | [Quy trình nghiệp vụ](03-quy-trinh-nghiep-vu.md) | Dữ liệu đi từ nguồn tới quyết định và kết quả vận hành thế nào, ai duyệt |
| 04 | [Quy trình kỹ thuật Databricks](04-quy-trinh-ky-thuat-databricks.md) | Dựng workspace, kết nối 3 nguồn, Jobs/Pipelines, lịch, chạy lại, nghiệm thu |

## Tóm tắt một trang

| Nguồn kỹ thuật | Nhóm nghiệp vụ | Vào Bronze bằng | Ghi chú |
|---|---|---|---|
| PostgreSQL (Neon `pharmaflow_source_postgre_v2`) | Nghiệp vụ tổng hợp: catalog, store/warehouse, POS, procurement, inventory, transfer, return/recall | JDBC full snapshot theo run (pilot) → sau đó Lakeflow Connect query-based/CDC | 35 bảng, 5 schema |
| MongoDB (`pharmaflow_product_knowledge.product_snapshots`) | Nghiệp vụ tổng hợp: tri thức sản phẩm (thành phần, bảo quản) | Spark MongoDB connector, incremental theo `provenance.captured_at` | Observed public page, không phải tồn/bán |
| Amazon S3 (`raw/open_meteo/...`) | Thời tiết Open-Meteo | Auto Loader, chỉ đọc theo `accepted.json` | Đã chạy P1–P4; reader policy chưa gắn |
| Amazon S3 (hồ sơ thầu) | Thuộc platform MD-05 | Không nạp; app xử lý PDF, lưu kết quả ở App DB | Databricks chỉ cấp tồn, hàng về, forecast, SKU cho MD-05 |
| CSV sim `md04-transfer-transport-sim` | Tham chiếu MD-04: ma trận đường, hồ sơ 3PL | Volume `bronze_sim.landing` + Auto Loader | Dữ liệu nghiệp vụ của sim đi qua loader vào PostgreSQL |
| App DB (khi app có) | Dữ liệu MD-03/04/05 tạo ra, sự kiện 3PL; MD-06 giữ ở đây | JDBC chỉ đọc → `bronze_app` (không đọc mật khẩu/token) | Đo KPI chấp nhận đề xuất, trúng ↔ giao, outcome |

**Hiện trạng nguồn (issue #8, 13/11/2026):** PostgreSQL chỉ có catalog, cửa hàng và bán hàng. 23 bảng `procurement.*`, `inventory.*`, `pos.customer_request*`, `pos.sales_channel` còn 0 dòng. MD-02/03/04 chờ loader dữ liệu sim.

| Layer | Một câu |
|---|---|
| Bronze | Bản sao nguyên trạng từng lần nạp + metadata run, append-only, không sửa nghĩa |
| Silver | Kiểu dữ liệu đúng, khóa chuẩn, thời gian UTC + local, khử trùng lặp, giữ grain và provenance |
| Gold | Data product theo module (mart, KPI, feature/trainset, forecast, risk, scenario input) có contract |

## Nguyên tắc bắt buộc

1. Giữ `data_origin`/`source`/`provenance_class` (OBSERVED, SYNTHETIC, UNVERIFIED) từ Bronze tới Gold.
2. Không cộng `pos.sales_observation` với POS synthetic sinh ra từ chính nó.
3. Sales ≠ demand; ordered ≠ received; on-hand/available ≠ saleable; transfer ≠ goods receipt; tender award ≠ fulfillment.
4. Forecast metrics (MAE, RMSE, WAPE, Bias) và decision metrics (stockout, fill rate, tồn TB, expiry, chi phí mô phỏng) nằm ở bảng khác nhau.
5. Gold không ghi PO/transfer thật. Khuyến nghị đi qua Human Approval trong app.
6. Backtest chỉ dùng dữ liệu khả dụng tại forecast origin (as-of join).

## Nguồn đã đọc

- `AGENTS.md`, `docs/architecture/pharmaflow-system-architecture.md`, `pharmaflow-domain-module-map.md`, `pharmaflow-data-products.md`.
- `src/synthetic_data_source/pharmaflow_source_postgre/README.md`, `schema_full.sql`; `src/synthetic_data_source/mongodb/README.md`.
- `src/weather/README.md`, `src/weather/SDD.md`, một `metadata.json`/`accepted.json` thật trong `.runtime/weather/raw/`.
- Module: `jobs/W19.10/REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md` (MD-01), `jobs/W2.11/` (MD-02), `jobs/W9.11/md03-md04-usecase-v3/docs/4_sua_doi.md`, `5_sua_doi.md` (MD-03, MD-04), `jobs/W9.11/module-05-tender/` (MD-05), `jobs/W9.11/module-06-system-admin/` (MD-06, năng lực dùng chung).
- GitHub issue [#8 Bổ sung dữ liệu MD-03 / MD-04](https://github.com/minhnhut273/PharmaFlow/issues/8) (MT-024) và [#7 Data requirements](https://github.com/minhnhut273/PharmaFlow/issues/7) (nam2312186), đọc ngày 14/11/2026. Issue #7 có tiêu đề "Module 05 & 06" nhưng nội dung hiện là MD-03/MD-04. Yêu cầu dữ liệu MD-05/06 lấy từ bản người dùng gửi trong chat ngày 14/11/2026 (tham chiếu `jobs/module-05-tender/research/task/W05…`, `W07…` và tài liệu Module 06 theo PR #6). File `jobs/W13.11/md03-md04-data-readiness/DATA_READINESS.md` và `dataset/md04-transfer-transport-sim` mà issue nhắc tới chưa có trong repo.
- Databricks docs: [PostgreSQL connector](https://docs.databricks.com/aws/en/ingestion/lakeflow-connect/postgresql), [query-based connectors](https://docs.databricks.com/aws/en/ingestion/lakeflow-connect/query-based-overview).

Bản này độc lập với `../MDD_vCodex/` và `../MDD_vAgy/`; có thể đối chiếu để chọn phương án.

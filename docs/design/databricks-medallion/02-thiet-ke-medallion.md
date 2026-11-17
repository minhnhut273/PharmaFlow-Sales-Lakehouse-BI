# 02 — Thiết kế 3 layer Medallion trên Databricks

## 1. Bố cục Unity Catalog

Một catalog cho mỗi môi trường. Mỗi layer là một nhóm schema. Tách theo nguồn ở Bronze, theo miền ở Silver/Gold.

```text
pharmaflow_dev            (sau này: pharmaflow_prod)
├── ops                   # control: run log, watermark, DQ result, readiness
├── bronze_pg             # 35 bảng Neon, giữ tên <schema>__<table>
├── bronze_mongo          # product_snapshots
├── bronze_weather        # accepted / metadata / response
├── bronze_sim            # CSV tham chiếu MD-04: travel_matrix, service_profiles
├── bronze_app            # (khi app có) App DB chỉ đọc: review, ops, sự kiện 3PL, tender, role-scope
├── silver_core           # dim dùng chung: product, category, location, supplier, calendar
├── silver_sales          # MD-01
├── silver_inventory      # MD-02 + transfer MD-04a
├── silver_procurement    # MD-03
├── silver_logistics      # MD-04b: ma trận đường, 3PL profile, chuyến, GPS, nhiệt độ
├── silver_decision       # dữ liệu module tạo ra (từ App DB): yêu cầu, đề xuất, duyệt, nhu cầu mua
├── silver_weather        # hourly / daily / snapshot
├── gold_md01_sales
├── gold_md02_inventory
├── gold_md03_procurement
├── gold_md04_distribution
├── gold_md05_tender      # đầu vào cung ứng cho app MD-05
├── gold_kpi              # KPI xuyên miền cho dashboard
└── ml                    # feature, trainset, forecast, backtest, decision eval
```

Volumes:

| Volume | Loại | Trỏ tới | Dùng cho |
|---|---|---|---|
| `bronze_weather.weather_raw` | External volume | `s3://pharmaflow-dev-weather-raw-.../raw/open_meteo/` | Auto Loader đọc weather |
| `bronze_mongo.landing` | Managed volume | — | Phương án B: thả `documents.ejsonl` đã verify |
| `bronze_sim.landing` | Managed volume | — | CSV tham chiếu MD-04 (`travel_matrix.csv`, `service_profiles.csv`) |
| `ops.checkpoints` | Managed volume | — | Checkpoint Auto Loader/streaming |

Tên bảng: `snake_case`, tiền tố `dim_`, `fact_`, `bridge_`, `snap_`, `feat_`, `mart_`, `kpi_`. Không đổi tên cột nguồn ở Bronze.

## 2. Cột kỹ thuật chung

| Cột | Bronze | Silver | Gold | Ý nghĩa |
|---|:-:|:-:|:-:|---|
| `_ingest_run_id` | ✓ | ✓ | | Run nạp (Job run id + nguồn) |
| `_ingested_at` | ✓ | | | Thời điểm Databricks nhận |
| `_source_system` | ✓ | ✓ | | `neon:pharmaflow_source_postgre_v2`, `mongo:pharmaflow_product_knowledge`, `s3:open_meteo` |
| `_source_object` | ✓ | | | Bảng / collection / S3 key |
| `_row_hash` | ✓ | ✓ | | SHA-256 của cột nghiệp vụ, phát hiện đổi |
| `_snapshot_mode` | ✓ | | | `FULL`, `INCREMENTAL`, `CDC` |
| `provenance_class` | | ✓ | ✓ | `OBSERVED`, `SYNTHETIC`, `UNVERIFIED`, `CANDIDATE` (map từ `source`/`data_origin`) |
| `source_code` | | ✓ | ✓ | Giá trị gốc `source`/`data_origin` |
| `_valid_from` / `_valid_to` / `_is_current` | | ✓ (dim) | | SCD2 cho dim đổi theo thời gian |
| `as_of_date` / `published_at` | | | ✓ | Mốc dữ liệu và thời điểm phát hành product |

## 3. Bronze — giữ nguyên trạng

Nguyên tắc: append-only, không lọc, không ép nghĩa. Lỗi parse vào cột `_rescued_data` hoặc bảng `_quarantine`. Bronze cho phép tái xử lý Silver từ đầu.

### 3.1 PostgreSQL → `bronze_pg`

| Hạng mục | Thiết kế |
|---|---|
| Bảng | `bronze_pg.<schema>__<table>`, ví dụ `bronze_pg.pos__sales_order_line` (35 bảng) |
| Cách nạp (pilot) | Job Python: `spark.read.format("postgresql")` hoặc JDBC, đọc **full snapshot** mỗi run, ghi append kèm `_ingest_run_id` |
| Lý do full | Nhiều bảng không có `updated_at`; tổng ~1 triệu dòng, full snapshot rẻ và đơn giản |
| Nâng cấp | Lakeflow Connect query-based (cursor `created_at`/id cho bảng append-only) hoặc PostgreSQL CDC (logical replication, đang Public Preview) |
| Partition | `_ingest_date` |
| Giữ lịch sử | 30 snapshot gần nhất; cũ hơn VACUUM sau khi Silver đã chốt |
| Quyền nguồn | Role Neon chỉ `SELECT`, khác role loader và role `weather_reader` |

### 3.2 MongoDB → `bronze_mongo.product_snapshots`

| Hạng mục | Thiết kế |
|---|---|
| Cột | `_id`, `source`, `source_sku`, `source_product_key`, `captured_at`, `content_hash`, `raw_doc` (JSON string toàn document) + cột kỹ thuật |
| Cách A | MongoDB Spark Connector, filter `provenance.captured_at > watermark` (lưu ở `ops.watermark`) |
| Cách B | Upload `runs/<run-id>/documents.ejsonl` + `manifest.json` vào volume `landing`, Auto Loader đọc; kiểm SHA-256 với manifest |
| Khóa dedup | `(source, source_product_key, captured_at, content_hash)` — giống unique index nguồn |

### 3.3 S3 Weather → `bronze_weather`

| Bảng | Nguồn file | Cách đọc |
|---|---|---|
| `weather_accepted` | `tasks/*/accepted.json` | Auto Loader `cloudFiles.format=json`, `pathGlobFilter=accepted.json` |
| `weather_metadata` | `metadata_key` trong accepted | Đọc theo danh sách key mới, giữ toàn JSON + cột trích |
| `weather_response` | `response_key` trong accepted | Đọc `raw` dạng text (`wholetext`) + `raw_sha256` |
| `weather_run_summary` | `summary/*.json` | Auto Loader, dùng cho giám sát |

Kiểm `sha256(response) == accepted.raw_sha256`. Sai → quarantine, không vào Silver. Attempt không có `accepted.json` không được đọc.

### 3.4 Hồ sơ thầu — không nạp vào lakehouse

PDF mời thầu nằm trên S3 của platform; trích xuất (OCR/AI, kèm trang và trạng thái `PROPOSED` / `CONFIRMED`) do app làm và lưu ở App DB. Databricks không đọc PDF. Không có `bronze_tender`.

### 3.5 CSV tham chiếu MD-04 → `bronze_sim`

| Bảng | Nguồn | Ghi chú |
|---|---|---|
| `travel_matrix` | `travel_matrix.csv` | Khoảng cách, thời gian theo loại xe và khung giờ. Đường OSRM là thật, hệ số mưa và xe máy là giả định |
| `service_profiles` | `service_profiles.csv` | Loại xe, tải trọng, thể tích, có lạnh, cước. Không phải báo giá thật |

Dữ liệu nghiệp vụ của bộ sim (lô, nhu cầu, phiếu) **không** vào đây; nó đi qua loader vào PostgreSQL nguồn rồi vào `bronze_pg` như mọi dữ liệu nghiệp vụ khác. `weather_*.csv` của bộ sim không nạp vào luồng chính để khỏi lẫn với S3 Open-Meteo.

### 3.6 App DB → `bronze_app` (khi app có)

Đọc chỉ-đọc theo JDBC như PostgreSQL nguồn, cursor theo `updated_at`/id. Gồm: `review.*` (yêu cầu, đề xuất, phản hồi, duyệt, giữ chỗ, phiếu, kế hoạch chuyến, nhu cầu mua, gợi ý NCC, thẩm định NCC, cảnh báo), cấu hình chính sách có phiên bản, và sự kiện 3PL trong `ops` (chuyến, điểm dừng, GPS, nhiệt độ thùng, giao lỗi). Tên schema App DB là theo issue #8; chưa có DDL.

## 4. Silver — chuẩn hóa, giữ nghĩa

Luật chung:

1. Khử trùng lặp theo khóa nghiệp vụ; lấy bản từ `_ingest_run_id` mới nhất.
2. Ép kiểu: số lượng `DECIMAL(18,4)`, tiền `DECIMAL(18,2)`, giữ `currency_code`.
3. Thời gian: lưu `*_utc` (TIMESTAMP) và `*_local` + `local_date` theo `org.store.timezone_name`. IRPD là `Asia/Jakarta`.
4. Giữ UOM gốc. Quy đổi chỉ khi `catalog.product_packaging.quantity_in_base_uom` có giá trị; nếu null thì `base_qty = NULL`, không đoán.
5. `provenance_class` bắt buộc NOT NULL.

### 4.1 `silver_core` (dùng chung)

| Bảng | Grain | Khóa | Ghi chú |
|---|---|---|---|
| `dim_product` | product (SCD2) | `product_id` | + brand, manufacturer, `base_uom_code`; thuộc tính vận chuyển (khối lượng, thể tích kiện, nhóm bảo quản thường / mát / 2–8 °C, cờ kiểm soát đặc biệt, hạn dùng chuẩn) khi nguồn có; giá vốn để tính giá trị yêu cầu |
| `dim_product_packaging` | packaging | `product_packaging_id` | `quantity_in_base_uom` có thể null |
| `dim_product_category` | category | `category_id` | giữ `taxonomy_scheme`, cây cha-con |
| `bridge_product_category` | product × category | cả hai | `assignment_status` (`CANDIDATE` ≠ observed) |
| `dim_product_knowledge` | product key × capture | `source_product_key, captured_at` | từ Mongo; `is_latest`; `storage_text`, `composition` |
| `xref_product_source` | product × external key | `product_source_reference_id` | nối Postgres ↔ Mongo qua `SKU:<sku>` |
| `dim_location` | store hoặc warehouse | `location_key` (`STORE:<id>`, `WH:<id>`) | `location_kind` (`CENTRAL`, kho vùng, `STORE`), `parent_location_key`, vùng/cụm, `has_fridge`, khung giờ nhận, thời gian phục vụ, `timezone_name`, lat/lon, `coordinate_status`; tên hiển thị dùng chung cho UI |
| `snap_location_heartbeat` | location × thời điểm | `location_key, reported_at` | Thời điểm cập nhật tồn cuối của từng điểm (bảng nguồn đề xuất `org.location_heartbeat`) |
| `dim_supplier`, `dim_manufacturer` | 1 dòng / thực thể | id | supplier ≠ manufacturer; supplier có MST, phường, trạng thái hợp tác |
| `dim_calendar` | ngày | `date` | tuần, tháng, lễ VN/ID (nếu nhóm bổ sung) |

### 4.2 `silver_sales` (MD-01)

| Bảng | Grain | Luật |
|---|---|---|
| `fact_sales_line` | order line | Join order + line. `sold_quantity`, `sales_uom_code`, `base_qty`, `line_amount`, `ordered_at_utc/local`, `local_date`, `demand_location_key`. `provenance_class=SYNTHETIC` cho Onyx/Pharma Sales POS sinh ra |
| `fact_sales_observation` | store × subject × period | Aggregate nguồn. `subject_kind` (product/category). Không union với `fact_sales_line` |
| `fact_customer_request_line` | request line | `requested`, `available`, `fulfilled`, `unmet` tách riêng — bằng chứng demand duy nhất; `available_quantity = 0` là cờ hết hàng trong ngày |

Nhu cầu mô phỏng TP.HCM (`source = SIMULATED_MD04_DEMAND`) nằm trong `fact_sales_observation`, `provenance_class = SYNTHETIC`. Không gộp với IRPD/Onyx khi tính KPI theo vùng.

### 4.3 `silver_inventory` (MD-02, MD-04a)

| Bảng | Grain | Luật |
|---|---|---|
| `dim_batch_lot` | lot | `expiry_date` null → giữ null (Gold gán `UNKNOWN_EXPIRY`) |
| `snap_inventory_balance` | warehouse × lot × `as_of` | `on_hand_quantity`, `reserved_quantity`, `unreserved_quantity`, `restricted_quantity`. Không tạo cột saleable ở Silver |
| `fact_inventory_movement` | event | `movement_type`, `quantity_delta` có dấu; giữ FK nguồn (sales line / GR line / transfer line / stock take line) |
| `fact_transfer_line` | transfer line | `requested/shipped/received` + `requested_at/dispatched_at/received_at`; `in_transit = shipped − received` khi chưa nhận |
| `fact_stock_take_line` | count line | `book`, `counted`, `variance` |
| `fact_quality_event` | event | `event_action`, `affected_quantity`, `authorization_reference` |
| `fact_return_line`, `fact_recall_scope`, `fact_recall_action`, `snap_recall_reconciliation` | theo bảng nguồn | notice ≠ action ≠ recovered |

### 4.4 `silver_procurement` (MD-03)

| Bảng | Grain | Luật |
|---|---|---|
| `fact_po_line` | PO line | `ordered_quantity`, `order_uom_code`, `unit_cost`, `ordered_at`, `expected_delivery_date`, `po_status`. PO do ERP phát hành; PharmaFlow chỉ đọc |
| `fact_po_confirmation` | PO line × lần xác nhận | `confirmed_quantity`, `confirmed_at`, `new_eta`, lý do giao thiếu / từ chối (bảng nguồn đề xuất) |
| `fact_goods_receipt_line` | GR line | `received`, `accepted`, `rejected`, `received_at`, `batch_lot_id`, hạn dùng, kết quả QC, nhiệt độ khi nhận hàng lạnh; FK `purchase_order_line_id` |
| `dim_supplier_certificate` | NCC × chứng nhận | loại (GDP, giấy phép KD dược), phạm vi (hàng lạnh, kiểm soát đặc biệt), số, ngày cấp, ngày hết hạn, link minh chứng |
| `dim_supplier_product_price` | NCC × SKU × hiệu lực (SCD2) | đơn giá theo đơn vị mua, MOQ, bậc giá, lead time cam kết, tiền tệ, `vat_included`; `base_unit_price` chỉ khi có hệ số quy đổi |

Bốn lượng **đặt → xác nhận → nhận → đạt QC** luôn ở bốn cột khác nhau, không gộp.

### 4.5 `silver_weather`

| Bảng | Grain | Khóa | Luật |
|---|---|---|---|
| `weather_snapshot` | 1 accepted attempt | `snapshot_id` | `source_type`, `store_id`, `model`, `window`, `validation_status`, `retrieved_at_utc` = **available_at** |
| `weather_hourly` | snapshot × giờ | `snapshot_id, valid_time_utc` | explode mảng `hourly`; `valid_time_local`; `lead_hours = valid_time − retrieved_at` (chỉ forecast); null giữ null |
| `weather_daily` | snapshot × ngày local | `snapshot_id, local_date` | từ `daily`; ngày DST tự tổng hợp từ hourly |
| `store_grid_mapping` | store × version (P5) | `store_id, mapping_version` | `grid_id`, công thức ô 0,13° |

Phân biệt rõ ba loại: forecast snapshot thu mỗi sáng (as-of hợp lệ), historical forecast stitched (không phải thông tin từng biết ở cutoff cũ), ERA5 reanalysis (quan sát hậu kiểm).

### 4.5b `silver_logistics` (MD-04b)

| Bảng | Grain | Nguồn | Luật |
|---|---|---|---|
| `ref_travel_matrix` | điểm đi × điểm đến × loại xe × khung giờ | `bronze_sim` | giữ `distance_source` (OSRM thật) tách khỏi hệ số giả định |
| `ref_service_profile` | loại xe 3PL | `bronze_sim` | nhãn "không phải báo giá thật" |
| `fact_trip` / `fact_trip_stop` | chuyến / điểm dừng | `bronze_app` (sự kiện 3PL) | bắt buộc có mã phiếu điều chuyển để nối `fact_transfer_line` |
| `fact_gps_ping` | chuyến × thời điểm | `bronze_app` | khoảng trống > ngưỡng → sự kiện mất tín hiệu |
| `fact_temperature_reading` | chuyến × thời điểm | `bronze_app` | ngoài 2–8 °C với hàng lạnh → sự kiện lệch nhiệt |

### 4.5c `silver_decision` (dữ liệu module tạo ra, từ App DB)

| Bảng | Module | Nội dung chính |
|---|---|---|
| `fact_purchase_need` | MD-03 | kỳ, kho, SKU, phiên bản forecast, tồn khả dụng, hàng đang về, phần trừ điều chuyển, tồn an toàn, đề xuất, điều chỉnh + lý do, người xác nhận, trạng thái nháp / đã xác nhận |
| `fact_supplier_suggestion` | MD-03 | SKU, lượng, phương pháp (chấm điểm / tối ưu chi phí), trọng số, điểm từng NCC, NCC được chọn, người chọn |
| `fact_supplier_assessment` | MD-03 | NCC, kết luận đạt / đạt có điều kiện / không đạt, lý do, người thẩm định, hiệu lực |
| `fact_transfer_request` (+ line) | MD-04 | mã, điểm nhận, ngày cần, mức khẩn, cách tạo, trạng thái (nháp → chờ duyệt KSĐB → chờ cấp 1 → chờ cấp 2 → đã duyệt / từ chối / hủy), thời điểm từng bước, đạt SLA |
| `fact_transfer_proposal` (+ line) | MD-04 | giải pháp heuristic / MILP, phiên bản tham số, `inventory_as_of` đã dùng, nguồn, lô, lượng, lý do, chi phí ước tính, ETA, số chuyến |
| `fact_proposal_feedback` | MD-04 | chấp nhận / sửa / từ chối, lượng trước và sau, lý do |
| `fact_approval` | MD-03/04 | cấp, người duyệt, kết quả, lý do; dòng KSĐB bị từ chối tách riêng |
| `fact_stock_reservation` | MD-04 | lô, lượng, yêu cầu, hết giữ lúc |
| `fact_transfer_order` (+ link request) | MD-04 | mã phiếu, các yêu cầu được gộp, nguồn, đích, dòng lô và lượng, gửi cho ai, lúc nào |
| `fact_trip_plan` | MD-04 | phiếu thuộc chuyến, giải pháp tuyến, thứ tự điểm, ETA, km, chi phí ước tính |
| `fact_alert` | MD-03/04 | loại (PO trễ, giao thiếu, chứng nhận sắp hết hạn, chuyến trễ, lệch nhiệt, mất tín hiệu), đối tượng, thời điểm, trạng thái đã xem |
| `dim_policy_param` | MD-03/04/06 | tham số, giá trị, phiên bản, hiệu lực, người sửa |

Nhãn trạng thái không được nâng: đề xuất được chọn ≠ đã duyệt ≠ đã xuất kho; đã giao ≠ đã nhận đủ; NCC được chọn ≠ PO đã phát hành.

### 4.6 Tender trong Silver

Chỉ khi app có: `silver_decision.fact_tender_commitment` (cam kết / đặt trước theo SKU × kho × kỳ), `fact_tender_award_line` (chỉ kết quả `CONFIRMED`, có căn cứ), `fact_tender_delivery` (đợt giao thực tế). Đọc từ `bronze_app`. Lượng trúng và lượng giao ở hai bảng khác nhau.

## 5. Gold — data product theo module

Mỗi bảng Gold có contract: grain, khóa, owner, độ mới, consumer, giới hạn.

### MD-01 `gold_md01_sales`

| Product | Grain | Nội dung |
|---|---|---|
| `mart_sales_daily` | product × location × local_date × provenance_class | `sold_qty`, `base_qty`, `revenue`, `order_count`; chỉ từ `fact_sales_line` |
| `mart_sales_observation_period` | store × subject × period | Aggregate nguồn, hiển thị riêng |
| `kpi_sales_trend` | category × location × tuần/tháng | so kỳ, mùa vụ (FR-SD-02, 03) |

`ml` cho MD-01:

| Bảng | Nội dung |
|---|---|
| `feat_sales_daily` | lag/rolling từ `mart_sales_daily`, calendar, weather daily as-of |
| `trainset_sales_<version>` | cắt theo forecast origin, ghi `feature_cutoff_at` |
| `forecast_sales` | `forecast_origin`, `target_date`, `horizon_d`, `model_name`, `model_version`, `yhat`, `yhat_lo/hi`, `is_adjusted` |
| `forecast_adjustment` | đọc từ app DB khi có (FR-SD-10), giữ giá trị trước/sau |
| `backtest_forecast_metrics` | fold × model × grain: MAE, RMSE, WAPE, Bias; luôn có baseline naive/seasonal-naive |

### MD-02 `gold_md02_inventory`

| Product | Grain | Nội dung |
|---|---|---|
| `mart_inventory_position` | location × product × lot × as_of | on_hand, reserved, unreserved, restricted, `quality_state`, `hold_or_recall_flag`, `available_for_decision` = unreserved − restricted khi lô không bị giữ / thu hồi / hết hạn; `eligibility_status = UNKNOWN` khi thiếu dữ kiện |
| `mart_lot_expiry_status` | lot × location × evaluation_date | `days_to_expiry`, `expiry_bucket` theo warning-days cấu hình (logic khớp `inventory.lot_expiry_status()`), `UNKNOWN_EXPIRY` |
| `mart_inventory_movement_daily` | location × product × ngày × movement_type | |
| `fefo_candidate_lots` | location × product × lot | đã lọc eligibility, sort expiry; là gợi ý |
| `risk_stock_projection` | location × product × ngày tương lai × scenario | projected balance = tồn + incoming (MD-03) − forecast (MD-01); cờ stockout/overstock/expiry |
| `mart_recall_tracking` | recall × scope line | notice, action, recovered tách cột |

### MD-03 `gold_md03_procurement`

| Product | Grain | Nội dung |
|---|---|---|
| `mart_po_tracking` | PO line | 4 lượng: ordered, confirmed, received, accepted; `open = ordered − accepted`; `is_late` (quá ETA, kể cả ETA mới), `is_short` (confirmed hoặc received < ordered) (FR-MD03-13, 27) |
| `mart_supplier_scorecard` | supplier × tháng | lead time TB/P90, đúng hạn %, giao đủ %, tỷ lệ lô bị giữ / thu hồi; cần 12–24 tháng lịch sử (FR-MD03-05) |
| `mart_supplier_certificate_expiry` | supplier × chứng nhận | `days_to_expiry`, cờ sắp hết hạn theo số ngày báo trước trong `dim_policy_param` (FR-MD03-28) |
| `mart_supplier_price_compare` | SKU × NCC hiệu lực | giá quy về đơn vị bán (khi có hệ số), MOQ, bậc giá, lead time, phạm vi chứng nhận (hàng lạnh chỉ NCC đủ điều kiện lạnh) |
| `mart_incoming_supply` | product × warehouse × expected_date | open qty theo ETA mới nhất |
| `net_purchase_need_input` | product × warehouse × kỳ | forecast (hoặc baseline mùa vụ, ghi rõ) − `available_for_decision` − incoming − phần dư ở kho khác **chưa giữ chỗ** + nhu cầu chưa đáp ứng từ MD-04 + tồn an toàn (FR-MD03-06/07/21). Chỉ đặt về kho tổng hoặc kho vùng |
| `supplier_score_input` | SKU × NCC | các tiêu chí đã chuẩn hóa; trọng số mặc định từ `dim_policy_param` (giá 35 %, lead time 25 %, tin cậy 25 %, chất lượng 15 %) |

### MD-04 `gold_md04_distribution`

| Product | Grain | Nội dung |
|---|---|---|
| `mart_network_inventory` | location × product | view trên `mart_inventory_position`; không tạo balance thứ hai |
| `imbalance_signal` | location × product × ngày | thiếu / dư / cận date (FR-MD04-01); `inventory_stale_flag` khi heartbeat quá ngưỡng → chặn đề xuất |
| `transfer_candidate_input` | source × dest × product × lot | chỉ lô `available_for_decision > 0`, hạn dùng tại ETA ≥ ngưỡng, nguồn không phải điểm có tồn cũ; kèm khoảng cách / thời gian từ `ref_travel_matrix`, cờ hàng lạnh và xe lạnh. Input cho heuristic / MILP; solver chạy ngoài Gold |
| `mart_transfer_tracking` | transfer line | requested, shipped, received, in_transit, lead time; nối `fact_transfer_order` và chuyến qua mã phiếu |
| `mart_trip_daily` | ngày × vùng | số chuyến, đúng giờ %, chi phí ước tính, số lần lệch nhiệt, mất GPS (FR-MD04-21, 22, 37, 43) |
| `kpi_transfer_daily` | ngày × điểm | tỷ lệ chấp nhận đề xuất (từ `fact_proposal_feedback`), lượng hàng cận date đã chuyển, đạt SLA theo mức khẩn (FR-MD04-23) |
| `unmet_after_transfer` | SKU × điểm × kỳ | lượng thiếu sau điều chuyển, chuyển sang MD-03 |

### MD-05 `gold_md05_tender` — đầu vào cho platform

MD-05 chạy chủ yếu trong platform (App DB + S3). Gold chỉ phát hành dữ liệu cung ứng mà app cần để phân tích gói thầu:

| Product | Grain | Nội dung |
|---|---|---|
| `tender_supply_input` | SKU × kho/vùng × as_of | `available_for_decision` (đã trừ giữ chỗ, bị giữ, hết hạn), on_hand, đơn vị, lô/hạn gần nhất, `as_of`, `provenance_class` |
| `tender_incoming_supply` | SKU × kho/vùng × ngày dự kiến | hàng đang về từ `mart_incoming_supply`, trạng thái, nguồn |
| `tender_forecast_input` | SKU × vùng × kỳ | forecast bán lẻ, khoảng dự báo, model, phiên bản, thời điểm chạy |
| `tender_sku_reference` | SKU | mã ổn định, hoạt chất, hàm lượng, dạng bào chế, đơn vị, quy cách, hệ số quy đổi (chỉ khi đã xác nhận) |

App đối chiếu dòng thuốc của hồ sơ với `tender_sku_reference`, chạy kịch bản, lưu kết quả ở App DB. Khi app có, `bronze_app` đọc lại cam kết tender, lượng trúng đã xác nhận và các đợt giao để (1) trừ cam kết tender khỏi `available_for_decision` cho MD-03/MD-04, không trừ lặp; (2) tính KPI trúng ↔ giao trong `gold_kpi`. Dùng chung `dim_product`, `dim_location`, `mart_inventory_position` với MD-03/MD-04; không sinh danh mục riêng.

### MD-06 — không có Gold

Tài khoản, role/permission, role-scope (GLOBAL/REGION/STORE) và audit nằm ở App DB. Backend dùng một service principal đọc Gold, rồi **lọc theo scope ở API** trước khi trả dữ liệu. Không chép mật khẩu/token vào lakehouse. Nếu cần báo cáo quyền, chỉ đọc bảng gán role-scope (không có thông tin đăng nhập) vào `bronze_app`.

### Xuyên miền

| Bảng | Nội dung |
|---|---|
| `gold_kpi.kpi_catalog` | Mã KPI, domain, category, công thức, numerator/denominator, grain |
| `gold_kpi.kpi_daily` | KPI × location × ngày, có `provenance_class` |
| `ml.decision_eval` | scenario × policy: stockout rate, fill rate, avg inventory, overstock, expiry qty, simulated cost. Không chứa MAE/RMSE |

## 6. Luật chất lượng (Lakeflow expectations)

| Layer | Luật | Hành động |
|---|---|---|
| Bronze | file JSON hợp lệ; sha256 khớp (weather/mongo B) | quarantine |
| Silver | khóa NOT NULL, unique | DROP + ghi `ops.dq_result` |
| Silver | `sold_quantity > 0`; `on_hand >= 0`; `received = accepted + rejected` (nếu nguồn định nghĩa vậy) | WARN |
| Silver | `confirmed_quantity <= ordered_quantity` trừ khi NCC giao dư có ghi nhận | WARN |
| Silver | `fact_trip_stop` có mã phiếu tồn tại trong `fact_transfer_order` | DROP + báo |
| Silver | người duyệt ≠ người tạo yêu cầu; dòng KSĐB có duyệt US-13 trước cấp 1 | WARN (báo vi phạm quy tắc) |
| Gold | scorecard tính lại từ PO sim ≈ tham số ẩn của bộ sinh (xác suất trễ, tỷ lệ giao đủ, tỷ lệ lô bị giữ) trong ngưỡng nhóm chốt | FAIL khi lệch |
| Silver | FK tồn tại (line → order, line → product, packaging thuộc product) | DROP |
| Silver | `provenance_class` NOT NULL | FAIL pipeline |
| Silver weather | `validation_status IN ('ACCEPTED','ACCEPTED_WITH_WARNINGS')` | DROP |
| Gold | độ mới: `max(as_of_date) >= today − N` | chặn publish, báo |
| Gold | reconciliation: tổng `sold_qty` Gold = Silver theo nguồn | FAIL |

Ví dụ SQL Lakeflow Declarative Pipelines:

```sql
CREATE OR REFRESH MATERIALIZED VIEW silver_sales.fact_sales_line (
  CONSTRAINT pk_not_null EXPECT (sales_order_line_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT qty_positive EXPECT (sold_quantity > 0),
  CONSTRAINT has_provenance EXPECT (provenance_class IS NOT NULL) ON VIOLATION FAIL UPDATE
) AS
SELECT l.sales_order_line_id, l.sales_order_id, l.product_id, l.product_packaging_id,
       l.sold_quantity, l.sales_uom_code,
       l.sold_quantity * p.quantity_in_base_uom AS base_qty,
       l.line_amount, l.currency_code,
       o.ordered_at AS ordered_at_utc,
       from_utc_timestamp(o.ordered_at, s.timezone_name) AS ordered_at_local,
       to_date(from_utc_timestamp(o.ordered_at, s.timezone_name)) AS local_date,
       o.demand_location_id,
       l.source AS source_code,
       CASE WHEN l.source LIKE '%SYNTH%' OR l.source LIKE '%SIM%' THEN 'SYNTHETIC' ELSE 'OBSERVED' END AS provenance_class
FROM silver_sales.v_latest_sales_order_line l
JOIN silver_sales.v_latest_sales_order o USING (sales_order_id)
LEFT JOIN silver_core.dim_product_packaging p USING (product_packaging_id)
LEFT JOIN silver_core.dim_location s ON s.location_key = concat('STORE:', o.demand_location_id);
```

Bảng map `source` → `provenance_class` phải lấy từ giá trị thật trong nguồn (xem preflight), không dùng `LIKE` như ví dụ khi đã có danh sách.

## 7. Chống rò rỉ thời gian

- Feature weather cho forecast origin `t0` chỉ dùng `weather_snapshot` có `retrieved_at_utc <= t0` và `source_type = DAILY_FORECAST`.
- Backtest trên lịch sử trước khi có snapshot hằng ngày: dùng `HISTORICAL_FORECAST_STITCHED`/ERA5 với nhãn `weather_asof_valid = false`; báo cáo tách riêng.
- Sales lag tính từ dữ liệu `local_date < t0`.
- Mỗi trainset lưu `feature_cutoff_at` và `source_snapshot_ids`.

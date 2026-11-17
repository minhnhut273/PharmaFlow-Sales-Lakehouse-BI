# 01 — Nguồn dữ liệu và 5 module

## 1. Hai cách nhìn nguồn

| Góc nhìn | Thành phần |
|---|---|
| **Kỹ thuật** (3 nguồn) | PostgreSQL (Neon), MongoDB, Amazon S3 |
| **Nghiệp vụ** (2 nhóm) | (1) Nghiệp vụ tổng hợp: POS, WMS/kho, procurement, transfer, catalog, tri thức sản phẩm. (2) Thời tiết Open-Meteo |

PostgreSQL và MongoDB là **nguồn upstream giả lập** cho DSS. Chúng đóng vai POS/ERP/WMS. Dataset, crawler, generator chỉ dùng để dựng hai kho này; Databricks không đọc thẳng `dataset/` hay `Dataset/longchau-knowledge/`.

## 2. Nguồn 1 — PostgreSQL `pharmaflow_source_postgre_v2`

Theo `schema_full.sql` (version `20261104_01_forecast_source_contract_v2`): 35 bảng, 5 schema.

| Schema | Bảng | Module dùng chính | Grain chính |
|---|---|---|---|
| `catalog` | `manufacturer`, `unit_of_measure`, `product_category`, `product`, `product_category_assignment`, `product_source_reference`, `product_packaging` | Tất cả | 1 dòng / product, / category, / packaging |
| `org` | `store`, `warehouse` | Tất cả | 1 dòng / store; 1 dòng / warehouse (có `warehouse_kind`, `store_id`) |
| `pos` | `sales_channel`, `sales_order`, `sales_order_line`, `sales_observation`, `customer_request`, `customer_request_line` | MD-01 | order line; observation = aggregate theo `period_start/period_end`; request line |
| `procurement` | `supplier`, `purchase_order`, `purchase_order_line`, `goods_receipt`, `goods_receipt_line` | MD-03 | PO line; GR line (accepted/rejected/received tách riêng) |
| `inventory` | `batch_lot`, `inventory_balance`, `inventory_movement`, `stock_transfer(_line)`, `stock_take(_line)`, `return_case(_line/_event)`, `quality_control_event`, `recall_case`, `recall_scope_line`, `recall_action_event`, `recall_reconciliation` | MD-02, MD-04a | balance = warehouse × lot × `as_of`; movement = event; transfer line |

Cột provenance có sẵn: `source` (catalog, org.store, pos order/line/observation) và `data_origin` (warehouse, procurement, inventory, request). Silver phải giữ cả hai.

**Hiện trạng số dòng (GitHub issue #8, đối chiếu ngày 13/11/2026):**

| Nhóm | Số dòng | Ghi chú |
|---|---:|---|
| `catalog.product` | 5.674 | Long Châu 2.482, IRPD 2.972, Onyx 220 |
| `catalog.product_packaging` | 5.833 | `quantity_in_base_uom` phần lớn null |
| `org.store` | 2.816 | 2.694 Long Châu (chỉ có tọa độ, **không có dòng bán**), 120 Onyx, 1 IRPD, 1 Niš |
| `org.warehouse` | 122 | Toàn bộ `SYNTHETIC` kiểu `SIM_STORE_WH::`; chưa có `CENTRAL` hay kho vùng |
| `pos.sales_order` / `_line` | 393.942 / 714.959 | IRPD (quan sát), Onyx và Pharma Sales (mô phỏng) |
| `pos.sales_observation` | 78.884 | Onyx 62.036, Pharma Sales 16.848 |
| 23 bảng còn lại | **0** | toàn bộ `procurement.*`, `inventory.*`, `pos.sales_channel`, `pos.customer_request*` |

Hệ quả: hiện chỉ MD-01 có dữ liệu nguồn. MD-02, MD-03, MD-04 cần loader nạp dữ liệu mô phỏng vào PostgreSQL trước. Không có dữ liệu bán nào ở TP.HCM.

**Lưu ý schema thật (đã đọc `schema_full.sql`):** `inventory.inventory_balance` có `on_hand_quantity`, `reserved_quantity`, `unreserved_quantity` (đổi tên từ `available_quantity`), `restricted_quantity`, `as_of`. `unreserved` = tồn − giữ chỗ, **chưa phải** lượng bán được. Có sẵn hàm `inventory.lot_expiry_status()`. `warehouse_kind` ∈ `CENTRAL`, `STORE`, `OTHER`. `transfer_status` chỉ có `DRAFT`, `DISPATCHED`, `PARTIALLY_RECEIVED`, `RECEIVED`, `CANCELLED`.

**Bảng nguồn được đề xuất thêm (issue #8, chưa có trong schema):** `procurement.supplier_certificate`, `procurement.supplier_product_price`, `procurement.po_confirmation`, `org.location_heartbeat`, bảng thuộc tính vận chuyển của product (khối lượng, thể tích, nhóm bảo quản, cờ kiểm soát đặc biệt), cột cụm / tủ lạnh / khung giờ nhận của điểm. Thiết kế Bronze/Silver dưới đây đã chừa chỗ cho chúng; khi schema đổi thì cập nhật `ops.source_contract`.

## 3. Nguồn 2 — MongoDB `pharmaflow_product_knowledge.product_snapshots`

- 1 document = 1 capture version, khóa `(source, source_product_key, provenance.captured_at, provenance.content_hash)`.
- Run đã verify `lc-longchau-full-20261105-02`: 2.481 snapshot, 2.480 product key, 2.452 SKU, 28 URL-fallback.
- Nội dung: `composition.*` (thành phần), `storage.instructions_text` (bảo quản), `provenance.*`, `extraction.*`.
- Join sang Postgres: `catalog.product_source_reference.external_product_key` ↔ `source_product_key = 'SKU:<sku>'`. Không có FK xuyên database; URL-fallback không join được.
- Dùng cho: MD-02 (điều kiện bảo quản, hàng lạnh), MD-05 (đối chiếu hoạt chất/thuốc), ngữ cảnh hiển thị MD-01. Không phải dữ liệu tồn, bán hay cung ứng.

## 4. Nguồn 3 — Amazon S3 (Weather; hồ sơ thầu thuộc platform)

### 4.1 Weather (đã chạy P1–P4)

Layout key (giống `.runtime/weather/raw/`):

```text
raw/open_meteo/<prefix>/ingest_date=YYYY-MM-DD/run_id=<run_id>/
  plan.json, locations.json, summary/<rev>.json
  tasks/<task_id>/attempts/<attempt_id>/response.json   # bytes gốc Open-Meteo
  tasks/<task_id>/attempts/<attempt_id>/metadata.json   # 60+ trường kiểm soát
  tasks/<task_id>/accepted.json                         # cổng duy nhất cho consumer
```

`<prefix>` ∈ `daily_forecast`, `historical_forecast` (GFS, từ 2022-01-01), `historical_weather` (ERA5, trước 2022-01-01).

Trường quan trọng trong `metadata.json`: `snapshot_id`, `source_type` (`DAILY_FORECAST` / `HISTORICAL_FORECAST_STITCHED` / `HISTORICAL_ERA5_REANALYSIS`), `store_id`, `store_code`, `timezone_returned`, `model=gfs_global`, `window`, `validation_status`, `null_report`, `coordinate_verification_status`, `retrieved_at_utc`, `raw_sha256`.

Quy tắc consumer đã chốt trong `src/weather/SDD.md`:

- Chỉ đọc attempt mà `accepted.json` trỏ tới.
- `null` là thiếu dữ liệu, không phải 0. Các giờ cuối ngày 16 có thể null.
- Thời gian là `unixtime`; quy đổi local bằng `timezone_name` của location.
- Policy S3 reader cho Databricks đã có nhưng **chưa gắn** role nào.
- P5 (chưa làm): gom 2.694 store VN thành 655 ô lưới 0,13°; Silver cần `store_grid_mapping`.

### 4.2 Tender (thuộc platform, không phải nguồn của lakehouse)

Hồ sơ thầu gốc lưu trên S3 của **platform**; metadata, trích xuất và mọi bản ghi tender nằm trong App DB. Databricks không đọc PDF. Không tự tạo facts bid/award.

## 4b. Hai nguồn phụ do issue #7 và #8 nêu

| Nguồn | Nội dung | Cách vào Databricks | Provenance |
|---|---|---|---|
| `dataset/md04-transfer-transport-sim` (23 CSV) | `products.csv` (42 SKU + thuộc tính vận chuyển), `locations.csv` (52 điểm), `time_windows.csv`, `inventory_lots_t0.csv` (4.043 lô), `demand_daily.csv` (120 ngày), `transfer_orders_log.csv`, `requests_log.csv`, `trips`, `trip_stops`, `gps_pings`, `temperature_readings`, `travel_matrix.csv`, `service_profiles.csv`, `weather_*.csv`, `policy_params.csv`, `urgency_sla.csv`, `approval_policies.csv` | **Dữ liệu nghiệp vụ** (lô, nhu cầu, phiếu) đi qua loader vào PostgreSQL nguồn. **Dữ liệu tham chiếu** (`travel_matrix`, `service_profiles`) nạp thẳng vào Databricks qua volume. `weather_*.csv` chỉ dùng thử; luồng chính vẫn là S3 Open-Meteo | `SYNTHETIC`, trừ đường OSRM và thời tiết Open-Meteo là thật |
| Database ứng dụng (App DB) | Dữ liệu do MD-03/MD-04 tạo: nhu cầu mua đã xác nhận, gợi ý NCC, thẩm định NCC, yêu cầu điều chuyển, đề xuất, phản hồi đề xuất, duyệt, giữ chỗ, phiếu điều chuyển, kế hoạch chuyến, cảnh báo; cấu hình chính sách có phiên bản; sự kiện 3PL (chuyến, GPS, nhiệt độ thùng, giao lỗi) đi qua Integration Gateway vào schema `ops` của App DB | Nạp chỉ-đọc vào `bronze_app` khi app có | Theo bản ghi; dữ liệu sim giữ `SYNTHETIC` |

Bộ sim chưa có trong repo này (chưa thấy `dataset/md04-transfer-transport-sim` và `jobs/W13.11/md03-md04-data-readiness/DATA_READINESS.md`). Mô tả trên lấy từ nội dung issue.

## 5. Năm module và nhu cầu dữ liệu

| Module | Phạm vi (theo tài liệu jobs + issue) | Bảng nguồn cần | Data product Gold cần | Sẵn sàng nguồn (13/11) |
|---|---|---|---|---|
| **MD-01 Sales & Demand** (`jobs/W19.10`) | FR-SD-01…10: theo dõi/so sánh sales qty, xu hướng mùa vụ, xem forecast, đối soát/kiểm định forecast, điều chỉnh 1 giá trị forecast | `pos.*`, `catalog.*`, `org.store`, weather | Sales mart ngày; observation mart; feature/trainset; forecast; backtest eval | **Có**, nhưng chỉ cho nhà thuốc ID/EU/Serbia. Nhu cầu TP.HCM × SKU phải lấy từ sim (`pos.sales_observation`, `source = SIMULATED_MD04_DEMAND`), cần kéo dài 24 tháng và thêm cờ hết hàng |
| **MD-02 Inventory & Expiry** (`jobs/W2.11`) | FR-MD02-01…15: tồn theo product/location/lot, trạng thái tồn, movement, expiry status, risk theo scenario, FEFO suggestion, QA hold/release/recall, KPI | `inventory.*`, `procurement.goods_receipt_line`, `catalog.*`, Mongo storage | Inventory position; lot expiry status; movement; FEFO candidate; risk scenario input; recall tracking | **Rỗng**. Nạp `inventory_lots_t0.csv`; sinh thêm lô bị giữ QC và recall (hiện 0/4.043 lô bị giữ) |
| **MD-03 Mua hàng & NCC** (`4_sua_doi.md`, issue #7, #8) | NCC, chứng nhận (GDP, giấy phép KD dược), bảng giá × SKU (đơn giá, MOQ, bậc giá, lead time, hiệu lực, VAT), PO chỉ đọc từ ERP, xác nhận của NCC, nhận hàng + QC + nhiệt độ hàng lạnh, scorecard 12–24 tháng, nhu cầu mua sau khi trừ điều chuyển, gợi ý NCC (chấm điểm: giá 35 %, lead time 25 %, tin cậy 25 %, chất lượng 15 %; hoặc tối ưu chi phí), cảnh báo PO trễ / giao thiếu / chứng nhận sắp hết hạn | `procurement.*` (+ 3 bảng đề xuất), `inventory_balance`, forecast MD-01, phần dư MD-04, App DB | PO tracking 4 lượng; incoming supply; scorecard; certificate expiry; price comparison; net purchase need | **Rỗng**. Chưa có bộ sinh MD-03. IRPD phần kho (`Pembelian`) cần tải lại để lấy tần suất nhập, cỡ lô, số NCC |
| **MD-04 Phân phối** (`5_sua_doi.md`, issue #7, #8) | 04a: thiếu/dư/cận date, đề xuất heuristic / MILP, mức khẩn + SLA, duyệt kiểm soát đặc biệt → cấp 1 → cấp 2, giữ chỗ, phiếu gộp. 04b: gom chuyến, tuyến NN/savings và VRPTW, ETA, cảnh báo trễ / lệch nhiệt 2–8 °C / mất GPS | `org.*` (+ heartbeat, cụm, tủ lạnh, khung giờ), `inventory.*`, `travel_matrix`, `service_profiles`, sự kiện 3PL, App DB | Network inventory; imbalance signal (chặn khi tồn cũ); transfer candidate input; transfer tracking; trip KPI | **Có dữ liệu sim** đủ chạy thuật toán, nhưng chưa nạp. Thiếu: heuristic, không khẩn, hủy, chờ duyệt, phiếu gộp, kho tổng làm nguồn, mã phiếu trên `trip_stops` |
| **MD-05 Đấu thầu** (`module-05-tender`, yêu cầu MD-05/06) | FR-T01…T09: hồ sơ/version, trích xuất + xác nhận, đối chiếu SKU, phân tích cung ứng, kiến nghị nội bộ, ghi kết quả trúng theo mặt hàng, theo dõi đợt giao | **Từ Databricks:** SKU + quy đổi, tồn khả dụng theo kho/vùng, hàng đang về, forecast. **Ở platform:** PDF trên S3, mọi bản ghi tender trong App DB | `gold_md05_tender.tender_supply_input` (đầu vào cho app); sau này KPI trúng ↔ giao đọc lại từ `bronze_app` | **Chưa có** dữ liệu. Dữ liệu chính nằm ở App DB của platform, không ở lakehouse |
| MD-06 Quản trị hệ thống | Đơn vị/phạm vi (GLOBAL/REGION/STORE), tài khoản giả lập, role/permission, gán role-scope, chính sách cấp/thu hồi, SoD, audit | App DB của platform | Không có Gold. Databricks chỉ cấp quyền cho service principal của backend; lọc theo scope làm ở API | Ngoài lakehouse |

### 5.1 Quy tắc nghiệp vụ từ issue (phải giữ trong Silver/Gold)

- MD-03 tách **4 lượng**: đặt (PO line), NCC xác nhận (`po_confirmation`), nhận (GR line), đạt QC (`accepted_quantity`). Chọn NCC chưa phải PO đã phát hành.
- Chỉ **lượng khả dụng** mới được trừ khỏi nhu cầu mua: `unreserved − restricted`, bỏ lô đang giữ QC, thu hồi hoặc hết hạn.
- MD-03 chỉ trừ phần dư ở kho khác **chưa** giữ chỗ cho điều chuyển, để không trừ hai lần.
- Ngày hết hàng phải gắn cờ; lượng bán ngày đó thấp hơn nhu cầu thật.
- MD-04 chỉ lấy lô khả dụng, có hạn dùng tại ETA không dưới ngưỡng, làm nguồn. Tồn ở điểm nhận đã cũ (theo heartbeat) thì chặn đề xuất.
- Duyệt: hàng kiểm soát đặc biệt do US-13 duyệt từng dòng trước cấp 1; cấp 1 là quản lý điểm nguồn; cấp 2 là US-10 hoặc US-01. Không ai tự duyệt yêu cầu mình tạo.
- Các mốc khác nhau: chọn đề xuất ≠ đã duyệt ≠ đã xuất kho; đã giao ≠ đã nhận đủ.
- Chi phí 3PL là ước tính để so sánh, không phải cước thật. MD-04 không quản lý xe, tài xế, không trừ tồn.
- Dữ liệu sinh gắn `data_origin = 'SYNTHETIC'` hoặc `source` bắt đầu bằng `SIMULATED_`; UI phải hiện nhãn.
- Danh mục SKU, danh mục điểm và tồn kho dùng **một bộ chung** cho MD-03, MD-04, MD-05.

### 5.2 MD-05 và MD-06 nằm ở đâu (theo yêu cầu dữ liệu MD-05/06)

Yêu cầu dữ liệu MD-05/06 (bản người dùng gửi ngày 14/11/2026; tiêu đề issue #7 gốc) cho thấy phần lớn dữ liệu của hai module do **platform tạo và giữ**. Lakehouse chỉ cấp đầu vào và đọc lại để phân tích.

| Dữ liệu | Chủ dữ liệu / nơi lưu | Databricks làm gì |
|---|---|---|
| Danh mục SKU (mã ổn định, hoạt chất, hàm lượng, dạng bào chế, đơn vị, quy cách, quy đổi) | Nguồn chung (PostgreSQL `catalog.*` + Mongo) | Phát hành `silver_core.dim_product`, `dim_product_packaging`; quy đổi chưa xác nhận để `NULL` |
| Tồn theo thời điểm (SKU, kho/vùng, lượng, đơn vị, khả dụng/bị giữ, lô, hạn, snapshot, nguồn) | Nguồn chung `inventory.*` | Phát hành `available_for_decision` đã trừ giữ chỗ và bị giữ, có `as_of` |
| Nguồn cung bổ sung (hàng đang về, đã cam kết/đặt trước) | Nguồn chung `procurement.*` + App DB (cam kết tender khác) | `mart_incoming_supply`; cam kết tender đọc lại từ `bronze_app` để không trừ lặp |
| Forecast bán lẻ | `ml.forecast_sales` | Phát hành kèm model, phiên bản, thời điểm chạy |
| Hồ sơ mời thầu PDF (có lớp chữ và scan) | **S3 của platform** + metadata trong App DB | Không đọc PDF |
| Kết quả trích xuất kèm trang + trạng thái xác nhận | **App DB** | Không có |
| Đầu vào, giả định, kết quả kịch bản; kiến nghị / quyết định nội bộ | **App DB** | Chỉ đọc lại (sau) |
| Kết quả trúng theo mặt hàng/số lượng có căn cứ; các đợt giao thực tế | **App DB** | Chỉ đọc lại (sau) để tính KPI trúng ↔ giao |
| Đơn vị/phạm vi, tài khoản, role/permission, gán role-scope, audit (MD-06) | **App DB** | Không có. Không chép mật khẩu/token |

Quy tắc giữ: kịch bản được chọn ≠ đã trúng; lượng trúng ≠ lượng đã giao; liên kết thuốc ↔ SKU chưa xác nhận không dùng như đã đúng; lượng khả dụng tách lượng bị giữ để không trừ lặp. Lập/nộp hồ sơ và quản lý hợp đồng không thuộc module.

## 6. Khoảng trống cần nhóm chốt

| # | Khoảng trống | Ảnh hưởng | Đề xuất |
|---|---|---|---|
| G1 | 23 bảng `procurement.*`, `inventory.*`, `pos.customer_request*` đang rỗng | Gold MD-02/03/04 rỗng | Viết loader CSV sim → PostgreSQL nguồn (issue #8, việc 1–10); readiness flag chặn Gold tới khi có dữ liệu |
| G2 | Sự kiện 3PL (chuyến, GPS, nhiệt độ) không vào PostgreSQL mà qua Integration Gateway vào App DB `ops`; `trip_stops` thiếu mã phiếu | Chưa nối phiếu với chuyến | Thêm mã phiếu khi sinh chuyến; Bronze đọc từ App DB |
| G3 | Chưa có `supplier_certificate`, `supplier_product_price`, `po_confirmation` | Không gợi ý / cảnh báo NCC được | Thêm 3 bảng vào schema nguồn, sinh dữ liệu MD-03 |
| G4 | MD-05: chưa có PDF mẫu được phép dùng, chưa chốt cách đối chiếu dòng thuốc ↔ SKU, chưa có dữ liệu cam kết/đặt trước | Không kiểm thử được phân tích cung ứng | Nhóm chốt theo "Đầu ra đề nghị" của yêu cầu MD-05/06; ít nhất 4 ca: đủ hàng, thiếu hàng, cần quy đổi, thiếu/chưa xác nhận dữ liệu |
| G5 | Dữ liệu MD-03/04 tạo ra (đề xuất, phản hồi, duyệt, giữ chỗ…) nằm ở App DB | Không đo được KPI "tỷ lệ chấp nhận đề xuất" và outcome | Nạp App DB chỉ-đọc vào `bronze_app` |
| G6 | Weather reader policy chưa gắn; P5 grid chưa làm | Databricks chưa đọc được S3 | Gắn policy cho IAM role của storage credential |
| G7 | Onyx/IRPD/Pharma Sales store có tọa độ `UNVERIFIED_PERTURBED`/`SIMULATED` | Weather join cho các store này là giả định | Giữ `coordinate_verification_status` tới feature |
| G8 | Tên SKU và tên điểm trên UI (Amoxicillin, "Kho vùng Q.12"…) không khớp `products.csv` / `locations.csv` | Dashboard và dữ liệu lệch nhau | Một danh mục chung; UI lấy tên từ `silver_core.dim_product` / `dim_location` |
| G9 | Nhu cầu TP.HCM chỉ có 120 ngày, chưa có cờ hết hàng | Không đủ 2 chu kỳ mùa để backtest | Kéo dài 24 tháng theo mùa vụ Pharma Sales (ATC), thêm `pos.customer_request_line.available_quantity` |
| G10 | `transfer_status` thiếu `IN_TRANSIT`, `FAILED_DELIVERY`, `RETURNING`; chưa có `org.location_heartbeat` | Không theo dõi đủ trạng thái chuyến, không chặn tồn cũ | Mở rộng CHECK hoặc giữ trạng thái chuyến ở sự kiện 3PL; thêm bảng heartbeat |
| G11 | `quantity_in_base_uom` phần lớn null; bảng giá có thể ghi theo thùng | Không quy đổi giá và lượng mua ↔ bán | Bổ sung hệ số quy đổi cho SKU demo; Silver để `NULL` khi thiếu, không đoán |

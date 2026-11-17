# 03 — Quy trình nghiệp vụ trên nền Databricks

Quy trình này nối hai góc nhìn:

- Xử lý: `DATA → FORECAST → RISK → DECISION → OPERATIONAL OUTCOME`.
- Nghiệp vụ: `Business Monitoring → Business Insight → Business Optimization → Human Approval → Operational Outcome`.

Databricks lo DATA, FORECAST, RISK và chuẩn bị input cho DECISION. Duyệt và ghi quyết định nằm trong app (backend + app DB). Hệ nguồn (POS/WMS/ERP) vẫn là nơi thực thi.

## 1. Bảng vai trò

| Bước | Ai làm | Ở đâu | Sản phẩm |
|---|---|---|---|
| B0. Chốt contract nguồn | Data owner từng miền + Data engineer | Tài liệu + `ops.source_contract` | Grain, khóa, provenance, lịch |
| B1. Nạp nguồn | Lakeflow Jobs (tự động) | Bronze | Snapshot theo run |
| B2. Chuẩn hóa & kiểm chất lượng | Lakeflow Pipelines | Silver + `ops.dq_result` | Bảng sạch, báo cáo lỗi |
| B3. Monitoring | Gold job | `gold_*`, `gold_kpi` | KPI hiện tại |
| B4. Insight: forecast | ML job (`ml`) | `ml.forecast_*` | Dự báo + backtest |
| B5. Insight: risk | Gold job | `risk_*`, `imbalance_signal`, `mart_po_tracking` | Cờ thiếu/dư/hết hạn/trễ |
| B6. Optimization | Solver/heuristic job | `transfer_candidate_input` → kết quả scenario | Phương án đề xuất + lý do |
| B7. Human Approval | Người dùng có quyền | App (web) + app DB | Duyệt / sửa / từ chối, có audit |
| B8. Thực thi | Hệ nguồn (ngoài DSS) | POS/WMS/ERP | PO, transfer, xuất kho thật |
| B9. Outcome | Gold + `ml.decision_eval` | Sau khi nguồn ghi nhận | Stockout, fill rate, tồn, expiry, chi phí |

B7 → B9 khép vòng khi app DB được nạp ngược vào Bronze (khoảng trống G5).

## 2. Lịch nghiệp vụ hằng ngày (đề xuất, giờ Asia/Ho_Chi_Minh)

| Giờ | Việc | Phụ thuộc |
|---|---|---|
| 06:00 | Weather Planner (AWS) chạy daily forecast | EventBridge (đã có P4) |
| ~06:20 | Weather summary chốt trên S3 | Reconciler |
| 06:30 | Databricks nạp PostgreSQL, MongoDB, Weather vào Bronze | Nguồn đã đóng sổ ngày hôm trước |
| 06:45 | Silver refresh + DQ | Bronze xong |
| 07:00 | Gold monitoring + risk refresh | Silver đạt DQ |
| 07:15 | Forecast scoring (dùng model đã duyệt) | Gold + weather snapshot sáng nay |
| 07:30 | Publish: cập nhật `ops.product_release`, app đọc bản mới | Tất cả kiểm đạt |
| Tuần (CN 22:00) | Retrain + backtest, so baseline | Data Admin duyệt trước khi dùng |

Nếu một bước fail, Gold giữ bản publish cũ và app hiện "dữ liệu tới ngày X".

## 3. Quy trình theo module

### MD-01 Sales & Demand

1. **Monitoring:** `mart_sales_daily` theo product/category/location/kênh (FR-SD-01, 02). Synthetic và observed hiển thị bằng nhãn.
2. **Insight:** xu hướng, mùa vụ (FR-SD-03); forecast theo grain nguồn cho phép (FR-SD-04). Pharma Sales là ATC-group: forecast ở mức ATC, không suy ra SKU.
3. **Kiểm định:** Data Admin xem `backtest_forecast_metrics` (MAE, RMSE, WAPE, Bias) so baseline; chỉ model vượt baseline mới được `APPROVED` (FR-SD-05).
4. **Điều chỉnh:** người có quyền sửa một giá trị forecast trong app (FR-SD-10). Giá trị gốc giữ ở `ml.forecast_sales`; bản sửa nằm ở app DB và `ml.forecast_adjustment`.
5. **Không làm:** coi sales là demand khi có stockout; dùng `customer_request_line.unmet_quantity` nếu có.

### MD-02 Inventory & Expiry

1. **Monitoring:** `mart_inventory_position` (FR-MD02-01, 02), movement (03), lot expiry (04).
2. **Risk:** `risk_stock_projection` theo scenario: tồn + incoming MD-03 − forecast MD-01 (FR-MD02-05).
3. **Optimization:** `fefo_candidate_lots` là thứ tự ưu tiên trong lô đủ điều kiện (FR-MD02-06). GP0 `NO_ACTION` luôn là một scenario để so (FR-MD02-08).
4. **Approval:** QA (US-13) quyết hold/release/recall trong app (FR-MD02-09). Databricks không đổi trạng thái lô.
5. **Chuyển tín hiệu:** risk signal gửi MD-03 (mua) hoặc MD-04 (điều chuyển) qua payload có `signal_id`, product, location, scenario (FR-MD02-11).
6. **Outcome:** KPI theo mục 6 của `REQUIREMENTS_INVENTORY_EXPIRY_V1.md`; thiếu mẫu số → "chưa đánh giá được".

### MD-03 Mua hàng & NCC

1. **Monitoring:** `mart_po_tracking` với 4 lượng đặt / xác nhận / nhận / đạt QC (FR-MD03-13); scorecard (05); dashboard theo vai trò (18, 23–26).
2. **Cảnh báo:** PO trễ (kể cả ETA mới), giao thiếu, chứng nhận NCC sắp hết hạn (27, 28) → `fact_alert` trong app.
3. **Insight:** `net_purchase_need_input` = forecast − tồn khả dụng − hàng đang về − phần dư ở kho khác **chưa giữ chỗ** + nhu cầu chưa đáp ứng từ MD-04 + tồn an toàn (06, 21). Chưa có forecast MD-01 thì dùng baseline mùa vụ và ghi rõ là baseline. Chỉ đặt về kho tổng hoặc kho vùng.
4. **Optimization:** gợi ý NCC: giải pháp 1 chấm điểm đa tiêu chí (trọng số mặc định giá 35 %, lead time 25 %, tin cậy 25 %, chất lượng 15 %), giải pháp 2 tối ưu chi phí tổng (08, 09). Hàng lạnh chỉ xét NCC có chứng nhận phạm vi lạnh. SKU chưa có bảng giá thì báo thiếu dữ liệu.
5. **Approval:** người mua xác nhận hoặc điều chỉnh nhu cầu, kèm lý do (07, 22); US-13 thẩm định NCC (03). Lưu trong App DB.
6. **Không làm:** tạo, sửa, hủy PO; ghi nhập kho; đối soát hóa đơn. Chọn NCC không có nghĩa PO đã phát hành.
7. **Phần thiếu chuyển kỳ sau:** NCC từ chối, giao thiếu, lô bị từ chối cộng vào kỳ sau.

### MD-04 Phân phối

1. **Monitoring:** `imbalance_signal` thiếu / dư / cận date (FR-MD04-01); `mart_transfer_tracking` (16); `mart_trip_daily` (21, 22).
2. **Chặn dữ liệu cũ:** điểm có heartbeat quá ngưỡng thì không tạo đề xuất cho điểm đó.
3. **Optimization:** `transfer_candidate_input` → heuristic (03) hoặc MILP (04). Kèm chi phí ước tính, ETA, lý do (05). Chỉ lô khả dụng, hạn dùng tại ETA ≥ ngưỡng; loại lô bị giữ / thu hồi; hàng lạnh cần xe lạnh. Không gọi là "tối ưu" khi chưa chốt objective / constraint / horizon.
4. **Phản hồi:** US-03 chấp nhận, sửa lượng hoặc từ chối đề xuất, kèm lý do (27) → KPI tỷ lệ chấp nhận.
5. **Approval:** dòng kiểm soát đặc biệt do US-13 duyệt từng dòng trước; cấp 1 do quản lý điểm nguồn; cấp 2 (liên vùng hoặc vượt ngưỡng giá trị) do US-10 hoặc US-01 (09–12). Không ai tự duyệt yêu cầu mình tạo. Mức khẩn có SLA (ví dụ mức 1: 15 phút). Cần nhóm chốt người duyệt thay và ngưỡng cấp 2.
6. **Giữ chỗ và phiếu:** duyệt xong thì giữ chỗ lô có hạn; gộp yêu cầu cùng nguồn thành phiếu (28, 41) và gửi bên liên quan (29).
7. **Vận chuyển (04b):** gom phiếu thành chuyến, gợi ý tuyến NN/savings hoặc VRPTW (17–19). Theo dõi ETA, trễ, lệch nhiệt 2–8 °C, mất GPS từ sự kiện 3PL (21, 37, 43). Chi phí là ước tính, không phải cước thật. Không quản lý xe, tài xế.
8. **Thực thi:** xuất / nhận thật ở WMS. Databricks thấy kết quả qua `inventory.stock_transfer*` lần nạp sau.
9. **Chuyển tiếp:** `unmet_after_transfer` gửi sang MD-03.

### Kịch bản kiểm thử dữ liệu (issue #7)

Bộ dữ liệu sim phải có đủ các ca sau trước khi nghiệm thu Gold MD-03/MD-04:

| MD-03 | MD-04 |
|---|---|
| SKU đủ tồn, không cần mua | Điểm thiếu, có nguồn dư ở gần |
| SKU cần mua, có 3 NCC để so | Nguồn duy nhất là lô cận date |
| SKU có dư ở kho khác, phải trừ phần điều chuyển | Hàng lạnh, nguồn không có xe lạnh |
| NCC có GDP sắp hết hạn | Yêu cầu có dòng kiểm soát đặc biệt |
| PO giao thiếu | Liên vùng hoặc vượt ngưỡng, cần cấp 2 |
| PO trễ | Yêu cầu bị từ chối; bị hủy trước khi duyệt |
| Lô nhận về bị QC giữ | Khẩn mức 1, SLA 15 phút |
| Hàng lạnh chỉ đặt được ở NCC đủ điều kiện lạnh | Hai yêu cầu cùng nguồn gộp một phiếu |
| Bảng giá theo thùng, cần quy đổi sang đơn vị bán | Chuyến nhiều điểm có khung giờ (VRPTW); chuyến trễ |
| SKU chưa có bảng giá | Lệch nhiệt; mất GPS; lô bị giữ / thu hồi bị loại; tồn ở điểm nhận quá cũ bị chặn |

Số lượng bản ghi cụ thể còn chờ nhóm thống nhất.

### MD-05 Đấu thầu (chạy chủ yếu trong platform)

Theo yêu cầu dữ liệu MD-05/06, các bước 1, 2, 4, 5 diễn ra trong app và App DB. Databricks chỉ tham gia bước 3 (cấp dữ liệu) và bước 6 (đọc lại để đo).

| Bước | Ở đâu | Việc |
|---|---|---|
| 1 | App + S3 platform | Tải PDF (có lớp chữ hoặc scan), lưu phiên bản; trích xuất dòng thuốc kèm trang, trạng thái `PROPOSED`; nhân viên xác nhận (FR-T01, T02) |
| 2 | App | Đối chiếu dòng thuốc ↔ SKU qua `gold_md05_tender.tender_sku_reference`; chỉ dùng liên kết / quy đổi đã xác nhận (T03) |
| 3 | App đọc Gold | Phân tích cung ứng: lượng yêu cầu so `tender_supply_input` (tồn khả dụng), `tender_incoming_supply`, `tender_forecast_input`, lead time; lưu giả định và kết quả kịch bản ở App DB (T04) |
| 4 | App | Kiến nghị và quyết định nội bộ có người duyệt (T05, T09) |
| 5 | App | Ghi kết quả trúng có căn cứ theo mặt hàng / số lượng (T06); ghi từng đợt giao thực tế và lượng còn giao (T07) |
| 6 | Databricks đọc `bronze_app` | Trừ cam kết tender khỏi tồn khả dụng cho MD-03/MD-04; KPI trúng ↔ giao |

Không suy ra kịch bản được chọn đã trúng; không nhầm lượng trúng với lượng đã giao. Lập / nộp hồ sơ và quản lý hợp đồng nằm ngoài module.

Kịch bản kiểm thử tối thiểu (cùng SKU / đơn vị giữa các bảng): đủ hàng; thiếu hàng; dòng thuốc cần quy đổi / đối chiếu; dữ liệu thiếu hoặc chưa xác nhận.

### MD-06 Quản trị (toàn bộ trong platform)

Đơn vị / phạm vi GLOBAL-REGION-STORE, tài khoản giả lập, role-permission, gán role-scope và audit đều ở App DB. Backend kiểm quyền và lọc dữ liệu theo scope ở server trước khi trả kết quả đọc từ Gold. Databricks không giữ thông tin đăng nhập.

## 4. Hai lớp đánh giá

| Lớp | Câu hỏi | Bảng | Chỉ số |
|---|---|---|---|
| Prediction Quality | Dự báo đúng tới đâu? | `ml.backtest_forecast_metrics` | MAE, RMSE, WAPE, Bias |
| Decision Quality | Quyết định có tốt hơn không? | `ml.decision_eval` | stockout rate, fill rate, avg inventory, overstock, expiry/wastage, simulated cost |

Forecast tốt hơn không tự động cho quyết định tốt hơn. Mỗi lần đổi model phải chạy lại cả hai lớp. Kết quả trên dữ liệu synthetic ghi rõ "mô phỏng".

## 5. Điều kiện phát hành một data product

| # | Điều kiện |
|---|---|
| 1 | Contract có grain, khóa, owner, độ mới, consumer, giới hạn |
| 2 | Silver input đạt DQ, không có lỗi FAIL |
| 3 | Reconciliation Gold ↔ Silver khớp |
| 4 | `provenance_class` có trên mọi dòng |
| 5 | Owner miền xem và ký nhận lần đầu |
| 6 | Ghi `ops.product_release(product, version, as_of_date, published_at, run_id)` |

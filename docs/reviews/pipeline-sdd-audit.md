# Đánh giá lại SDD Databricks Pipeline — 16/11/2026

**Đối tượng:** `src/pipeline/databricks/SDD.md`, phiên bản v1.0, 358 dòng; kèm README và ba YAML hiện có.

**Kết luận:** hướng kiến trúc phù hợp PharmaFlow DSS, nhưng SDD hiện là bản thiết kế khái quát, **chưa đủ làm đặc tả để hiện thực và nghiệm thu**. Cần sửa contract Weather, thứ tự tính forecast/risk, định nghĩa GP1/GP2 và các bảo đảm snapshot/release/giữ chỗ trước khi triển khai các miền phụ thuộc tồn kho. Khung bundle cũng chưa sẵn sàng chạy. Đánh giá này không thay đổi quyết định kiến trúc, SDD hay mã nguồn.

## 1. Phạm vi và bằng chứng

- Kiểm kê **10.659 tệp** trong cây dự án tại thời điểm bắt đầu audit; bao gồm nội dung ignored/untracked ngoài các thư mục loại trừ. Phân bố: `dataset/` 8.102; `jobs/` 1.275; `src/` 446; `docs/` 144; `artifacts/` 106; `tests/` 23; `scripts/` 17. Chi tiết trong [evidence.json](evidence.json).
- Loại trừ dependency/browser/Git/worktree nội bộ: `.git`, `.venv`, `node_modules`, `.playwright-browsers`, `.sites-checkout`, `.agent` và `__pycache__`. Không mở secret/config credential như `.env`, không quét nội dung dependency.
- Lập danh sách **139 tệp code/config/tài liệu** thuộc `src/`, `scripts/`, `tests/` ngoài `runs/`; parse AST **55 tệp Python**, không có lỗi cú pháp. Kiểm tra sâu pipeline, source DDL/config/loader/README, Weather producer/contract/tests, MongoDB contract, kiến trúc, MDD, AppDB DDL và đặc tả MD-01…MD-06.
- Đối chiếu hồ sơ dataset, dictionary, run metadata và góp ý cuộc họp 14/11. Kiểm kê toàn cây không đồng nghĩa đọc từng byte CSV/XLSX/PDF/raw HTML hoặc xác minh mọi số liệu trong mỗi run lịch sử; các nguồn này được xem theo contract và bằng chứng liên quan đến SDD.
- Không gọi DB/AWS/Databricks để xác minh deployment hiện thời; không chạy deploy, job cloud, loader hay migration. Các số lượng DB trong README/run lịch sử chỉ được dùng như bằng chứng có ngày, không phải số đo live ngày 16/11.
- Git HEAD lúc rà soát: `9a1d855`. Trước audit đã có HTML prototype bị sửa, hai prototype v2/v3 untracked và toàn bộ `src/pipeline/` untracked; giữ nguyên trạng thái này.

### Hiện trạng thực thi

| Thành phần | Quan sát được | Có thể kết luận |
|---|---|---|
| Pipeline | SDD, README, 3 YAML, 6 `__init__.py`; Silver/Gold chưa có transform | Scaffold; chưa có pipeline thực thi |
| Job entry points | 9 lần tham chiếu tới 8 script Python khác nhau, đều chưa tồn tại | Chưa thể chạy các task khai báo |
| Pipeline libraries | Hai `file.path` trỏ vào thư mục Silver/Gold, không phải tệp source | Cấu hình cần sửa trước validation/deploy |
| PostgreSQL upstream | Canonical DDL có 35 `CREATE TABLE`; loader, mapping và run evidence | Có source package; không suy ra cả 35 bảng đã có dữ liệu |
| MongoDB upstream | Importer, schema validator, snapshot contract và test offline | Có source implementation; audit này không xác nhận live collection |
| Weather upstream | Có producer, tests, Terraform và ledger lịch sử | Không còn chỉ là ý tưởng; quyền reader Databricks chưa được audit live |
| AppDB | DDL địa phương 59 bảng và tài liệu `PROPOSED TARGET DESIGN` | Có mô hình đề xuất; chưa phải runtime/deployment |
| Backend / forecasting độc lập | `src/forecasting/`, `src/common/` hiện chỉ `.gitkeep`; không có backend theo target được chứng minh | Không có consumer/runtime để kiểm thử end-to-end |

### Phần SDD nên giữ

Giữ ranh giới upstream → Databricks → backend/API + AppDB; tách năm miền nghiệp vụ; Gold là data product chứ không ghi sổ WMS/ERP; người có thẩm quyền duyệt quyết định; tách sales line với aggregate observation; giữ provenance; temporal backtest có baseline; tách Prediction Quality và Decision Quality. Lựa chọn EJSONL cho Mongo có căn cứ trong MDD, không phải tự thân một sai lệch.

## 2. Phát hiện cần sửa trước triển khai

Mức **P0**: có thể đọc sai nguồn, tính sai hoặc công bố dữ liệu không nhất quán. **P1**: thiếu đặc tả/đầu nối quan trọng để hiện thực và vận hành. **P2**: làm rõ trạng thái, traceability và phạm vi nghiệm thu. Các lỗi dưới đây là lỗi/thiếu sót của thiết kế và scaffold; không khẳng định đã xảy ra sự cố production.

### F01 — P0 — Contract Weather lệch producer đang có

**Vị trí:** SDD:176–178, 229–233; MDD `01-nguon-va-module.md`:53–58 cũng mang cùng sai lệch.

SDD đọc `raw/open_meteo/daily_forecast/` và lọc `source_type='DAILY_FORECAST'`. Trong code, `src/weather/planner.py`:34–42 quy định prefix **`raw/open_meteo/weather_forecast/`**, loại **`FORECAST`**; `daily_forecast` là giá trị `mode`. Áp dụng nguyên SDD sẽ bỏ sót dữ liệu hoặc sinh tập weather rỗng.

Quy tắc “folder có accepted.json” chưa đủ: `accepted.json` nằm ở `tasks/<task_id>/`; response/metadata nằm dưới `attempts/<attempt_id>/` và marker chỉ đích danh `response_key`, `metadata_key`, `raw_sha256` (`worker.py`:165–167, 268–278). Đọc tất cả attempt khi thấy marker sẽ nhập cả attempt thất bại.

**Sửa:** lấy marker làm danh sách đầu vào; chỉ đọc đúng hai key được trỏ tới; xác minh SHA-256 trên bytes response gốc; dedup theo identity nguồn/task/attempt; giữ `validation_status`, `null_report` và contract version. Bổ sung ba nhánh `FORECAST`, `HISTORICAL_FORECAST_STITCHED`, `HISTORICAL_ERA5_REANALYSIS`; backfill không khôi phục snapshot từng có ở cutoff lịch sử. Test phải phủ một task có nhiều attempt, checksum sai, orphan và replay.

### F02 — P0 — DAG xây Gold phụ thuộc forecast trước scoring

**Vị trí:** SDD:100–106, 204–219, 270–278; `resources/jobs.yml`:52–66.

`risk_stock_projection`, `net_purchase_need_input`, `tender_forecast_input` cần forecast, nhưng DAG hiện là `gold → score_forecast → publish`. Lần đầu thiếu forecast; lần sau có nguy cơ ghép inventory mới với forecast cũ. Task tạo feature cũng chưa được thể hiện giữa sales mart và scoring.

**Sửa đề xuất:** tách dependency rõ ràng: Silver → Gold nguồn/lịch sử không phụ thuộc forecast (sales, inventory base, incoming supply) → feature → score → Gold risk/procurement/tender phụ thuộc forecast → kiểm tra release → publish. Không gọi lại cùng pipeline chứa cả đầu vào và đầu ra forecast nếu chưa tách ownership/đồ thị. Mọi đầu ra phải ghép đúng `forecast_run_id`, source snapshots và release. Đây cũng là lỗi đã có trong DAG mẫu của MDD, cần sửa tại nguồn thiết kế khi được giao cập nhật.

### F03 — P0 — Định nghĩa GP1/GP2 sai đặc tả MD-02

**Vị trí:** SDD:211; đối chiếu `jobs/W2.11/FEFO_AND_INVENTORY_POLICY_SPEC_V1.md`:166–184.

SDD gọi GP1 “Điều phối nhanh”, GP2 “Bổ sung khẩn cấp”. Contract MD-02 quy định **GP1 = static min–max + FEFO**, **GP2 = forecast ROP/safety stock + FEFO**. GP0 còn phân biệt `NO_ACTION` với `CURRENT_PRACTICE_EVIDENCED`; thiếu bằng chứng thì mode thứ hai là `NOT_ASSESSABLE`.

**Sửa:** dẫn trực tiếp policy spec, giữ đúng ID/ý nghĩa; khai báo horizon, lead time, review interval, min/max, phương pháp safety stock và common inputs. Thiếu tham số không tự tạo kết quả. Tách chính sách tồn kho khỏi nhãn khẩn cấp điều chuyển. Nghiệm thu so ba chính sách trên cùng input, FEFO, treatment của inbound và cách tính outcome.

### F04 — P0 — Append full snapshot chưa có giao thức chọn snapshot hoàn chỉnh

**Vị trí:** SDD:154–158, 170–172, 184–200.

35 bảng được JDBC full snapshot rồi append hằng ngày, nhưng chưa quy định tập bảng hoàn tất, visibility boundary, tính nhất quán giữa bảng, row count/hash, retry và delete. Lấy toàn bộ Bronze sẽ nhân bản sales; lấy “bản mới nhất theo từng PK” có thể giữ lại record đã bị xóa hoặc trộn các lần nạp. `_ingest_date` được dùng làm partition nhưng chưa được khai báo trong bộ cột bắt buộc.

**Sửa:** contract run/table manifest có version, cutoff, trạng thái hoàn tất và kiểm đếm; Silver chỉ đọc snapshot được chốt, không đọc run dở. Phân biệt logical snapshot ID với task attempt để retry không tăng dữ liệu. Quy định cách giữ cùng source snapshot khi JDBC dùng nhiều connection, hoặc ghi rõ giới hạn consistency pilot. Quy định record biến mất, hash serialization và precision/null/timezone. Acceptance: nạp lại cùng snapshot không đổi tổng sales; fail giữa 35 bảng không làm Silver chuyển bản; delete và cập nhật chạy đúng.

### F05 — P0 — `product_release` chưa bảo đảm đọc nhất quán nhiều bảng

**Vị trí:** SDD:281–289; AppDB DBD `01-kien-truc-va-quan-he-databricks.md`:§2.

Ghi một watermark sau khi score xong chưa đủ đóng băng bảng Gold đã thay đổi trước đó. Backend đọc bảng “latest” có thể thấy một phần release mới trong khi registry vẫn chỉ release cũ. Record minh họa còn thiếu `product_name`, trong khi AppDB registry đồng bộ theo product.

**Sửa:** chốt cơ chế publication: dữ liệu có `release_id` và query bắt buộc lọc theo release, hoặc manifest pin Delta versions/immutable outputs. Manifest phải liên kết từng product, source snapshot, forecast/model version, DQ, thời điểm nguồn, provenance và trạng thái. Chỉ chuyển pointer sau khi tất cả dependency bắt buộc đạt; có đường giữ/khôi phục bản cũ và đồng bộ metadata sang AppDB. Test fail sau khi một product hoàn tất: API vẫn đọc nguyên release trước.

### F06 — P0 — Công thức khả dụng thiếu điều kiện chống trừ trùng giữ chỗ/cam kết

**Vị trí:** SDD:119, 208–210; source DDL:779–782; AppDB DDL:559–573, 876–890.

`unreserved` đã là on-hand trừ reserved ở nguồn; `restricted_quantity=NULL` nghĩa chưa biết, không phải zero. AppDB có `review.stock_reservation.reservation_source='MD05_TENDER'` và `tender_commitment.reservation_id` trỏ tới cùng reservation. Nếu trừ cả hai bảng sẽ trừ cam kết tender hai lần. Công thức SDD chưa chỉ ra lớp nào sở hữu khoản trừ, hiệu lực/thời điểm chốt, lượng còn lại hay trường hợp nguồn WMS đã phản ánh reservation.

**Sửa:** lập bảng quantity lineage theo location/product/lot/UOM/as-of; đối soát source reservation, AppDB reservation và tender commitment bằng reference; chỉ trừ phần nghĩa vụ chưa phản ánh ở nguồn, đúng một lần. Xét trạng thái active, expiry reservation, remaining commitment, QC/recall, expiry chưa biết và freshness. Batch ngày chỉ hỗ trợ phân tích; kiểm tra tại thời điểm phê duyệt/giữ chỗ và concurrency thuộc backend/AppDB, không được suy ra batch ngăn giữ trùng tức thời.

## 3. Thiếu sót quan trọng về thiết kế và triển khai

### F07 — P1 — Vòng `bronze_app` không có task và cursor quá sơ lược

SDD:179–182 mô tả `app_sync.py`, nhưng `jobs.yml` không có task này và DAG Silver không có dependency AppDB. Promotion, adjustment, policy và decision evaluation vì vậy chưa có đường dữ liệu được khai báo. Nói “updated_at hoặc id” cũng yếu hơn contract DBD §2: **`(updated_at, primary_key)`** cho mutable table, ID cho append-only.

**Sửa:** bổ sung task/dependency có điều kiện khi app được triển khai; whitelist bảng/cột theo DBD thay vì `review.*`/`ops.*`; cursor composite, upper bound, overlap/reconciliation, dedup và watermark chỉ advance sau commit. Phải có quy ước update timestamp và delete: DDL `DEFAULT NOW()` tự nó không cập nhật timestamp khi UPDATE. Giữ hash/snapshot chứng cứ; không ingest password, session token hay cache UI. Chưa có AppDB thì đánh dấu khả năng phụ thuộc chưa sẵn sàng, không tạo bản ghi quyết định giả.

### F08 — P1 — Chuẩn hóa toàn bộ sang giờ Việt Nam làm lệch ngày nguồn

SDD:30, 187 áp `Asia/Ho_Chi_Minh`; nguồn IRPD dùng `Asia/Jakarta`, Onyx có 8 timezone châu Âu, Pharma Sales dùng `Europe/Belgrade`. Contract MDD:§4 yêu cầu lấy timezone theo location, không ép tất cả về Việt Nam. Giao dịch sát nửa đêm có thể chuyển ngày; weather/sales join sai ngày và DST.

**Sửa:** lưu UTC instant và local date/time theo `org.store.timezone_name`; warehouse có timezone hoặc quy tắc kế thừa được xác nhận; giờ VN chỉ dùng cho lịch điều phối chung khi phù hợp. Gold cần contract UOM/currency: không cộng quantity khác đơn vị hoặc tiền khác currency; thiếu conversion giữ null, không suy `base_qty`. Kiểm thử UTC-boundary, DST và quantity có UOM chưa rõ.

### F09 — P1 — Ba nhãn provenance chưa đủ thay cho mapping nguồn và trạng thái mapping

SDD:159–163 có ý định đúng, nhưng chưa định nghĩa map `source`, `data_origin`, `evidence_status` sang provenance. `ONYX_CHALLENGE_DAILY_SALES_FACT_UNVERIFIED` khác POS `SIMULATED_ONYX_DAILY_FACT_TO_POS`; taxonomy mapping `assignment_status=CANDIDATE` là mức xác nhận liên kết, không phải cùng chiều với nguồn dữ liệu thật/mô phỏng. MDD đưa `CANDIDATE` vào enum provenance, còn SDD bỏ mà không giải thích cách bảo toàn.

**Sửa:** giữ raw source code và evidence status; registry mapping có version; giữ `assignment_status` riêng. Aggregate bảo toàn lineage tới source và không coi POS sinh từ observation là một dòng bán quan sát thứ hai. Khóa/grain mart cần chỉ rõ source/series và UOM khi provenance label không phân biệt hết series. Unknown mapping phải được cảnh báo hoặc chặn, không tự nâng thành `OBSERVED`.

### F10 — P1 — SCD2 chưa nối đúng với full snapshot và lịch sử as-of

SDD:190 dùng `AUTO CDC ... SCD TYPE 2`, sequence `_ingested_at`, trong khi đầu vào PG là full snapshot. Không mô tả diff → CDC, xử lý deletes, tracked business columns hay effective/system time; dùng lại cột audit làm trigger có thể tạo version giả. `product_id` là business key, chưa đủ mô tả version key và fact-to-dimension join. Giá không tự nằm trong bảng `catalog.product`.

**Sửa:** chọn rõ snapshot differencing hoặc `AUTO CDC FROM SNAPSHOT`, business/version key, thứ tự snapshot và join as-of; loại cột audit khỏi so sánh thay đổi nghiệp vụ; xác định thuộc tính nào thực sự có ở nguồn. Databricks phân biệt API CDC feed và API snapshot; edition/runtime phải được chốt trước khi chọn cú pháp. [Tài liệu AUTO CDC chính thức](https://docs.databricks.com/aws/en/ldp/cdc).

### F11 — P1 — ML lifecycle chưa có output contract và protocol đủ tái lập

SDD:223–255 chưa chốt target sales quantity hay demand, series/cohort, train window, origin/horizon, label availability, gap/missing/zero, promotion gate và fallback khi chưa có champion. Tên `forecast_sales` nhưng nội dung có chỗ gọi “dự báo cầu”; nguồn POS/ATC không chứng minh latent demand. Lags 7/14/21/28 là lựa chọn đề xuất, chưa có protocol so sánh. Có baseline là tốt nhưng chưa có cùng fold/actuals/denominator và cách xử lý WAPE khi tổng actual bằng zero.

Lọc weather theo `retrieved_at <= origin` tránh một lớp leakage, nhưng dữ liệu sales 2014–2025 có weather tải năm 2026; stitched/reanalysis không tự trở thành weather từng biết ở origin cũ. Cần chế độ thử nghiệm được gắn nhãn, sales-only baseline và coverage/fallback cho horizon 30 ngày trong khi daily Weather cung cấp 16 ngày. Sales `local_date < origin` cũng chưa đủ xử lý late-arriving/corrected data; cần tách thời điểm sự kiện và thời điểm dữ liệu sẵn có theo protocol.

**Sửa:** contract forecast tối thiểu có `forecast_run_id`, target/series/location, `forecast_origin`, `target_date`, horizon, UOM, provenance, source snapshots, feature cutoff, model/baseline version và loại output. P10/P50/P90 là quantile, cần phương pháp tạo và kiểm calibration/coverage, không chỉ yêu cầu có cột. Daily job phải có task feature hoặc tuyên bố rõ scoring tạo feature thế nào; weekly job phải nối backtest và hồ sơ kiểm định. Alias champion chỉ promotion qua worker được cấp quyền, lưu bằng chứng review ở AppDB; override giữ output gốc và version điều chỉnh riêng. Decision evaluation phải có simulator/observed outcome source, policy version, common inputs và giới hạn kết luận; không suy tác động nhân quả từ approval/override log.

### F12 — P1 — Readiness chưa độc lập theo module và có xung đột với preflight

SDD:282 bắt toàn job dừng khi Mongo/S3 hôm nay không sẵn sàng, nhưng 285 hứa từng module có thể bị skip riêng. YAML nối cả ba Bronze bắt buộc vào Silver; forecast fail cũng chặn publish mọi product. `NOT_READY` vì “chưa nạp dữ liệu mô phỏng” chưa phân biệt nguồn thật hợp lệ, bảng rỗng hợp lệ, thiếu coverage, nguồn stale và DQ fail.

**Sửa:** ma trận product → nguồn bắt buộc/tùy chọn → checks → fallback/độ cũ cho phép → quyền publish; tách preflight hạ tầng chung khỏi readiness miền. Chốt cách conditional execution được truyền vào declarative pipelines, không chỉ ghi trạng thái rồi giả định Gold tự bỏ qua. Lịch 06:30/07:15 là mục tiêu đề xuất; existence của prefix hôm nay không chứng minh đủ accepted tasks/summary. Chưa đo duration thì chưa bảo đảm scoring đúng 07:15.

### F13 — P1 — Bundle YAML parse được nhưng chưa đúng hợp đồng triển khai

**Vị trí:** `databricks.yml`:16–24; `pipelines.yml`:5–18; toàn bộ Python tasks trong `jobs.yml`.

- Pipeline thiếu trường `catalog`; `target` đang mang chuỗi `catalog.schema` trong khi target là schema. Cần chọn `catalog` và `schema`/target đúng mô hình UC đã chốt, đồng thời quy định qualified outputs cho nhiều schema.
- `libraries.file.path` trỏ thư mục. Dùng file thật hoặc `glob.include` cho cây source khi phiên bản CLI hỗ trợ. `development: true` hiện áp cả prod.
- `workspace.host: https://${workspace.host}` tự tham chiếu host; chưa có endpoint/profile được xác minh. Cần cấu hình host/profile thật hoặc để auth context cung cấp, rồi validate bằng CLI đã pin.

Các trường catalog/schema và file/glob được mô tả trong [resource reference chính thức](https://docs.databricks.com/aws/en/dev-tools/bundles/resources). Đây là đối chiếu tĩnh; chưa có output `bundle validate` để gán một thông báo lỗi CLI cụ thể.

Python tasks chưa chọn classic compute hoặc serverless environment. Nếu serverless, cần `environment_key` và environment spec theo [bundle examples](https://docs.databricks.com/aws/en/dev-tools/bundles/examples); nếu classic cần cấu hình compute tương ứng. Thiếu pin CLI/runtime, dependencies Spark/MLflow/model, config/secret references và luồng truyền catalog/run context tới scripts. `--run-id` mới được truyền cho Bronze PG; chưa có giao thức chung cho các task. Không nên deploy để “thử” trước khi giải quyết các thiếu sót này.

### F14 — P1 — Danh mục product bị rút gọn nhưng chưa ghi rõ hoãn phạm vi

SDD bỏ `bronze_sim`, landing/checkpoints, `ref_travel_matrix`, `ref_service_profile` dù MD-04:217 cần travel matrix. Cũng thiếu nhiều đường lineage cụ thể cho heartbeat, customer-request, quality/recall/return, incoming supply, certificate/price/PO confirmation. Một số bảng nguồn MDD yêu cầu bổ sung chưa tồn tại trong canonical 35 bảng; `dataset/md04-transfer-transport-sim` và `jobs/W13.11/md03-md04-data-readiness/DATA_READINESS.md` hiện không có trong workspace.

**Sửa:** không cần hiện thực tất cả ngay; cần matrix từng product với input hiện có/thiếu/đề xuất, grain/key/cột/time/UOM/owner/freshness/DQ/consumer và milestone. Silver snapshot như inventory balance phải có snapshot/as-of semantics thay vì chỉ đổi tên `fact_` rồi bỏ thời điểm. Góp ý họp 14/11 yêu cầu tách thiết kế luận lý/vật lý và Star Schema: danh sách tên mart trong SDD chưa thay được fact/dimension design. Việc vẽ/sửa diagram là hạng mục riêng theo skill của repo, chưa thực hiện trong audit này.

### F15 — P1 — Serving thiếu quyền đọc release và đường kiểm định/promotion

SDD:289 yêu cầu backend đọc `ops.product_release`, nhưng 300 chỉ cấp SELECT `gold_*` và `ml.forecast_sales`; quyền đọc release/control metadata chưa được mô tả. UI Data Admin cần hồ sơ backtest/kiểm định, trong khi cùng reader không có đường đến `ml.backtest_forecast_metrics`; hành động duyệt champion cũng cần một executor có quyền riêng, không thể suy ra từ reader chỉ đọc.

**Sửa:** lập role/use-case/access matrix cho serving data, release registry, validation evidence và promotion worker; ghi quyền catalog/schema/warehouse tương ứng khi triển khai. Nếu backend chỉ đọc registry trong AppDB thì phải chỉ rõ dịch vụ đồng bộ metadata nào được đọc release phía Databricks. Scope filtering phải fail closed, dùng query templates/parameters và bao phủ join/drilldown/cache/snapshot; không chỉ nối chuỗi `WHERE location_id IN (...)`. Làm rõ `location_id` với `location_key` phân biệt STORE/WH theo MDD.

## 4. Bổ sung để SDD có thể nghiệm thu

### F16 — P2 — Trạng thái đề xuất và thứ tự ưu tiên tài liệu chưa rõ

README pipeline nói “chứa toàn bộ mã nguồn”, SDD dùng nhiều câu như đã hiện thực, nhưng chỉ có scaffold. MDD và AppDB README đều tự ghi đề xuất; kiến trúc canonical vẫn ghi Weather chưa có ingestion, AppDB chưa có schema, trong khi code Weather và DBD đã tiến thêm. Không nên kết luận mọi chi tiết mới trong SDD là sai chỉ vì chưa có ở kiến trúc cũ; cũng không được biến đề xuất mới thành quyết định đã duyệt.

**Sửa:** đầu SDD có bảng `confirmed decision / proposed design / implemented locally / verified deployed`; source-of-truth theo từng lĩnh vực, ngày và unresolved conflicts. Weather producer/contract sở hữu literal runtime; MD-02 policy sở hữu GP definitions; AppDB sở hữu workflow state; MDD và SDD đề xuất cấu trúc Databricks. Link yêu cầu FR/BR/AC vào từng contract/test. Tất cả **11 liên kết Markdown tương đối** trong SDD/README hiện resolve tới tệp tồn tại; không có lỗi đường dẫn được phát hiện trong tập này.

### F17 — P2 — DoD chưa phân tầng và chưa có bộ test pipeline

SDD:348–358 gộp “đủ 35 bảng”, đủ 5 miền, model registry, quantile và API <2 giây thành một đợt nghiệm thu trong khi nguồn tồn/mua/transfer chưa đủ. `DROP ROW` có thể làm mọi dòng còn lại đạt EXPECT mà không cho biết đã mất bao nhiêu dữ liệu. Không có test body trong `src/pipeline/databricks/tests`; mục tên CI/CD mới chỉ là lệnh CLI, chưa có workflow tự động trong `.github`.

**Sửa:** DoD theo milestone: config/source contracts; Bronze idempotency/complete snapshots; Silver quality/lineage; một product + serving release; forecast baseline/backtest; sau đó mở từng miền khi nguồn đủ. Quality metrics cần input/output/drop/quarantine counts, reconciliation và ngưỡng được chốt, không chỉ “100% dòng còn lại pass”. NFR latency phải nêu workload, số concurrent user, cold/warm, p95 và timeout; <2 giây chưa có bằng chứng. Thêm recovery/backfill/runbook, retention, checkpoint isolation và rollback tests phù hợp.

## 5. Kết quả kiểm tra tại lượt audit

| Kiểm tra | Kết quả quan sát | Giới hạn |
|---|---|---|
| Python AST của code first-party thuộc phạm vi trên | 55 tệp parse thành công | Không chứng minh dependency/runtime hoặc logic đúng |
| YAML pipeline | 3 tệp parse được bằng PyYAML | Không phải `databricks bundle validate` |
| Task/library references | 9 Python task references chưa có file; hai library references là folder | Xem [evidence.json](evidence.json) |
| Liên kết Markdown SDD/README | 11/11 trỏ đến tệp tồn tại | Không kiểm mọi anchor/URL bên trong tài liệu được dẫn |
| `.venv/Scripts/python.exe -B -m pytest tests/weather -q -p no:cacheprovider` | **137 passed**, 5,22 giây | Offline; không xác minh scheduler/S3 live |
| `.venv/Scripts/python.exe -B -m pytest src/synthetic_data_source/mongodb/test_product_knowledge.py -q -p no:cacheprovider` | **11 passed**, 1,41 giây | Offline; không xác minh Mongo live |
| `.venv/Scripts/python.exe -B -m pytest src/pipeline/databricks/tests -q -p no:cacheprovider` | **no tests ran** | Không có evidence test cho pipeline |
| `.venv/Scripts/python.exe -B -m pytest src/synthetic_data_source/pharmaflow_source_postgre/tests/test_forecast_source_contract.py -q -p no:cacheprovider -k 'bootstrap_retains or bounded_sample_manifests or source_mapping_csvs'` | **2 passed, 1 failed, 4 deselected** | Failure là `MemoryError` khi `list(csv.DictReader(...))` đọc IRPD full `lines.csv` tại test:63,112; chưa chạy xong assertions tiếp theo, không kết luận data sai |
| Databricks CLI | `Get-Command databricks` không tìm thấy trong PATH | Chưa validate/deploy/run bundle; không kiểm CLI nơi khác hoặc workspace |

Không sửa test/source để làm kết quả audit xanh. Failure RAM được báo riêng; không phải bằng chứng SDD đã làm hỏng dữ liệu. Chi tiết máy đọc được của kết quả kiểm tra nằm trong [validation-results.json](validation-results.json).

## 6. Thứ tự sửa đề xuất

1. **Chốt semantics và contract:** F01, F03, F06, F08, F09; đối chiếu lại MDD/Weather producer và ghi các nguồn thiếu. Đầu ra review được: source contract, policy contract, quantity lineage và matrix provenance.
2. **Chốt dependency và publication:** F02, F04, F05, F07, F12; viết task inputs/outputs, snapshot/release protocol, conditional readiness và bootstrap khi chưa có AppDB/champion. Đầu ra: DAG specification và failure/retry examples.
3. **Hoàn thiện thiết kế vật lý và ML:** F10, F11, F14, F15; product dictionary, dimension/fact keys, forecast/evaluation schema, source availability protocol và serving access matrix.
4. **Sửa scaffold rồi chạy pilot giới hạn:** F13, F16, F17; pin môi trường và validate local/CLI trước. Pilot một lát cắt Sales và Weather có provenance rõ; không cần chờ đủ năm miền mới chứng minh một đường end-to-end. Sau đó mở Inventory/Procurement/Distribution/Tender theo readiness thực tế.

Mỗi bước phải cập nhật bằng chứng tương ứng; ghi SDD ở trạng thái **DRAFT — REQUIRES REVISION** tới khi các vấn đề P0 đã có contract và test nghiệm thu. Audit này chỉ tạo hồ sơ review trong `artifacts/reviews/2026-11-16-pipeline-sdd/`.

## 7. Nguồn đối chiếu chính

- [SDD pipeline](../../../src/pipeline/databricks/SDD.md), [bundle](../../../src/pipeline/databricks/databricks.yml), [jobs](../../../src/pipeline/databricks/resources/jobs.yml), [pipelines](../../../src/pipeline/databricks/resources/pipelines.yml).
- [System architecture](../../../docs/architecture/pharmaflow-system-architecture.md), [domain/module map](../../../docs/architecture/pharmaflow-domain-module-map.md), [data products](../../../docs/architecture/pharmaflow-data-products.md), [dictionary](../../../docs/data-model/Relations-DataSource/README.md).
- [MDD sources](../../../jobs/W9.11/MDD_vKiro/01-nguon-va-module.md), [Medallion design](../../../jobs/W9.11/MDD_vKiro/02-thiet-ke-medallion.md), [business flow](../../../jobs/W9.11/MDD_vKiro/03-quy-trinh-nghiep-vu.md), [technical flow](../../../jobs/W9.11/MDD_vKiro/04-quy-trinh-ky-thuat-databricks.md).
- [PostgreSQL source README](../../../src/synthetic_data_source/pharmaflow_source_postgre/README.md), [DDL](../../../src/synthetic_data_source/pharmaflow_source_postgre/schema_full.sql), `config/sources/*.yaml`, `scripts/source_prepare.py`, `scripts/source_db.py`.
- [MongoDB source contract](../../../src/synthetic_data_source/mongodb/README.md), [implementation](../../../src/synthetic_data_source/mongodb/product_knowledge.py).
- [Weather SDD](../../../src/weather/SDD.md), [planner](../../../src/weather/planner.py), [worker](../../../src/weather/worker.py), [backfill ledger](../../../src/weather/BACKFILL_AUDIT_PLAN.md).
- [MD-01 requirements](../../../jobs/W19.10/REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md), [MD-02 policy](../../../jobs/W2.11/FEFO_AND_INVENTORY_POLICY_SPEC_V1.md), [MD-03](../../../jobs/W9.11/md03-md04-usecase-v3/docs/4_sua_doi.md), [MD-04](../../../jobs/W9.11/md03-md04-usecase-v3/docs/5_sua_doi.md), [MD-05](../../../jobs/W9.11/module-05-tender/research/task/W07-yeu-cau-he-thong.md), [MD-06](../../../jobs/W9.11/module-06-system-admin/README.md).
- [AppDB status](../../../jobs/W9.11/DBD/README.md), [AppDB architecture](../../../jobs/W9.11/DBD/01-kien-truc-va-quan-he-databricks.md), [sync contract](../../../jobs/W9.11/DBD/03-truy-van-api-va-dong-bo-bronze-app.md), [local DDL](../../../jobs/W9.11/DBD/appdb_schema_full.sql).
- [Meeting feedback 14/11](../../../jobs/W16.11/W16.11_meeting_14.11_feedback_and_tasks.md). Các nguồn ngoài được trích ngay tại phát hiện F10/F13; chỉ dùng tài liệu Databricks chính thức, truy cập 16/11/2026.

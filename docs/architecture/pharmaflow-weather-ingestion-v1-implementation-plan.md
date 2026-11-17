# PharmaFlow Weather Ingestion v1.0 — kế hoạch Open-Meteo → S3

Ngày lập: 2026-11-07. Cập nhật sau P0 Open-Meteo Probe: 2026-11-10. Trạng thái: đã hoàn tất thăm dò API Open-Meteo (`jobs/W09.11/weather-openmeteo/`); S3 dev (Terraform) đã apply ngày 2026-11-11 với đủ 3 prefix (`src/infra/terrafrom/environments/dev/`); đã kiểm tra Neon live `org.store` (SELECT-only) và chốt cohort pilot 7 store; **P1 xong ngày 2026-11-12**: code `src/weather/` chạy được ở local (CLI + `LocalSink` ghi vào `.runtime/weather/`), `pytest tests/weather` đạt 84/84 (56 test gốc + 28 test phụ), smoke live thành công cho daily `daily-20261112-43a4ad4d` (store 516, 5404) và backfill vắt mốc 2022 `backfill-20261112-40918cf6` (ERA5 + GFS, store 516), `resume` gọi 0 HTTP, SHA-256 khớp; chi tiết xem [SDD mục 7.1](../../src/weather/SDD.md). **P2 xong ngày 2026-11-13**: CLI local chạy `--sink s3`, assume role least-privilege `pharmaflow-dev-weather-local-writer` (tạo bằng Terraform, chỉ có policy writer, `simulate-principal-policy` 15/15 đúng kỳ vọng) và ghi 18 object thật lên bucket dev cho daily `daily-20261113-7ab85399` và backfill vắt mốc 2022 `backfill-20261113-c992aa84`. Đọc ngược từ S3 thì SHA-256 khớp 4/4 task; `resume` gọi 0 HTTP và không tạo object mới; test offline 99/99. Chi tiết xem [SDD mục 7.2](../../src/weather/SDD.md). **P3 xong ngày 2026-11-13**: Terraform tạo 37 resource (3 Lambda, 5 SQS, 1 bảng DynamoDB, 2 lịch EventBridge **`DISABLED`**, 6 alarm, IAM); DSN Neon nằm ở SSM SecureString. Smoke live khi kích hoạt thủ công đạt 5/5 kịch bản: daily `daily-20261113-52f2a1fe` chạy qua SQS → Worker → Reconciler, backfill vắt mốc 2022 `backfill-20261113-543ad296`, SQS giao trùng gọi 0 HTTP, message độc vào DLQ sau 5 lần nhận và alarm chuyển `ALARM`, replay Planner không đọc Neon. Test offline 125/125. Chi tiết xem [SDD mục 7.3](../../src/weather/SDD.md). Chưa chạy tự động theo lịch (P4).

## 1. Kết quả cần bàn giao và phạm vi

Triển khai lấy locations từ Neon, gọi Open-Meteo theo các luồng dưới đây và lưu response gốc cùng metadata lên một S3 bucket để Databricks đọc sau này:

- Daily Forecast: `https://api.open-meteo.com/v1/forecast`, khởi động lúc 06:00 `Asia/Ho_Chi_Minh`, yêu cầu `forecast_days=16` (`models=gfs_global`).
- Historical Backfill (tự định tuyến theo mốc `2022-01-01`):
  - Từ `2022-01-01` trở đi: `https://historical-forecast-api.open-meteo.com/v1/forecast` (`models=gfs_global`, `source_type=HISTORICAL_FORECAST_STITCHED`).
  - Trước `2022-01-01` (`1940-01-01` → `2021-12-31`, ví dụ giai đoạn dữ liệu Pharma Sales 2015–2019): `https://archive-api.open-meteo.com/v1/archive` (ERA5 reanalysis, `source_type=HISTORICAL_ERA5_REANALYSIS`).
- Giữ mọi snapshot đã thu nhận; retry và replay có contract idempotency rõ ràng.
- Có CLI, hạ tầng dưới dạng code, run evidence, quota control, retry/DLQ và hướng dẫn vận hành.
- Đầu ra của giai đoạn này là raw S3 có thể truy xuất/đọc lại và kiểm chứng bằng checksum. Databricks, Silver/Gold, FE/BE và dự báo Sales là giai đoạn tiếp theo.

Nguồn yêu cầu: bản Weather v1.0 người dùng cung cấp ngày 2026-11-07 (cập nhật mở rộng định tuyến `< 2022-01-01` sang ERA5 `archive-api` ngày 2026-11-10 theo yêu cầu người dùng). Các chi tiết hạ tầng chưa triển khai được ghi rõ là **đề xuất**, không coi là quyết định đã được duyệt.

## 2. Căn cứ trong repo và các quyết định đề xuất

Đã đọc `src/synthetic_data_source/pharmaflow_source_postgre/schema_full.sql`, `config/project.yaml`, `scripts/source_db.py`, `requirements.txt`, benchmark cũ `jobs/W26.10/weather-api-benchmark/` và kết quả P0 Open-Meteo probe mới tại `jobs/W09.11/weather-openmeteo/` (ngày 2026-11-10).

- Local DDL có `org.store(store_id, store_code, country_code, latitude, longitude, timezone_name, store_status, source)`. `store_status` gồm ACTIVE/INACTIVE/UNKNOWN; không có `org.store.is_active` hoặc cột xác minh tọa độ riêng.
- `org.warehouse` không có tọa độ riêng. V1 dùng store; không tự tạo tọa độ cho warehouse hoặc suy từ địa chỉ.
- Config source hiện chỉ định `pharmaflow_source_postgre_v2`. Phải đối chiếu `current_database()` khi kết nối live, không suy trạng thái live từ local DDL.
- Benchmark W26.10 là sandbox lịch sử (từng đánh dấu nhầm `historical-forecast-api` và `archive-api` là `paid_only`). P0 probe ngày 2026-11-10 (`jobs/W09.11/weather-openmeteo/`) đã xác nhận cả 3 public endpoint Free (`api.open-meteo.com/v1/forecast`, `historical-forecast-api.open-meteo.com/v1/forecast` và `archive-api.open-meteo.com/v1/archive`) đều trả HTTP 200 ở gói Free phi thương mại không cần API key; production package chỉ allowlist đúng 3 endpoint này.
- Python project dùng `.venv/` chung; đã có requests, psycopg, PyYAML, pytest. Khi triển khai mới thêm boto3 và dependency phục vụ test cần thiết vào `requirements.txt`; Lambda artifact được build riêng, không đóng gói toàn bộ crawler dependencies.

| Hạng mục | Phương án đề xuất / đã chốt cho v1 | Điều kiện xác nhận |
|---|---|---|
| Compute | Python Lambda cho planner, worker và reconciler | Pilot chứng minh mỗi task nằm trong timeout; ưu tiên xong CLI local + S3 Dev (P1–P2) trước khi dựng compute (P3) |
| Điều phối | EventBridge Scheduler → planner → SQS → worker | Schedule lúc 06:00; xử lý tiếp sau thời điểm trigger |
| Queue | Hai SQS Standard queues: daily và backfill, mỗi queue có DLQ | Cùng code worker; tách backlog để backfill không chặn daily |
| Control state | Một DynamoDB table (`PAY_PER_REQUEST`) cho run/task lease, quota/budget và trạng thái | Chỉ metadata điều phối; raw vẫn ở S3; không phải DB của web |
| IaC storage | Terraform trong `src/infra/terrafrom/`, môi trường dev | Profile my-aws/account 522346104596 đã xác minh; `main.tf` có 3 prefix (`weather_forecast/`, `historical_forecast/`, `historical_weather/` cho ERA5) và đã apply ngày 2026-11-11 (0 add / 2 change / 0 destroy) |
| Region | Đề xuất `ap-southeast-1`, cùng region cho Lambda/SQS/S3/DynamoDB | Đối chiếu nơi Databricks sẽ chạy và account thực tế |
| Bucket | Một bucket được cấu hình (`pharmaflow-dev-weather-raw-<account>-ap-southeast-1` ở dev) | Kiểm tra ownership/availability; tên S3 phải duy nhất toàn cục |
| Model | **Đã chốt:** `gfs_global` cho Forecast & Historical Forecast (`>= 2022-01-01`); ERA5 default cho `archive-api` (`< 2022-01-01`) | Đã xác nhận cả 2 hệ trên P0 probe 2026-11-10; giữ tách `source_type` giữa forecast và ERA5 reanalysis |

Terraform cho S3 dev ở ap-southeast-1 là lựa chọn mới của người dùng ngày 2026-11-07; bộ cấu hình nằm trong [src/infra/terrafrom](../../src/infra/terrafrom/README.md) và S3 dev đã được apply (bucket state, bucket dữ liệu, 2 IAM policy; verified bằng HeadBucket, state object và IAM readback ngày 2026-11-11). Các lựa chọn DynamoDB/Lambda và IaC cho compute ingestion đã được triển khai ở P3 (2026-11-13, `src/infra/terrafrom/environments/dev/weather_compute.tf`); lịch EventBridge vẫn tắt. Từ P2 (2026-11-13), policy writer đã gắn cho role local `pharmaflow-dev-weather-local-writer` và bucket đã có object Weather do CLI local ghi lên; từ P3, policy writer cũng gắn cho 3 role Lambda; policy reader vẫn chưa gắn cho role nào.

## 3. Luồng thực thi

1. Scheduler gửi event daily chứa lịch dự kiến và version contract tới planner. Backfill đi vào cùng planner qua CLI với request ID ổn định; API web có thể dùng lại contract này về sau.
2. Planner xác thực request, đọc Neon bằng tài khoản SELECT-only, kiểm tra locations và ghi snapshot locations/plan vào S3.
3. Planner chia task, ước lượng API cost và chỉ admit lượng task phù hợp budget. Giữ nguyên plan khi invocation bị retry; không đọc lại locations rồi thay plan trong cùng run.
4. Planner đẩy task IDs/S3 plan reference sang queue tương ứng. SQS message không chứa DSN, secret hoặc toàn bộ response body.
5. Worker claim task có lease, kiểm tra task đã hoàn thành chưa, xin quyền gọi từ limiter/budget dùng chung cho cả hai endpoint và mọi worker.
6. Worker gọi đúng endpoint, ghi raw response và metadata theo attempt, kiểm tra chất lượng cấu trúc/coverage. Dữ liệu lỗi vẫn có bằng chứng riêng.
7. Worker công bố receipt/ready marker cho attempt được chấp nhận rồi cập nhật control state. SQS message chỉ được ACK sau khi có receipt bền vững hoặc lỗi terminal đã được lưu.
8. Reconciler đọc expected task plan và task trạng thái để xuất summary terminal; không kết luận hoàn thành từ queue depth bằng 0.

Planner có lease và cơ chế replay dispatch từ plan đã ghi: crash sau khi gửi một phần SQS được phép gửi lại; worker phải chịu được task trùng. Planner không coi `SendMessage` thành công là task đã ingest thành công.

## 4. Location reader và cohort policy

Query dự kiến (bind tham số, không nối chuỗi IDs):

```sql
SELECT store_id, store_code, country_code, latitude, longitude,
       timezone_name, store_status, source
FROM org.store
WHERE store_id = ANY(%s)
ORDER BY store_id;
```

Daily dùng cohort cấu hình; planner resolve cohort thành tập IDs cụ thể rồi query. Không gọi toàn bộ store trong DB ngay ở pilot. Backfill bắt buộc chỉ định IDs hoặc một cohort version được resolve ra IDs và lưu lại.

Điều kiện xét từng location:

- Cặp lat/lon đầy đủ, finite và trong khoảng hợp lệ; không sửa NULL thành 0 hoặc tự geocode.
- Timezone là IANA hợp lệ; giữ timezone từng store. Giờ chạy hệ thống là giờ Việt Nam, nhưng valid date của dữ liệu theo timezone của store.
- **Chính sách lọc mặc định (cập nhật 2026-11-11):** Trong tập `store_id`/cohort yêu cầu, mọi bản ghi đạt điều kiện kỹ thuật (`lat/lon` & `timezone_name` hợp lệ) và có `store_status = 'ACTIVE'` đều được nhận vào `eligible_locations` — **không chặn theo `source`** (bao gồm cả Onyx và IRPD). `INACTIVE` bị loại; `UNKNOWN` mặc định bị loại trừ khi có override rõ lý do trong cấu hình cohort.
- **Bảo toàn provenance:** Giữ nguyên `source`; thêm `coordinate_provenance`, `coordinate_verification_status`, `eligibility_reason` dựa trên mapping version và source/run evidence xuyên suốt pipeline. Không suy tọa độ đã xác minh từ việc cột lat/lon có giá trị, và không coi tọa độ Onyx (jittered/unverified) hay IRPD/Pharma Sales (mô phỏng đại diện vùng) là nhà thuốc vật lý đã xác minh.
- Lưu location snapshot: IDs, tọa độ yêu cầu, timezone, source/status, provenance, selection policy version và thời điểm đọc. Không cần xuất tên/địa chỉ đầy đủ nếu worker không dùng.
- V1 một request cho một location. Không gộp các store chỉ vì cùng tọa độ; tối ưu theo nhóm tọa độ/ô lưới GFS (probe đã chứng minh `hcm_vn` và `longchau_store_82556` cách 630 m cùng snap về 1 ô lưới GFS `10.71917, 106.640625`) cần mapping và contract riêng ở giai đoạn mở rộng P5.

Quyền Neon chỉ CONNECT/USAGE và SELECT các cột cần thiết của `org.store`. Secret riêng `WEATHER_NEON_DSN`; không import helper source_db có khả năng ghi hoặc quyền loader của source database.

## 5. API và Weather Variable Contract

### 5.1 Gate chọn model trước khi build cloud (Đã probe ngày 2026-11-10)

Đã thực hiện 3 đợt probe tại `jobs/W09.11/weather-openmeteo/` (`20261110T103514Z-p0-probe`, `20261110T124534Z-full-surface-bounds`, và `20261110T153626Z-era5-compat`) trên 3 locations đại diện cohort (`hcm_vn` tại TP.HCM, `longchau_store_82556` từ locator Long Châu, và `berlin_eu` tại Đức để kiểm tra múi giờ có DST), gọi cả 3 endpoints:

- **Network/Protocol thực tế**: `api.open-meteo.com` (`157.90.83.168`), `historical-forecast-api.open-meteo.com` (`5.9.98.12`) và `archive-api.open-meteo.com` đều dùng HTTP/1.1, TLSv1.3, nén `Content-Encoding: deflate` và trả HTTP 200 ở gói Free phi thương mại.
- **Kết quả model Forecast & Historical Forecast (`>= 2022-01-01`)**: `models=gfs_global` và `models=gfs_seamless` trả dữ liệu giống hệt nhau 100% trên cả hai endpoint ở VN & EU, phủ đủ **384 giờ / 16 ngày, 0 giá trị `null`** (5 ngày đầu GFS chạy bước gốc 1h và ngày 6–16 chạy bước gốc 3h được Open-Meteo nội suy thành 1h).
- **Kết quả ERA5 Reanalysis (`< 2022-01-01`, `archive-api`)**: `archive-api.open-meteo.com/v1/archive` phủ đầy đủ dữ liệu từ 1940 (đã probe `2016-01-01..07` và `2021-12-20..26` ở HCM & Berlin); hỗ trợ **35 / 44 biến `hourly`** của GFS và **5 / 5 biến `daily`**, còn 9 biến GFS đặc thù (như `precipitation_probability`, `visibility`, `uv_index`, `cape`...) không có trong ERA5 (trả 100% `null`).
- **Quyết định**: Pin **`models=gfs_global`** cho `/v1/forecast` và `historical-forecast-api` (`>= 2022-01-01`), và dùng **`archive-api` (ERA5)** với contract tương thích `weather_era5_v1` cho backfill **`< 2022-01-01`**. Phần P0 còn lại cần xác nhận trước khi deploy cloud (kiểm tra Neon live `org.store` và ownership/region AWS thực tế) đã thực hiện ngày 2026-11-11: xem mục P0b ở lộ trình.

### 5.2 Request contract v1 đã chốt (`weather_variables_v1` & `weather_era5_v1`)

1. **Contract chính (`weather_variables_v1` — 49 biến cho `/v1/forecast` và `historical-forecast-api` `>= 2022-01-01`)**:
   - **Loại 11 biến `hourly` GFS trả 100% `null`**: `wind_speed_180m`, `wind_direction_180m`, `soil_temperature_0cm/6cm/18cm/54cm`, `soil_moisture_0_to_1cm/1_to_3cm/3_to_9cm/9_to_27cm/27_to_81cm`.
   - **Chốt 44 biến `hourly` có dữ liệu thật + 5 biến `daily` đặc thù** (`weather_code`, `sunrise`, `sunset`, `daylight_duration`, `wind_direction_10m_dominant`). Toàn bộ thống kê `min/max/mean/sum` ngày khác tầng Silver sẽ tổng hợp từ `hourly` để tiết kiệm ~4.68 call units/store (so với lấy đủ 45 biến `daily`).

```yaml
hourly:
  - temperature_2m
  - relative_humidity_2m
  - dew_point_2m
  - apparent_temperature
  - wet_bulb_temperature_2m
  - precipitation_probability
  - precipitation
  - rain
  - showers
  - snowfall
  - snow_depth
  - weather_code
  - pressure_msl
  - surface_pressure
  - cloud_cover
  - cloud_cover_low
  - cloud_cover_mid
  - cloud_cover_high
  - visibility
  - evapotranspiration
  - et0_fao_evapotranspiration
  - vapour_pressure_deficit
  - wind_speed_10m
  - wind_speed_80m
  - wind_speed_120m
  - wind_direction_10m
  - wind_direction_80m
  - wind_direction_120m
  - wind_gusts_10m
  - uv_index
  - uv_index_clear_sky
  - is_day
  - sunshine_duration
  - cape
  - lifted_index
  - convective_inhibition
  - freezing_level_height
  - boundary_layer_height
  - shortwave_radiation
  - direct_radiation
  - diffuse_radiation
  - direct_normal_irradiance
  - terrestrial_radiation
  - total_column_integrated_water_vapour
daily:
  - weather_code
  - sunrise
  - sunset
  - daylight_duration
  - wind_direction_10m_dominant
temperature_unit: celsius
wind_speed_unit: ms
precipitation_unit: mm
timezone: <location.timezone_name>
timeformat: unixtime
models: gfs_global
```

2. **Contract tương thích cho Backfill `< 2022-01-01` (`weather_era5_v1` — 40 biến trên `archive-api.open-meteo.com/v1/archive`)**:
   - Dùng **35 biến `hourly` giao nhau** có dữ liệu thật trên ERA5 (bỏ 9 biến ERA5 trả toàn `null`: `precipitation_probability`, `visibility`, `evapotranspiration`, `uv_index`, `uv_index_clear_sky`, `cape`, `lifted_index`, `convective_inhibition`, `freezing_level_height`) + giữ nguyên **5 biến `daily`**. Không gửi tham số `models=gfs_global` sang `archive-api` (dùng ERA5 default).
   - *(Ghi chú: ERA5 có thêm 6 biến riêng có dữ liệu là `wind_speed_100m`, `wind_direction_100m`, `soil_temperature_0_to_7cm/7_to_28cm`, `soil_moisture_0_to_7cm/7_to_28cm`; v1 ưu tiên giữ đúng 35 biến giao nhau để đồng nhất schema với GFS và tiết kiệm quota).*

Forecast thêm `forecast_days=16`; backfill thêm `start_date`, `end_date`, không gửi `forecast_days`. Chỉ ba hostname/path allowlist chính xác được phép (`api.open-meteo.com/v1/forecast`, `historical-forecast-api.open-meteo.com/v1/forecast`, `archive-api.open-meteo.com/v1/archive`); không tự chuyển paid endpoint hoặc theo redirect ngoài allowlist.

Daily contract tương lai: mean/min/max temperature (°C), mean relative humidity (%), precipitation sum (mm), wind mean/max (m/s) & dominant direction (°), mean cloud cover (%), sunrise/sunset/daylight_duration, daily weather code từ provider. Các thống kê hourly → daily thuộc Silver; v1 worker giữ raw. Không dùng max số WMO code để tự đại diện mức nguy hiểm.

Chi phí thực tế đã kiểm chứng:
- `weather_variables_v1` (49 biến): `forecast_days=16` tốn **`5.60`** call units/location; backfill `>= 2022-01-01` (`≤ 14 ngày`) tốn **`4.90`** call units/task.
- `weather_era5_v1` (40 biến): backfill `< 2022-01-01` (`≤ 14 ngày`) tốn **`4.00`** call units/task.
- Null là missing, không phải 0; contract phải định nghĩa completeness và số timesteps theo timezone/DST thực tế, không mặc định mọi ngày đều có 24 giờ.

### 5.3 Thời gian và snapshot

- Scheduler: `cron(0 6 * * ? *)`, timezone `Asia/Ho_Chi_Minh`, FlexibleTimeWindow OFF. AWS Scheduler có precision trong một phút; 06:00 là thời điểm trigger, không phải giờ toàn bộ raw đã vào S3.
- `scheduled_at_utc`, `planned_at_utc`, `retrieved_at_utc`, `persisted_at_utc` và provider model initialization time (nếu có) là các khái niệm riêng. Không giả retrieved time là model issue time.
- Daily valid start được xác định theo timezone của location tại plan time; expected end = start + 15 ngày. Với store ở Việt Nam, chạy 07/11/2026 kỳ vọng 07–22/11/2026.
- Retry có deadline đề xuất 09:00 giờ Việt Nam, đồng thời không vượt local midnight làm đổi cửa sổ ngày của task. Khi quá hạn, đánh dấu missed/expired; không gọi endpoint live rồi gắn nhãn đó là forecast từng có lúc 06:00.
- **Quy tắc DST & Timestamp (đã xác minh qua probe `berlin_eu` `2026-10-23..27`)**: Khi dùng `timeformat=iso8601` với `timezone=Europe/Berlin` qua ngày đổi giờ mùa đông (`2026-10-25`), Open-Meteo áp **1 `utc_offset_seconds` tĩnh (`3600` = `GMT+1`)** cho toàn bộ response, làm chuỗi local trước ngày đổi giờ bị lệch 1 tiếng so với giờ Berlin thực tế (`+02:00`). Do đó, v1 **bắt buộc dùng `timeformat=unixtime`** để nhận epoch UTC tuyệt đối cho cả `hourly.time` và `daily.time`; tầng Silver quy đổi epoch UTC sang local time bằng `ZoneInfo(location.timezone_name)` (tự xuất hiện ngày 23h/25h chuẩn DST). Lưu ý thêm với vùng có DST: `daily` trả sẵn từ API vẫn bị provider cắt theo `utc_offset_seconds` tĩnh khi vắt qua ngày đổi giờ, nên tầng Silver cần tự tính aggregate ngày từ `hourly` đối với múi giờ có DST.
- `forecast_snapshot_id` xác định snapshot thực thu theo run/task/attempt, không giả là ID model-run nguyên gốc. Backfill dùng `snapshot_id` generic và `forecast_snapshot_id=null`, phân tách rõ `source_type=HISTORICAL_FORECAST_STITCHED` (cho `>= 2022-01-01`) vs `source_type=HISTORICAL_ERA5_REANALYSIS` (cho `< 2022-01-01`).

## 6. Backfill và ngân sách API

Input: request_id, ISO start_date/end_date inclusive, location_ids, cohort policy version, variable contract version và lý do backfill.

- Kiểm tra `start_date ≤ end_date`, IDs tồn tại, locations eligible; không nhận khoảng tương lai cho historical hoặc ngày trước **`1940-01-01`** (chặn ngay ở Planner với mã `UNAVAILABLE_BEFORE_MODEL_COVERAGE`).
- **Quy tắc định tuyến Backfill tại mốc `2022-01-01` (Bắt buộc)**:
  - Khoảng ngày **`>= 2022-01-01`**: định tuyến tới `https://historical-forecast-api.open-meteo.com/v1/forecast` với `models=gfs_global`, contract `weather_variables_v1` (49 biến), prefix `historical_forecast/`.
  - Khoảng ngày **`< 2022-01-01`** (`1940-01-01` → `2021-12-31`): định tuyến tới `https://archive-api.open-meteo.com/v1/archive` (ERA5), contract `weather_era5_v1` (40 biến), prefix `historical_weather/`.
  - **Không trộn qua ranh giới năm 2022**: nếu yêu cầu backfill vắt qua mốc `2022-01-01` (ví dụ `2021-12-20` → `2022-01-10`), `planner.py` bắt buộc cắt đôi tại ranh giới `2021-12-31` | `2022-01-01` thành các task riêng biệt theo đúng endpoint, contract và S3 prefix của từng phần.
- Đề xuất chunk tối đa 14 ngày/location/task, giới hạn một request backfill pilot ở 2 locations × 14 ngày. Mở rộng bằng resume/admission từng phần, không enqueue hàng năm dữ liệu cho toàn bộ chuỗi một lần.
- Kiểm tra freshness gần hiện tại (`2026-11-05..10`) cho thấy `historical-forecast-api` (`gfs_global`) có đủ `24/24` giờ tới ngày hiện tại (`2026-11-10`); tuy nhiên vẫn giữ kiểm tra coverage ở worker để xử lý các ngày/biến bị trễ hoặc thiếu đột xuất (đánh dấu missing/deferred).
- Historical Forecast là chuỗi ghép từ các model runs, còn Historical Weather (`archive-api`) là dữ liệu tái phân tích ERA5. Cả hai dùng cho weather-history features có `source_type` riêng; không dùng để giả lập forecast 16 ngày từng biết tại cutoff cũ.
- Dry-run luôn xuất task count, date chunks (kèm endpoint đích của từng chunk), quota estimate và phần budget dành daily trước khi thực thi.

Open-Meteo Free hiện công bố 600 calls/phút, 5.000/giờ, 10.000/ngày, 300.000/tháng và mục đích phi thương mại. P0 probe xác nhận server trả thẳng các header `X-RateLimit-Cost`, `X-RateLimit-Limit` (`600.0`), `X-RateLimit-Remaining`, `X-RateLimit-Window` (`60`), `X-RateLimit-Reset` (các host public đếm cửa sổ phút độc lập nhau) theo công thức số thực:

```text
cost = max(1.0, (n_variables / 10.0) * max(1.0, n_days / 14.0))
```

Với gói `weather_variables_v1` (49 biến): mỗi task `forecast_days=16` tốn **`5.60` call units**, mỗi task backfill `>= 2022-01-01` (`≤ 14 ngày`) tốn **`4.90` call units**; còn task backfill `< 2022-01-01` (`weather_era5_v1`, 40 biến) tốn **`4.00` call units**. Do đó trần 10.000 calls/ngày chỉ đáp ứng tối đa ~1.785 stores/ngày (trước khi trừ daily reserve) nếu gọi `1 store = 1 request`, trong khi DB nguồn hiện có 2.694 stores Long Châu + 120 stores Onyx; pilot v1 giữ cohort nằm gọn trong ngân sách và bước mở rộng P5 sẽ áp dụng gom nhóm theo ô lưới GFS (hoặc cắt giảm biến nếu chưa gom lưới).

Limiter/budget trong DynamoDB dùng conditional atomic updates theo provider/gói, chung các queues và endpoints; retry cũng tiêu budget. `limiter.py` dùng công thức `cost` thực tế đã kiểm chứng ở trên (làm tròn trần hoặc cộng dồn số thực theo ledger) và ghi nhận lại `X-RateLimit-*` từ response headers.

Khởi đầu đề xuất: tối đa 1 outbound request/giây toàn hệ thống, có cửa sổ phút/giờ/ngày/tháng, daily reserve và backfill allowance riêng. Các con số vận hành cuối cùng phụ thuộc số locations/cost factor; concurrency không thay thế limiter. Budget của workflow này không thể đo usage của ứng dụng khác dùng chung public API (hoặc dùng chung egress IP AWS); phải trừ phần dự phòng đó. Khi hết budget: DEFERRED với next_allowed_at, không retry nóng.

## 7. S3 và metadata contract

Ví dụ backfill event gửi vào planner (IDs là placeholder, phải lấy IDs thật qua reader):

```json
{
  "contract_version": "weather_ingestion_v1",
  "mode": "historical_backfill",
  "request_id": "pilot-backfill-2016-01-v1",
  "start_date": "2016-01-01",
  "end_date": "2016-01-14",
  "location_ids": [101, 102],
  "cohort_policy_version": "pilot_v1",
  "variable_contract_version": "weather_variables_v1"
}
```

Planner tự resolve endpoint, model và variable contract (`weather_variables_v1` cho `>= 2022-01-01`, `weather_era5_v1` cho `< 2022-01-01`), không cho caller gửi endpoint tùy ý. Daily event chứa `mode=daily_forecast`, `scheduled_at_utc`, `schedule_id`, `cohort_id` và contract version; không nhận start/end quá khứ để gọi daily endpoint.

Queue message đề xuất chỉ chứa `message_schema_version`, `run_id`, `task_id`, `plan_s3_key` và task index; worker đọc frozen task từ plan, kiểm tra config hash. `accepted.json` chứa task/attempt/snapshot IDs, raw key, metadata key, checksum và accepted_at_utc. Run summary ghi expected, succeeded, failed, deferred, expired, rejected_locations và trạng thái tổng thể; các task counters được tính theo ID duy nhất.

```text
s3://<configured-bucket>/raw/open_meteo/
  weather_forecast/ingest_date=YYYY-MM-DD/run_id=<id>/
  historical_forecast/ingest_date=YYYY-MM-DD/run_id=<id>/
  historical_weather/ingest_date=YYYY-MM-DD/run_id=<id>/
    plan.json
    locations.json
    tasks/<task_id>/attempts/<attempt_id>/response.json
    tasks/<task_id>/attempts/<attempt_id>/metadata.json
    tasks/<task_id>/accepted.json
    summary/<terminal_revision>.json
```

*(Lưu ý IaC: `src/infra/terrafrom/environments/dev/main.tf` và `tests/policies.tftest.hcl` khai báo 3 prefix `weather_forecast/`, `historical_forecast/` và `historical_weather/`; IAM writer/reader policy đã được apply lên AWS dev ngày 2026-11-11. Hai policy chưa gắn cho role nào).*

`ingest_date` là ngày run được tạo trong Asia/Ho_Chi_Minh, cố định qua retry; backfill không partition theo ngày quá khứ được yêu cầu. Metadata có UTC timestamps. Tên file là hợp đồng đề xuất cho implementation.

Raw payload là bytes JSON nhận được sau HTTP decompression nếu client tự giải nén (Open-Meteo thực tế trả `Content-Encoding: deflate`); ghi rõ representation và SHA-256 của chính bytes được lưu. Không parse/reformat raw rồi gọi đó là bản response nguyên gốc. HTTP status, safe response headers (bao gồm `X-RateLimit-*`) và content encoding được ghi sidecar; không ghi credential, DSN hoặc API key trong URL.

Metadata tối thiểu:

- `schema_version`, `request_contract_version`, `config_hash`, `code_version`.
- `run_id`, `task_id`, `attempt_id`, `snapshot_id`, `forecast_snapshot_id`, `source_type`.
- Endpoint, query parameters đã loại secret, requested date window, model requested/returned nếu provider có.
- Location ID/code, requested coordinates, returned grid-cell coordinates, timezone requested/returned, `utc_offset_seconds`, `timeformat`, source và coordinate provenance.
- Scheduled/planned/retrieved/persisted time, status, latency, unit map, coverage/null report.
- S3 raw key, byte length, checksum, validation status, retry cause, `rate_limit_headers` (`X-RateLimit-Cost`, `Remaining`, `Limit`, `Reset`, `Window`) và estimated quota charge.

Run/task identity: daily logical run key chứa schedule date + cohort version + contract version + model; backfill key chứa client request_id. task_id hash từ run identity + frozen location + window + request contract + endpoint/source_type. Planner retry tái dùng run/task IDs. Yêu cầu refresh có chủ đích tạo run mới và tham chiếu run trước.

Mỗi HTTP attempt có ID/key riêng; không overwrite bytes cũ. `accepted.json` là marker bất biến trỏ tới response và metadata đã hoàn chỉnh, ghi conditional `If-None-Match: *`. Chỉ một accepted attempt/task. Worker redelivery kiểm tra marker/checksum rồi hoàn thiện DDB state/ACK, không fetch lại nếu đã thành công. Crash giữa raw và sidecar tạo orphan chưa ready; replay reconcile hoặc tạo attempt mới, giữ orphan có nhãn để audit. Consumer sau này chỉ đọc attempt có accepted marker, không glob toàn bộ JSON/metadata lẫn nhau.

Một bản raw vật lý trên S3; không copy thêm bản vào bucket Databricks hoặc thư mục latest. Bật versioning và chặn public access; versioning là lớp bảo vệ thêm, không thay thế unique keys/conditional writes. Đề xuất SSE-S3 trước, SSE-KMS khi có yêu cầu tương ứng. Không đặt expiration cho raw snapshots trong v1. Log retention đề xuất 30 ngày và DLQ retention 14 ngày.

## 8. Reliability và control state

Trạng thái đề xuất: PLANNED → DISPATCHING → RUNNING → SUCCEEDED/PARTIAL/FAILED; task thêm DEFERRED, EXPIRED và terminal validation failures. Đây là trạng thái của ingestion, không phải nghiệp vụ tender/sales.

- **Task success khi raw, sidecar, accepted marker tồn tại và checksum/coverage hợp lệ. HTTP 200 không đủ để success — Quy trình xử lý khi HTTP 200 trả toàn `null`**:
  1. *Vẫn lưu bằng chứng attempt lỗi, tuyệt đối không xuất `accepted.json`*: Ghi `response.json` và `metadata.json` vào `tasks/<task_id>/attempts/<attempt_id>/` với `validation_status = "FAILED_ALL_NULL_COVERAGE"`, không tạo `accepted.json` để Databricks/consumer không bao giờ đọc nhầm dữ liệu rỗng.
  2. *Phân loại Terminal vs Transient*:
     - Nếu toàn bộ biến cốt lõi (`temperature_2m`, `relative_humidity_2m`, `precipitation`, `wind_speed_10m`) đều `100% null` cho một khoảng **quá khứ đã đóng** (vượt ngoài coverage model): đây là **Terminal Validation Failure** (`UNAVAILABLE_BEFORE_MODEL_COVERAGE`). Worker cập nhật DDB state = `FAILED_VALIDATION` và **ACK (xóa) SQS message ngay**, không để SQS retry vô ích rồi đẩy vào DLQ.
     - Nếu toàn `null` xảy ra ở **ngày hiện tại / cận hiện tại** (do model archive chưa kịp đồng bộ): coi là **Transient / Delayed**, chuyển state sang `DEFERRED` với `next_allowed_at` (hoặc trả failed batch item để SQS delay retry) cho tới deadline.
     - Nếu **chỉ biến phụ bị `null` một phần/toàn bộ** nhưng các biến cốt lõi vẫn có dữ liệu: chấp nhận kèm cảnh báo (`accepted_with_warnings`), ghi rõ `null_ratio` từng biến vào `metadata.json`.
  3. *Phản ánh lên Run Summary*: Run chứa task `FAILED_VALIDATION` kết thúc với trạng thái `PARTIAL` (nếu có task khác đạt) hoặc `FAILED` (nếu hỏng hết), không đánh dấu `SUCCEEDED`.
- Fail-fast với endpoint/contract/permission sai; 429 tôn trọng Retry-After; 5xx/network timeout dùng backoff có jitter và số attempt hữu hạn. Không ngủ lâu trong Lambda; defer qua control state/queue visibility.
- Start với worker timeout 120s, SQS visibility ≥720s cộng batching window nếu có, batch size 1; bounded connect/read timeout. Cấu hình cuối đo bằng pilot. SQS Standard có thể giao trùng, dùng task lease và marker ở trên.
- Bật `ReportBatchItemFailures` để mở rộng batch sau này; lỗi transient trả failed item, thành công không bị retry theo batch. Retry terminal maxReceiveCount đề xuất 5; worker/DLQ reconciler ghi terminal state để run không treo.
- Scheduler → planner dùng synchronous invoke target qua Scheduler universal target `lambda:invoke`/RequestResponse nếu hỗ trợ cấu hình đã chọn; kiểm chứng bằng induced planner failure. Nếu dùng async invocation, phải có Lambda async failure destination/retry riêng: Scheduler delivery success không chứng minh planner xử lý thành công.
- Có Scheduler delivery DLQ riêng, hai worker DLQ và alarm. Hỏng Neon phải báo planner failure; không tạo run rỗng rồi đánh dấu success.
- Reconciler mỗi 5 phút (đề xuất) xử lý planner lease hết hạn, task hết hạn/DLQ và final summary. Ghi các summary revision bất biến; final run outcome tính từ tập task IDs duy nhất.
- Giới hạn số task và input body; oversized plan lưu S3 và message chỉ giữ reference. Replay DLQ dùng cùng task identity và plan snapshot, không đọc lại location hiện tại để âm thầm đổi tọa độ.

Metrics: eligible/rejected locations theo lý do; planned/succeeded/failed/deferred/expired tasks; HTTP attempts, 429/5xx, budget used/remaining; raw byte count; coverage/null ratio; schedule-to-first-object và schedule-to-run-complete latency. Alarm khi daily chưa có terminal outcome đúng deadline, task DLQ >0, planner failed hoặc forecast đủ 16 ngày giảm bất thường.

## 9. IAM, kết nối và môi trường

- Planner: đọc một Secrets Manager secret Neon, ghi plan/locations trong prefix weather, gửi hai queues và truy cập control table.
- Worker: nhận/xóa queue message, đọc plan, ghi/get/head objects ở weather prefixes, cập nhật control table; không có quyền ghi Neon hoặc đọc Neon secret.
- Reconciler: đọc control table/plan/receipts/DLQ theo nhu cầu, ghi summary và CloudWatch metrics; không cần gọi Weather API.
- Runtime roles không có S3 DeleteObject; bucket private, deny non-TLS. Secret không có trong SQS/S3/log/fixture.
- Neon public TLS + Open-Meteo public HTTPS: đề xuất Lambda không gắn VPC cho v1 để có outbound internet trực tiếp; nếu dùng private Neon/network policy khác thì thiết kế egress/VPC riêng trước deploy. Không gắn Lambda vào VPC rồi mặc định còn internet.
- IaC tách parameters environment, region, bucket, secret ARN, cohort/contract version và schedule_enabled. Schedule mặc định disabled đến khi acceptance đạt.
- Đóng gói đúng runtime/architecture Lambda, đặc biệt psycopg binary. Local dùng `.venv` chung; build artifact cô lập không phải tạo thêm môi trường Python phát triển trong repo.

## 10. File và module cần tạo

Đề xuất package mới `src/weather_ingestion/`, giữ nguyên crawler và source packages hiện tại. Không thực hiện cuộc đổi tên cây src cùng task này.

```text
src/weather_ingestion/
  README.md
  __init__.py
  cli.py                       # preflight, locations, plan, run, status, resume
  config.py                    # versioned config; validated defaults
  locations.py                 # SELECT-only Neon reader + cohort policy
  planner.py                   # stable run/task IDs, chunks, quota estimates
  open_meteo.py                # exact three allowlisted Open-Meteo endpoint clients
  validation.py                # response shape, dates, units, null/coverage (catches HTTP 200 all-null)
  storage.py                   # immutable S3 raw, sidecars, accepted markers
  state.py                     # DDB leases, ledger, conditional transitions
  limiter.py                   # shared rate/budget, daily reservation
  worker.py                    # fetch → persist → publish receipt
  reconcile.py                 # final outcomes, expired tasks, partial dispatch
  handlers.py                  # Lambda adapters
  config/cohorts.yaml
  config/weather_variables_v1.yaml # 44 hourly + 5 daily (models=gfs_global, timeformat=unixtime)
  config/weather_era5_v1.yaml      # 35 hourly + 5 daily (archive-api ERA5 cho < 2022-01-01)
  schemas/                     # JSON schemas: trigger, task, metadata, receipts
scripts/weather/               # CLI launch/deploy helpers if necessary
src/infra/terrafrom/                # Terraform S3 dev (thêm prefix historical_weather/); compute ingestion bổ sung khi chốt
tests/weather_ingestion/       # deterministic tests + synthetic fixtures
artifacts/weather/runs/<id>/   # small, sanitized probe/acceptance manifests
```

Raw thực tế ghi S3; local probe raw ở `.runtime/weather/` và ignore. Không commit full raw hoặc secrets. Synthetic fixtures gắn nhãn rõ. Cập nhật `requirements.txt`, `.gitignore`, docs index và architecture status trong cùng implementation sau khi có bằng chứng; không sửa/push các file jobs/W19.10 đang dirty của công việc khác.

CLI contract dự kiến:

```text
python -m src.weather_ingestion.cli preflight
python -m src.weather_ingestion.cli locations --cohort pilot
python -m src.weather_ingestion.cli plan daily --cohort pilot --dry-run
python -m src.weather_ingestion.cli plan backfill --start-date 2025-01-01 --end-date 2025-01-14 --location-ids <ids> --request-id <id> --dry-run
python -m src.weather_ingestion.cli run --plan <saved-plan> --sink s3
python -m src.weather_ingestion.cli status --run-id <id>
python -m src.weather_ingestion.cli resume --run-id <id>
```

Các command này là API CLI cần xây, chưa có để chạy hôm nay. `--dry-run` đọc/validate cấu hình và locations nhưng không gọi Weather API hoặc ghi cloud resources; output không chứa secrets.

## 11. Thứ tự triển khai và điều kiện chuyển bước

| Bước | Công việc cụ thể | Bằng chứng hoàn tất |
|---|---|---|
| P0a — API Probe (**Đã xong 2026-11-10**) | Probe 3 endpoints (`/v1/forecast`, `historical-forecast-api`, `archive-api`), xác nhận model, 49 biến GFS + 40 biến ERA5, DST (`Europe/Berlin`), `X-RateLimit-*` và ngày biên archive (`2021-03-23` cho GFS; `2022-01-01` làm ranh giới định tuyến) | `jobs/W09.11/weather-openmeteo/outputs/runs/20261110T103514Z-p0-probe/model-probe.json`, `20261110T124534Z-full-surface-bounds/full-surface-bounds.json`, và `20261110T153626Z-era5-compat/era5-compat.json`; đã pin `gfs_global`, `weather_variables_v1` & `weather_era5_v1` |
| P0b — DB & AWS preflight (**Xong phần kỹ thuật 2026-11-11**) | Xác minh account/region/bucket ownership (`src/infra/terrafrom/environments/dev/`), bổ sung prefix `historical_weather/` nếu dùng ERA5, Neon DB live (`current_database()`) + column metadata read-only, cohort counts/provenance/status | Account `522346104596`/`ap-southeast-1` xác minh bằng STS; S3 dev đã apply với 3 prefix; Neon `pharmaflow_source_postgre_v2`: 2.816 store, tọa độ/timezone hợp lệ, cohort pilot 7 store đã duyệt, role `weather_reader` SELECT-only 8 cột. Chưa có `preflight.json` và location exclusion report (thuộc P1/CLI `preflight`); chưa bật schedule |
| P1 — local core | Viết reader/config/planner/client/storage/validation interfaces, schemas, dry-run; thử nhỏ 1–3 locations và backfill nhỏ (cả `< 2022` và `>= 2022`) | Stable task IDs, cắt chunk đúng ranh giới `2022-01-01`, raw giữ bytes, checksum, immutable attempts; validation bắt HTTP 200 all-null; parser/quota/DST tests đạt |
| P2 — S3 đầu tiên | Provision S3 dev bucket (Terraform đã viết), IAM và secret; chạy CLI local ghi thẳng vào S3 cho pilot (chưa cần DynamoDB/Lambda) | HEAD/GET readback hash trùng, metadata đúng, raw/accepted marker đúng prefix (`weather_forecast/`, `historical_forecast/`, `historical_weather/`); không trùng khi resume |
| P3 — queue/compute | Deploy hai queues + DLQ, DynamoDB (`PAY_PER_REQUEST`), planner/worker/reconciler, budget limiter, metrics/alarms; schedule disabled | Mô phỏng duplicate, partial dispatch, crash giữa raw và marker, 429, budget exhausted, timeout, access denied và DLQ đạt kỳ vọng |
| P4 — scheduled pilot | Enable 06:00 cho cohort nhỏ sau acceptance; chạy ít nhất 2 ngày liên tiếp | Hai run/snapshot khác nhau, mỗi location có 16 valid dates hoặc lỗi coverage rõ, summary deadline và alarms được kiểm chứng |
| P5 — mở rộng | Dry-run toàn cohort, đánh giá gom nhóm theo ô lưới GFS (giữ dưới 10.000 units/ngày), budget reserve và thời gian; tăng locations/backfill theo admission | Daily không bị backfill chiếm budget; run có status đầy đủ, backfill resume không mất/nhân đôi kết quả |
| P6 — bàn giao | Runbook, source/version/coverage report, S3 keys và read role cho Databricks giai đoạn sau | Người khác chạy preflight/plan/status/resume theo README; chưa tuyên bố Databricks/Silver/Gold đã triển khai |

P0b xong mới chạy P2 vào cloud thật. Không ấn định ngày go-live khi các đầu vào này chưa được xác nhận. Thứ tự ưu tiên là API probe (xong) → DB preflight & local core → S3 readback → queue/recovery → schedule → scale.

## 12. Acceptance checklist bắt buộc

1. Neon SELECT-only, đúng database, không có lệnh sửa source schema/data; mọi store hợp lệ kỹ thuật có `store_status = 'ACTIVE'` được nhận và giữ nguyên nhãn `source`/provenance vào `eligible_locations`; location lỗi tọa độ/timezone hoặc `INACTIVE`/`UNKNOWN` (chưa override) vào `rejected_locations` có lý do loại rõ.
2. Forecast yêu cầu 16 ngày; valid date window đúng timezone location. Giữ `requested` và `returned` grid coordinates riêng.
3. Backfill chia chunk bao phủ đúng khoảng inclusive, không gaps/overlap ngoài ý muốn; định tuyến `< 2022-01-01` sang `archive-api` và `>= 2022-01-01` sang `historical-forecast-api`, tách task tại ranh giới `2022-01-01`, chặn trước `1940-01-01` (`UNAVAILABLE_BEFORE_MODEL_COVERAGE`); không gọi ngoài 3 endpoint allowlist.
4. Đồng nhất `timeformat=unixtime`, units giữa các endpoint; dùng `weather_variables_v1` (49 biến) cho Forecast/Historical Forecast và `weather_era5_v1` (40 biến) cho ERA5; phân tách `source_type` rõ (`HISTORICAL_FORECAST_STITCHED` vs `HISTORICAL_ERA5_REANALYSIS`); không biến `null` thành `0`; HTTP 200 toàn `null` phải fail validation (không tạo `accepted.json`, phân loại terminal cho quá khứ đóng hoặc deferred cho ngày cận hiện tại).
5. Cùng daily task được giao lại không phát sinh accepted snapshot thứ hai hoặc gọi API lại nếu receipt đã có. Sáng hôm sau tạo run/snapshot mới, giữ cả bản cũ.
6. Raw và metadata upload chưa hoàn tất không được consumer xem là ready. Raw hash readback đúng; thử crash tại các điểm chuyển trạng thái và resume thành công.
7. Tổng budget across queues/workers/retries không vượt admission limit; 429 và exhaustion không retry nóng; backfill không tiêu daily reserve.
8. Scheduler cấu hình đúng cron/timezone, flexible window OFF; kiểm tra cả scheduler delivery failure và planner processing failure, không chỉ invocation accepted.
9. Run PARTIAL/FAILED khi một task terminal fail; deferred/DLQ không bị đếm success; summary khớp unique expected tasks.
10. Không có DSN/secret/API key trong Git, CloudWatch, S3 metadata hoặc SQS; least-privilege roles và bucket private được read back sau deploy.
11. Hai ngày scheduled pilot có run evidence; tắt schedule và pause queue mapping được thử trong rollback, raw cũ vẫn đọc được.

Rollback: disable Scheduler, disable worker event source mappings, giữ queue/DLQ/control state và raw để điều tra; rollback code bằng phiên bản deploy trước. Không xóa bucket, raw, Neon records hoặc replay hàng loạt khi chưa xem failure reason. Thay variable contract tạo version mới.

## 13. Tài liệu chính thức đã đối chiếu ngày 2026-11-07 (cập nhật probe 2026-11-10)

- [Open-Meteo Forecast API](https://open-meteo.com/en/docs): forecast_days tối đa 16; biến/timezone/models; đã probe thực tế biến và coverage ngày 2026-11-10.
- [GFS API documentation](https://open-meteo.com/en/docs/gfs-api): model `gfs_global` đã xác nhận trên `/v1/forecast` và `historical-forecast-api`.
- [Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api): stitched series cho `>= 2022-01-01` (coverage GFS thực tế từ `2021-03-23`); không phải full issued run snapshots.
- [Historical Weather API (ERA5)](https://open-meteo.com/en/docs/historical-weather-api): dữ liệu tái phân tích ERA5 từ `1940-01-01`, dùng cho backfill `< 2022-01-01` (`weather_era5_v1`).
- [Open-Meteo Pricing](https://open-meteo.com/en/pricing): gói, rate limits và công thức `X-RateLimit-Cost` đã kiểm chứng.
- [EventBridge Scheduler schedule types](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html): timezone, cron và precision một phút.
- [Lambda SQS configuration](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html): queue visibility, timeout, region và event source mapping.
- [Lambda with SQS](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html): xử lý batch failures và idempotency.
- [Lambda asynchronous invocation](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async.html): accepted invocation khác processing outcome.
- [S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html): chống overwrite bằng If-None-Match.

Liên quan: [System Architecture](pharmaflow-system-architecture.md), [Data Products](pharmaflow-data-products.md), [PostgreSQL source package](../../src/synthetic_data_source/pharmaflow_source_postgre/README.md), [P0 Open-Meteo Probe](../../jobs/W09.11/weather-openmeteo/README.md).

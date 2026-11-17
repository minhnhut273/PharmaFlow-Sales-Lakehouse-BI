# Weather Ingestion `src/weather/` — hướng dẫn vận hành CLI & AWS (P1–P5)

Thiết kế: [SDD.md](SDD.md). Đặc tả test: [tests/weather/TEST_CASES.md](../../tests/weather/TEST_CASES.md). Nhật ký backfill: [BACKFILL_AUDIT_PLAN.md](BACKFILL_AUDIT_PLAN.md).

**Phạm vi hiện tại:**
- CLI chạy trên máy local:
  - `--sink local` (mặc định, P1): ghi vào `.runtime/weather/`.
  - `--sink s3` (P2): ghi lên bucket dev `pharmaflow-dev-weather-raw-...` qua role `pharmaflow-dev-weather-local-writer`.
- Trên AWS (P3–P5): 3 Lambda (`planner`, `worker`, `reconciler`), 5 queue SQS và bảng DynamoDB `pharmaflow-dev-weather-control`. Hai lịch EventBridge hiện đã `ENABLED` (`06:00 VN` daily với `cohort_id = "full_network"` gồm 880 điểm gọi từ gom cụm lưới VN `0.111° floor` + 122 store quốc tế = `4.928` units/ngày; và Reconciler `rate(5 minutes)`). Backfill lịch sử 122 store quốc tế (6.590 tasks) đã hoàn tất 100%. Xem mục 7–8.

## 1. Chuẩn bị

- Python 3.12 trong `.venv/` chung của repo. Các thư viện cần dùng (`requests`, `PyYAML`, `psycopg[binary]`, `python-dotenv`, `boto3[crt]`) đã có trong `requirements.txt`. Gói `[crt]` là bắt buộc để boto3 đọc được profile tạo bằng `aws login`.
- Khai báo `WEATHER_NEON_DSN` trong `.env` ở gốc repo. DSN này dùng role `weather_reader`, chỉ có quyền `SELECT` trên `org.store` của DB `pharmaflow_source_postgre_v2`. CLI không bao giờ in DSN; khi lỗi kết nối, chuỗi DSN bị thay bằng `<redacted-dsn>`.
- Luôn chạy với `-B` để không sinh `__pycache__`.

### 1.1. Thêm cho `--sink s3` (P2)

- Đăng nhập AWS bằng `aws login --profile my-aws`. Credential là loại ngắn hạn, tự làm mới; không đưa access key vào `.env`.
- Thêm vào `.env` các biến sau (không chứa secret):

  ```dotenv
  WEATHER_S3_BUCKET=pharmaflow-dev-weather-raw-<account>-ap-southeast-1
  WEATHER_S3_REGION=ap-southeast-1
  WEATHER_S3_ROLE_ARN=arn:aws:iam::<account>:role/pharmaflow-dev-weather-local-writer
  WEATHER_AWS_PROFILE=my-aws
  ```

- CLI dùng profile `WEATHER_AWS_PROFILE` để gọi `sts:AssumeRole` vào `WEATHER_S3_ROLE_ARN` (phiên tối đa 1 giờ), rồi kiểm tra identity nhận được đúng là role writer.
  - Role chỉ cho `GetObject`/`PutObject` trong 3 prefix weather, cùng `ListBucket` có điều kiện theo prefix.
  - Role không có quyền xoá object.
- Role được tạo bằng Terraform, qua biến `weather_local_writer_principal_arns`. Xem [src/infra/terrafrom/README.md](../infra/terrafrom/README.md).

## 2. Lệnh CLI

Chạy từ gốc repo. Output là JSON.

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -B -m src.weather.cli preflight
& $py -B -m src.weather.cli locations --cohort pilot
& $py -B -m src.weather.cli plan daily --cohort pilot --location-ids 516,5404 --dry-run
& $py -B -m src.weather.cli plan daily --cohort pilot --location-ids 516,5404
& $py -B -m src.weather.cli plan backfill --start-date 2021-12-25 --end-date 2022-01-05 --location-ids 516 --request-id pilot-smoke-cross-2022
& $py -B -m src.weather.cli run --plan <plan_s3_key> --sink local
& $py -B -m src.weather.cli status --run-id <run_id>
& $py -B -m src.weather.cli resume --run-id <run_id>

# P2: cùng các lệnh, thêm --sink s3 (preflight còn kiểm tra assume role, region bucket và quyền list 3 prefix)
& $py -B -m src.weather.cli preflight --sink s3
& $py -B -m src.weather.cli plan daily --cohort pilot --location-ids 516,5404 --sink s3
& $py -B -m src.weather.cli run --plan <plan_s3_key> --sink s3
& $py -B -m src.weather.cli status --run-id <run_id> --sink s3
& $py -B -m src.weather.cli resume --run-id <run_id> --sink s3
```

Mỗi sink có state riêng: `--sink local` dùng `.runtime/weather/state/`, còn `--sink s3` dùng `.runtime/weather/state/s3/<bucket>/`. Một `run_id` đã đăng ký với sink này sẽ không được nhận ra ở sink kia. Vì vậy `status` và `resume` phải truyền đúng `--sink` mà bạn đã dùng khi `plan`.

| Lệnh | Gọi Neon | Gọi Open-Meteo | Ghi file |
|---|---|---|---|
| `preflight` | Có: kiểm tra `current_database()`, `current_user`, quyền trên `org.store`, session read-only | Không | Không (chỉ tạo rồi xoá 1 file thử) |
| `locations` | Có | Không | Không |
| `plan ... --dry-run` | Có | Không | Không |
| `plan ...` | Có, trừ khi `plan.json` của `run_id` đã tồn tại (khi đó replay, không đọc DB) | Không | `locations.json`, `plan.json`, `state/runs/` |
| `run`, `resume` | Không | Có, chỉ cho task chưa có `accepted.json` | attempt, `accepted.json`, `summary/`, `state/` |
| `status` | Không | Không | Không |

Các tham số của `plan daily`:
- `--schedule-id`: mặc định `manual`. Hạn chót của task là `planned_at + 3h`, và không vượt quá nửa đêm theo giờ địa phương của store. Lịch `daily-0600-vn` (từ P3) dùng hạn chót 09:00 giờ VN.
- `--scheduled-at`: thời điểm lịch, dạng ISO UTC.
- `--refresh-seq`: tạo một run làm mới có chủ đích.
- `--location-ids`: chạy một tập con. Khi đó `cohort_id` thành `pilot:ids=...`, nên `run_id` khác với run của cả cohort.

## 3. Layout `.runtime/weather/`

```text
.runtime/weather/
  raw/open_meteo/<prefix>/ingest_date=YYYY-MM-DD/run_id=<run_id>/
    plan.json, locations.json, summary/<rev>.json      # đặt dưới prefix của tasks[0]
    tasks/<task_id>/attempts/<attempt_id>/response.json # nguyên bytes Open-Meteo trả về
    tasks/<task_id>/attempts/<attempt_id>/metadata.json
    tasks/<task_id>/accepted.json                       # ghi create-only
  state/
    runs/<run_id>.json            # run_id -> plan key
    tasks/<run_id>/<task_id>.json # status, lease, attempt_count
    budget/<YYYY-MM-DD>.json      # units đã dùng theo ngày VN (bộ đếm thận trọng phía mình)
```

Với backfill vắt qua `2022-01-01`, các file của run (`plan.json`, `locations.json`, `summary/`) nằm dưới `historical_weather/`. Task ERA5 nằm cùng chỗ đó, còn task GFS (`>= 2022-01-01`) nằm dưới `historical_forecast/.../run_id=<cùng run_id>/tasks/...`. Muốn biết prefix của từng task, đọc `plan.json` (`tasks[].s3_prefix`).

Consumer chỉ được đọc attempt mà `accepted.json` trỏ tới. Attempt lỗi hoặc attempt mồ côi được giữ lại làm bằng chứng.

Với `--sink s3`, layout key trên bucket giống hệt phần `raw/open_meteo/...` ở trên. Mọi object đều được ghi kèm `ChecksumSHA256`. `accepted.json` và `plan.json` dùng `If-None-Match: *`, nên đã có thì không bị ghi đè. Bucket có versioning, và role writer không có quyền xoá.

## 4. Runbook

- **Chạy lại hoặc gặp sự cố:** chạy `resume --run-id <run_id>`. Task đã có `accepted.json` sẽ bị bỏ qua mà không gọi HTTP. Task `FAILED_VALIDATION`, `FAILED` hoặc `EXPIRED` cũng không bị gọi lại.
- **HTTP 429:** CLI dừng vòng chạy và ghi `DEFERRED`. Chờ hết `Retry-After` rồi `resume`.
- **5xx hoặc timeout:** CLI retry tối đa 2 lần, có backoff và jitter. Timeout hoặc mất kết nối được ghi là `RETRYABLE`, chỉ có `metadata.json` vì không có bytes nào nhận về. Read timeout tùy endpoint: forecast 30s, historical-forecast 60s, archive 90s. Sau đó task giữ trạng thái `RETRYABLE` và có thể `resume` sau. Smoke ngày 2026-11-12 cho thấy `archive-api` có lúc trả `503 "The service is overloaded"`; chờ vài phút rồi `resume`.
- **`HTTP 200` nhưng toàn null:**
  - Nếu là quá khứ đã đóng: `FAILED_VALIDATION` (`FAILED_ALL_NULL_COVERAGE`), không có `accepted.json`.
  - Nếu `end_date >= today - 5 ngày`: `DEFERRED`, có thể `resume` sau.
- **Budget:** backfill không được dùng vào phần dự trữ 2.000 units/ngày dành cho daily. Plan vượt hạn mức bị từ chối với lỗi `BUDGET_EXCEEDED_FOR_RUN`.
- **`WINDOW_MISMATCH`:** dữ liệu trả về có ngày địa phương đầu hoặc cuối không khớp `start_date`/`end_date` của task thì bị `FAILED_VALIDATION` và không có `accepted.json`. Nguyên nhân thường gặp: chạy daily với `--scheduled-at` của một ngày khác hôm nay, trong khi `/v1/forecast` luôn trả dữ liệu tính từ hôm nay. **Không** dùng `scheduled_at` ở tương lai hoặc quá khứ để "giả lập" snapshot trên S3.
- **Đổi request backfill:** cùng `--request-id` trong cùng ngày luôn replay plan cũ. Nếu đổi khoảng ngày, dùng `--request-id` mới.
- **Lỗi AWS khi `--sink s3`:**
  - `AWS session failed ... expired`: chạy lại `aws login --profile my-aws`.
  - `AccessDenied` khi assume role: kiểm tra ARN của bạn có nằm trong `weather_local_writer_principal_arns` hay không.
  - Phiên role kéo dài 1 giờ; một lệnh `run` dài hơn thế thì chạy `resume` sau khi đăng nhập lại.

## 5. Kiểm thử

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/weather
```

Toàn bộ test chạy offline với fixture tổng hợp (`SYNTHETIC_TEST_FIXTURE`) và S3 giả trong bộ nhớ (`tests/weather/test_p2_s3.py`), không chạm Neon, Open-Meteo hay AWS.

## 6. Ghi nguồn

Weather data by Open-Meteo.com (CC BY 4.0). Chuỗi ghi nguồn này cũng được lưu trong mỗi `metadata.json` (trường `attribution`).

## 7. Vận hành trên AWS (P3)

Mọi lệnh dưới đây chạy từ gốc repo với `AWS_PROFILE=my-aws` (sau `aws login --profile my-aws`), region `ap-southeast-1`.

### 7.1. Thay đổi hạ tầng hay code?

| Thay đổi | Cách làm |
|---|---|
| Logic hoặc config trong `src/weather/` (`.py`, `.yaml`) | `scripts/weather/build_lambda.ps1` rồi `scripts/weather/deploy_code.ps1`. Script deploy kiểm tra `CodeSha256` khớp với gói local. |
| RAM, timeout, biến môi trường, IAM, queue, lịch, alarm | Sửa `src/infra/terrafrom/environments/dev/weather_compute.tf`, rồi `terraform plan` và `apply`. Terraform không ghi đè code đã deploy, nhờ `ignore_changes`. |
| DSN Neon | Sửa `WEATHER_NEON_DSN` trong `.env`, rồi chạy `scripts/weather/put_neon_dsn_param.ps1`. Script ghi lên SSM SecureString `/pharmaflow/dev/weather/neon_dsn` mà không in giá trị. |

Phiên bản thư viện trong gói Lambda được ghim ở `scripts/weather/lambda-requirements.txt`, gồm cả `boto3` (không dùng boto3 có sẵn của runtime) và `tzdata`.

### 7.2. Kích hoạt thủ công

```powershell
$env:AWS_PROFILE = "my-aws"; $r = "ap-southeast-1"
# Smoke (không gọi Neon, không gọi Open-Meteo, không ghi gì)
'{"dry_run": true}' | Set-Content -Encoding ascii $env:TEMP\ev.json
aws lambda invoke --function-name pharmaflow-dev-weather-planner --payload fileb://$env:TEMP/ev.json --region $r out.json

# Daily (cohort pilot hoặc một tập con; refresh_seq dùng khi cố ý chạy lại cùng ngày)
'{"mode":"daily_forecast","cohort_id":"pilot","location_ids":[516,5404],"schedule_id":"manual"}' | Set-Content -Encoding ascii $env:TEMP\ev.json
aws lambda invoke --function-name pharmaflow-dev-weather-planner --payload fileb://$env:TEMP/ev.json --region $r out.json

# Backfill (request_id mới cho mỗi khoảng ngày mới)
'{"mode":"historical_backfill","request_id":"<id>","start_date":"2021-12-25","end_date":"2022-01-05","location_ids":[516]}' | Set-Content -Encoding ascii $env:TEMP\ev.json
aws lambda invoke --function-name pharmaflow-dev-weather-planner --payload fileb://$env:TEMP/ev.json --region $r out.json

# Chốt summary (cũng là việc lịch 5 phút sẽ làm từ P4)
'{}' | Set-Content -Encoding ascii $env:TEMP\ev.json
aws lambda invoke --function-name pharmaflow-dev-weather-reconciler --payload fileb://$env:TEMP/ev.json --region $r out.json
```

Output của Planner gồm `run_id`, `plan_s3_key`, `dispatched`, `already_accepted` và `neon_read`. Gọi lại với cùng event là replay: Planner trả `replayed_frozen_plan: true`, không đọc SSM/Neon, và chỉ gửi lại các task chưa có `accepted.json`. Worker tự chạy khi có message trong SQS.

### 7.3. Xem trạng thái và xử lý sự cố

- **Trạng thái run:** query DynamoDB với `pk = RUN#<run_id>` (item `META` và các item `TASK#...`). Các run chưa kết thúc nằm trên GSI `active_runs`. Quota ngày nằm ở item `BUDGET#<YYYY-MM-DD>` (ngày theo giờ VN).
- **Log:** `/aws/lambda/pharmaflow-dev-weather-{planner,worker,reconciler}`, mỗi dòng là một JSON. Các event chính: `planner_dispatched`, `worker_task`, `worker_record_error`, `dlq_message`, `reconcile_run`. Log không chứa DSN hay credential.
- **Alarm `*-dlq-not-empty`:** invoke Reconciler. Reconciler đọc DLQ:
  - Message hợp lệ của task chưa có `accepted.json` thì đánh dấu task `DLQ`.
  - Message không khớp plan (sai `config_hash`, sai `task_id`, JSON hỏng) thì ghi log và bỏ qua.
  - Cả hai trường hợp đều xoá message khỏi DLQ. Alarm tự về `OK` ở chu kỳ metric tiếp theo.
- **Alarm `*-errors`:** xem log của function tương ứng. Planner bị từ chối (ví dụ `BUDGET_EXCEEDED_FOR_RUN`, ngày không hợp lệ) sẽ báo lỗi và không gửi message nào.
- **Worker:**
  - `DEFERRED` (429, hết quota ngày, phút hoặc giờ `HOURLY_LIMIT` 4.980/h, toàn null cận hiện tại) và `RETRYABLE` (5xx, timeout): đổi visibility rồi trả failed item, để SQS tự giao lại.
  - Message hỏng: hiện lại sau 20–40 giây, sau 5 lần nhận sẽ vào DLQ.
  - Kết quả terminal: ACK ngay.

---

## 8. Việc cần làm tiếp theo: Bàn giao & Tích hợp sang Databricks (Free Edition Bridge)

Phần thu thập từ Open-Meteo → S3 Raw (`src/weather/`) đã hoàn thiện cấu hình `full_network` (880 điểm = 2.816 cửa hàng) và đóng băng toàn bộ backfill lịch sử. Với lựa chọn vận hành trên **Databricks Free Edition** (tránh hết hạn 14-day Trial và tránh phát sinh phí DBU):

1. **Workspace & Cầu nối S3 → Managed Volume tự động (đã triển khai):**
   - Do **Databricks Free Edition** không hỗ trợ cross-account AWS IAM Role Storage Credential / External Location, **S3 (`pharmaflow-dev-weather-raw-522346104596-ap-southeast-1`) vẫn là nguồn raw gốc (canonical store)**.
   - Workspace Free Edition đã cấu hình Catalog `pharmaflow_dev`, Schema `bronze_weather`, Managed Volume `weather_raw` (`/Volumes/pharmaflow_dev/bronze_weather/weather_raw/`).
   - Cầu nối sync delta đã triển khai qua CLI [sync_s3_to_volume.py](../pipeline/databricks/src/bronze/sync_s3_to_volume.py) (chạy tay/backfill) và AWS Lambda tự động `pharmaflow-dev-databricks-weather-sync` ([aws_volume_sync_lambda.py](../pipeline/databricks/src/bronze/aws_volume_sync_lambda.py), [databricks_bridge.tf](../infra/terrafrom/environments/dev/databricks_bridge.tf)) lúc `06:18 VN`. *(Ghi chú: [main.tf](../infra/terrafrom/environments/dev/main.tf) vẫn giữ sẵn biến `weather_reader_role_names` cho Paid/Prod đọc S3 trực tiếp sau này.)*
2. **Đường ống Bronze/Silver Weather tại Databricks (`src/pipeline/databricks/` — đã chạy live Daily):**
   - [weather_autoloader.py](../pipeline/databricks/src/bronze/weather_autoloader.py) nhận `weather_raw_root`, quét `accepted.json`, đối chiếu `raw_sha256` và nạp `store_grid_mapping.json`.
   - [silver/weather.sql](../pipeline/databricks/src/silver/weather.sql) bung 758 ô VN + 122 store quốc tế thành **2.816 `store_id`**, chuẩn hóa UTC/`local_date` và lọc `null` cuối ngày 16.
   - Chi tiết kế hoạch Gold MD-01 xem [src/pipeline/databricks/SDD.md](../pipeline/databricks/SDD.md).
3. **Nghiệm thu chạy thực tế `06:00 VN` (`2026-11-18`):**
   - Kiểm tra run tự động đầu tiên của `full_network` hoàn tất `880/880` tasks dưới 15 phút (`summary/*.json` + `store_grid_mapping.json` trên S3).
   - *(Tùy chọn)* Gắn SNS Topic (email/chat) cho 6 CloudWatch Alarms trong `weather_compute.tf`.

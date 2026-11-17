# Đặc tả Test Cases & Hợp đồng Code cho P1 (`src/weather/` & `tests/weather/`)

Tài liệu này đi kèm với bộ unit test trong `tests/weather/` để bạn tự code từng module trong `src/weather/` theo hướng **TDD (Test-Driven Development)**: viết xong module nào → chạy lệnh test của module đó → xanh (`PASSED`) rồi mới sang module tiếp theo.

> **Mẹo thuận tiện:** Trong [conftest.py](conftest.py), bộ test dùng hàm `get_field(obj, key)` hỗ trợ **cả `dict` lẫn `@dataclass` / object attribute**. Vì vậy khi code, bạn trả về `dict` hay `@dataclass` đều được miễn là đúng tên trường bên dưới.

---

## 1. Lệnh chạy kiểm thử (không sinh rác `__pycache__` / `.pytest_cache`)

Chạy toàn bộ suite:
```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/weather
```

Hoặc chạy lẻ từng module theo đúng thứ tự gợi ý khi bạn code:
```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/weather/test_config.py
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/weather/test_locations.py
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/weather/test_limiter.py
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/weather/test_planner.py
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/weather/test_open_meteo.py
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/weather/test_validation.py
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/weather/test_storage_and_worker.py
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/weather/test_state_and_cli.py
```

---

## 2. Hợp đồng Chữ ký Hàm & Trường dữ liệu theo từng Module

### 2.1. Module `src/weather/config.py` (Test: [test_config.py](test_config.py))
File YAML cấu hình đã được tạo sẵn tại `src/weather/config/` (`cohorts.yaml`, `weather_variables_v1.yaml`, `weather_era5_v1.yaml`).

- **`load_variable_contract(contract_name: str, config_dir: Path | None = None) -> dict | Any`**
  - Đọc `<config_dir>/<contract_name>.yaml` (nếu `config_dir=None` thì mặc định trỏ tới `src/weather/config`).
  - Kiểm tra bắt buộc: `timeformat == "unixtime"`, `hourly_variables` và `daily_variables` không rỗng. Nếu sai ném `ValueError` (chứa từ `"unixtime"` khi sai timeformat).
  - Các trường trả về: `contract_version`, `model`, `timeformat`, `units` (`temperature_unit`, `wind_speed_unit`, `precipitation_unit`), `core_hourly_variables`, `hourly_variables`, `daily_variables`.
- **`load_cohorts_config(config_dir: Path | None = None) -> dict | Any`**
  - Đọc `cohorts.yaml`, trả về: `cohort_policy_version`, `default_policy`, `source_provenance_map`, `cohorts`.
- **`compute_config_hash(payload: Mapping[str, Any]) -> str`**
  - Serialize JSON tất định (`json.dumps(payload, sort_keys=True, separators=(",", ":"))`) rồi băm SHA-256, trả về chuỗi dạng `"sha256:<64-hex>"`.

---

### 2.2. Module `src/weather/locations.py` (Test: [test_locations.py](test_locations.py))

- **`evaluate_locations(rows: Sequence[Mapping[str, Any]], requested_store_ids: Sequence[int], allow_unknown_status: bool = False, override_reason: str | None = None, source_provenance_map: Mapping[str, Any] | None = None) -> dict | Any`**
  - Đầu vào: `rows` đọc từ `org.store`, danh sách `requested_store_ids`.
  - Xử lý:
    1. Nếu một `store_id` trong `requested_store_ids` không có trong `rows` → đưa vào `rejected_locations` với `store_id` và `rejection_reason` (ví dụ `"STORE_NOT_FOUND"`).
    2. Kiểm tra `latitude` / `longitude`: khác `None`, là số hữu hạn (`math.isfinite`), nằm trong `[-90, 90]` và `[-180, 180]`. Sai → `rejected_locations`.
    3. Kiểm tra `timezone_name`: thử `ZoneInfo(timezone_name)`. Nếu lỗi → `rejected_locations` với `rejection_reason` có chữ `"INVALID_TIMEZONE"`.
    4. Kiểm tra `store_status`:
       - `"ACTIVE"` → **Nhận** vào `eligible_locations` cho **mọi `source`** (cả Long Châu, Onyx, IRPD, Pharma Sales).
       - `"INACTIVE"` → **Loại** vào `rejected_locations` (`rejection_reason` có chữ `"INACTIVE"`).
       - `"UNKNOWN"` → Mặc định **loại**; chỉ nhận nếu `allow_unknown_status=True` và `override_reason` khác rỗng.
    5. Gắn nhãn provenance cho mỗi bản ghi trong `eligible_locations`: giữ nguyên `source`, thêm `coordinate_provenance`, `coordinate_verification_status` (tra từ `cohorts.yaml` / `source_provenance_map`), và `eligibility_reason`.
    6. Sắp xếp `eligible_locations` tăng dần theo `store_id`.
  - Trả về object/dict có 2 trường: `eligible_locations` và `rejected_locations`.

---

### 2.3. Module `src/weather/limiter.py` (Test: [test_limiter.py](test_limiter.py))

- **`estimate_call_cost(n_variables: int, n_days: int) -> float`**
  - Công thức Open-Meteo: `max(1.0, (n_variables / 10.0) * max(1.0, n_days / 14.0))`.
- **`check_budget_admission(*, mode: str, required_units: float, daily_limit: float = 10000.0, daily_reserve: float = 2000.0, used_daily: float = 0.0, used_backfill: float = 0.0) -> dict | Any`**
  - Nếu `mode == "historical_backfill"`: ngân sách tối đa được phép dùng cho backfill là `daily_limit - daily_reserve - used_backfill` (hoặc `min(daily_limit - used_daily - used_backfill, daily_limit - daily_reserve - used_backfill)`). Nếu `required_units` vượt quá → trả về `{"allowed": False, "reason": "BUDGET_EXCEEDED_FOR_RUN"}`.
  - Nếu `mode == "daily_forecast"`: được phép dùng vào `daily_reserve`, miễn tổng `used_daily + used_backfill + required_units <= daily_limit` → trả về `{"allowed": True, "reason": "OK"}`.

---

### 2.4. Module `src/weather/planner.py` (Test: [test_planner.py](test_planner.py))

- **`build_daily_run_id(*, schedule_date_vn: str, schedule_id: str, cohort_id: str, cohort_policy_version: str, contract_version: str, model: str, refresh_seq: int | None = None) -> str`**
  - Sinh `"daily-<YYYYMMDD>-<hash8>"` tất định. Nếu có `refresh_seq` thì đưa `refresh_seq` vào chuỗi băm (hoặc hậu tố) để sinh `run_id` khác với bản gốc.
- **`build_backfill_run_id(*, ingest_date_vn: str, request_id: str, cohort_policy_version: str, contract_version: str) -> str`**
  - Sinh `"backfill-<YYYYMMDD>-<hash8>"` tất định.
- **`build_task_id(*, run_id: str, store_id: int, endpoint_key: str, start_date: str, end_date: str, contract_version: str, model: str | None) -> str`**
  - Trả về 16 ký tự hex đầu của SHA-256.
- **`create_daily_plan(*, eligible_locations: Sequence[Any], rejected_locations: Sequence[Any], scheduled_at_utc: datetime, schedule_id: str, cohort_id: str, cohort_policy_version: str = "pilot_v1", contract_version: str = "weather_variables_v1", model: str = "gfs_global") -> dict | Any`**
  - Mỗi store trong `eligible_locations` tạo 1 task:
    - Tính ngày bắt đầu `start_date` theo `scheduled_at_utc.astimezone(ZoneInfo(store.timezone_name)).date()`, `end_date = start_date + 15 days` (`16` ngày).
    - `endpoint_key = "forecast"`, `s3_prefix = "raw/open_meteo/weather_forecast"`, `contract_version = "weather_variables_v1"`, `model = "gfs_global"`, `estimated_cost = 5.60`.
- **`create_backfill_plan(*, eligible_locations: Sequence[Any], rejected_locations: Sequence[Any], request_id: str, start_date: str, end_date: str, today_vn: str, cohort_policy_version: str = "pilot_v1") -> dict | Any`**
  - Kiểm tra hợp lệ:
    - Nếu `start_date > end_date` → `raise ValueError("start_date must be <= end_date")`.
    - Nếu `end_date >= today_vn` → `raise ValueError("end_date must be before today")`.
    - Nếu `end_date < "1940-01-01"` → `raise ValueError("UNAVAILABLE_BEFORE_MODEL_COVERAGE")`.
  - Nếu khoảng ngày vắt qua `2022-01-01`, tách thành 2 đoạn:
    - Đoạn `< 2022-01-01`: `endpoint_key = "historical_weather"`, `s3_prefix = "raw/open_meteo/historical_weather"`, `contract_version = "weather_era5_v1"`, `model = None`, `source_type = "HISTORICAL_ERA5_REANALYSIS"`, `estimated_cost = 4.00`.
    - Đoạn `>= 2022-01-01`: `endpoint_key = "historical_forecast"`, `s3_prefix = "raw/open_meteo/historical_forecast"`, `contract_version = "weather_variables_v1"`, `model = "gfs_global"`, `source_type = "HISTORICAL_FORECAST_STITCHED"`, `estimated_cost = 4.90`.
  - Mỗi đoạn chia thành các chunk liên tiếp tối đa **14 ngày** (`[d, min(d + 13 days, seg_end)]`).
- **`build_task_queue_message(*, run_id: str, task_id: str, task_index: int, plan_s3_key: str, config_hash: str) -> dict[str, Any]`**
  - Trả về đúng 6 khóa: `message_schema_version` (`"1"`), `run_id`, `task_id`, `task_index`, `plan_s3_key`, `config_hash`.
- **`load_or_create_plan(*, sink: Any, plan_s3_key: str, expected_config_hash: str, db_reader: Callable) -> dict | Any`**
  - Nếu `sink.exists(plan_s3_key)` là `True`: đọc `plan.json` đã đóng băng, kiểm tra `config_hash == expected_config_hash` (sai → `raise ValueError`), **không gọi `db_reader()`**, lọc ra các task chưa có `accepted.json` vào `pending_tasks`.
- *(Lưu ý đường dẫn `plan_s3_key` khi Backfill vắt qua `2022-01-01`)*: Đặt `plan.json`, `locations.json`, `summary/` theo `s3_prefix` của task đầu tiên (`tasks[0].s3_prefix`, tức `raw/open_meteo/historical_weather/ingest_date=<YYYY-MM-DD>/run_id=<run_id>/plan.json`), còn từng task ghi vào `task["s3_prefix"]` riêng của nó.

---

### 2.5. Module `src/weather/open_meteo.py` (Test: [test_open_meteo.py](test_open_meteo.py))

- **`resolve_endpoint_url(endpoint_key: str) -> str`**
  - Chỉ nhận đúng 3 khóa:
    - `"forecast"` → `"https://api.open-meteo.com/v1/forecast"`
    - `"historical_forecast"` → `"https://historical-forecast-api.open-meteo.com/v1/forecast"`
    - `"historical_weather"` → `"https://archive-api.open-meteo.com/v1/archive"`
  - Khóa hoặc URL khác → `raise ValueError(...)`.
- **`build_open_meteo_params(*, endpoint_key: str, latitude: float, longitude: float, timezone_name: str, hourly_variables: Sequence[str], daily_variables: Sequence[str], forecast_days: int | None = None, start_date: str | None = None, end_date: str | None = None, model: str | None = None) -> dict[str, Any]`**
  - Luôn đặt `timeformat="unixtime"`, `temperature_unit="celsius"`, `wind_speed_unit="ms"`, `precipitation_unit="mm"`.
  - Chỉ thêm `"models": model` khi `model` khác `None` (ERA5 không truyền `models`).
- **`fetch_open_meteo(*, endpoint_key: str, params: Mapping[str, Any], session: Any = None, timeout: float = 30.0) -> dict | Any`**
  - Gọi `session.get(url, params=params, timeout=timeout, allow_redirects=False)`.
  - Giữ nguyên `resp.content` (`raw_bytes`), tính `raw_byte_length`, `raw_sha256`, lọc các header `X-RateLimit-*` vào `rate_limit_headers`, trả kèm `http_status`.
- **`classify_http_response(*, http_status: int, headers: Mapping[str, str] | None = None) -> dict | Any`**
  - Phân loại: `200` → `"OK"`, `429` → `"DEFERRED_RATE_LIMIT"` (kèm `retry_after_seconds` kiểu `int` nếu có header `Retry-After`), `5xx` → `"RETRYABLE_SERVER_ERROR"`, `4xx` khác → `"TERMINAL_CLIENT_ERROR"`.

---

### 2.6. Module `src/weather/validation.py` (Test: [test_validation.py](test_validation.py))

- **`validate_open_meteo_response(*, raw_bytes: bytes, expected_days: int, timezone_name: str, end_date: str, today_vn: str, core_variables: Sequence[str] = ("temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m")) -> dict | Any`**
  - Parse JSON từ `raw_bytes` (chỉ để kiểm tra, không sửa `raw_bytes`).
  - Kiểm tra `hourly_units.time == "unixtime"` và `len(hourly["time"]) == expected_days * 24`. Sai → `status="FAILED_VALIDATION"`, `is_accepted=False`, `is_terminal=True`.
  - Quy đổi từng epoch trong `hourly["time"]` sang `ZoneInfo(timezone_name)` để thống kê số giờ mỗi ngày địa phương vào `non_24h_days` (ví dụ ngày đổi giờ DST `2026-10-25` tại `Europe/Berlin` có `25` giờ vẫn hợp lệ vì tổng số bước giờ = `expected_days * 24`).
  - Tính `null_report` (`total`, `nulls`, `null_ratio`) cho từng biến trong `hourly`:
    - Nếu các biến `core_variables` bị `100% null`:
      - Khoảng quá khứ đã đóng (`end_date < today_vn - 5 days`) → `status="FAILED_VALIDATION"`, `reason="FAILED_ALL_NULL_COVERAGE"`, `is_accepted=False`, `is_terminal=True`.
      - Khoảng cận hiện tại (`end_date >= today_vn - 5 days`) → `status="DEFERRED"`, `reason="NEAR_PRESENT_ALL_NULL_LAG"`, `is_accepted=False`, `is_terminal=False`.
    - Nếu `core_variables` đều có dữ liệu nhưng có biến phụ bị `null` (`null_ratio > 0`) → `status="ACCEPTED_WITH_WARNINGS"`, `is_accepted=True`, `is_terminal=True`.
    - Nếu tất cả đều sạch → `status="SUCCEEDED"`, `is_accepted=True`, `is_terminal=True`.

---

### 2.7. Module `src/weather/storage.py` & `src/weather/worker.py` (Test: [test_storage_and_worker.py](test_storage_and_worker.py))

- **`class LocalSink(root_dir: Path)`** trong `storage.py`:
  - `put_bytes(key: str, data: bytes) -> None`
  - `get_bytes(key: str) -> bytes`
  - `put_json(key: str, payload: Mapping[str, Any]) -> None`
  - `get_json(key: str) -> dict[str, Any]`
  - `exists(key: str) -> bool`
  - `put_json_if_absent(key: str, payload: Mapping[str, Any]) -> bool`: Nếu file chưa tồn tại thì ghi và trả `True`; nếu đã tồn tại thì **không ghi đè** và trả `False` (hoặc `raise FileExistsError`).
- **`execute_task(*, task: Mapping[str, Any], sink: Any, fetcher: Callable, attempt_id: str, today_vn: str) -> dict | Any`** trong `worker.py`:
  1. Đường dẫn cơ sở của task: `<s3_prefix>/ingest_date=<ingest_date>/run_id=<run_id>/tasks/<task_id>`.
  2. Kiểm tra xem `<base>/accepted.json` đã tồn tại trong `sink` chưa. Nếu đã có → **không gọi `fetcher`**, trả ngay `{"status": "SKIPPED_ALREADY_ACCEPTED", "attempt_id": ...}`.
  3. Gọi `fetcher(endpoint_key, params)` lấy `raw_bytes`, `raw_sha256`, `rate_limit_headers`.
  4. Lưu `<base>/attempts/<attempt_id>/response.json` (nguyên bản `raw_bytes`) và `<base>/attempts/<attempt_id>/metadata.json`.
  5. Gọi `validate_open_meteo_response(...)`.
  6. Nếu `is_accepted is True`: ghi `<base>/accepted.json` (qua `put_json_if_absent`) chứa tối thiểu `attempt_id`, `raw_sha256`, `status`; trả về kết quả `status`.
  7. Nếu `is_accepted is False` (ví dụ `FAILED_VALIDATION` hoặc `DEFERRED`): **tuyệt đối không tạo `accepted.json`**, trả về `status`.

---

### 2.8. Module `src/weather/state.py`, `src/weather/reconcile.py` & `src/weather/cli.py` (Test: [test_state_and_cli.py](test_state_and_cli.py))

- **`class LocalStateStore(root_dir: Path)`** trong `state.py`:
  - `acquire_task_lease(*, run_id: str, task_id: str, worker_id: str, now_epoch: int, lease_seconds: int = 120) -> bool`: Cấp khóa lease nếu task chưa có lease hoặc lease cũ đã hết hạn (`now_epoch >= lease_expires_at`), từ chối (`False`) nếu lease của worker khác vẫn còn hạn.
- **`summarize_run_outcomes(*, run_id: str, expected_task_ids: Sequence[str], task_statuses: Mapping[str, str], rejected_locations: Sequence[Any]) -> dict | Any`** trong `reconcile.py`:
  - Trả về `run_status`: `"SUCCEEDED"` nếu 100% `expected_task_ids` thuộc `{"SUCCEEDED", "ACCEPTED_WITH_WARNINGS"}`; `"PARTIAL"` nếu có ít nhất 1 task thành công và có task lỗi; `"FAILED"` nếu không có task nào thành công.
- **`run_cli(argv: Sequence[str], *, store_rows_override: Sequence[Mapping[str, Any]] | None = None, runtime_dir: Path | None = None) -> tuple[int, dict | str]`** trong `cli.py`:
  - Hỗ trợ các lệnh `preflight`, `locations`, `plan`, `run`, `status`, `resume`; trả về `(exit_code, output)`.

---

## 3. Bảng tổng hợp 43 Test Cases (56 lượt chạy Pytest) trong `tests/weather/`

| Mã TC | File Test | Nội dung kiểm thử | Kỳ vọng |
|---|---|---|---|
| `TC-CFG-01` | `test_config.py` | Nạp `weather_variables_v1.yaml` | Đủ 44 biến hourly + 5 biến daily = 49 biến, `gfs_global`, `unixtime`, không chứa 11 biến đất/180m. |
| `TC-CFG-02` | `test_config.py` | Nạp `weather_era5_v1.yaml` | Đủ 35 biến hourly + 5 biến daily = 40 biến cho `< 2022-01-01`, không chứa 9 biến chỉ có ở GFS. |
| `TC-CFG-03` | `test_config.py` | Nạp `cohorts.yaml` | Đúng 7 `store_ids` pilot (`104, 516, 1234, 2137, 5389, 5404, 5631`) và bảng ánh xạ provenance. |
| `TC-CFG-04` | `test_config.py` | Băm `compute_config_hash` | Hai dict khác thứ tự key ra cùng 1 mã `sha256:...`; đổi 1 giá trị ra mã khác. |
| `TC-CFG-05` | `test_config.py` | Chặn cấu hình sai `timeformat` | Báo `ValueError` khi `timeformat != "unixtime"`. |
| `TC-LOC-01` | `test_locations.py` | Nhận tất cả store `ACTIVE` | Cả 7 store pilot thuộc 4 `source` khác nhau đều vào `eligible_locations`. |
| `TC-LOC-02` | `test_locations.py` | Bảo toàn `source` & nhãn provenance | Giữ nguyên `source`, gắn rõ `UNVERIFIED` cho Onyx và `SIMULATED` cho IRPD/Pharma Sales. |
| `TC-LOC-03` | `test_locations.py` | Loại store `INACTIVE` | Rơi vào `rejected_locations` kèm lý do `INACTIVE`. |
| `TC-LOC-04` | `test_locations.py` | Xử lý store `UNKNOWN` | Mặc định loại; khi bật `allow_unknown_status=True` kèm `override_reason` thì được nhận. |
| `TC-LOC-05` | `test_locations.py` | Loại tọa độ `NULL`, `NaN`, `Inf`, ngoài miền | Kiểm tra 9 trường hợp biên tọa độ đều vào `rejected_locations`, không biến `NULL` thành `0`. |
| `TC-LOC-06` | `test_locations.py` | Loại `timezone_name` sai chuẩn IANA | Vào `rejected_locations` với lý do `TIMEZONE`. |
| `TC-LOC-07` | `test_locations.py` | `store_id` yêu cầu không có trong DB | Ghi nhận ID thiếu vào `rejected_locations`, không làm rơi âm thầm. |
| `TC-LIM-01` | `test_limiter.py` | Công thức cost Forecast 16 ngày (49 biến) | Ra đúng `5.60` units. |
| `TC-LIM-02` | `test_limiter.py` | Công thức cost GFS Backfill `<= 14` ngày | Ra đúng `4.90` units cho cả 14 ngày, 7 ngày, 1 ngày. |
| `TC-LIM-03` | `test_limiter.py` | Công thức cost ERA5 Backfill `<= 14` ngày | Ra đúng `4.00` units (40 biến). |
| `TC-LIM-04` | `test_limiter.py` | Giá trị sàn tối thiểu của cost | Request ít biến (`< 10` biến, `<= 14` ngày) luôn có cost tối thiểu = `1.0`. |
| `TC-LIM-05` | `test_limiter.py` | Bảo vệ phần ngân sách `daily_reserve` | Backfill muốn lấn vào `daily_reserve` bị chặn (`BUDGET_EXCEEDED`); Daily Forecast được phép dùng. |
| `TC-PLN-01` | `test_planner.py` | Sinh `run_id` và `task_id` tất định | Gọi nhiều lần cùng tham số ra cùng ID; thêm `refresh_seq=1` sinh `run_id` mới. |
| `TC-PLN-02` | `test_planner.py` | Cửa sổ 16 ngày theo múi giờ từng store | Lúc `22:30 UTC` ngày `10/11` (`2026-11-10T22:30:00Z`; VN 05:30 ngày 11/11, Berlin 23:30 ngày 10/11), store VN lấy `11/11..26/11`, còn store Berlin lấy `10/11..25/11`. |
| `TC-PLN-03` | `test_planner.py` | Tự động cắt đôi tại mốc `2022-01-01` | Khoảng `2021-12-20..2022-01-10` tách thành 1 task ERA5 (`4.00` units) và 1 task GFS (`4.90` units). |
| `TC-PLN-04` | `test_planner.py` | Chia chunk liên tiếp tối đa 14 ngày | Khoảng 35 ngày tách thành 3 chunk `14 + 14 + 7` ngày không hở, không trùng. |
| `TC-PLN-05` | `test_planner.py` | Chặn khoảng ngày backfill bất hợp lệ | Báo `ValueError` khi `start > end`, `end >= today`, hoặc `< 1940-01-01`. |
| `TC-PLN-06` | `test_planner.py` | Nội dung message SQS tối giản | Chỉ chứa 6 trường tham chiếu nhẹ, không rò rỉ secret hay tọa độ. |
| `TC-PLN-07` | `test_planner.py` | Replay từ `plan.json` đã đóng băng | Không gọi lại DB reader, chỉ trả về các task chưa có `accepted.json`. |
| `TC-PLN-08` | `test_planner.py` | Chế độ `dry_run=True` | Trả về plan và dự toán cost mà không ghi file nào xuống sink. |
| `TC-OM-01` | `test_open_meteo.py` | Allowlist đúng 3 URL Open-Meteo | Chấp nhận 3 khóa chuẩn; truyền URL lạ hoặc endpoint khác báo `ValueError`. |
| `TC-OM-02` | `test_open_meteo.py` | Tham số query `unixtime` & `models` | Luôn có `timeformat=unixtime`; GFS có `models=gfs_global`, ERA5 không truyền `models`. |
| `TC-OM-03` | `test_open_meteo.py` | Bảo toàn `raw_bytes` & `X-RateLimit-*` | Không tắt/đổi bytes gốc, `allow_redirects=False`, khớp SHA-256 và đọc đủ header quota. |
| `TC-OM-04` | `test_open_meteo.py` | Phân loại HTTP status (`200`, `429`, `5xx`, `4xx`) | Trả đúng `OK`, `DEFERRED_RATE_LIMIT` (kèm `Retry-After`), `RETRYABLE_SERVER_ERROR`, `TERMINAL_CLIENT_ERROR`. |
| `TC-VAL-01` | `test_validation.py` | Response dự báo 16 ngày hợp lệ | `384` bước giờ, `16` bước ngày, `0` null → `SUCCEEDED` (`is_accepted=True`). |
| `TC-VAL-02` | `test_validation.py` | Bẫy `HTTP 200` toàn `null` ở quá khứ đóng | Trả `FAILED_VALIDATION` (`is_accepted=False`, `is_terminal=True`). |
| `TC-VAL-03` | `test_validation.py` | Bẫy `HTTP 200` toàn `null` ở ngày cận hiện tại | Trả `DEFERRED` (`is_accepted=False`, `is_terminal=False`) để thử lại sau. |
| `TC-VAL-04` | `test_validation.py` | Chỉ biến phụ bị `null`, 4 biến cốt lõi đủ | Trả `ACCEPTED_WITH_WARNINGS` (`is_accepted=True`), ghi tỷ lệ null vào `null_report`. |
| `TC-VAL-05` | `test_validation.py` | Kiểm tra ngày đổi giờ DST `Europe/Berlin` | Quy đổi `unixtime` qua `ZoneInfo("Europe/Berlin")`, nhận diện ngày `2026-10-25` có `25` giờ và cho qua. |
| `TC-VAL-06` | `test_validation.py` | Từ chối `timeformat=iso8601` | Trả `FAILED_VALIDATION` (`is_accepted=False`). |
| `TC-STO-01` | `test_storage_and_worker.py` | `LocalSink` lưu và đọc lại nguyên bytes | Khớp 100% mảng byte và mã băm SHA-256. |
| `TC-STO-02` | `test_storage_and_worker.py` | Ghi bất biến `accepted.json` (`put_json_if_absent`) | Ghi lần 1 thành công (`True`), ghi đè lần 2 bị chặn (`False` hoặc `FileExistsError`), giữ nguyên bản đầu. |
| `TC-WRK-01` | `test_storage_and_worker.py` | Luồng Worker thành công chuẩn | Lưu đủ `response.json`, `metadata.json` và `accepted.json` khớp SHA-256. |
| `TC-WRK-02` | `test_storage_and_worker.py` | Tính Idempotent khi chạy lại task đã xong | Thấy đã có `accepted.json` thì bỏ qua, không gọi lại Open-Meteo (`call_count == 1`). |
| `TC-WRK-03` | `test_storage_and_worker.py` | Worker gặp `HTTP 200` toàn `null` | Vẫn lưu `response.json` + `metadata.json` để làm bằng chứng, nhưng **không tạo `accepted.json`**. |
| `TC-STA-01` | `test_state_and_cli.py` | Khóa `acquire_task_lease` chống chạy trùng | Worker 1 giữ lease; Worker 2 bị chặn khi lease còn hạn và chỉ lấy lại được sau khi hết hạn. |
| `TC-STA-02` | `test_state_and_cli.py` | Tổng hợp `run_status` của Reconciler | Đạt hết → `SUCCEEDED`; có đạt có lỗi → `PARTIAL`; lỗi hết → `FAILED`. |
| `TC-CLI-01` | `test_state_and_cli.py` | Lệnh CLI `plan daily --cohort pilot --dry-run` | Trả exit code `0`, in thông tin plan và không ghi file JSON nào ra đĩa. |

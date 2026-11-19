# PharmaFlow BI — Dashboard Streamlit Multipage (4 Trang Tiếng Việt)

Ứng dụng Business Intelligence 4 trang bằng **100% tiếng Việt**, mô phỏng và nâng cấp bố cục từ AWS QuickSight (*Phân tích Bán lẻ Dược phẩm — Thời tiết, Cửa hàng & ATC*), truy vấn trực tiếp Neon PostgreSQL (`quick_gold_md01`) bằng **SQL aggregation pushdown** qua `psycopg` + `@st.cache_data`.

---

## 1. Cấu trúc 4 trang
1. **Tổng Quan (`01_tong_quan.py`)**: 6 thẻ KPI tách theo tiền tệ/đơn vị, biểu đồ tăng trưởng `kpi_sales_trend` (kỳ `MONTH`, tính tăng trưởng trung bình `%`), Donut tỷ trọng quốc gia, Top 15 thương hiệu và bảng đối chiếu `OBSERVED` vs `SYNTHETIC`.
2. **Thời Tiết & Địa Điểm (`02_thoi_tiet_dia_diem.py`)**: Bộ lọc đa yếu tố `Mức mưa`, `Mức độ ẩm`, 4 nút chọn nhanh ô thời tiết + bộ chọn `Ô Nhiệt độ × Ô Mức mưa` đánh dấu trực tiếp trên bản đồ nhiệt toàn chiều rộng, so sánh ngày thường/cuối tuần, Scatter nhiệt độ, bảng chi tiết ngày (+ mở rộng theo Cửa hàng & Đơn vị tính) và Top 15 thuốc + Thứ trong tuần.
3. **Cửa Hàng & Lợi Nhuận (`03_cua_hang_loi_nhuan.py`)**: Bản đồ Châu Âu (Choropleth ISO-3) + Heatmap 8 quốc gia EU × 12 tháng, Top 20 cửa hàng, Gauge khuyến mãi %, Scatter/Bar lợi nhuận thương hiệu, bảng hiệu suất cửa hàng có tìm kiếm/CSV, và ma trận bong bóng 120 cửa hàng EU.
4. **Sản Phẩm & ATC (`04_san_pham_atc.py`)**: Bảng chi tiết sản phẩm có tìm kiếm/CSV, Treemap Thương hiệu–Sản phẩm, Histogram đơn giá tính trên PostgreSQL (`WIDTH_BUCKET`), Line & Heatmap 8 nhóm ATC toàn kỳ `2014–2019`, Top 15 Nhà sản xuất (`IRPD — IDR`), và xếp hạng 8 nhóm thuốc ATC.

---

## 2. Yêu cầu tối thiểu cho thành viên trong nhóm
Để **chỉ chạy Dashboard Streamlit**, máy thành viên **chỉ cần**:
- **Git**
- **Python `3.12+`**
- **2 biến kết nối Neon** (`QUICK_NEON_DATABASE_URL` và `QUICK_NEON_SCHEMA=quick_gold_md01`) do nhóm trưởng gửi riêng.

> **Không cần** cài AWS CLI, Terraform, Databricks CLI, MongoDB hay file `requirements.txt` đầy đủ của toàn bộ pipeline ETL.

---

## 3. Cài đặt & Chạy nhanh trong 3 bước

### Bước 1 — Clone repo, tạo môi trường ảo & cài 5 thư viện nhẹ

```bash
git clone https://github.com/minhnhut273/PharmaFlow-Sales-Lakehouse-BI.git
cd PharmaFlow-Sales-Lakehouse-BI
python -m venv .venv
```

Cài đúng 5 gói Streamlit bằng file [`src/streamlit/requirements.txt`](requirements.txt):

- **Windows (PowerShell):**
  ```powershell
  .\.venv\Scripts\pip.exe install -r src\streamlit\requirements.txt
  ```
- **macOS / Linux:**
  ```bash
  ./.venv/bin/pip install -r src/streamlit/requirements.txt
  ```

*(Lưu ý: Trên Windows không cần chạy `Activate.ps1` — gọi thẳng `.venv\Scripts\pip.exe` và `.venv\Scripts\streamlit.exe` để tránh lỗi ExecutionPolicy.)*

### Bước 2 — Tạo file `.env` (chỉ 2 dòng)

Tạo file `.env` ở **thư mục gốc repo** (`PharmaFlow-Sales-Lakehouse-BI/.env`) hoặc đặt trong `src/streamlit/.env` rồi dán 2 biến nhóm trưởng gửi:

```env
QUICK_NEON_DATABASE_URL=postgresql://<readonly_user>:<password>@<neon-pooler-host>/neondb?sslmode=require
QUICK_NEON_SCHEMA=quick_gold_md01
```

> ⚠️ **Bảo mật:** Tuyệt đối **không commit** file `.env` hoặc `.streamlit/secrets.toml` lên GitHub. Cả hai đã được chặn trong `.gitignore`.

*(Thứ tự tự động tìm cấu hình của [db.py](db.py): OS env → `src/streamlit/.env` → `.env` tại gốc repo → thư mục cha → `Path.cwd()/.env` → `st.secrets`.)*

### Bước 3 — Khởi chạy Dashboard

- **Windows (PowerShell):**
  ```powershell
  .\.venv\Scripts\streamlit.exe run src\streamlit\app.py --server.port 8501
  ```
- **macOS / Linux:**
  ```bash
  ./.venv/bin/streamlit run src/streamlit/app.py --server.port 8501
  ```

Sau khi chạy, mở trình duyệt tại **`http://localhost:8501`**.

---

## 4. Hướng dẫn sử dụng giao diện

- **Thanh điều hướng & Bộ lọc phân tầng (Sidebar trái):**
  - Chuyển qua lại giữa 4 trang (`Tổng Quan`, `Thời Tiết & Địa Điểm`, `Cửa Hàng & Lợi Nhuận`, `Sản Phẩm & ATC`); bộ lọc được giữ xuyên suốt khi đổi trang.
  - Chọn **Bảng màu giao diện** gồm 4 preset (`PharmaFlow Teal`, `AWS Quick Classic`, `Ocean Blue`, `Warm Amber`).
  - Lọc phân tầng theo **Nhóm dữ liệu (`Track`) → Quốc gia → Cửa hàng → Đơn vị tính (`UOM`) → Khoảng ngày bán → Mức nhiệt độ**.
  - Có nút **Đặt lại toàn bộ bộ lọc** ở cuối sidebar.
- **Nguyên tắc toàn vẹn dữ liệu hiển thị:**
  - Không gộp chung tiền tệ khác loại (`EUR` của `ONYX_EU_SYNTHETIC` vs `IDR` của `IRPD_ID_OBSERVED`) hoặc đơn vị tính hỗn hợp (`multi-UOM` trên `IRPD_ID_OBSERVED` — app có banner cảnh báo riêng khi chưa lọc 1 UOM cụ thể).
  - Tách biệt nhãn nguồn gốc dữ liệu **`OBSERVED` (Quan sát thực tế)** và **`SYNTHETIC` (Mô phỏng)** trên KPI & bảng đối chiếu.
- **Tương tác nổi bật trên từng trang:**
  - **Trang 2 (Thời Tiết & Địa Điểm):** Dùng 4 nút chọn nhanh hoặc cặp dropdown **`Ô Nhiệt độ` × `Ô Mức mưa`** để khoanh đen ô trên Heatmap toàn chiều rộng và lọc chéo các biểu đồ bên dưới.
  - **Trang 3 & Trang 4:** Có ô tìm kiếm trực tiếp theo **Cửa hàng / Sản phẩm** và nút **Tải CSV (UTF-8)** giữ đúng dấu tiếng Việt khi mở bằng Excel.

---

## 5. Mẹo cho nhóm trưởng (tùy chọn)

### Tạo tài khoản Neon chỉ đọc (`bi_reader`) trước khi gửi nhóm
Thay vì chia sẻ chuỗi kết nối owner (`neondb_owner`), mở **Neon Console → SQL Editor** của project BI Mirror (`landing_datamart_md01`) và chạy:

```sql
CREATE ROLE bi_reader WITH LOGIN PASSWORD '<dat_mat_khau_manh>';
GRANT CONNECT ON DATABASE neondb TO bi_reader;
GRANT USAGE ON SCHEMA quick_gold_md01 TO bi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA quick_gold_md01 TO bi_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA quick_gold_md01
    GRANT SELECT ON TABLES TO bi_reader;
```

Sau đó thay user/password trong `QUICK_NEON_DATABASE_URL` bằng `bi_reader` rồi gửi cho thành viên. Dòng `ALTER DEFAULT PRIVILEGES` đảm bảo sau mỗi lần job Databricks sync/swap bảng mới, `bi_reader` vẫn giữ nguyên quyền `SELECT`.

### Deploy miễn phí lên Streamlit Community Cloud (xem qua link web)
1. Truy cập https://share.streamlit.io và đăng nhập GitHub.
2. Chọn repo `minhnhut273/PharmaFlow-Sales-Lakehouse-BI`, branch `main`, **Main file path:** `src/streamlit/app.py`.
3. Streamlit Cloud sẽ tự cài gói từ file [`requirements.txt`](../../requirements.txt) hoặc bạn có thể trỏ/sao chép 5 dòng từ [`src/streamlit/requirements.txt`](requirements.txt).
4. Trong **Advanced settings → Secrets**, dán cấu hình dạng TOML:
   ```toml
   QUICK_NEON_DATABASE_URL = "postgresql://..."
   QUICK_NEON_SCHEMA = "quick_gold_md01"
   ```

---

## 6. Xử lý lỗi thường gặp (Troubleshooting)

| Triệu chứng / Lỗi | Nguyên nhân & Cách khắc phục |
|---|---|
| `Chưa tìm thấy biến môi trường QUICK_NEON_DATABASE_URL` | Kiểm tra tên file đúng là `.env` (không phải `.env.txt` trên Windows), đặt tại gốc repo hoặc `src/streamlit/.env`, và có đủ 2 dòng `QUICK_NEON_DATABASE_URL` + `QUICK_NEON_SCHEMA=quick_gold_md01`. |
| PowerShell báo lỗi `running scripts is disabled` khi chạy `Activate.ps1` | Không cần activate venv — chạy trực tiếp `.\.venv\Scripts\pip.exe ...` và `.\.venv\Scripts\streamlit.exe run src\streamlit\app.py --server.port 8501`. |
| `Port 8501 is already in use` | Đổi sang cổng khác, ví dụ: `--server.port 8502`. |
| Lỗi kết nối SSL hoặc timeout tới Neon | Đảm bảo chuỗi `QUICK_NEON_DATABASE_URL` có `?sslmode=require` ở cuối (nếu dùng Neon `-pooler`, giữ nguyên hostname có `-pooler`) và kiểm tra kết nối mạng. |
| Cảnh báo `multi-UOM` trên tập `IRPD_ID_OBSERVED` | Đây là cảnh báo đúng chuẩn miền dữ liệu vì `IRPD` có nhiều đơn vị tính (`tab`, `bottle`, `box`, ...). Chọn 1 `Đơn vị tính` ở sidebar khi cộng/so sánh sản lượng. |

---

## 7. Chạy kiểm thử tự động (Offline)
Để chạy test suite (cần thêm `pytest>=8,<9`):

```powershell
# Windows
.\.venv\Scripts\python.exe -B -m pytest tests\test_streamlit_dashboard.py -v -p no:cacheprovider
```
```bash
# macOS / Linux
./.venv/bin/python -B -m pytest tests/test_streamlit_dashboard.py -v -p no:cacheprovider
```

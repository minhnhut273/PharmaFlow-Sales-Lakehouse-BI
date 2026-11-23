# PharmaFlow BI — Dashboard Streamlit Multipage (5 Trang Tiếng Việt)

Ứng dụng Business Intelligence 5 trang bằng **100% tiếng Việt**, mô phỏng và nâng cấp bố cục từ AWS QuickSight (*Phân tích Bán lẻ Dược phẩm — Thời tiết, Cửa hàng & ATC*), truy vấn trực tiếp Neon PostgreSQL (`quick_gold_md01`) bằng **SQL aggregation pushdown** qua `psycopg` + `@st.cache_data` và đọc artifact dự báo ML (`artifacts/forecasting/`) cho Trang 5.

---

## 1. Cấu trúc 5 trang & Mô-đun phân tích (`analytics.py` · `forecast_data.py`)
1. **Tổng Quan (`01_tong_quan.py`)**: 6 thẻ KPI kèm biến động so với kỳ so sánh tương thích (`Tóm tắt điều hành` tự sinh theo rule), tăng trưởng tổng MoM tính từ tổng kỳ cùng phạm vi (tự ngắt đường khi thiếu tháng hoặc tháng chưa đủ ngày), biểu đồ đóng góp biến động số học (`Quốc gia` / `Thương hiệu` / `Sản phẩm`), bảng tách ĐVT (khi gặp đa ĐVT như IRPD) và bảng đối chiếu `OBSERVED` vs `SYNTHETIC`.
2. **Thời Tiết & Địa Điểm (`02_thoi_tiet_dia_diem.py`)**: Bộ lọc cục bộ **chỉ áp dụng Trang 2** (`Mức mưa`, `Mức độ ẩm`, chọn nhanh ô `Nhiệt độ × Mức mưa`), chỉ số chuẩn hóa theo **Cửa hàng-Ngày có bán** (`active_store_days`, cảnh báo ô `n < 30`, nêu rõ không gồm ngày bán = 0), mùa vụ thời tiết (`apparent_temp_mean` oi bức, mưa, nhiệt độ TB) theo tháng và bảng tra cứu ngày ở cuối trang.
3. **Cửa Hàng & Biên Lợi Nhuận (`03_cua_hang_loi_nhuan.py`)**: Biến động cùng cửa hàng (*Same-Store*), danh sách cửa hàng cần xem xét (*Watchlist* theo rule doanh thu/biên LN gia quyền/suy giảm), ma trận doanh thu × biên lợi nhuận gia quyền (số cửa hàng động theo bộ lọc), bản đồ & mùa vụ EU, tỷ trọng sản lượng có khuyến mãi + bảng so sánh mô tả (không suy diễn nhân quả) và bảng tra cứu cuối trang.
4. **Sản Phẩm & ATC (`04_san_pham_atc.py`)**: Sản phẩm tăng/giảm mạnh ở đúng grain `Sản phẩm × ĐVT`, dịch chuyển cơ cấu (*Mix Shift — điểm %*), Treemap, Histogram đơn giá cấp dòng mart (khóa an toàn khi trộn đa ĐVT), Top 15 Nhà sản xuất (`IRPD — OBSERVED`) và chuỗi quan sát 8 nhóm ATC (`PHARMA_SALES_DAILY_ATC · OBSERVED`) kèm thanh phạm vi rõ ràng.
5. **Dự Báo Nhu Cầu ML (`05_du_bao_nhu_cau.py` · `forecast_data.py`)**: Tab 1 trực quan hóa Fan Chart dự báo `52W` / `365D` trên `store_id = 5631 · OBSERVED`, dải tin cậy **Split CQR `P10–P90`**, giải thích **Top 10 `TreeSHAP`** (`F1/F2/ERA5 F3`) bằng tiếng Việt và xếp hạng `WAPE` 8 nhóm ATC; Tab 2 đối chiếu Ablation, độ phủ CQR, ổn định 4-Fold, kiểm định `DM'` và bảng 2 tầng Fourkiotis & Tsadiras (2024) (`DATA -> FORECAST`, không gồm Tồn kho/ROP).

---

## 2. Yêu cầu tối thiểu cho thành viên trong nhóm
Để **chỉ chạy Dashboard Streamlit**, máy thành viên **chỉ cần**:
- **Git**
- **Python `3.12+`**
- **2 biến kết nối Neon** (`QUICK_NEON_DATABASE_URL` và `QUICK_NEON_SCHEMA=quick_gold_md01`) do nhóm trưởng gửi riêng.

> **Không cần** cài AWS CLI, Terraform, Databricks CLI, MongoDB hay file `requirements.txt` đầy đủ của toàn bộ pipeline ETL.

---

## 3. Cài đặt & Chạy nhanh trong 3 bước

### Bước 1 — Clone repo, tạo môi trường ảo & cài 6 thư viện nhẹ

```bash
git clone https://github.com/minhnhut273/PharmaFlow-Sales-Lakehouse-BI.git
cd PharmaFlow-Sales-Lakehouse-BI
python -m venv .venv
```

Cài đúng 6 gói Streamlit bằng file [`src/streamlit/requirements.txt`](requirements.txt):

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
  - Chuyển qua lại giữa 5 trang (`Cửa Hàng & Mặt Hàng`, `Cụm CH & Bản Đồ`, `Thời Tiết & Mùa Vụ`, `So Sánh Kỳ & Danh Mục`, `Dự Báo Nhu Cầu (ML)`); bộ lọc toàn cục giữ xuyên suốt cho Trang 1–4, còn Trang 5 dùng bộ chọn cục bộ độc lập cho 8 nhóm ATC (`store_id = 5631 · OBSERVED`).
  - Chọn **Bảng màu giao diện** gồm 7 preset (`PharmaFlow Xanh Ngọc`, `AWS Quick Tím Chàm`, `Đại Dương Hiện Đại`, `Hổ Phách Ấm`, `Ant Enterprise`, `Shadcn Minimal`, `Clean Analytics`).
  - Lọc phân tầng theo **Nhóm dữ liệu (`Track`) → Quốc gia → Cửa hàng → Đơn vị tính (`UOM`) → Khoảng ngày bán → Mức nhiệt độ**.
  - Có nút **Đặt lại toàn bộ bộ lọc** ở cuối sidebar.
- **Nguyên tắc toàn vẹn dữ liệu & Giới hạn Data Contract:**
  - **Không trộn tiền tệ & Đa ĐVT:** Tách biệt `EUR` (`ONYX_EU_SYNTHETIC`), `IDR` (`IRPD_ID_OBSERVED`) và nguồn không tiền tệ (`SERBIA_RS_SYNTHETIC`). Vì cột `base_qty` hiện `NULL` (thiếu hệ số quy đổi ĐVT), app khóa cộng gộp sản lượng & đơn giá bình quân khi đang gộp nhiều ĐVT (`IRPD`), cho phép chọn 1 ĐVT hoặc đối chiếu qua doanh thu/bảng tách ĐVT.
  - **Số đơn hàng (Distinct Order):** Gold mirror đang ở grain `Sản phẩm × Cửa hàng × Ngày` (`SUM(order_count)` sẽ cộng trùng đơn nhiều mặt hàng), nên KPI hiển thị **`Chưa khả dụng`** và thay bằng chỉ số cộng được chính xác là **`Số dòng POS` (`SUM(line_count)`)** và **`CH-ngày có bán`**.
  - **Biên LN & Đơn giá gia quyền:** Dùng `SUM(margin)/SUM(revenue)` và `SUM(revenue)/SUM(qty)` làm KPI điều hành; trung bình theo dòng mart chỉ giữ làm thông tin phụ. Phân biệt rõ `0`, `Không có dữ liệu` và `Nguồn không hỗ trợ`.
  - **Phạm vi Sales BI & Thời tiết:** Gold mart chỉ chứa ngày có bán (`sold_qty > 0`, không gồm ngày bán = 0); mẫu từ nguồn `SYNTHETIC` được gắn nhãn mô phỏng và không suy diễn nhân quả hay đề xuất tồn kho/điều chuyển (thuộc module Distribution/Inventory).
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
3. Streamlit Cloud sẽ tự cài gói từ file [`requirements.txt`](../../requirements.txt) hoặc bạn có thể trỏ/sao chép 6 dòng từ [`src/streamlit/requirements.txt`](requirements.txt).
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

---

## 8. Tài liệu liên quan & Hướng mở rộng ML Forecasting

* **Module ML Dự báo Nhu cầu (`src/ml/`, `DATA -> FORECAST`):** [src/ml/README.md](../ml/README.md) | [Tổng Giải pháp & Kết quả](../../docs/design/demand-forecasting-solution.md) | [Google Docs đầy đủ (4 Tab)](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit)
* **Trạng thái tích hợp vào Streamlit:** Trang 5 ([`pages/05_du_bao_nhu_cau.py`](pages/05_du_bao_nhu_cau.py) + [`forecast_data.py`](forecast_data.py)) đã được tích hợp theo mô hình đọc trực tiếp precomputed artifacts trong [`artifacts/forecasting/`](../../artifacts/forecasting/) qua `@st.cache_data`, giữ nguyên 6 gói gọn nhẹ trong [`src/streamlit/requirements.txt`](requirements.txt) mà không huấn luyện mô hình trực tiếp trong app web.

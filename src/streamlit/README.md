# PharmaFlow BI — Dashboard Streamlit Multipage (4 Trang)

Ứng dụng Business Intelligence 4 trang bằng **100% tiếng Việt**, mô phỏng và nâng cấp bố cục từ AWS QuickSight (*Phân tích Bán lẻ Dược phẩm — Thời tiết, Cửa hàng & ATC*), truy vấn trực tiếp Neon PostgreSQL (`quick_gold_md01`) bằng **SQL aggregation pushdown** qua `psycopg` + `@st.cache_data`.

## 1. Cấu trúc 4 trang
1. **Tổng Quan (`01_tong_quan.py`)**: 6 thẻ KPI tách theo tiền tệ/đơn vị, biểu đồ tăng trưởng `kpi_sales_trend` (kỳ `MONTH`, tính tăng trưởng trung bình `%`), Donut tỷ trọng quốc gia, Top 15 thương hiệu và bảng đối chiếu `OBSERVED` vs `SYNTHETIC`.
2. **Thời Tiết & Địa Điểm (`02_thoi_tiet_dia_diem.py`)**: Bộ lọc đa yếu tố `Mức mưa`, `Mức độ ẩm`, 4 nút chọn nhanh ô thời tiết + bộ chọn `Ô Nhiệt độ × Ô Mức mưa` đánh dấu trực tiếp trên bản đồ nhiệt toàn chiều rộng, so sánh ngày thường/cuối tuần, Scatter nhiệt độ, bảng chi tiết ngày (+ mở rộng theo Cửa hàng & Đơn vị tính) và Top 15 thuốc + Thứ trong tuần.
3. **Cửa Hàng & Lợi Nhuận (`03_cua_hang_loi_nhuan.py`)**: Bản đồ Châu Âu (Choropleth ISO-3) + Heatmap 8 quốc gia EU × 12 tháng, Top 20 cửa hàng, Gauge khuyến mãi %, Scatter/Bar lợi nhuận thương hiệu, bảng hiệu suất cửa hàng có tìm kiếm/CSV, và ma trận bong bóng 120 cửa hàng EU.
4. **Sản Phẩm & ATC (`04_san_pham_atc.py`)**: Bảng chi tiết sản phẩm có tìm kiếm/CSV, Treemap Thương hiệu–Sản phẩm, Histogram đơn giá tính trên PostgreSQL (`WIDTH_BUCKET`), Line & Heatmap 8 nhóm ATC toàn kỳ `2014–2019`, Top 15 Nhà sản xuất (`IRPD — IDR`), và xếp hạng 8 nhóm thuốc ATC.

## 2. Cấu hình `.env` tối thiểu để chạy Dashboard
Thành viên chỉ chạy Dashboard Streamlit **chỉ cần tạo file `.env` ở thư mục gốc repo với 2 biến** (không cần AWS, Databricks hay MongoDB):

```env
QUICK_NEON_DATABASE_URL=postgresql://<readonly_user>:<password>@<neon-pooler-host>/neondb?sslmode=require
QUICK_NEON_SCHEMA=quick_gold_md01
```

*(Ứng dụng tự tìm biến môi trường theo thứ tự: OS env → `.env` tại gốc repo → thư mục cha → `st.secrets`.)*

## 3. Chạy ứng dụng từ môi trường `.venv`
```powershell
# Từ thư mục gốc của repo (PharmaFlow-Sales-Lakehouse-BI):
.\.venv\Scripts\streamlit.exe run src\streamlit\app.py --server.port 8501
```

## 4. Chạy kiểm thử tự động
```powershell
.\.venv\Scripts\python.exe -B -m pytest tests\test_streamlit_dashboard.py -v -p no:cacheprovider
```

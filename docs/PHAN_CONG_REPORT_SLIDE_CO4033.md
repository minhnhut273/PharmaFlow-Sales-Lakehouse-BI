# Phân công Hoàn thiện Báo cáo & Thuyết trình Slide — CO4033 (PharmaFlow BI)

Tài liệu phân công công việc cho **3 thành viên (`TV A`, `TV B`, `TV C`)** dựa trên hiện trạng **Leader** đã dựng hoàn chỉnh toàn bộ hệ thống kỹ thuật (AWS IaC, Databricks Medallion Pipeline, Neon BI Mirror, Dashboard Streamlit 5 trang Live Cloud, ML Demand Forecasting 5 Notebooks) cùng **bộ khung Báo cáo LaTeX HCMUT** và **15 Slide thuyết trình HTML (`Swiss IKB`)**.

- 🌐 **Live Dashboard (Streamlit Community Cloud):** https://pharmaflow-sales-lakehouse-bi-ut7zhiigkcrzqwvz93krzy.streamlit.app/
- 📄 **Thư mục Báo cáo LaTeX:** [`report/`](report/README.md) (`17` tệp · đã có sẵn bản biên dịch [`main.pdf`](report/main.pdf) làm mẫu kiểm tra)
- 🖥️ **Bộ Slide thuyết trình (15 slides + Speaker Notes):** [`slides/index.html`](slides/index.html)
- 📋 **Rubric & Danh sách điểm cần vá:** [`reviews/yêu cầu bigdata.docx`](<reviews/yêu cầu bigdata.docx>)

> ⚠️ **Cảnh báo quan trọng khi tham khảo [`reviews/bao_cao_structure_co4033.md`](reviews/bao_cao_structure_co4033.md):**
> Chỉ tham khảo bố cục khung. **Tuyệt đối không copy** số liệu benchmark minh họa ở Mục 4.2 (`145.2s vs 38.6s`, `8.45s vs 0.42s`, v.v.) hay 3 insight giả định ở Mục 5.3 (*"miền Trung mưa >50mm"*, *"miền Bắc đợt lạnh"* — dữ liệu POS thực tế chỉ gồm `ONYX` EU `SYNTHETIC`, `IRPD` Indonesia `OBSERVED`, và `PHARMA_SALES_DAILY_ATC` Serbia `store_id = 5631 · OBSERVED`). Toàn bộ số liệu thật đã nằm sẵn trong [`report/`](report/README.md).

---

## 1. Bảng phân công tổng thể 3 thành viên (Report + Thực nghiệm + Slide)

> **Lưu ý khi điền tên thành viên vào LaTeX:** [`report/main.tex`](report/main.tex) và [`report/frontmatter/phancong.tex`](report/frontmatter/phancong.tex) hiện đang để `3` dòng sinh viên mẫu — **TV A** nhớ mở rộng thành **`4` dòng** (ghi rõ đóng góp của **Leader** ở phần kiến trúc/code/ML/live app cùng **TV A, TV B, TV C**, tổng tỷ lệ = `100%`).

| Thành viên | Phần Report LaTeX (`docs/report/`) | Đầu việc kỹ thuật / minh chứng phải tự làm | Phần Slide & Bảo vệ (`slides/index.html` — ~15 phút tổng) |
| :--- | :--- | :--- | :--- |
| **TV A**<br/>*(Ngữ cảnh, Dữ liệu & Tái lập)* | • [`main.tex`](report/main.tex) (điền DS 4 SV, GVHD)<br/>• [`camdoan.tex`](report/frontmatter/camdoan.tex), [`phancong.tex`](report/frontmatter/phancong.tex), [`tomtat.tex`](report/frontmatter/tomtat.tex)<br/>• [`ch01_baitoan_kpi.tex`](report/chapters/ch01_baitoan_kpi.tex)<br/>• [`ch02_dulieu_quanly.tex`](report/chapters/ch02_dulieu_quanly.tex)<br/>• [`ch06_tongket_tailap.tex`](report/chapters/ch06_tongket_tailap.tex) & [`references.bib`](report/references.bib) | • Thu thập đủ họ tên, MSSV, chốt tuyên bố AI theo đúng mẫu CO4033.<br/>• Kiểm tra lại mô tả nguồn/license trong `ch02` (`OBSERVED` vs `SYNTHETIC`).<br/>• Clone repo sang máy sạch (hoặc `.venv` mới), chạy thử bộ `pytest` offline theo [`README.md`](../README.md) và chụp màn hình terminal pass `212+` tests đưa vào `ch03` / `ch06`. | • Sửa nhẹ **Slide `01`** (thêm tên/MSSV 4 thành viên nếu muốn hiển thị ở bìa).<br/>• Thuyết trình **Slides `01–05` (`4.2 phút`)**: Mở đầu → 3 Câu hỏi nghiệp vụ → 4 Hàng rào KPI → Quy mô 3 nguồn → Medallion & Atomic Gate. |
| **TV B**<br/>*(Benchmark Engineering, Scale-up & Rubric)* | • Rà & hoàn thiện [`ch03_kientruc_pipeline.tex`](report/chapters/ch03_kientruc_pipeline.tex)<br/>• Chốt số thực đo trong [`ch04_phantich_sosanh.tex`](report/chapters/ch04_phantich_sosanh.tex) (điền dòng `8` cấu hình máy & dòng `54` Baseline SQL/Pandas)<br/>• Rà đối chiếu [`appendix01_rubric_mapping.tex`](report/appendices/appendix01_rubric_mapping.tex) | • Vá 2 điểm cộng lớn nhất trong [`yêu cầu bigdata.docx`](<reviews/yêu cầu bigdata.docx>):<br/>1. Viết & chạy đo **Baseline** (`Pandas` / `PostgreSQL raw` kéo full bảng) vs **Gold Mart SQL Pushdown** (lấy thời gian & RAM thực tế).<br/>2. Viết & chạy **Scale-up Stress Test `3× / 5× / 10×`** (lên `~2–7 triệu` dòng, ghi rõ *synthetic scale-up*) chứng minh ngưỡng nghẽn tài nguyên. | • Cập nhật **Slide `12`** (`baseline-vs-proposed`): thay dòng placeholder `[TV B bổ sung số thực đo & Scale-up 3×–10×]` bằng con số bạn vừa đo được.<br/>• Thuyết trình **Slides `06–10` (`4.6 phút`)**: Kiến trúc 5 phân vùng → EDA 8 ATC → Luồng 5 NB → Benchmark `8/8` thắng SNaïve → Ablation ERA5 & `TreeSHAP`. |
| **TV C**<br/>*(Live BI Capture, Insights thật & Xuất PDF)* | • Hoàn thiện toàn bộ [`ch05_bi_quyetdinh.tex`](report/chapters/ch05_bi_quyetdinh.tex) (chèn 5 ảnh thật vào bảng `tab:ui_screenshots`, bổ sung số liệu quan sát thực tế từ Dashboard)<br/>• Rà soát format & biên dịch **`main.pdf`** sạch từ [`main.tex`](report/main.tex) | • Mở link live `pharmaflow-sales-lakehouse-bi-ut7zhiigkcrzqwvz93krzy.streamlit.app`, chọn bảng màu **`Ant Enterprise`** / **`Đại Dương Hiện Đại`** (cho đồng bộ tông xanh với slide `ikb`), chụp 5–6 ảnh nét (`screenshot_page1..5.png` + Tab 2 Trang 5) lưu vào `docs/report/Images/`.<br/>• Rút **số thật từ app** (tuyệt đối không copy insight giả miền Trung/Bắc trong `bao_cao_structure_co4033.md`). | • Kiểm tra & tổng duyệt Slide + Live Demo (tùy chọn gắn thêm ảnh chụp live vào **Slide `13`**).<br/>• Thuyết trình **Slides `11–15` + Live Demo Web (`4.4 phút`)**: Fan Chart & Paper 2024 → Đối sánh Baseline → bấm Live Demo Streamlit 45s → 4 Quyết định & Giới hạn → Chốt hạ & mời Q&A. |

---

## 2. Phân công chi tiết từng Slide (`01–15`, tổng thời lượng `13.2 phút` / quỹ `15 phút`)

Trong [`slides/index.html`](slides/index.html), toàn bộ **Speaker Notes** (`SPEAKER_NOTES`) đã được gắn sẵn nhãn `[TV A]`, `[TV B]`, `[TV C]` và thời lượng từng trang để khi nhấn phím `P` (**Speaker View**), người nói xem thẳng gợi ý từng ý và đồng hồ đếm ngược.

| Slide | `data-slide-id` | Nội dung chính | Người thuyết trình | Thời lượng | Việc cần chỉnh / Ghi chú thực chiến |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **01** | `cover` | Trang bìa · PharmaFlow Lakehouse & Demand Forecasting | **TV A** | `0.5'` | Có thể thêm tên/MSSV 4 SV; kiểm tra đồng bộ màn hình chiếu khi bắt đầu. |
| **02** | `business-context` | Bối cảnh ngành dược & 3 Câu hỏi nghiệp vụ kiểm chứng | **TV A** | `0.9'` | Nêu rõ 3 nguồn (`ONYX`, `IRPD`, `Serbia 5631`) và phạm vi `DATA -> FORECAST`. |
| **03** | `kpi-governance` | Khung KPI & 4 Hàng rào Toàn vẹn (`OBSERVED/SYNTHETIC`, `UOM`, `line_count`, `WAPE/CQR`) | **TV A** | `0.9'` | Nhấn mạnh tư duy tránh sai số cộng dồn & bóp méo KPI. |
| **04** | `data-sources` | Quy mô 3 nguồn dữ liệu đã kiểm chứng (`714.9K` POS · `19,902` JSON · `474.6K` Gold) | **TV A** | `0.9'` | Đọc nhanh 4 tháp số liệu đối soát thực tế, không trộn nguồn. |
| **05** | `medallion-stack` | 3 tầng Medallion (`Bronze → Silver DLT → Gold`) & `ops.product_release` | **TV A** | `1.0'` | Chốt lại Atomic Swap sang Neon #2 (`449 MB`) rồi chuyển mic sang **TV B**. |
| **06** | `architecture-overview` | Sơ đồ kiến trúc 5 phân vùng (`~$0/tháng`, `100%` thời tiết, `0.08–0.48s` pushdown) | **TV B** | `1.0'` | Diễn giải ngắn gọn luồng AWS Terraform IaC → Databricks → BI → ML. |
| **07** | `eda-diagnostics` | Chẩn đoán 8 nhóm ATC (`Syntetos-Boylan`) & Tương quan trễ ERA5 (`CCF`) | **TV B** | `0.9'` | Chỉ rõ nhóm mượt (`N02BE/R06`), biến động (`R03`) và bán thưa `N05C` (`67.9%` ngày = `0`). |
| **08** | `ml-pipeline-flow` | Luồng 5 Notebooks thống nhất (`166.6s`, `Leakage = 0.0`, `qty_rate`) | **TV B** | `0.8'` | Giải thích xử lý `W302` thiếu `2/7` ngày & Perturbation Leakage test. |
| **09** | `benchmark-atc` | `AutoRouted Champion` vs `Seasonal Naïve` (giảm `31.4%–69.0%` MSE, `DM' p < 0.05` trên `8/8`) | **TV B** | `1.0'` | Nhấn mạnh khóa chọn mô hình theo Val MAE, không nhìn tập Test. |
| **10** | `ablation-xai` | Thực chứng Ablation `F1→F2→F3` & `TreeSHAP` (`11.3%–25.9%` từ ERA5) | **TV B** | `0.9'` | Lấy ví dụ `R06` (`25.9%` từ ERA5) và `N02BE`, rồi chuyển mic sang **TV C**. |
| **11** | `fanchart-cqr` | Fan Chart `52W`, Split CQR `P10–P90` (`78.8%`) & Đối chuẩn Paper `2024` (`6/8` vượt MSE, `1,166.9×`) | **TV C** | `0.9'` | Báo cáo trung thực cả 2 nhóm chưa vượt Paper (`M01AE`, `R03`). |
| **12** | `baseline-vs-proposed` | Đối sánh toàn diện Baseline vs Giải pháp đề xuất (Engineering + ML) | **TV C** *(TV B điền số)* | `0.9'` | **TV B** thay dòng `[TV B bổ sung số thực đo & Scale-up 3×–10×]` sau khi chạy benchmark; **TV C** thuyết trình. |
| **13** | `bi-dashboard-live` | Dashboard Streamlit 5 trang tiếng Việt + **Bấm Live Demo Cloud** | **TV C** | `1.3'` | Alt-Tab mở link Streamlit Cloud demo ~45s (Trang 1 → Trang 2/3 → Trang 5); dự phòng bằng ảnh nếu rớt mạng. |
| **14** | `actionable-decisions` | 4 Đề xuất quyết định vận hành & Giới hạn trung thực (`Human-in-the-loop`, chưa gồm ROP/tồn kho) | **TV C** | `0.8'` | Gắn rõ từng khuyến nghị với điều kiện áp dụng & giới hạn dữ liệu `~715K` dòng. |
| **15** | `closing` | Tổng kết `212+` Unit Tests, khả năng tái lập & Mời Q&A | **TV C** | `0.5'` | Giữ màn hình slide cuối hoặc tab Live Streamlit sẵn cho phần hỏi đáp hội đồng. |

---

## 3. Quy trình phối hợp & thao tác nhanh

1. **Bước 1 — Kéo code mới nhất về máy:**
   ```bash
   git pull origin main
   ```
2. **Bước 2 — Chốt số liệu & ảnh (Ngày 1):**
   - **TV A** gom đủ MSSV, tuyên bố AI, chạy thử `pytest` chụp terminal.
   - **TV B** chạy xong Benchmark Baseline vs Gold Mart + Scale-up `3×/5×/10×`, gửi kết quả vào `ch04_phantich_sosanh.tex` và **Slide `12`** trong `slides/index.html`.
   - **TV C** mở Streamlit Cloud chụp 5–6 ảnh nét lưu vào `docs/report/Images/` và ghi số liệu thật vào `ch05_bi_quyetdinh.tex`.
3. **Bước 3 — Xuất PDF & Tổng duyệt 15 phút (Ngày 2–3):**
   - **TV C** biên dịch `docs/report/main.tex` ra `main.pdf` (MiKTeX local hoặc upload `docs/report/`, `docs/images/`, `artifacts/forecasting/*.png` lên Overleaf chạy `pdfLaTeX`).
   - Cả 3 bạn mở [`slides/index.html`](slides/index.html) trên Chrome/Edge, bấm **`P`** (Speaker View), đọc đúng các ý trong mục `talk` để chạy khớp ~`13.2 phút` (dư `~1.8 phút` dự phòng chuyển tab demo và chuyển người).
   - Nếu giảng viên yêu cầu nộp Slide PDF: nhấn `B` (tắt hiệu ứng động) → `Ctrl + P` → **Landscape** + bật **Background graphics** → Save as PDF.

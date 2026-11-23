# Báo cáo LaTeX Bài tập lớn CO4033 (Mẫu HCMUT)

Khung báo cáo được tạo theo bố cục chuẩn Trường Đại học Bách khoa -- ĐHQG TP.HCM (`pharmaflow-btl-report.sty`, tham khảo từ `docs/reports/` ở root) và ánh xạ 1:1 vào **Rubric 100 điểm môn CO4033**.

## Biên dịch thành PDF (MiKTeX / TeX Live + vntex + BibTeX)

Chạy từ thư mục `BTL_BI/docs/report/`:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
```

*(Hoặc nén thư mục `BTL_BI/docs/report/`, `BTL_BI/docs/images/` và `BTL_BI/artifacts/forecasting/*.png` để upload lên Overleaf dùng compiler `pdfLaTeX`.)*

## Checklist 5 mục nhóm cần tự điền trước khi xuất PDF nộp

1. **`main.tex`:** Điền họ tên sinh viên + MSSV (`\studentnames`) và tên Giảng viên (`\advisor`) ở trang bìa.
2. **`frontmatter/camdoan.tex`:** Xác nhận tên công cụ AI nhóm đã sử dụng trong mục Liêm chính học thuật.
3. **`frontmatter/phancong.tex`:** Điền bảng phân công đầu việc và tỷ lệ `%` đóng góp thực tế của từng thành viên (`Tổng = 100%`).
4. **`chapters/ch02_dulieu_quanly.tex` & `chapters/ch04_phantich_sosanh.tex`:** Điền URL/giấy phép nguồn gốc dataset nếu cần, cấu hình phần cứng máy chạy thực nghiệm và thời gian baseline `pandas` kéo full bảng (nếu nhóm đo thêm).
5. **`chapters/ch05_bi_quyetdinh.tex`:** Chụp ảnh giao diện 5 trang ứng dụng Streamlit đang chạy thực tế (`screenshot_page1..5.png`) và thay vào Bảng `tab:ui_screenshots` bằng `\includegraphics`.

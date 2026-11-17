# Đặc tả Use Case PharmaFlow — Sales & Demand (Landscape V1)

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | `PF-UC-SALES-DEMAND-LANDSCAPE-V1` |
| Trạng thái | Đặc tả đề xuất từ Landscape; cần stakeholder xác nhận trước khi khóa baseline |
| Phạm vi | Sales & Demand DSS: theo dõi Sales Quantity, xem forecast theo location/kỳ, kiểm định forecast nội bộ và theo dõi vận hành hệ thống |
| Ngày tạo | 2026-11-05 |
| Cập nhật lần cuối | 2026-11-07 |
| Người tạo / cập nhật | Chưa xác nhận |
| Sơ đồ đi kèm | [pharmaflow_sales_and_demand_usecase.drawio](pharmaflow_sales_and_demand_usecase.drawio) |
| Nguồn yêu cầu | [User Stories](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md); [Requirements](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md) |

## 1. Mục đích và quy ước

Tài liệu mô tả hành vi người dùng theo cấu trúc use case của tài liệu tham khảo: **Use-case name, Created by, Last updated by, Date created, Last updated date, Actor, Description, Pre-conditions, Post-conditions, Normal Flow, Alternative Flow**. Mỗi use case có thêm mã ổn định và truy vết về user story, user requirement, functional requirement.

- Luồng chính được đánh số liên tục. Luồng thay thế dùng hậu tố `a` và chỉ rõ bước phát sinh, ví dụ `3a`.
- “Sales Quantity” là lượng bán quan sát được; không tự đồng nhất với nhu cầu tiềm ẩn, tồn kho hay lượng mua.
- Forecast hiển thị riêng theo từng location và kỳ. Chọn nhiều location không đồng nghĩa với cộng thành tổng.
- Người dùng được quyền xem Sales/Forecast nhận nhãn nghiệp vụ, location, kỳ và đơn vị đã xác nhận. Metadata model, protocol, cutoff, run ID, grain kỹ thuật và lineage dành cho hồ sơ nội bộ, không phải thông tin cần đọc trên màn hình nghiệp vụ.
- Data admin đối soát dữ liệu và kiểm định **Prediction Quality**. **Decision Quality** và kết quả vận hành là lớp đánh giá riêng, không suy ra từ forecast error.
- IT admin theo dõi vận hành. Retry, restart và thay đổi lịch chỉ thực hiện khi quyền và quy trình được xác nhận.
- Các use case phản ánh đặc tả đề xuất; không phải bằng chứng chức năng đã được triển khai hay deploy.

### Nguyên tắc thiết kế use case đã áp dụng

| Nguyên tắc | Cách áp dụng trong Sales & Demand |
|---|---|
| Bắt đầu từ mục tiêu của actor | Mỗi use case mô tả kết quả actor cần đạt; không biến màn hình, thuật toán, API hay từng bước nội bộ thành use case độc lập. |
| Đặt actor theo trách nhiệm nghiệp vụ | Supply Chain đọc kết quả nghiệp vụ; Data admin kiểm định dữ liệu và Prediction Quality; IT admin theo dõi dịch vụ/job/log. Metadata kỹ thuật không đưa vào trải nghiệm Supply Chain. |
| Giữ đúng ranh giới và ngữ nghĩa | Phân biệt Sales Quantity với nhu cầu, forecast với quyết định tồn kho, Prediction Quality với Decision Quality, và dữ liệu quan sát với dữ liệu mô phỏng. |
| Dùng `include` cho phần bắt buộc | Use case cơ sở gọi hành vi con mỗi lần hoàn tất mục tiêu; mũi tên đi từ use case cơ sở đến hành vi được bao gồm. |
| Dùng `extend` cho phần tùy chọn/có điều kiện | Use case mở rộng chỉ chạy tại extension point nêu rõ điều kiện; mũi tên đi từ use case mở rộng về use case cơ sở. |
| Chỉ tách use case con khi có hành vi đáng kiểm soát | Tách phần kiểm tra hoặc ghi nhận có kết quả riêng, tái sử dụng hoặc điều kiện rõ; không tách từng bước tuần tự thành một oval. |
| Giữ hai mức đọc của sơ đồ | 12 trang chi tiết tập trung vào từng UC chính và ngữ cảnh quan hệ cần thiết; trang 13 tổng hợp đủ 22 UC để xem actor và quan hệ ở mức toàn cảnh. |
| Duy trì truy vết | Mỗi UC được nối về User Story, User Requirement và Functional Requirement; UC phân rã kế thừa nguồn truy vết của hành vi cha. |

## 2. Actor

| Actor | Trách nhiệm trong phạm vi này | Quyền/ranh giới |
|---|---|---|
| `Người dùng được quyền xem Sales/Forecast` | Theo dõi/so sánh Sales Quantity; xem xu hướng, forecast theo location/kỳ và ngữ cảnh nghiệp vụ. | US-01, US-02, US-03 (Supply Chain Planner), US-04, US-06, US-07, US-11, US-12, US-14, US-15; chỉ trong scope assignment. Chỉ cần thông tin nghiệp vụ, không xem metadata kỹ thuật, phê duyệt hay thực thi hành động tồn kho. |
| `Supply Chain Planner (US-03)` | Dùng các UC đọc chung và điều chỉnh một giá trị forecast qua UC-SD-13. | Có `forecast:read` và `forecast:adjust` trong scope; không phê duyệt, publish hay thay đổi model output. |
| `Data admin` | Đối soát dữ liệu đầu vào; kiểm tra tính hợp lệ của evaluation; so sánh forecast với baseline khi đủ điều kiện; lưu kết luận và bằng chứng. | Đọc metadata kỹ thuật và hồ sơ dữ liệu/evaluation theo quyền được cấp. Không sửa đè source facts hoặc score gốc. |
| `IT admin` | Theo dõi trạng thái dịch vụ/job, lịch chạy và log; xác định sự cố vận hành, chuyển vấn đề dữ liệu/forecast cho Data admin. | Quyền retry/restart/thay đổi lịch và quyền truy cập chi tiết còn cần role matrix/quy trình xác nhận. Không kết luận chất lượng model thay Data admin. |

## 3. Danh mục và truy vết

| Mã use case | Use-case name | Actor chính | Truy vết |
|---|---|---|---|
| `UC-SD-01` | Theo dõi Sales Quantity | Người dùng được quyền xem Sales/Forecast | `US-SD-LS-01` / `UR-SD-01` / `FR-SD-01` |
| `UC-SD-02` | So sánh Sales Quantity | Người dùng được quyền xem Sales/Forecast | `US-SD-LS-02` / `UR-SD-02` / `FR-SD-02` |
| `UC-SD-03` | Xem xu hướng và biểu hiện mùa vụ | Người dùng được quyền xem Sales/Forecast | `US-SD-LS-03` / `UR-SD-03` / `FR-SD-03` |
| `UC-SD-04` | Xem forecast theo location và kỳ | Người dùng được quyền xem Sales/Forecast | `US-SD-LS-04` / `UR-SD-04` / `FR-SD-04` |
| `UC-SD-05` | Đối soát dữ liệu và kiểm định forecast | Data admin | `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-06` | Đọc ngữ cảnh nghiệp vụ Sales/Forecast | Người dùng được quyền xem Sales/Forecast | `US-SD-LS-06` / `UR-SD-06` / `FR-SD-06` |
| `UC-SD-07` | Theo dõi vận hành hệ thống | IT admin | `US-SD-LS-07` / `UR-SD-07` / `FR-SD-09` |
| `UC-SD-08` | Đối soát dữ liệu đầu vào | Data admin | Phân rã `UC-SD-05` / `FR-SD-05` |
| `UC-SD-09` | So sánh forecast với baseline | Data admin | Phân rã `UC-SD-05` / `FR-SD-05` |
| `UC-SD-10` | Ghi nhận kết luận kiểm định | Data admin | Phân rã `UC-SD-05` / `FR-SD-05` |
| `UC-SD-11` | Xem trạng thái dịch vụ/job và lịch chạy | IT admin | Phân rã `UC-SD-07` / `FR-SD-09` |
| `UC-SD-12` | Tra cứu log theo job/run | IT admin | Mở rộng có điều kiện `UC-SD-07` / `FR-SD-09` |
| `UC-SD-13` | Điều chỉnh một giá trị forecast | Supply Chain Planner (US-03) | `US-SD-LS-08` / `UR-SD-08` / `FR-SD-10` |
| `UC-SD-02.1` | Đối chiếu tính tương thích các chuỗi Sales | Người dùng được quyền xem Sales/Forecast (qua UC-SD-02) | Phân rã `US-SD-LS-02` / `UR-SD-02` / `FR-SD-02` |
| `UC-SD-03.1` | Xem biểu hiện mùa vụ | Người dùng được quyền xem Sales/Forecast (qua UC-SD-03) | Phân rã có điều kiện `US-SD-LS-03` / `UR-SD-03` / `FR-SD-03` |
| `UC-SD-08.1` | Đối chiếu nguồn và snapshot | Data admin (qua UC-SD-08) | Phân rã `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-08.2` | Đối chiếu đơn vị và location mapping | Data admin (qua UC-SD-08) | Phân rã `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-08.3` | Rà soát độ phủ, thiếu và trùng dữ liệu | Data admin (qua UC-SD-08) | Phân rã `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-09.1` | Kiểm tra tính hợp lệ theo thời gian | Data admin (qua UC-SD-09) | Phân rã `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-09.2` | Đối chiếu protocol forecast và baseline | Data admin (qua UC-SD-09) | Phân rã `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-10.1` | Ghi căn cứ và tham chiếu kiểm định | Data admin (qua UC-SD-10) | Phân rã `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-11.1` | Xem trạng thái dịch vụ/job | IT admin (qua UC-SD-11) | Phân rã `US-SD-LS-07` / `UR-SD-07` / `FR-SD-09` |
| `UC-SD-11.2` | Xem lịch chạy và độ mới trạng thái | IT admin (qua UC-SD-11) | Phân rã `US-SD-LS-07` / `UR-SD-07` / `FR-SD-09` |

## 4. Đặc tả chi tiết

### UC-SD-01 — Theo dõi Sales Quantity

| Trường | Nội dung |
|---|---|
| Use-case name | Theo dõi Sales Quantity |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast |
| Truy vết | `US-SD-LS-01`; `UR-SD-01`; `FR-SD-01` |

**Description:** Người dùng được quyền xem Sales/Forecast xem Sales Quantity theo kỳ và các chiều mà dữ liệu nguồn hỗ trợ để nắm trạng thái bán hàng trong phạm vi dữ liệu có căn cứ.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast được cấp quyền xem dữ liệu trong phạm vi được phê duyệt.
2. Có dữ liệu Sales cùng kỳ và trạng thái nguồn/provenance để trình bày.
3. Các chiều product/group, location, channel chỉ được chọn nếu source contract có hỗ trợ.

**Post-conditions**

- Kết quả được hiển thị theo grain, đơn vị, kỳ và provenance mà nguồn cung cấp.
- Không có source fact nào bị thay đổi bởi thao tác xem.

**Normal Flow**

1. Người dùng được quyền xem Sales/Forecast mở chức năng theo dõi Sales Quantity.
2. Người dùng được quyền xem Sales/Forecast chọn khoảng thời gian và các chiều khả dụng.
3. Hệ thống kiểm tra coverage, grain, đơn vị và trạng thái dữ liệu của phạm vi chọn.
4. Hệ thống hiển thị Sales Quantity cùng kỳ, đơn vị và các nhãn nghiệp vụ liên quan.
5. Người dùng được quyền xem Sales/Forecast xem kết quả theo phạm vi đã chọn.

**Alternative Flow**

- `2a`. Một chiều được chọn không có trong nguồn → hệ thống thông báo chiều đó không khả dụng và không dựng dữ liệu thay thế.
- `3a`. Không có bản ghi trong kỳ → hệ thống hiển thị trạng thái không có bản ghi, phân biệt với quantity bằng zero.
- `3b`. Provenance hoặc đơn vị chưa xác định → hệ thống đánh dấu chưa xác định/không khả dụng; không nâng dữ liệu thành actual đã kiểm chứng.
- `4a`. Lỗi tải dữ liệu → thông báo không thể tải kết quả; không hiển thị trạng thái lỗi như số liệu hợp lệ.

### UC-SD-02 — So sánh Sales Quantity

| Trường | Nội dung |
|---|---|
| Use-case name | So sánh Sales Quantity |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast |
| Truy vết | `US-SD-LS-02`; `UR-SD-02`; `FR-SD-02` |

**Description:** Người dùng được quyền xem Sales/Forecast so sánh Sales Quantity giữa các đối tượng hoặc kỳ tương thích để nhận biết chênh lệch trong tập đang xem.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast có quyền xem các series được chọn.
2. Có ít nhất hai đối tượng hoặc kỳ để so sánh.
3. Measure và metadata cần thiết để đối chiếu đơn vị, grain và coverage có sẵn.

**Post-conditions**

- Kết quả nêu rõ tập so sánh, kỳ, đơn vị và grain.
- Không tạo thứ hạng cho những series không tương thích.

**Normal Flow**

1. Người dùng được quyền xem Sales/Forecast mở chức năng so sánh Sales Quantity.
2. Người dùng được quyền xem Sales/Forecast chọn các đối tượng và/hoặc kỳ cần so sánh.
3. Hệ thống kiểm tra measure, đơn vị, grain và coverage của từng series.
4. Hệ thống tính và hiển thị giá trị cùng chênh lệch hoặc thứ hạng trong tập đã chọn.
5. Người dùng được quyền xem Sales/Forecast xem kết quả và phạm vi so sánh.

**Alternative Flow**

- `2a`. Chỉ chọn một đối tượng/kỳ → hệ thống yêu cầu chọn thêm đối tượng/kỳ hoặc quay lại màn hình theo dõi.
- `3a`. Đơn vị, grain hoặc measure không tương thích → hệ thống nêu lý do; không so sánh trực tiếp hay xếp hạng các series đó.
- `3b`. Coverage thiếu hoặc khác nhau đáng kể → hệ thống cảnh báo giới hạn so sánh và không kết luận nhóm tốt/xấu.
- `4a`. Cần tổng hợp giữa grain nhưng chưa có rule được xác nhận → hệ thống giữ series riêng và không tự cộng.

### UC-SD-03 — Xem xu hướng và biểu hiện mùa vụ

| Trường | Nội dung |
|---|---|
| Use-case name | Xem xu hướng và biểu hiện mùa vụ |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast |
| Truy vết | `US-SD-LS-03`; `UR-SD-03`; `FR-SD-03` |

**Description:** Người dùng được quyền xem Sales/Forecast xem lịch sử Sales Quantity và các biểu hiện xu hướng/mùa vụ có đủ coverage để hỗ trợ việc xem xét trong planning.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast được quyền xem series Sales đã chọn.
2. Có dữ liệu theo thời gian và thông tin về khoảng thời gian/coverage.

**Post-conditions**

- Chuỗi lịch sử và trạng thái đủ/thiếu bằng chứng được trình bày cùng phạm vi.
- Sales history không bị đổi nhãn thành demand history.

**Normal Flow**

1. Người dùng được quyền xem Sales/Forecast mở chức năng xu hướng và mùa vụ.
2. Người dùng được quyền xem Sales/Forecast chọn series, measure và khoảng thời gian.
3. Hệ thống kiểm tra tính liên tục của kỳ, coverage và số chu kỳ có thể quan sát.
4. Hệ thống hiển thị chuỗi Sales Quantity và xu hướng lịch sử.
5. Nếu điều kiện đánh giá mùa vụ phù hợp, hệ thống hiển thị biểu hiện mùa vụ cùng phạm vi bằng chứng.

**Alternative Flow**

- `3a`. Chuỗi quá ngắn, thiếu kỳ hoặc thiếu chu kỳ → hệ thống ghi “chưa đủ dữ liệu” và nêu phần coverage còn thiếu.
- `3b`. Provenance không rõ → hệ thống giữ cảnh báo nguồn; không trình bày nhận định như sự thật đã kiểm chứng.
- `5a`. Không có phương pháp/điều kiện đủ để kết luận mùa vụ → chỉ hiển thị lịch sử/mẫu hình quan sát được, không khẳng định có mùa vụ.

### UC-SD-04 — Xem forecast theo location và kỳ

| Trường | Nội dung |
|---|---|
| Use-case name | Xem forecast theo location và kỳ |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast |
| Truy vết | `US-SD-LS-04`; `UR-SD-04`; `FR-SD-04` |

**Description:** Người dùng được quyền xem Sales/Forecast xem số Forecast Sales Quantity theo từng location và kỳ để tham khảo trong planning. Có thể chọn một hoặc nhiều location (ví dụ cửa hàng hoặc node) khi nguồn và forecast hỗ trợ.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast được quyền xem forecast trong phạm vi location được phê duyệt.
2. Có output forecast cho một phần hoặc toàn bộ location/kỳ được chọn.
3. Location, kỳ forecast và đơn vị được trình bày theo nghĩa mà source/run contract xác nhận.

**Post-conditions**

- Forecast được hiển thị riêng cho từng location và kỳ; nhiều location không bị cộng ngầm định.
- Màn hình chỉ có thông tin nghiệp vụ cần thiết; metadata kỹ thuật được giữ trong hồ sơ nội bộ.
- Không có model, dữ liệu nguồn hay quyết định vận hành nào bị thay đổi.

**Normal Flow**

1. Người dùng được quyền xem Sales/Forecast mở chức năng forecast Sales Quantity.
2. Người dùng được quyền xem Sales/Forecast chọn một hoặc nhiều location được hỗ trợ và kỳ forecast.
3. Hệ thống tìm output hợp lệ tương ứng với từng cặp location/kỳ.
4. Hệ thống hiển thị Forecast Sales Quantity riêng theo location và kỳ, kèm đơn vị đã xác nhận.
5. Người dùng được quyền xem Sales/Forecast đọc kết quả để tham khảo trong planning.

**Alternative Flow**

- `2a`. Location không được nguồn/run hỗ trợ → hệ thống nêu location không khả dụng; không đổi thành demand location hoặc fulfillment location khác.
- `3a`. Chưa có forecast hợp lệ cho một hay nhiều cặp location/kỳ → hiển thị “chưa có forecast cho location/kỳ này” cho đúng phần thiếu; không tạo zero hay giá trị thay thế.
- `3b`. Run nội bộ chưa hợp lệ/hoàn tất → không công bố forecast đó; chi tiết kỹ thuật ở hồ sơ nội bộ, thông báo trên màn hình vẫn dùng ngôn ngữ nghiệp vụ.
- `4a`. Đơn vị chưa được xác nhận → hiển thị rõ đơn vị chưa xác định hoặc ẩn đơn vị; không tự suy ra.
- `4b`. Kết quả là dữ liệu mô phỏng → gắn nhãn dễ hiểu “dữ liệu mô phỏng”; không yêu cầu Người dùng được quyền xem Sales/Forecast đọc mã provenance.

### UC-SD-05 — Đối soát dữ liệu và kiểm định forecast

| Trường | Nội dung |
|---|---|
| Use-case name | Đối soát dữ liệu và kiểm định forecast |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin |
| Truy vết | `US-SD-LS-05`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin đối soát dữ liệu nguồn và hồ sơ evaluation, kiểm định Prediction Quality bằng temporal backtesting và baseline tương thích, rồi lưu kết luận có thể truy vết. Đây là công việc nội bộ; Supply Chain chỉ xem kết quả nghiệp vụ.

**Pre-conditions**

1. Data admin có quyền truy cập snapshot/dataset và hồ sơ evaluation tương ứng.
2. Có quy ước dữ liệu, metric và protocol cần thiết để kiểm tra; phần nào chưa được xác nhận phải được đánh dấu.
3. Forecast, actuals, baseline và protocol có thể được xác định theo target, grain, horizon và evaluation origins.

**Post-conditions**

- Kết quả kiểm tra dữ liệu và trạng thái evaluation được ghi nhận.
- Kết luận được gắn actor, thời điểm và tham chiếu bằng chứng/run; source facts và score gốc không bị ghi đè.
- Prediction Quality được lưu tách với Decision Quality; không suy chất lượng quyết định hay outcome từ forecast error.

**Normal Flow**

1. Data admin mở hồ sơ dữ liệu/evaluation cần kiểm định.
2. Hệ thống hiển thị snapshot, provenance, location mapping, đơn vị và các trường kỹ thuật có trong contract.
3. Data admin thực hiện đối soát dữ liệu đầu vào theo `UC-SD-08`.
4. Nếu dữ liệu và protocol đủ điều kiện, Data admin kiểm tra temporal validity và so sánh forecast với baseline theo `UC-SD-09`.
5. Hệ thống hiển thị metric, phạm vi đánh giá và khác biệt cần lưu ý theo protocol.
6. Data admin ghi kết luận kiểm định cùng bằng chứng theo `UC-SD-10`.
7. Hệ thống lưu bản ghi kết luận, actor, thời điểm và tham chiếu hồ sơ liên quan.

**Alternative Flow**

- `2a`. Một trường metadata không có trong contract → hệ thống đánh dấu chưa có/chưa xác định; không tự điền giá trị.
- `3a`. Phát hiện lỗi dữ liệu ảnh hưởng evaluation → Data admin ghi nhận lỗi; evaluation chuyển sang không hợp lệ hoặc chưa đánh giá được theo bằng chứng, không tiếp tục diễn giải score như hợp lệ.
- `4a`. Actuals, baseline, origins, horizon, target hoặc protocol không tương thích → kết quả được đánh dấu không so sánh được/chưa đánh giá được.
- `4b`. Có dấu hiệu temporal leakage hoặc run chưa hoàn tất → không kết luận Prediction Quality; lưu trạng thái và bằng chứng kiểm tra.
- `5a`. Chưa đủ coverage để tính metric → không tạo score thay thế và không gán nhãn tốt/xấu.
- `7a`. Không lưu được kết luận → thông báo chưa lưu; giữ nguyên source facts và kết quả evaluation gốc.
- `7b`. Sự cố dịch vụ/job cản trở việc truy cập → ghi nhận mã hồ sơ có sẵn và chuyển IT admin xử lý vận hành; Data admin không tự thực hiện quyền IT chưa được xác nhận.

### UC-SD-06 — Đọc ngữ cảnh nghiệp vụ Sales/Forecast

| Trường | Nội dung |
|---|---|
| Use-case name | Đọc ngữ cảnh nghiệp vụ Sales/Forecast |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast |
| Truy vết | `US-SD-LS-06`; `UR-SD-06`; `FR-SD-06` |

**Description:** Khi xem kết quả Sales hoặc forecast, Người dùng được quyền xem Sales/Forecast nhận biết loại số liệu, location, kỳ và đơn vị đã xác nhận qua nhãn nghiệp vụ, không cần đọc lineage hay metadata kỹ thuật.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast đang xem kết quả Sales hoặc forecast.
2. Ngữ cảnh nghiệp vụ nào được source/run contract xác nhận thì có thể trình bày.

**Post-conditions**

- Kết quả mang nhãn Sales history hoặc Forecast Sales Quantity và ngữ cảnh khả dụng.
- Thiếu giá trị, quantity bằng zero và dữ liệu mô phỏng được phân biệt.

**Normal Flow**

1. Người dùng được quyền xem Sales/Forecast mở một kết quả Sales hoặc forecast.
2. Hệ thống xác định nhãn loại số liệu, location, kỳ, đơn vị và trạng thái có căn cứ.
3. Hệ thống hiển thị giá trị với các nhãn nghiệp vụ phù hợp.
4. Người dùng được quyền xem Sales/Forecast diễn giải kết quả trong đúng phạm vi được trình bày.

**Alternative Flow**

- `2a`. Thiếu location, kỳ hoặc đơn vị → hệ thống chỉ hiển thị phần đã xác nhận và diễn đạt phần thiếu là chưa có/chưa xác định.
- `2b`. Không có giá trị → hệ thống thông báo không có dữ liệu/forecast; không trình bày thành zero.
- `3a`. Output synthetic → gắn nhãn dữ liệu mô phỏng.
- `3b`. Lineage hoặc technical metadata không đầy đủ → giữ trạng thái thiếu trong hồ sơ nội bộ; không yêu cầu Người dùng được quyền xem Sales/Forecast tra cứu mã kỹ thuật.

### UC-SD-07 — Theo dõi vận hành hệ thống

| Trường | Nội dung |
|---|---|
| Use-case name | Theo dõi vận hành hệ thống |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | IT admin |
| Truy vết | `US-SD-LS-07`; `UR-SD-07`; `FR-SD-09` |

**Description:** IT admin theo dõi trạng thái dịch vụ/job và lịch chạy để phát hiện, phân loại sự cố vận hành. Khi cần, IT admin tra cứu log theo `UC-SD-12` và chuyển vấn đề dữ liệu/forecast cho Data admin.

**Pre-conditions**

1. IT admin được cấp quyền xem thông tin vận hành theo role matrix áp dụng.
2. Trạng thái dịch vụ/job, lịch chạy và telemetry có sẵn theo contract của hệ thống.

**Post-conditions**

- Tình trạng quan sát được được ghi nhận với trạng thái thành công/lỗi/chưa biết phù hợp evidence.
- Vấn đề dữ liệu/model được chuyển cho Data admin; quyền retry/restart/thay lịch không được mặc định cấp.

**Normal Flow**

1. IT admin mở chức năng theo dõi vận hành Sales & Demand.
2. IT admin chọn dịch vụ, job hoặc khoảng lịch cần kiểm tra.
3. Hệ thống hiển thị trạng thái vận hành, lịch và thời điểm liên quan theo quyền.
4. IT admin đánh giá trạng thái và ghi nhận vấn đề vận hành nếu có.
5. Nếu cần xem log chi tiết của job/run, IT admin kích hoạt phần mở rộng `UC-SD-12`.
6. IT admin chuyển vấn đề dữ liệu hoặc bất thường chất lượng forecast cho Data admin.

**Alternative Flow**

- `2a`. Không có job trong phạm vi/kỳ chọn → hệ thống thông báo không tìm thấy job phù hợp.
- `3a`. Telemetry thiếu hoặc không mới → trạng thái được hiển thị là chưa biết/không cập nhật; không suy thành thành công.
- `4a`. Sự cố là lỗi dữ liệu hoặc kết quả forecast bất thường → IT admin chuyển Data admin kiểm tra; không tự sửa source facts hay kết luận model.
- `4b`. Cần retry/restart/thay lịch nhưng quyền/quy trình chưa xác nhận → chỉ ghi nhận nhu cầu; không thực thi thao tác.

### UC-SD-08 — Đối soát dữ liệu đầu vào

| Trường | Nội dung |
|---|---|
| Use-case name | Đối soát dữ liệu đầu vào |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia như một phần bắt buộc của `UC-SD-05`) |
| Truy vết | Phân rã `US-SD-LS-05`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin kiểm tra dữ liệu và metadata liên quan trước khi đánh giá forecast, gồm source/snapshot, provenance, đơn vị, location mapping, missing/duplicate và tính đầy đủ theo contract.

**Pre-conditions**

1. Data admin được phép đọc snapshot và contract tương ứng.
2. Có thể nhận diện dataset/run cần đối soát.

**Post-conditions**

- Các kiểm tra, sai lệch và trường chưa xác định được ghi nhận để làm đầu vào cho `UC-SD-05`.
- Source fact không bị sửa đè trong use case này.

**Normal Flow**

1. Data admin chọn snapshot/dataset gắn với lần kiểm định.
2. Hệ thống hiển thị thông tin nguồn và metadata có trong contract.
3. Data admin kiểm tra đơn vị, location mapping, khoảng thời gian, missing/duplicate và provenance.
4. Hệ thống tổng hợp kết quả đối soát theo từng hạng mục.
5. Data admin xác nhận kết quả đối soát để quyết định điều kiện tiếp tục evaluation.

**Alternative Flow**

- `2a`. Snapshot/contract không tìm thấy → ghi nhận thiếu nguồn/contract; dừng đánh giá phụ thuộc thông tin đó.
- `3a`. Có mapping hoặc đơn vị không xác định → đánh dấu chưa xác định; không tự quy đổi hoặc ghép location.
- `3b`. Phát hiện duplicate/missing hoặc coverage sai lệch → ghi rõ phạm vi và mức ảnh hưởng; chưa kết luận evaluation hợp lệ.
- `5a`. Dữ liệu không đạt điều kiện → kết quả `invalid` hoặc `not assessable` được chuyển về `UC-SD-05` để ghi kết luận; không tự loại bỏ hay sửa bản ghi nguồn.

### UC-SD-09 — So sánh forecast với baseline

| Trường | Nội dung |
|---|---|
| Use-case name | So sánh forecast với baseline |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia như một phần của `UC-SD-05`) |
| Truy vết | Phân rã `US-SD-LS-05`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin kiểm tra và đọc kết quả temporal backtest của forecast so với baseline tương thích trên cùng phạm vi evaluation để đánh giá Prediction Quality.

**Pre-conditions**

1. Đối soát dữ liệu tại `UC-SD-08` không chặn evaluation.
2. Forecast, baseline, actuals, target, grain, horizon, origins và protocol có đủ tham chiếu để kiểm tra tính tương thích.
3. Quy tắc metric áp dụng có định nghĩa; metric chưa được stakeholder chốt phải được ghi là lựa chọn/chờ xác nhận.

**Post-conditions**

- Metric và phạm vi so sánh được gắn với evaluation protocol tương ứng.
- Prediction Quality được lưu riêng; không suy ra Decision Quality hay operational outcome.

**Normal Flow**

1. Data admin mở kết quả evaluation đã qua kiểm tra dữ liệu.
2. Hệ thống hiển thị cutoff/origins, horizon, target, actuals reference, model/baseline/protocol version và metric definitions theo contract.
3. Data admin kiểm tra temporal validity, bảo đảm mỗi origin chỉ dùng thông tin có trước origin đó.
4. Hệ thống kiểm tra model và baseline dùng cùng actuals, target, grain, horizon, origins và protocol.
5. Hệ thống trình bày metric forecast cùng phạm vi và trạng thái so sánh.
6. Data admin xem xét kết quả Prediction Quality để ghi nhận trong `UC-SD-10`.

**Alternative Flow**

- `2a`. Metadata/version cần thiết thiếu → đánh dấu evaluation chưa đủ căn cứ; không suy diễn cấu hình.
- `3a`. Phát hiện temporal leakage → đánh dấu run không hợp lệ cho kết luận chất lượng.
- `4a`. Baseline không cùng phạm vi/actuals/protocol → không so sánh trực tiếp; ghi rõ nguyên nhân.
- `4b`. Run chưa hoàn tất hoặc actuals chưa đủ coverage → trạng thái chưa đánh giá được; không tự tạo score.
- `5a`. Metric chưa được chốt hoặc không xác định được do dữ liệu → trình bày trạng thái/căn cứ, không xếp hạng model tốt/xấu.

### UC-SD-10 — Ghi nhận kết luận kiểm định

| Trường | Nội dung |
|---|---|
| Use-case name | Ghi nhận kết luận kiểm định |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia như một phần của `UC-SD-05`) |
| Truy vết | Phân rã `US-SD-LS-05`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin lưu kết quả đối soát và kết luận kiểm định forecast cùng người thực hiện, thời điểm, phạm vi và bằng chứng có thể truy vết.

**Pre-conditions**

1. Data admin đã thực hiện hoặc ghi rõ trạng thái các kiểm tra liên quan tại `UC-SD-08` và `UC-SD-09`.
2. Có thể nhận diện hồ sơ/run và bằng chứng tương ứng; kết luận có thể là hợp lệ, không hợp lệ hoặc chưa đánh giá được theo bằng chứng.

**Post-conditions**

- Một bản ghi kết luận gắn với actor, thời điểm, phạm vi, trạng thái và tham chiếu evidence được lưu nếu thao tác thành công.
- Source facts, actuals và score gốc không bị sửa.

**Normal Flow**

1. Data admin mở biểu mẫu kết luận cho evaluation.
2. Hệ thống hiển thị kết quả đối soát, metric, phạm vi protocol và các bằng chứng liên quan.
3. Data admin chọn trạng thái kết luận và nhập nhận xét/căn cứ.
4. Data admin gắn tham chiếu snapshot, run và bằng chứng hiện có.
5. Hệ thống kiểm tra các trường cần thiết, gắn actor và thời điểm lưu.
6. Hệ thống lưu kết luận và xác nhận hoàn tất.

**Alternative Flow**

- `2a`. Evaluation không đủ điều kiện → Data admin chọn `chưa đánh giá được` hoặc `không hợp lệ` và nêu lý do thay vì ghi score thay thế.
- `4a`. Thiếu evidence reference → hệ thống nhắc ghi rõ bằng chứng còn thiếu; kết luận không được thể hiện như đã truy vết đầy đủ.
- `5a`. Thiếu trạng thái hoặc căn cứ bắt buộc → hệ thống yêu cầu bổ sung và không lưu bản ghi hoàn chỉnh.
- `6a`. Lưu thất bại → giữ dữ liệu nguồn và score nguyên vẹn, báo chưa lưu để Data admin xử lý lại theo quyền/quy trình.

### UC-SD-11 — Xem trạng thái dịch vụ/job và lịch chạy

| Trường | Nội dung |
|---|---|
| Use-case name | Xem trạng thái dịch vụ/job và lịch chạy |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | IT admin (tham gia như một phần bắt buộc của `UC-SD-07`) |
| Truy vết | Phân rã `US-SD-LS-07`; `UR-SD-07`; `FR-SD-09` |

**Description:** IT admin xem tình trạng dịch vụ/job và lịch chạy trong phạm vi được cấp quyền để xác định job thành công, lỗi, đang chạy hay chưa xác định.

**Pre-conditions**

1. IT admin có quyền xem thông tin vận hành liên quan.
2. Hệ thống có telemetry/lịch chạy hoặc xác định rõ dữ liệu đó chưa được cung cấp.

**Post-conditions**

- Trạng thái và thời điểm được trình bày theo telemetry hiện có.
- Không có job nào bị khởi động lại hoặc thay đổi lịch chỉ bởi thao tác xem.

**Normal Flow**

1. IT admin mở màn hình vận hành.
2. IT admin chọn dịch vụ/job hoặc khoảng lịch cần xem.
3. Hệ thống tra cứu trạng thái, thời điểm bắt đầu/kết thúc và lịch chạy hiện có.
4. Hệ thống hiển thị trạng thái cùng dấu thời gian/độ mới nếu có.
5. IT admin xác định job cần theo dõi sâu hơn hoặc ghi nhận tình trạng hiện tại.

**Alternative Flow**

- `2a`. Không có job phù hợp → hệ thống báo không tìm thấy job trong phạm vi đã chọn.
- `3a`. Không có telemetry → hiển thị chưa biết/chưa có telemetry, không coi là thành công.
- `4a`. Trạng thái quá cũ hoặc lịch không cập nhật → hiển thị thời điểm cập nhật cuối và cảnh báo dữ liệu cũ.
- `5a`. IT admin cần log chi tiết → tiếp tục bằng `UC-SD-12` khi có job/run để tra cứu.

### UC-SD-12 — Tra cứu log theo job/run

| Trường | Nội dung |
|---|---|
| Use-case name | Tra cứu log theo job/run |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | IT admin; mở rộng có điều kiện từ `UC-SD-07` |
| Truy vết | Phân rã `US-SD-LS-07`; `UR-SD-07`; `FR-SD-09` |

**Description:** Khi cần chẩn đoán một dịch vụ/job/run cụ thể, IT admin tra cứu log được phép xem để nhận diện sự cố vận hành và chuyển vấn đề đúng đầu mối.

**Pre-conditions**

1. IT admin đang theo dõi vận hành tại `UC-SD-07` và có job/run cần tra cứu.
2. IT admin có quyền đọc log tương ứng; log đã được lưu và lập chỉ mục theo contract.

**Post-conditions**

- Log phù hợp được hiển thị hoặc hệ thống nêu rõ không có log/không đủ quyền.
- Credentials và sensitive values không được lộ; log không thay đổi trạng thái job.

**Normal Flow**

1. Tại điểm mở rộng “Xem chi tiết job/run” của `UC-SD-07`, IT admin yêu cầu tra cứu log.
2. IT admin chọn hoặc xác nhận job/run ID cần xem.
3. Hệ thống kiểm tra quyền và tra cứu log liên quan theo thời gian/phạm vi có sẵn.
4. Hệ thống che thông tin nhạy cảm theo chính sách rồi hiển thị kết quả.
5. IT admin phân loại vấn đề vận hành; nếu có dấu hiệu lỗi dữ liệu/model thì chuyển Data admin.

**Alternative Flow**

- `2a`. Thiếu hoặc sai job/run ID → yêu cầu chọn lại từ danh sách job/run khả dụng.
- `3a`. Không có log hoặc telemetry tương ứng → báo không có dữ liệu log; không tự kết luận job thành công.
- `3b`. Không đủ quyền → từ chối truy cập và ghi nhận kết quả kiểm tra quyền theo chính sách.
- `4a`. Phát hiện credentials/sensitive values trong nguồn log → không hiển thị giá trị nhạy cảm; ghi nhận sự cố theo quy trình bảo mật.
- `5a`. Log gợi ý lỗi dữ liệu hoặc chất lượng forecast → chuyển Data admin; IT admin không tự sửa dữ liệu/kết luận evaluation.

### UC-SD-02.1 — Đối chiếu tính tương thích các chuỗi Sales

| Trường | Nội dung |
|---|---|
| Use-case name | Đối chiếu tính tương thích các chuỗi Sales |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast (tham gia thông qua `UC-SD-02`) |
| Truy vết | Phân rã bước 3–4 của `UC-SD-02`; `UR-SD-02`; `FR-SD-02` |

**Description:** Hệ thống xác định các chuỗi Sales được chọn có measure, đơn vị, grain và coverage đủ tương thích để so sánh hay không.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast đã chọn các chuỗi/kỳ trong `UC-SD-02`.
2. Metadata cần thiết có trong contract hoặc được đánh dấu chưa xác định.

**Post-conditions**

- Trạng thái tương thích và lý do được trả về `UC-SD-02`.
- Chuỗi không tương thích không bị xếp hạng hoặc gộp ngầm định.

**Normal Flow**

1. Hệ thống nhận tập chuỗi, measure và kỳ từ `UC-SD-02`.
2. Hệ thống kiểm tra measure, đơn vị, grain và coverage theo contract.
3. Hệ thống xác định tập có thể so sánh trực tiếp và điểm không tương thích.
4. Hệ thống trả kết quả cùng phạm vi/lý do về `UC-SD-02`.

**Alternative Flow**

- `2a`. Thiếu metadata → đánh dấu chưa xác định; không tự quy đổi đơn vị hoặc grain.
- `3a`. Có chuỗi không tương thích → loại khỏi so sánh trực tiếp và nêu lý do.

### UC-SD-03.1 — Xem biểu hiện mùa vụ

| Trường | Nội dung |
|---|---|
| Use-case name | Xem biểu hiện mùa vụ |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast (tham gia thông qua `UC-SD-03`) |
| Truy vết | Mở rộng có điều kiện tại `UC-SD-03`; `UR-SD-03`; `FR-SD-03` |

**Description:** Hệ thống bổ sung nhận định mùa vụ khi coverage, số chu kỳ và phương pháp được xác nhận đủ căn cứ.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast đang xem xu hướng trong `UC-SD-03`.
2. Dữ liệu đáp ứng điều kiện coverage và chu kỳ theo phương pháp đã xác nhận.

**Post-conditions**

- Biểu hiện mùa vụ được trình bày kèm phạm vi thời gian và căn cứ.
- Nếu không đủ điều kiện, `UC-SD-03` vẫn hiển thị chuỗi/xu hướng lịch sử mà không kết luận mùa vụ.

**Normal Flow**

1. Hệ thống nhận series, measure và khoảng thời gian từ `UC-SD-03`.
2. Hệ thống kiểm tra điều kiện coverage và phương pháp.
3. Hệ thống hiển thị biểu hiện mùa vụ cùng chu kỳ làm căn cứ.
4. Hệ thống trả nội dung bổ sung về `UC-SD-03`.

**Alternative Flow**

- `2a`. Thiếu chu kỳ, missing period hoặc provenance chưa rõ → không kết luận mùa vụ và nêu phạm vi thiếu.
- `2b`. Phương pháp chưa được xác nhận → chỉ hiển thị lịch sử.

### UC-SD-08.1 — Đối chiếu nguồn và snapshot

| Trường | Nội dung |
|---|---|
| Use-case name | Đối chiếu nguồn và snapshot |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia thông qua `UC-SD-08` và `UC-SD-05`) |
| Truy vết | Phân rã bước 1–2 của `UC-SD-08`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin xác định snapshot/dataset có nguồn và contract phù hợp để diễn giải evaluation hay không.

**Pre-conditions**

1. Data admin đã mở hồ sơ cần kiểm định.
2. Có tham chiếu snapshot/dataset cần đối chiếu.

**Post-conditions**

- Nguồn, snapshot và contract được liên kết hoặc trạng thái thiếu được ghi nhận.
- Evaluation phụ thuộc nguồn thiếu không được đánh dấu hợp lệ.

**Normal Flow**

1. Hệ thống nhận tham chiếu snapshot/dataset từ `UC-SD-08`.
2. Data admin kiểm tra nguồn và contract gắn với snapshot.
3. Hệ thống ghi nhận phiên bản snapshot và trạng thái tham chiếu.
4. Hệ thống trả kết quả cho `UC-SD-08`.

**Alternative Flow**

- `2a`. Không tìm thấy snapshot/contract → ghi nhận thiếu căn cứ và dừng phần đánh giá phụ thuộc.
- `3a`. Không xác định được phiên bản → đánh dấu chưa truy vết đầy đủ; không suy đoán nguồn.

### UC-SD-08.2 — Đối chiếu đơn vị và location mapping

| Trường | Nội dung |
|---|---|
| Use-case name | Đối chiếu đơn vị và location mapping |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia thông qua `UC-SD-08` và `UC-SD-05`) |
| Truy vết | Phân rã bước 3 của `UC-SD-08`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin đối chiếu đơn vị và mapping location với contract, giữ nguyên khác biệt chưa được xác nhận.

**Pre-conditions**

1. Nguồn/snapshot đã được nhận diện hoặc trạng thái thiếu đã ghi nhận.
2. Contract có định nghĩa đơn vị/location mapping tương ứng, nếu định nghĩa tồn tại.

**Post-conditions**

- Đơn vị và mapping được đánh dấu phù hợp, không phù hợp hoặc chưa xác định.
- Không có phép đổi đơn vị hay ghép location tự suy diễn.

**Normal Flow**

1. Hệ thống hiển thị đơn vị/location trong snapshot cùng contract liên quan.
2. Data admin đối chiếu với định nghĩa có căn cứ.
3. Hệ thống ghi kết quả theo từng đơn vị/location.
4. Hệ thống trả kết quả cho `UC-SD-08`.

**Alternative Flow**

- `1a`. Thiếu định nghĩa trong contract → đánh dấu chưa xác định.
- `2a`. Mapping/đơn vị không khớp → ghi chênh lệch; không tự sửa source fact.

### UC-SD-08.3 — Rà soát độ phủ, thiếu và trùng dữ liệu

| Trường | Nội dung |
|---|---|
| Use-case name | Rà soát độ phủ, thiếu và trùng dữ liệu |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia thông qua `UC-SD-08` và `UC-SD-05`) |
| Truy vết | Phân rã bước 3–4 của `UC-SD-08`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin kiểm tra độ phủ theo contract và ghi nhận bản ghi thiếu/trùng hoặc kỳ/location chưa được đại diện.

**Pre-conditions**

1. Phạm vi snapshot/dataset được nhận diện.
2. Contract định nghĩa grain/phạm vi mong đợi để đánh giá coverage.

**Post-conditions**

- Coverage và sai lệch missing/duplicate được ghi cùng phạm vi ảnh hưởng.
- Trạng thái không đạt/chưa đánh giá được được trả về `UC-SD-08`.

**Normal Flow**

1. Hệ thống nhận grain, kỳ và phạm vi mong đợi theo contract.
2. Hệ thống đối chiếu dữ liệu với phạm vi đó.
3. Hệ thống tổng hợp coverage, missing và duplicate theo hạng mục.
4. Data admin xác nhận và trả kết quả cho `UC-SD-08`.

**Alternative Flow**

- `1a`. Contract không xác định phạm vi mong đợi → đánh dấu chưa đánh giá được.
- `2a`. Phát hiện sai lệch → ghi phạm vi và mức ảnh hưởng; không tự loại/sửa bản ghi nguồn.

### UC-SD-09.1 — Kiểm tra tính hợp lệ theo thời gian

| Trường | Nội dung |
|---|---|
| Use-case name | Kiểm tra tính hợp lệ theo thời gian |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia thông qua `UC-SD-09` và `UC-SD-05`) |
| Truy vết | Phân rã bước 2–3 của `UC-SD-09`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin kiểm tra cutoff, origins, horizon và actuals reference để xác định thông tin tương lai có lọt vào evaluation hay không.

**Pre-conditions**

1. Dữ liệu/protocol đủ điều kiện mở rộng `UC-SD-05`.
2. Metadata thời gian cần thiết có trong evaluation contract.

**Post-conditions**

- Temporal validity và căn cứ được trả về `UC-SD-09`.
- Run có temporal leakage không được dùng để kết luận Prediction Quality hợp lệ.

**Normal Flow**

1. Hệ thống hiển thị cutoff/origins, horizon và actuals reference.
2. Data admin kiểm tra mỗi origin chỉ dùng thông tin có trước origin đó.
3. Hệ thống ghi nhận trạng thái và vấn đề cần xem xét.
4. Hệ thống trả kết quả cho `UC-SD-09`.

**Alternative Flow**

- `1a`. Thiếu metadata cần thiết → đánh dấu chưa đủ căn cứ.
- `2a`. Phát hiện temporal leakage → đánh dấu run không hợp lệ cho kết luận chất lượng.

### UC-SD-09.2 — Đối chiếu protocol forecast và baseline

| Trường | Nội dung |
|---|---|
| Use-case name | Đối chiếu protocol forecast và baseline |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia thông qua `UC-SD-09` và `UC-SD-05`) |
| Truy vết | Phân rã bước 2 và 4 của `UC-SD-09`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin xác nhận forecast và baseline có cùng actuals, target, grain, horizon, origins và protocol trước khi đọc so sánh metric.

**Pre-conditions**

1. Dữ liệu/protocol đủ điều kiện vào `UC-SD-09`.
2. Có tham chiếu forecast, baseline và actuals cần đối chiếu.

**Post-conditions**

- Trạng thái tương thích hoặc lý do không tương thích được trả về `UC-SD-09`.
- Metric khác phạm vi không bị trình bày như so sánh trực tiếp.

**Normal Flow**

1. Hệ thống hiển thị target, grain, horizon, origins, actuals và protocol của forecast/baseline.
2. Data admin đối chiếu các trường cần tương thích.
3. Hệ thống trả phạm vi so sánh và định nghĩa metric cho `UC-SD-09`.

**Alternative Flow**

- `1a`. Thiếu metadata/version → đánh dấu chưa đủ căn cứ; không suy diễn cấu hình.
- `2a`. Trường so sánh không khớp → không so sánh trực tiếp và ghi nguyên nhân.

### UC-SD-10.1 — Ghi căn cứ và tham chiếu kiểm định

| Trường | Nội dung |
|---|---|
| Use-case name | Ghi căn cứ và tham chiếu kiểm định |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia thông qua `UC-SD-10` và `UC-SD-05`) |
| Truy vết | Phân rã bước 2–4 của `UC-SD-10`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin gắn căn cứ/reference snapshot, run và evidence cho kết luận; bằng chứng còn thiếu được ghi rõ.

**Pre-conditions**

1. Data admin đã mở kết luận cần ghi trong `UC-SD-10`.
2. Kết quả đối soát/evaluation và evidence reference hiện có được cung cấp.

**Post-conditions**

- Kết luận lưu tham chiếu đang có và trạng thái bằng chứng còn thiếu.
- Hệ thống không tạo evidence reference hoặc sửa dữ liệu nguồn/score.

**Normal Flow**

1. Hệ thống hiển thị kết quả và reference hiện có.
2. Data admin gắn snapshot, run và bằng chứng liên quan.
3. Hệ thống ghi trạng thái đầy đủ/chưa đầy đủ của evidence.
4. Hệ thống trả kết quả cho `UC-SD-10` để lưu kết luận.

**Alternative Flow**

- `1a`. Không có evidence reference → ghi rõ bằng chứng thiếu và trạng thái phù hợp.
- `2a`. Reference không hợp lệ → yêu cầu xác nhận lại; không biểu thị đã truy vết đầy đủ.

### UC-SD-11.1 — Xem trạng thái dịch vụ/job

| Trường | Nội dung |
|---|---|
| Use-case name | Xem trạng thái dịch vụ/job |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | IT admin (tham gia thông qua `UC-SD-11` và `UC-SD-07`) |
| Truy vết | Phân rã bước 2–4 của `UC-SD-11`; `UR-SD-07`; `FR-SD-09` |

**Description:** IT admin xem trạng thái dịch vụ/job và timestamp telemetry để nhận biết đang chạy, hoàn tất, lỗi hay chưa có căn cứ.

**Pre-conditions**

1. IT admin có quyền xem phạm vi vận hành tương ứng.
2. Dịch vụ/job được nhận diện hoặc truy vấn xác định không có dữ liệu.

**Post-conditions**

- Trạng thái và thời điểm cập nhật cuối được trả về `UC-SD-11`.
- Thao tác xem không khởi động lại job hoặc thay đổi trạng thái nguồn.

**Normal Flow**

1. Hệ thống nhận dịch vụ/job cần kiểm tra từ `UC-SD-11`.
2. Hệ thống đọc telemetry trạng thái và timestamp có sẵn.
3. Hệ thống trình bày trạng thái cùng thời điểm cập nhật.
4. Hệ thống trả kết quả để IT admin theo dõi vận hành.

**Alternative Flow**

- `2a`. Không có telemetry → hiển thị chưa biết/chưa có telemetry, không coi là thành công.
- `3a`. Trạng thái cũ → hiển thị độ cũ và cảnh báo bằng ngôn ngữ vận hành.

### UC-SD-11.2 — Xem lịch chạy và độ mới trạng thái

| Trường | Nội dung |
|---|---|
| Use-case name | Xem lịch chạy và độ mới trạng thái |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | IT admin (tham gia thông qua `UC-SD-11` và `UC-SD-07`) |
| Truy vết | Phân rã bước 2–4 của `UC-SD-11`; `UR-SD-07`; `FR-SD-09` |

**Description:** IT admin xem lịch chạy và thời điểm cập nhật telemetry để xác định lịch/trạng thái có cũ so với thông tin hiện có hay không.

**Pre-conditions**

1. IT admin có quyền xem lịch vận hành tương ứng.
2. Có lịch/telemetry hoặc hệ thống có thể xác định dữ liệu chưa được cung cấp.

**Post-conditions**

- Lịch chạy và độ mới được trình bày theo nguồn hiện có.
- Thao tác xem không thay đổi lịch chạy hay quyền vận hành.

**Normal Flow**

1. Hệ thống nhận dịch vụ/job hoặc khoảng lịch từ `UC-SD-11`.
2. Hệ thống tra cứu lịch và timestamp liên quan.
3. Hệ thống hiển thị lịch cùng trạng thái mới/cũ theo timestamp.
4. Hệ thống trả kết quả để IT admin đánh giá vận hành.

**Alternative Flow**

- `2a`. Không có lịch/telemetry → nêu rõ dữ liệu vận hành chưa được cung cấp.
- `3a`. Lịch/trạng thái quá cũ → hiển thị timestamp cuối và cảnh báo; không tự thay lịch.

## 5. Quan hệ giữa các use case trên sơ đồ

| Quan hệ | Hướng trên sơ đồ | Căn cứ và điều kiện |
|---|---|---|
| Association | `Người dùng được quyền xem Sales/Forecast` — `UC-SD-01` đến `UC-SD-04` | Các role được cấp MD-01 xem Sales, so sánh, trend và forecast. `UC-SD-06` là hành vi ngữ cảnh được bao gồm, không phải mục tiêu actor khởi chạy độc lập. |
| Association | `Data admin` — `UC-SD-05` | Data admin khởi tạo mục tiêu tổng thể đối soát và kiểm định forecast. UC-08/10 là phần bắt buộc; UC-09 chỉ mở rộng khi dữ liệu và protocol đủ điều kiện. |
| Association | `IT admin` — `UC-SD-07` | IT admin khởi tạo mục tiêu theo dõi vận hành hệ thống. UC-11/12 biểu diễn hành vi thành phần của mục tiêu này. |
| `<<include>>` | `UC-SD-01`, `UC-SD-02`, `UC-SD-03`, `UC-SD-04` → `UC-SD-06` | Mỗi kết quả nghiệp vụ cần ngữ cảnh phù hợp (loại số liệu, location/kỳ, đơn vị/trạng thái có căn cứ) để người dùng diễn giải đúng. Mũi tên đi từ use case cơ sở tới UC được bao gồm. |
| `<<include>>` | `UC-SD-02` → `UC-SD-02.1` | So sánh cần xác định measure, đơn vị, grain và coverage tương thích trước khi trình bày chênh lệch/thứ hạng. |
| `<<extend>>` | `UC-SD-03.1` → `UC-SD-03` | Chỉ bổ sung nhận định mùa vụ khi coverage/phương pháp đủ căn cứ; extension point “Bổ sung thông tin mùa vụ”. |
| `<<include>>` | `UC-SD-05` → `UC-SD-08`, `UC-SD-10` | Kiểm định luôn ghi nhận kết quả đối soát và kết luận; kết luận có thể là invalid/not assessable khi điều kiện không đạt. |
| `<<include>>` | `UC-SD-08` → `UC-SD-08.1`, `UC-SD-08.2`, `UC-SD-08.3` | Đối soát có căn cứ cần nhận diện nguồn/snapshot, đơn vị/mapping và coverage/missing/duplicate theo contract. |
| `<<extend>>` | `UC-SD-09` → `UC-SD-05` | Chỉ đánh giá Prediction Quality khi dữ liệu/protocol đủ điều kiện, tại extension point “Đánh giá Prediction Quality”; UC-SD-05 vẫn hoàn chỉnh khi không so sánh được. |
| `<<include>>` | `UC-SD-09` → `UC-SD-09.1`, `UC-SD-09.2` | Đánh giá yêu cầu kiểm tra temporal validity và tính tương thích forecast/baseline trước khi đọc metric. |
| `<<include>>` | `UC-SD-10` → `UC-SD-10.1` | Kết luận cần ghi căn cứ/reference và thể hiện rõ evidence còn thiếu. |
| `<<include>>` | `UC-SD-07` → `UC-SD-11`; `UC-SD-11` → `UC-SD-11.1`, `UC-SD-11.2` | Theo dõi vận hành cần xem trạng thái dịch vụ/job, lịch chạy và độ mới telemetry trong phạm vi được cấp quyền. |
| `<<extend>>` | `UC-SD-12` → `UC-SD-07` | Tra cứu log chỉ xảy ra khi IT admin yêu cầu xem chi tiết job/run tại extension point cùng tên; mục tiêu theo dõi vận hành vẫn hoàn chỉnh khi không mở log. |

Association là đường liền không mũi tên. `<<include>>` là đường nét đứt có mũi tên từ use case cơ sở đến use case được bao gồm. `<<extend>>` là đường nét đứt từ use case mở rộng đến use case cơ sở. Chỉ dùng các quan hệ liệt kê trong bảng; không suy thêm actor, đăng nhập, retry hoặc thao tác quản trị ngoài phạm vi.

## 6. Ma trận truy vết UC → US/UR/FR

| Use case | User story | User requirement | Functional requirement |
|---|---|---|---|
| `UC-SD-01` | `US-SD-LS-01` | `UR-SD-01` | `FR-SD-01` |
| `UC-SD-02` | `US-SD-LS-02` | `UR-SD-02` | `FR-SD-02` |
| `UC-SD-03` | `US-SD-LS-03` | `UR-SD-03` | `FR-SD-03` |
| `UC-SD-04` | `US-SD-LS-04` | `UR-SD-04` | `FR-SD-04` |
| `UC-SD-05` | `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-06` | `US-SD-LS-06` | `UR-SD-06` | `FR-SD-06` |
| `UC-SD-07` | `US-SD-LS-07` | `UR-SD-07` | `FR-SD-09` |
| `UC-SD-08` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-09` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-10` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-11` | Phân rã `US-SD-LS-07` | `UR-SD-07` | `FR-SD-09` |
| `UC-SD-12` | Phân rã `US-SD-LS-07` | `UR-SD-07` | `FR-SD-09` |
| `UC-SD-13` | `US-SD-LS-08` | `UR-SD-08` | `FR-SD-10` |
| `UC-SD-02.1` | Phân rã `US-SD-LS-02` | `UR-SD-02` | `FR-SD-02` |
| `UC-SD-03.1` | Phân rã `US-SD-LS-03` | `UR-SD-03` | `FR-SD-03` |
| `UC-SD-08.1` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-08.2` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-08.3` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-09.1` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-09.2` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-10.1` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-11.1` | Phân rã `US-SD-LS-07` | `UR-SD-07` | `FR-SD-09` |
| `UC-SD-11.2` | Phân rã `US-SD-LS-07` | `UR-SD-07` | `FR-SD-09` |

`FR-SD-07` và `FR-SD-08` đã được retire trong Requirements; không tái sử dụng. `UC-SD-07` là mã Use Case độc lập và ánh xạ tới `FR-SD-09`.

## 7. Nguồn và giới hạn evidence

1. `OneNigth_report03.pdf`, mục 4 “Đặc tả Use case”, mẫu metadata và Actor/Description, trang in 22–25; mẫu luồng chính/thay thế, trang in 30–31. Tham khảo cấu trúc trình bày; không sao chép nghiệp vụ SSO/Tutor.
2. [User Stories Sales & Demand Landscape V1](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md), đặc biệt US-SD-LS-01–07 và phân công actor.
3. [Requirements Sales & Demand Landscape V1](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md), đặc biệt UR-SD-01–07, FR-SD-01–06/09, protocol evaluation và các giới hạn dữ liệu.
4. PharmaFlow project invariants trong `AGENTS.md`: `DATA → FORECAST → RISK → DECISION → OPERATIONAL OUTCOME`; phân biệt Prediction Quality và Decision Quality; observed và synthetic; yêu cầu human-in-the-loop cho recommendation vận hành.

**Trạng thái evidence:** Phân công `Supply Chain` / `Data admin` / `IT admin` được người dùng xác nhận ngày 2026-11-05. Actor đọc khái quát và role mapping MD-01, scope, SoD và audit policy lấy từ tab 2 đã được xác định. Capability/flow/interface vẫn là design proposal; tài liệu này không khẳng định implementation hay deployment.

## Addendum — quyền MD-01 và UC-SD-13 (2026-11-07)

### Actor và quyền xem chung

Actor đọc dùng chung trong UC-SD-01/02/03/04/06 là “Người dùng được quyền xem Sales/Forecast”. Danh sách role cấp quyền tại MD-01: US-01, US-02, US-03 (Supply Chain Planner), US-04, US-06, US-07, US-11, US-12, US-14, US-15; tất cả chịu scope assignment. Planner có thêm `forecast:adjust`. Data Admin có quyền kỹ thuật đọc evaluation/lưu kết luận; IT Admin có quyền kỹ thuật đọc job/log. Không được suy rộng từ quyền kỹ thuật sang quyền nghiệp vụ.

Trước mọi thao tác, kiểm tra permission, data scope và SoD liên quan; với ghi version, kiểm tra lại quyền hiện hành cùng reference và điều kiện trạng thái. Query không được trả location, aggregate hoặc metadata reference ngoài scope. Nếu không ánh xạ được dimension location vào cây tổ chức thì không tự coi đó là location nội bộ. Audit ghi actor, permission, resource, kết quả, thời điểm; ghi before/after cho thao tác tạo version. Quy tắc mô tả thiết kế, không tuyên bố đã triển khai.

### UC-SD-13 — Điều chỉnh một giá trị forecast

| Trường | Nội dung |
|---|---|
| Use-case name | Điều chỉnh một giá trị forecast |
| Actor | Supply Chain Planner (US-03) |
| Permission | `forecast:read` + `forecast:adjust` trong scope được gán |
| Truy vết | `US-SD-LS-08`; `UR-SD-08`; `FR-SD-10` |

**Description:** Planner tạo một version điều chỉnh riêng cho một giá trị forecast đã có, ghi lý do và giữ nguyên model output gốc. Lưu điều chỉnh không phê duyệt, phát hành hoặc thực thi hành động tồn kho.

**Pre-conditions**

1. Planner có quyền đọc và điều chỉnh cho resource cùng scope đó.
2. Forecast reference, location/kỳ, grain và unit nhận diện được theo contract.

**Post-conditions**

- Khi lưu thành công, có version điều chỉnh kèm giá trị gốc, giá trị mới, lý do, actor, thời điểm và reference.
- Forecast gốc, source facts và score evaluation không đổi.

**Normal Flow**

1. Planner mở forecast gốc trong scope được cấp.
2. Planner chọn một coordinate location/kỳ và product/grain được output hỗ trợ.
3. Planner nhập một giá trị hữu hạn không âm theo precision của unit contract và cung cấp lý do.
4. Hệ thống kiểm tra permission, scope, SoD áp dụng, reference, unit và giá trị; kiểm quyền lại ngay trước persistence.
5. Hệ thống trình giá trị gốc/mới, chênh lệch, unit và lý do.
6. Planner xác nhận lưu; hệ thống tạo version riêng cùng actor/thời điểm/reference và ghi audit.
7. Hệ thống báo lưu thành công; forecast gốc vẫn là lựa chọn mặc định.

**Alternative Flow**

- `1a`. Không đủ permission/scope → từ chối, không trả dữ liệu ngoài scope.
- `2a`. Forecast reference/coordinate/unit không xác định hoặc mapping location không được xác nhận → không cho chỉnh; nêu phần thiếu.
- `3a`. Thiếu lý do, giá trị âm/vô hạn hoặc precision sai → giữ form, không lưu.
- `4a`. Quyền bị thu hồi hoặc reference không còn hợp lệ trước khi lưu → từ chối, không tạo version.
- `6a`. Giá trị không đổi → báo không có thay đổi, không tạo version.
- `6b`. Persistence lỗi → báo chưa lưu, giữ dữ liệu nhập; không thay đổi forecast gốc.

Lưu version không áp dụng SoD duyệt phiếu nếu không có policy phê duyệt forecast riêng. Không tạo trạng thái approved/published.

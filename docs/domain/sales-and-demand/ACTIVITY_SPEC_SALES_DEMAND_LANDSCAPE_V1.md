# Đặc tả Activity — PharmaFlow Sales & Demand Landscape V1

| Thuộc tính | Giá trị |
|---|---|
| Mã | PF-ACT-SALES-DEMAND-LANDSCAPE-V1 |
| Ngày | 2026-11-06 |
| Trạng thái | Proposed — đặc tả trước dựng hình, không phải evidence implementation/deployment |
| Phạm vi | 6 activity tổng quan, 4 activity chi tiết; bao phủ 22 UC qua các hành vi thành phần |
| Nguồn chuẩn | [Use Case Specification](USE_CASE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md), [Requirements](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md), [User Stories](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md) |
| Đối chiếu tương tác | [Sequence Specification](SEQUENCE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md) |

## 1. Ý tưởng và cách tham khảo báo cáo mẫu

Activity trả lời: ai thực hiện hoạt động nào, điều kiện nào quyết định đường đi, đường lỗi kết thúc hoặc quay lại ở đâu. Sequence mô tả trao đổi giữa participant; không chuyển từng message đọc repository thành một activity riêng nếu không có ý nghĩa nghiệp vụ.

Đã tham khảo [OneNigth_report03.pdf](D:/DOWNLOAD/HCMUT/HK251/CNPM/BTL/OneNigth_report03.pdf), chương 7, trang in 127–166 (trang PDF 131–170), phần mô tả tiếp ở trang PDF 171. Đã xem trực tiếp Hình 90 (trang in 127) và Hình 118 (trang in 159). Ý tưởng áp dụng: swimlane người dùng/hệ thống, chia hình theo chức năng/actor, dùng decision cho điều kiện và mô tả bằng lời dưới hình.

Không lấy SSO, cache, export, chia sẻ bộ lọc, thông báo hoặc ngưỡng hiệu năng từ báo cáo mẫu làm yêu cầu PharmaFlow. Một số caption và mô tả gần nhau trong mẫu không khớp chủ đề; căn cứ nội dung W19.10 được ưu tiên khi xây đặc tả.

## 2. Quy ước dựng activity

### 2.1. Swimlane và các node

| Thành phần | Quy ước |
|---|---|
| Lane người dùng | Người dùng được quyền xem Sales/Forecast (10 role mapping ở Addendum) cho ACT-SD-01–04; Data admin cho ACT-SD-05/07–09; IT admin cho ACT-SD-06/10 |
| Lane hệ thống | PharmaFlow DSS; không bắt buộc tách UI/backend/database thành lane nghiệp vụ |
| Action | Động từ + đối tượng, ví dụ “Kiểm tra tính tương thích” |
| Decision | Câu hỏi cụ thể, nhánh có guard loại trừ nhau, bao gồm thiếu/chưa xác định khi có khả năng |
| Merge | Hợp các đường thay thế khi cần xử lý chung; không đồng nghĩa chờ song song |
| Fork/join | Chỉ dùng khi có căn cứ thực hiện đồng thời; bản này chưa quy định concurrency |
| Initial/final | Bắt đầu/kết thúc một lần thực hiện quy trình, không xóa đối tượng hoặc khóa toàn bộ hệ thống |
| Call activity | Hành vi chi tiết được tham chiếu từ activity tổng quan; không triển khai lại hai lần |

Mã Nxx/Gxx/Exx chỉ có phạm vi trong từng ACT. N là action, G là decision, E là kết quả kết thúc. Bảng đường đi dưới đây là đặc tả control flow; chưa phải mã hình.

### 2.2. Ràng buộc dùng chung

1. Mọi flow kiểm permission → data scope → SoD liên quan → điều kiện trạng thái trước khi đọc/ghi; từ chối quyền kết thúc ở outcome từ chối và không đi tới thành công. Backend thực thi kiểm tra; không thêm flow login/token/session của dịch vụ xác thực. Khi ghi, kiểm lại quyền/reference và ghi audit theo tab 2. NFR-SD-07; TC-SD-14.
2. Đối với ACT-SD-01–04, hành vi UC-SD-06 luôn được áp dụng khi trình bày: nhãn Sales/Forecast, location/kỳ, đơn vị đã xác nhận, nhãn mô phỏng; missing khác zero. Giữ lineage, cutoff, source/run/model/protocol metadata trong hồ sơ nội bộ.
3. Source facts không thay đổi do thao tác xem/đối soát. Không cộng UOM/grain không tương thích; không biến aggregate thành giao dịch, synthetic thành observed, sales thành latent demand; không đổi demand location thành fulfillment location.
4. Lỗi đọc nguồn khác không có bản ghi. Nếu một phần trả được, thể hiện phần hợp lệ/phần thiếu/phần lỗi riêng; không giả dữ liệu thay thế. Retry thao tác xem chỉ theo flow/quyền đã chốt, không tự thêm retry nền.
5. Không tự train model, chạy backtest, phát hành forecast, lập lệnh mua/chuyển kho hoặc thực thi quyết định. Prediction Quality tách khỏi Decision Quality.
6. Chuỗi toàn dự án `DATA → FORECAST → RISK → DECISION → OPERATIONAL OUTCOME` được giữ; phạm vi này chưa đặc tả toàn bộ các lớp đó. Các recommendation vận hành tương lai vẫn cần human review.

### 2.3. Thành phần và cách viết từng loại node

Phần này quy định nội dung thực sự được ghi trong hình. Mã N/G/E là mã tra cứu, không thay cho tên node. Đối chiếu ký pháp với [OMG UML 2.5.1](https://www.omg.org/spec/UML/2.5.1/PDF), chương 15 (Activities) và 16 (Actions); báo cáo mẫu là nguồn ý tưởng trình bày, không phải tiêu chuẩn ký pháp.

| Loại thành phần | Hình thức | Nội dung cần viết | Quy tắc vào/ra |
|---|---|---|---|
| Initial node | Chấm tròn đặc | Không ghi action trong chấm; trigger ghi trong mô tả activity | Trong mô hình tuần tự này, một cạnh đi tới bước đầu |
| Action node | Chữ nhật bo góc | Một hành động rõ bằng động từ + đối tượng; actor thể hiện qua lane | Hoàn tất action mới đi tiếp; không dùng hình thoi để mô tả một tác vụ |
| Decision node | Hình thoi | Câu hỏi ngắn hoặc điều kiện cần phân loại | Một dòng điều khiển vào, nhiều đường ra có guard; xét cả chưa biết khi cần |
| Merge node | Hình thoi | Thường không cần tên/hành động bên trong | Hợp nhiều đường thay thế thành một đường ra; không chờ đủ tất cả đường vào |
| Fork/join node | Thanh đậm | Không nhét câu hỏi vào thanh | Fork tách luồng đồng thời; join đồng bộ. Không dùng cho lựa chọn Có/Không; chưa có nhu cầu trong 10 activity này |
| CallBehaviorAction | Action có ký hiệu gọi hành vi con khi renderer hỗ trợ | Tên hành vi và mã ACT tham chiếu | Luồng quay lại activity cha khi hành vi con kết thúc; lane chi tiết nằm trong hình con |
| Activity final | Chấm đặc trong vòng tròn | Không nhét câu “Đã lưu thành công” vào ký hiệu final | Không có cạnh đi ra; kết thúc lần thực hiện activity |
| Flow final | Vòng tròn có dấu X | Chỉ dùng khi cần chấm dứt riêng một nhánh/token | Không tương đương activity final; hiện chưa cần trong bản tuần tự này |
| Object node/object flow | Ô đối tượng và cạnh dữ liệu nếu cần | Tên dữ liệu, ví dụ “Phạm vi location/kỳ”, “Kết luận kiểm định” | Phân biệt dòng dữ liệu với control flow; input/output trong prose không bắt buộc trở thành object node |
| Activity partition | Lane có tên vai trò | Người dùng được quyền xem Sales/Forecast, Data admin, IT admin hoặc PharmaFlow DSS theo hình | Tên lane xác định trách nhiệm, không phải một action hoặc deployment service |
| Note | Ghi chú nối với node/cạnh liên quan | Rule hoặc tham chiếu BR/UC cần giải thích | Không làm thay đổi control flow; không dùng note thay cho nhánh lỗi |

**Cách viết action:** ưu tiên “Chọn location và kỳ”, “Kiểm tra trạng thái run”, “Hiển thị forecast theo location/kỳ”. Không ghi một đoạn thuật toán dài trong một ô; nếu có nhiều quyết định bên trong thì tách action/decision hoặc gọi activity con. Không ghi `do/`, `entry/`, `exit/` vào action node của activity: đó là cách mô tả behavior trong state.

**Cách viết guard:** đặt trên cạnh đi ra decision, ví dụ `[được nguồn hỗ trợ]`, `[không được hỗ trợ]`, `[chưa xác định]`. Guard là điều kiện, không phải tác vụ; “Hiển thị lỗi” là action sau cạnh, không phải guard. Có thể dùng `[else]` cho phần còn lại khi các trường hợp trước đã rõ; không tự đồng nhất chưa xác định với đã xác nhận không hợp lệ. Bản hình W19.10 dùng guard loại trừ nhau để chọn một đường; không dựa vào thứ tự đánh giá guard.

**Cách viết điểm kết thúc:** E01/E02 trong bảng hiện là mã outcome, chưa phải node tròn có chứa chữ. Khi dựng hình, biểu diễn action cuối như “Thông báo không có bản ghi” rồi nối tới activity final; đặt mã outcome ở action/note nếu cần truy vết. Kết thúc call activity chỉ trả điều khiển về cha, không đặt activity final của sơ đồ cha ở giữa luồng.

### 2.4. Hồ sơ node và quy tắc chuyển bảng thành hình

Mỗi action khi triển khai từ bảng cần có hồ sơ: `ID; loại node; nhãn hiển thị; lane; điều kiện vào; input; output; cạnh ra/đích; nguồn UC/FR/BR`. Decision bổ sung danh sách guard; call activity bổ sung mã hành vi con; final không có output/cạnh ra. Thông tin dài giữ trong Markdown, chỉ đưa nhãn ngắn lên hình.

| Thành phần áp dụng ACT-SD-04 | Nhãn/nội dung trong hình | Điều kiện/dữ liệu và đường đi |
|---|---|---|
| I01 — Initial | Chấm đặc, không chữ | Bắt đầu lần yêu cầu xem; nối N01 |
| N01 — Action, lane Supply Chain | Chọn location và kỳ forecast | Input: phạm vi khả dụng; output: lựa chọn; tới G01 |
| G01 — Decision, lane Hệ thống | Location được hỗ trợ? | Cạnh `[được hỗ trợ]` tới N02; `[không/chưa xác định]` tới action báo không khả dụng rồi final |
| N02 — Action, lane Hệ thống | Tìm output và metadata | Output hiện có tới N03; lỗi tải tới action báo lỗi hoặc xử lý phần lỗi theo NFR-SD-09 |
| G02 — Decision, lane Hệ thống | Output đủ điều kiện? | `[có output hợp lệ]` tới N04; `[thiếu/chưa hợp lệ/chưa hoàn tất]` tới N05 |
| N04 — Action, lane Hệ thống | Chuẩn bị giá trị, unit đã xác nhận, nhãn mô phỏng; thêm cặp hợp lệ vào tập kết quả | Không hiển thị metadata run; unit/synthetic theo contract |
| N05 — Action, lane Hệ thống | Ghi chưa có forecast cho cặp đó vào tập kết quả | Không điền zero; giữ lý do kỹ thuật nội bộ |
| M06 — Merge, lane Hệ thống | Không cần chữ bên trong | Hợp kết quả của cặp hiện tại từ N04/N05 trước G03; không dùng join |
| N06 — Action, lane Hệ thống | Hoàn tất và hiển thị tập kết quả | Giữ phần hợp lệ/thiếu/lỗi riêng; không cộng location ngầm định |
| N07 — Action, lane Supply Chain | Đọc kết quả theo location/kỳ | Kết thúc đọc nối final; không tạo quyết định tồn kho |
| F01 — Activity final | Chấm đặc trong vòng tròn | Kết thúc lần xem, không thay đổi model/output nguồn |

Vòng N03–G02–N04/N05–M06 được điều khiển bởi G03: kiểm tra còn cặp chưa xử lý, xét một cặp, thêm kết quả hợp lệ hoặc trạng thái thiếu vào tập, rồi quay lại N03 nếu còn cặp; chỉ khi hết tập mới tới N06 để trình bày toàn bộ. Đây là lặp logic, không quy định query per item hay concurrency.

**Các merge bắt buộc làm rõ khi vẽ:** ACT-SD-01 trước N06; ACT-SD-03 trước điểm kết thúc chung nếu hai nhánh cùng kết thúc; ACT-SD-04 trước G03; ACT-SD-05 trước N06; ACT-SD-06 trước N06; ACT-SD-07 trước N05/E01 khi các đường thay thế cùng hội tụ; ACT-SD-08 trước kết quả trả về E01. Các vòng nhập lại ACT-SD-02/N01, ACT-SD-09/N02 và ACT-SD-10/N01 cũng hợp đường vào bằng merge. Bảng hiện rút gọn các điểm hợp luồng này; không nối nhiều cạnh thay thế trực tiếp vào một action theo cách tạo ngữ nghĩa chờ đồng thời. Hai nhánh có final riêng không cần merge chỉ để trang trí.

Các dòng ghi `Data admin + Hệ thống` hoặc `IT admin + Hệ thống` là call activity tổng quan. Khi phân rã, không tạo lane gộp hai chủ thể; từng action trong hình con phải thuộc lane thực hiện nó. Tác vụ kiểm tra và decision kết quả là hai thành phần khác nhau nếu cần thể hiện đầy đủ: action “Kiểm tra quyền” rồi decision “Có quyền?”; không biến decision thành công việc tính quyền.

## 3. Nhóm người dùng được quyền xem Sales/Forecast

### ACT-SD-01 — Theo dõi Sales Quantity

**Truy vết:** UC-SD-01/06; US-SD-LS-01/06; FR-SD-01/06; SEQ-SD-01; BR-SD-01–06/09; TC-SD-01/02/04/05/12/13/15.

**Trigger:** Người dùng được quyền xem Sales/Forecast mở theo dõi Sales. **Điều kiện trước:** có quyền theo phạm vi áp dụng, nhận diện được nguồn/contract; thiếu metadata được biểu diễn riêng. **Input:** kỳ, chiều/bộ lọc khả dụng. **Output:** Sales Quantity hoặc trạng thái theo phạm vi.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Người dùng được quyền xem Sales/Forecast | Mở chức năng và chọn kỳ/chiều | G01 |
| G01 | Hệ thống | Chiều có được nguồn hỗ trợ? | Có: N02; không/chưa rõ: E01 |
| N02 | Hệ thống | Đọc observation, UOM/grain/coverage/provenance | G02; lỗi tải: E02 |
| G02 | Hệ thống | Có bản ghi trong phạm vi? | Có: N03; không: E03 |
| N03 | Hệ thống | Kiểm tra điều kiện tổng hợp, metadata và nghĩa location | G03 |
| G03 | Hệ thống | Đủ điều kiện cho phép tính yêu cầu? | Có: N04; thiếu: N05 |
| N04 | Hệ thống | Tổng hợp theo rule/UOM/grain đã xác nhận | N06 |
| N05 | Hệ thống | Giữ phần có căn cứ, đánh dấu chưa xác định; không tính phần thiếu điều kiện | N06 |
| N06 | Hệ thống | Trình bày Sales và ngữ cảnh UC-SD-06 | N07 |
| N07 | Người dùng được quyền xem Sales/Forecast | Đọc kết quả và giới hạn | E04 |

**Kết thúc:** E01 chiều không khả dụng, không dựng chiều thay thế (UC-SD-01/2a); E02 không tải được (4a); E03 không có bản ghi, khác quantity zero (3a); E04 đã trình bày kết quả/phần chưa xác định (3b). Người dùng có thể gửi lựa chọn mới thành lần xem khác; không tự chạy vòng lặp vô hạn.

**Hậu điều kiện:** không đổi facts; không nhận provenance chưa rõ là actual đã kiểm chứng. **Đối chiếu hình:** nhánh zero phải đi qua dữ liệu có bản ghi; không đi từ no record đến giá trị 0.

### ACT-SD-02 — So sánh Sales Quantity

**Truy vết:** UC-SD-02/02.1/06; US-SD-LS-02/06; FR-SD-02/06; SEQ-SD-02; BR-SD-03/04/06; TC-SD-03/13.

**Trigger:** chọn so sánh. **Input:** các đối tượng/kỳ và measure. **Điều kiện trước:** quyền đọc, có metadata để kiểm tra hoặc ghi thiếu. **Output:** tập so sánh hợp lệ, chênh lệch/thứ hạng và giới hạn.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Người dùng được quyền xem Sales/Forecast | Chọn các đối tượng/kỳ | G01 |
| G01 | Hệ thống | Ít nhất hai đối tượng/kỳ? | Có: N02; không: N05 |
| N02 | Hệ thống | Đọc chuỗi và metadata; đối chiếu measure/UOM/grain/coverage theo UC-SD-02.1 | G02; lỗi: E01 |
| G02 | Hệ thống | Có tập đủ điều kiện so sánh trực tiếp? | Có: N03; không: E02 |
| N03 | Hệ thống | Giữ riêng chuỗi không tương thích, ghi lý do/cảnh báo coverage; tính trên tập đủ điều kiện | N04 |
| N04 | Hệ thống | Hiển thị tập, kỳ, đơn vị, phạm vi và kết quả với UC-SD-06 | E03 |
| N05 | Hệ thống | Yêu cầu chọn thêm hoặc quay về theo dõi | G03 |
| G03 | Người dùng được quyền xem Sales/Forecast | Chọn thêm đối tượng/kỳ? | Có: N01; không: E04 |

**Ngoại lệ:** khác measure/UOM/grain hoặc thiếu metadata: không so sánh trực tiếp (UC-SD-02/3a; UC-SD-02.1/2a,3a). Coverage thiếu/khác đáng kể: nêu giới hạn, nếu chưa đủ căn cứ thì G02 trả không (UC-SD-02/3b). Cần aggregation nhưng chưa có rule: giữ riêng, không tự cộng (4a). Không có ngưỡng coverage cố định được ngầm áp dụng.

**Kết thúc:** E01 lỗi tải; E02 chưa so sánh được kèm lý do; E03 đã trình bày; E04 quay lại theo dõi. **Hậu điều kiện:** không xếp hạng chuỗi không tương thích, không gọi high/low là tốt/xấu kinh doanh khi chưa có mục tiêu.

### ACT-SD-03 — Xu hướng và biểu hiện mùa vụ

**Truy vết:** UC-SD-03/03.1/06; US-SD-LS-03/06; FR-SD-03/06; SEQ-SD-03; TC-SD-11/12/13.

**Trigger:** yêu cầu xem lịch sử. **Input:** series/measure/khoảng thời gian. **Điều kiện trước:** quyền và nguồn lịch sử có thể kiểm tra. **Output:** lịch sử và phần mùa vụ đủ căn cứ.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Người dùng được quyền xem Sales/Forecast | Chọn series, measure và kỳ | N02 |
| N02 | Hệ thống | Đọc chuỗi và coverage/provenance | N03; lỗi: E01 |
| N03 | Hệ thống | Kiểm tính liên tục, missing period và số chu kỳ | N04 |
| N04 | Hệ thống | Hiển thị lịch sử có căn cứ và khoảng trống, áp dụng UC-SD-06 | G01 |
| G01 | Hệ thống | Coverage/chu kỳ/provenance và phương pháp đã xác nhận đủ cho mùa vụ? | Có: N05; không/chưa rõ: N06 |
| N05 | Hệ thống | Bổ sung biểu hiện mùa vụ kèm chu kỳ/phạm vi evidence theo UC-SD-03.1 | E02 |
| N06 | Hệ thống | Ghi chưa đủ căn cứ hoặc phương pháp chưa xác nhận; giữ lịch sử | E03 |

**Ngoại lệ:** UC-SD-03/3a,3b,5a và UC-SD-03.1/2a,2b cùng dẫn tới N06 khi ảnh hưởng căn cứ mùa vụ. Không tự đặt thuật toán/ngưỡng số tháng. E01 lỗi tải khác thiếu coverage; E02 có thông tin mùa vụ đủ căn cứ; E03 chỉ có lịch sử/cảnh báo. **Hậu điều kiện:** không đổi sales history thành demand history hoặc suy lost demand.

### ACT-SD-04 — Xem forecast theo location/kỳ

**Truy vết:** UC-SD-04/06; US-SD-LS-04/06; FR-SD-04/06; SEQ-SD-04; TC-SD-06/07/12/13/15.

**Trigger:** yêu cầu xem forecast. **Input:** một/nhiều location và kỳ. **Điều kiện trước:** scope quyền phù hợp và source/run contract nhận diện output. **Output:** giá trị/trạng thái riêng từng cặp location/kỳ.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Người dùng được quyền xem Sales/Forecast | Chọn location/kỳ được hỗ trợ | G01 |
| G01 | Hệ thống | Location có trong phạm vi nguồn/run hỗ trợ? | Có: N02; không: E01 |
| N02 | Hệ thống | Tìm output và metadata nội bộ | N03; lỗi: E02 |
| N03 | Hệ thống | Xét điều kiện cho từng cặp location/kỳ trong phạm vi yêu cầu | G02 |
| G02 | Hệ thống | Có output và đủ điều kiện hợp lệ theo contract? | Có: N04; không/chưa hoàn tất: N05 |
| N04 | Hệ thống | Chuẩn bị giá trị, unit đã xác nhận, nhãn mô phỏng; thêm cặp hợp lệ vào tập kết quả | M06 |
| N05 | Hệ thống | Ghi chưa có forecast cho cặp đó vào tập kết quả; giữ lý do kỹ thuật nội bộ | M06 |
| M06 | Hệ thống | Merge kết quả của cặp hiện tại từ N04/N05 | G03 |
| G03 | Hệ thống | Còn location/kỳ chưa xử lý? | Còn: N03; hết tập: N06 |
| N06 | Hệ thống | Hoàn tất tập kết quả, giữ riêng phần hợp lệ/thiếu/lỗi; áp dụng UC-SD-06 | N07 |
| N07 | Người dùng được quyền xem Sales/Forecast | Đọc kết quả theo từng location/kỳ | E03 |

G03 điều khiển vòng lặp theo cặp location/kỳ: mỗi lượt xử lý một cặp logic và thêm kết quả/trạng thái vào tập; khi còn cặp quay lại N03, khi hết mới tới N06. Đây là điều khiển logic; không yêu cầu query riêng per item hoặc xử lý song song.

**Ngoại lệ:** location không hỗ trợ → E01 (UC-SD-04/2a); thiếu output → N05 (3a); run chưa hợp lệ/hoàn tất → N05 (3b); unit chưa rõ → N04 chỉ hiện phần biết được, ghi chưa xác định/ẩn unit (4a); synthetic → nhãn mô phỏng (4b). E02 lỗi tải; nếu chỉ lỗi một phần thì giữ phần còn lại theo NFR-SD-09. E03 đã trình bày. **Hậu điều kiện:** không cộng ngầm định location, không train/chạy lại model, không công bố output thiếu điều kiện.

## 4. Nhóm Data admin

### ACT-SD-05 — Đối soát và kiểm định forecast tổng thể

**Truy vết:** UC-SD-05/08/09/10; US-SD-LS-05; FR-SD-05; SEQ-SD-05; TC-SD-08/09/10/17.

**Trigger:** mở hồ sơ kiểm định. **Input:** snapshot/run/evaluation reference. **Điều kiện trước:** quyền truy cập, nhận diện hồ sơ; metadata chưa có được ghi thiếu. **Output:** kết luận có evidence hoặc chưa lưu.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Data admin | Chọn hồ sơ cần kiểm định | N02 |
| N02 | Hệ thống | Nạp hồ sơ và trình phần có/thiếu | N03; lỗi dịch vụ cản trở: E01 |
| N03 | Data admin + Hệ thống | Thực hiện đối soát ACT-SD-07 | G01 |
| G01 | Hệ thống | Đối soát và protocol đủ điều kiện mở phần evaluation? | Có: N04; không/chưa rõ: N05 |
| N04 | Data admin + Hệ thống | Kiểm temporal validity và comparability theo ACT-SD-08 | N06 |
| N05 | Hệ thống | Giữ lý do invalid/chưa đánh giá được, không diễn giải score như hợp lệ | N06 |
| N06 | Data admin + Hệ thống | Hợp đường evaluation có/không đủ điều kiện; ghi kết luận theo ACT-SD-09 | G02 |
| G02 | Hệ thống | Lưu thành công? | Có: E02; không: E03 |

Các dòng “Data admin + Hệ thống” là call activity; khi dựng hình chi tiết phải tách action vào đúng lane. Không dùng join tại N06: chỉ một đường lựa chọn đi tới merge.

**Ngoại lệ:** metadata thiếu → đánh dấu và xét gate theo ảnh hưởng (UC-SD-05/2a); dữ liệu lỗi → N05 (3a); protocol/phạm vi không tương thích → N05 (4a); leakage/run chưa hoàn tất → N05 (4b); coverage metric thiếu → N06; nếu có giá trị metric nguồn, hiển thị nguyên số kèm nhãn “Chưa đánh giá được”; không tính score mới (5a). Lỗi lưu → E03 (7a). E01: chuyển IT với reference có sẵn, không tự restart, không khẳng định kết luận đã lưu (7b).

**Hậu điều kiện:** E02 có kết luận lưu thành công, có thể là invalid/chưa đánh giá được; E03 chưa lưu. Không suy Decision Quality từ forecast error; không tự phát hành forecast sau kiểm định.

### ACT-SD-07 — Đối soát dữ liệu đầu vào

**Truy vết:** UC-SD-08/08.1/08.2/08.3; FR-SD-05; SEQ-SD-07; TC-SD-17. **Ngữ cảnh:** call từ ACT-SD-05/N03. **Input:** nguồn/snapshot/contract. **Output:** kết quả từng hạng mục và ảnh hưởng tới evaluation.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Hệ thống | Đọc nguồn/snapshot/version/contract | G01 |
| G01 | Hệ thống | Có nguồn và contract cần thiết? | Có: N02; không: N06 |
| N02 | Data admin | Đối chiếu nguồn và snapshot, ghi thiếu version nếu có | N03 |
| N03 | Data admin | Đối chiếu UOM/location với định nghĩa contract, ghi phù hợp/không khớp/chưa rõ | G02 |
| G02 | Hệ thống | Contract có grain/kỳ/phạm vi mong đợi để kiểm coverage? | Có: N04; không: N05 |
| N04 | Hệ thống | Tổng hợp coverage/missing/duplicate theo contract, không sửa nguồn | N05 |
| N05 | Data admin | Xác nhận kết quả, phần thiếu và mức ảnh hưởng | E01 |
| N06 | Hệ thống | Ghi thiếu nguồn/contract; dừng kiểm tra phụ thuộc | E01 |

**Nhánh:** thiếu snapshot/contract: UC-SD-08/2a, UC-SD-08.1/2a; thiếu version: UC-SD-08.1/3a; UOM/mapping không rõ hoặc lệch: UC-SD-08/3a, UC-SD-08.2/1a,2a; thiếu phạm vi mong đợi: UC-SD-08.3/1a; missing/duplicate/coverage lệch: UC-SD-08/3b, UC-SD-08.3/2a. Không đủ điều kiện: trả invalid/not assessable theo evidence, UC-SD-08/5a.

**Hậu điều kiện E01:** trả kết quả đối soát cho gate ACT-SD-05/G01; không tự loại bản ghi, impute zero, sửa UOM hoặc tạo mapping. Định nghĩa duplicate và ngưỡng đạt còn cần contract.

### ACT-SD-08 — Kiểm tra và so sánh evaluation

**Truy vết:** UC-SD-09/09.1/09.2; FR-SD-05, Requirements §4.2; SEQ-SD-08; TC-SD-08/09/10/17. **Trigger:** ACT-SD-05/G01 cho phép tiếp tục. **Input:** forecast/baseline/actuals và protocol metadata. **Output:** trạng thái temporal/comparability, metric đọc được và căn cứ.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Hệ thống | Nạp metadata/evidence theo origin, trạng thái run và metric definition | G01 |
| G01 | Hệ thống | Đủ metadata cần kiểm và run/actuals sẵn sàng? | Có: N02; không/chưa rõ: N06 |
| N02 | Data admin | Kiểm mỗi origin chỉ dùng thông tin trước origin; ghi evidence | G02 |
| G02 | Data admin | Temporal validity có đủ căn cứ? | Có: N03; leakage: N05; chưa rõ: N06 |
| N03 | Hệ thống | Đối chiếu target/grain/UOM/horizon/origins/actuals/protocol/evaluation period | G03 |
| G03 | Hệ thống | Forecast và baseline tương thích, metric đủ định nghĩa/coverage? | Có: N04; không/chưa rõ: N06 |
| N04 | Data admin | Đọc metric/phạm vi và xem xét Prediction Quality | E01 |
| N05 | Hệ thống | Ghi run invalid cho kết luận chất lượng; không diễn giải score hợp lệ | E01 |
| N06 | Hệ thống | Nếu có giá trị metric nguồn, hiển thị nguyên số kèm nhãn “Chưa đánh giá được”; không tính số mới/xếp hạng. Nếu không có số, chỉ hiển thị trạng thái thiếu căn cứ/không so sánh được | E01 |

**Nguồn nhánh:** UC-SD-09/2a–5a; UC-SD-09.1/1a,2a; UC-SD-09.2/1a,2a. N05 khác N06: vi phạm đã có evidence khác thiếu bằng chứng để đánh giá. E01 trả ACT-SD-05/N06 để DA ghi kết luận. **Hậu điều kiện:** không sửa score hoặc chạy lại model; nếu N06 có giá trị metric nguồn thì vẫn hiển thị số kèm nhãn “Chưa đánh giá được”; không tính score mới/thay thế hoặc xếp hạng. MAE/RMSE/WAPE/Bias là ứng viên cần chốt, không tự gán metric thắng.

### ACT-SD-09 — Ghi và lưu kết luận kiểm định

**Truy vết:** UC-SD-10/10.1; FR-SD-05; SEQ-SD-09; TC-SD-17. **Trigger:** ACT-SD-05/N06. **Input:** kết quả đối soát/evaluation, trạng thái/nhận xét/căn cứ, evidence references. **Output:** kết luận đã lưu hoặc chưa lưu.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Hệ thống | Trình bày kết quả và bằng chứng còn thiếu | N02 |
| N02 | Data admin | Chọn trạng thái phù hợp, nhập căn cứ và gắn reference hiện có | G01 |
| G01 | Hệ thống | Đủ trạng thái/căn cứ bắt buộc và reference được xác nhận theo policy? | Có: N04; không: N03 |
| N03 | Hệ thống | Nêu trường thiếu/reference cần xác nhận lại | N02 khi DA bổ sung |
| N04 | Hệ thống | Ghi rõ mức đầy đủ evidence, gắn actor/thời điểm và lưu kết luận | G02 |
| G02 | Hệ thống | Nhận kết quả lưu thành công? | Có: E01; không: E02 |

**Ngoại lệ:** evaluation không đủ điều kiện vẫn được chọn kết luận invalid/chưa đánh giá được, UC-SD-10/2a. Thiếu evidence khác reference không hợp lệ: ghi thiếu và không nhận truy vết đầy đủ (UC-SD-10/4a; UC-SD-10.1/1a), reference không hợp lệ cần xác nhận lại (UC-SD-10.1/2a); không tự đặt điều kiện mọi evidence đều đầy đủ mới được lưu. Trường bắt buộc thiếu: UC-SD-10/5a. Lỗi lưu: UC-SD-10/6a.

**Hậu điều kiện:** E01 chỉ sau xác nhận lưu; E02 báo chưa lưu và giữ nguyên facts/actuals/score. N03 là vòng bổ sung do người dùng thao tác, không tự sửa nội dung. Rời biểu mẫu/lưu nháp/hủy chưa có policy thì không tự thêm transition hoặc cam kết giữ nội dung.

## 5. Nhóm IT admin

### ACT-SD-06 — Theo dõi vận hành

**Truy vết:** UC-SD-07/11/11.1/11.2/12; US-SD-LS-07; FR-SD-09; SEQ-SD-06; TC-SD-14/16. **Trigger:** IT chọn dịch vụ/job/khoảng lịch. **Điều kiện trước:** quyền xem áp dụng. **Input/output:** phạm vi vận hành → trạng thái, lịch, timestamp, phần thiếu/cũ và log tùy yêu cầu.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | IT admin | Chọn phạm vi | N02 |
| N02 | Hệ thống | Đọc job/status/lịch/timestamp | G01; lỗi đọc: E01 |
| G01 | Hệ thống | Có job phù hợp? | Có: N03; không: E02 |
| N03 | Hệ thống | Hiển thị từng trạng thái/độ mới, phần telemetry/lịch chưa có | N04 |
| N04 | IT admin | Xem và phân loại vấn đề vận hành | G02 |
| G02 | IT admin | Cần tra cứu log chi tiết? | Có: N05; không: N06 |
| N05 | IT admin + Hệ thống | Thực hiện ACT-SD-10 | N06 |
| N06 | IT admin | Ghi nhận vấn đề; nếu thuộc dữ liệu/model thì chuyển Data admin theo quy trình | E03 |

**Nhánh dữ liệu vận hành:** thiếu telemetry/lịch → ghi chưa biết/chưa cung cấp; cũ → timestamp cuối và cảnh báo, không tự nhận thành công (UC-SD-07/3a; UC-SD-11/3a,4a; UC-SD-11.1/2a,3a; UC-SD-11.2/2a,3a). Không có job → E02 (UC-SD-07/2a; UC-SD-11/2a). Cần quyền restart/thay lịch chưa chốt → chỉ ghi nhu cầu, không thực thi (UC-SD-07/4b). Vấn đề model → DA (4a).

**Hậu điều kiện:** E01 lỗi đọc riêng với chưa có telemetry; E02 không có job; E03 đã xem/ghi nhận theo scope. Không tự tạo ticket/email integration, đổi lịch, retry job hay kết luận model thay DA.

### ACT-SD-10 — Tra cứu log theo job/run

**Truy vết:** UC-SD-12; FR-SD-09; SEQ-SD-10; TC-SD-14/16. **Trigger:** ACT-SD-06/G02 chọn có. **Input:** job/run ID và phạm vi được phép. **Output:** log được phép xem hoặc trạng thái từ chối/không có/lỗi đọc.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | IT admin | Chọn/xác nhận job/run ID | G01 |
| G01 | Hệ thống | ID có hợp lệ trong phạm vi? | Có: G02; không: N02 |
| N02 | Hệ thống | Yêu cầu chọn lại từ danh sách khả dụng | N01 khi IT chọn lại |
| G02 | Hệ thống | Có quyền đọc log theo policy? | Có: N03; không: E01 |
| N03 | Hệ thống | Tra cứu log | G03; lỗi đọc: E02 |
| G03 | Hệ thống | Có dữ liệu log? | Có: N04; không: E03 |
| N04 | Hệ thống | Che/loại credentials và sensitive values theo policy trước hiển thị; ghi nhận sự cố bảo mật nếu có | N05 |
| N05 | IT admin | Đọc, phân loại; vấn đề dữ liệu/model chuyển DA theo quy trình | E04 |

**Nguồn nhánh:** UC-SD-12/2a,3a,3b,4a,5a. E01 từ chối và ghi nhận kiểm tra quyền theo policy; E02 lỗi truy cập; E03 không có log, không chứng minh run thành công; E04 đã xem. Các điểm kết thúc của activity con trả về ACT-SD-06/N06, không dừng toàn bộ quy trình cha. **Hậu điều kiện:** không đổi job state, source facts hoặc kết luận kiểm định.

## 6. Bao phủ, review và điều kiện dựng hình

| Nhóm UC | Activity | Sequence |
|---|---|---|
| UC-SD-01, UC-SD-06 | ACT-SD-01 và §2.2 | SEQ-SD-01 |
| UC-SD-02, UC-SD-02.1, UC-SD-06 | ACT-SD-02 và §2.2 | SEQ-SD-02 |
| UC-SD-03, UC-SD-03.1, UC-SD-06 | ACT-SD-03 và §2.2 | SEQ-SD-03 |
| UC-SD-04, UC-SD-06 | ACT-SD-04 và §2.2 | SEQ-SD-04 |
| UC-SD-05, UC-SD-08, UC-SD-09, UC-SD-10 | ACT-SD-05 | SEQ-SD-05 |
| UC-SD-07, UC-SD-11, UC-SD-11.1, UC-SD-11.2, UC-SD-12 | ACT-SD-06 | SEQ-SD-06 |
| UC-SD-08, UC-SD-08.1, UC-SD-08.2, UC-SD-08.3 | ACT-SD-07 | SEQ-SD-07 |
| UC-SD-09, UC-SD-09.1, UC-SD-09.2 | ACT-SD-08 | SEQ-SD-08 |
| UC-SD-10, UC-SD-10.1 | ACT-SD-09 | SEQ-SD-09 |
| UC-SD-12 | ACT-SD-10 | SEQ-SD-10 |

Checklist trước vẽ: mỗi action đúng lane; mọi decision có đường thiếu/chưa rõ khi cần; mọi nhánh có đích; lỗi không đi vào thông báo thành công; không dùng fork/join cho lựa chọn; kết thúc activity con trả đúng activity cha; không thêm hủy/retry/timeouts/quyền chưa xác nhận. Khi dựng hình, theo skill diagram-design của dự án, thống nhất style/layout trước render; tài liệu này chưa tạo hình.

Các quyết định còn mở dùng chung [Sequence Specification §14.2](SEQUENCE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md): contract dữ liệu, coverage/seasonality, output selection, evaluation protocol/metric, trạng thái kiểm định, enforcement triển khai, log/telemetry, persistence và retry. Policy role/scope/SoD/audit đã theo tab 2; không ngầm khóa baseline từ bản đặc tả này.

## Addendum — access control và ACT-SD-11 (2026-11-07)

### Phân quyền activity chung

Các action đọc Sales/Forecast dùng actor “Người dùng được quyền xem Sales/Forecast” và kiểm `sales:read` hoặc `forecast:read` cùng scope assignment. Danh sách role MD-01: US-01, 02, 03, 04, 06, 07, 11, 12, 14, 15. Planner có thêm `forecast:adjust`; Data Admin chỉ đọc/ghi hồ sơ evaluation kỹ thuật; IT Admin chỉ đọc job/log trong quyền vận hành. Mọi flow đọc kiểm permission và scope trước khi tải/trình dữ liệu. Flow ghi kiểm thêm SoD liên quan và kiểm lại permission/reference ngay trước persistence. Từ chối quyền kết thúc ở outcome lỗi được phép hiển thị; không đi vào outcome thành công. Audit ghi actor, permission, resource, outcome và thời điểm; ghi before/after khi lưu. Location chưa có mapping nội bộ được xác nhận không được dùng để nới scope.

### ACT-SD-11 — Điều chỉnh một giá trị forecast

**Lane:** Supply Chain Planner; Hệ thống. **Trigger:** Planner yêu cầu điều chỉnh một forecast đã có. **Điều kiện trước:** quyền đọc/điều chỉnh và scope phù hợp; output gốc, coordinate location/kỳ/product-grain và unit nhận diện được.

| Node | Lane | Hành động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Supply Chain Planner | Chọn forecast và một coordinate cần điều chỉnh | G01 |
| G01 | Hệ thống | Có `forecast:read`, `forecast:adjust` và đúng scope? | Có: N02; không: E01 |
| N02 | Hệ thống | Đọc model output/reference và unit trong scope | G02 |
| G02 | Hệ thống | Reference, coordinate, unit và mapping có căn cứ? | Có: N03; không: E02 |
| N03 | Supply Chain Planner | Nhập một giá trị mới và lý do | G03 |
| G03 | Hệ thống | Giá trị hữu hạn, không âm, precision hợp lệ, lý do đủ? | Có: N04; không: E03 |
| N04 | Hệ thống | Trình forecast gốc/mới/chênh lệch/unit/lý do | N05 |
| N05 | Supply Chain Planner | Xác nhận lưu version riêng | G04 |
| G04 | Hệ thống | Quyền còn hiệu lực, reference còn hợp lệ và có thay đổi? | Có thay đổi: N06; bị thu hồi/reference lỗi: E04; không đổi: E05 |
| N06 | Hệ thống | Lưu adjusted version, actor/thời điểm/reference và audit | G05 |
| G05 | Hệ thống | Persistence thành công? | Có: N07; không: E06 |
| N07 | Hệ thống | Báo lưu; giữ model forecast làm lựa chọn mặc định, adjusted version riêng sẵn để xem | N08 |
| E01–E04, E06 | Hệ thống | Từ chối quyền, thiếu căn cứ, input sai, mất quyền hoặc persistence failure; không tạo version | Kết thúc lỗi |
| E05 | Hệ thống | Giá trị không đổi; không tạo version, model output giữ nguyên | Kết thúc không đổi |
| N08 | Supply Chain Planner | Chọn model/adjusted version để xem nếu cần; không đổi mặc định sử dụng ở module khác | Kết thúc thành công |

**Hậu điều kiện:** không tạo version nếu nhánh lỗi hoặc giá trị không đổi; không sửa forecast gốc/source facts/score. Không có approval, publish hay execution.

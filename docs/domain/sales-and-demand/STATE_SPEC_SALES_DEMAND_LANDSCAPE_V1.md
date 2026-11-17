# Đặc tả State — PharmaFlow Sales & Demand Landscape V1

| Thuộc tính | Giá trị |
|---|---|
| Mã | PF-STATE-SALES-DEMAND-LANDSCAPE-V1 |
| Ngày | 2026-11-06 |
| Trạng thái | Proposed — mô hình trạng thái tương tác, chưa phải enum/schema/workflow đã triển khai |
| Nguồn nghiệp vụ | [Use Cases](USE_CASE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md), [Requirements](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md), [User Stories](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md) |
| Đối chiếu | [Sequence Specification](SEQUENCE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md), [Activity Specification](ACTIVITY_SPEC_SALES_DEMAND_LANDSCAPE_V1.md) |
| Phạm vi | 3 state machine ứng viên: yêu cầu xem kết quả, phiên kiểm định, lần gửi lưu kết luận; bảng điều kiện riêng cho chất lượng/khả dụng/telemetry |

## 1. Ý tưởng từ báo cáo mẫu và giới hạn áp dụng

Đã tham khảo [OneNigth_report03.pdf](D:/DOWNLOAD/HCMUT/HK251/CNPM/BTL/OneNigth_report03.pdf), chương 8, trang in 167–179 (trang PDF 171–183). Đã xem trực tiếp Hình 124–125 ở trang in 168 và Hình 134–135 ở trang in 172. Mẫu tổ chức state chart theo nhóm vai trò/chức năng; nhiều node mô tả trạng thái tương tác giao diện và có nhãn hành vi `do/`.

Áp dụng cách mô tả trạng thái tương tác khi chưa có lifecycle entity bền vững được xác nhận. Mỗi hình PharmaFlow phải nêu rõ chủ thể, phạm vi một lần thực hiện và ý nghĩa transition; không gọi mọi bước xử lý là trạng thái của forecast/model. Không chuyển lifecycle đăng ký Tutor, tài khoản, lịch hẹn, SSO hoặc quyền quản trị của mẫu thành yêu cầu PharmaFlow.
State trả lời “một chủ thể đang ở trạng thái nào, sự kiện và điều kiện nào cho phép đổi trạng thái”. Activity trả lời “bước tiếp theo của công việc là gì”. Không cần một state diagram cho mỗi oval UC hoặc một state cho mỗi message.

## 2. Chọn chủ thể và tách các trục trạng thái

| Chủ thể/khái niệm | Cách mô tả trong bản này | Lý do |
|---|---|---|
| Một yêu cầu xem kết quả | ST-SD-01, trạng thái tạm thời của yêu cầu | Có gửi yêu cầu, đọc, kiểm tra và trả kết quả/lỗi |
| Một phiên kiểm định | ST-SD-02, tiến trình tương tác của DA | Có đối soát, gate evaluation, ghi kết luận và kết quả lưu |
| Một lần gửi lưu kết luận | ST-SD-03, trạng thái tạm thời của lần gửi | Cần phân biệt không đạt validation, lưu thành công và thất bại |
| Chất lượng đầu vào/evaluation | Bảng điều kiện §6; giá trị gắn với scope/evidence | Invalid và not assessable khác nhau, không mặc định có quy tắc chuyển qua lại |
| Khả dụng forecast theo location/kỳ | Bảng điều kiện §6 | Có/thiếu/không hợp lệ là kết quả kiểm tra output, chưa có lifecycle tạo/phát hành |
| Job/run execution | Chỉ đọc telemetry theo UC-SD-07/11/12 | Chưa có scheduler contract để chốt queued/running/retry/cancel lifecycle |
| Kết luận đã lưu | Kết quả persistence; không tự có draft/approved/published/archived | Chưa chốt sửa/version/retention hoặc approval publication |

Các tên ST và state dưới đây là **Design proposal suy ra từ hành vi đã đặc tả**. Chưa tạo entity, DB status column, API hoặc tự động hóa. Không yêu cầu lưu từng trạng thái tạm thời vào database.

### 2.1. Quy ước transition

Mỗi transition ghi `event [guard] / action`. Sự kiện là điều quan sát được; guard kiểm điều kiện; action là tác động khi chuyển. Không đủ evidence không đồng nghĩa phát hiện vi phạm. Initial/final chỉ giới hạn một lần tương tác, không có nghĩa đối tượng nguồn bị tạo/xóa.

Các transition không có trong bảng chưa được định nghĩa trong mô hình đề xuất, không đồng nghĩa tất cả đều bị business cấm. Bảng “không được suy diễn” bên dưới phân biệt invariant có căn cứ với policy còn TBD. Không thêm tự động retry, timeout, cancel, restart hoặc reopen.

### 2.2. Thành phần bên trong state node và trên transition

Đối chiếu ký pháp với [OMG UML 2.5.1](https://www.omg.org/spec/UML/2.5.1/PDF), §14.2.3.4.3 và phần ký pháp StateMachines trong chương 14. Một state đơn có tên và có thể có ngăn behavior; không bắt buộc state nào cũng đủ entry/do/exit.

| Thành phần | Vị trí và cách viết | Ý nghĩa/cách áp dụng |
|---|---|---|
| State name | Ngăn tên phía trên, ví dụ `Đang đọc dữ liệu` | Mô tả tình trạng của đúng chủ thể; ID V2/K2/L2 dùng truy vết, không thay tên |
| `entry / behavior` | Ngăn behavior dưới tên | Hành vi khi vào state; chỉ ghi khi thực sự có hành vi riêng cần thể hiện |
| `do / behavior` | Cùng ngăn behavior | Hành vi diễn ra khi state đang active; có thể hoàn tất hoặc bị dừng khi rời state |
| `exit / behavior` | Cùng ngăn behavior | Hành vi khi rời state; không tự thêm xóa dữ liệu, cleanup, rollback hoặc ghi audit chưa có yêu cầu |
| Internal transition | Trong ngăn behavior, nếu cần | Phản ứng sự kiện không rời state; khác self-transition bên ngoài. Chưa có nhu cầu được đặc tả riêng trong bản này |
| Transition | Cạnh có hướng giữa state | Nhãn `trigger [guard] / effect`; bỏ phần không áp dụng, không điền cho đủ mẫu |
| Initial pseudostate | Chấm đặc | Mũi tên khởi tạo không có trigger/guard; điều kiện bắt đầu ghi ngoài hình hoặc trước khi khởi tạo machine |
| Final state | Chấm đặc trong vòng tròn | Kết thúc region/phạm vi machine; không chứa entry/do/exit, không có cạnh đi ra |

**Mẫu nội dung node, không phải mã diagram:**

```text
V2 — Đang đọc dữ liệu
-------------------
do / Đọc dữ liệu và metadata trong phạm vi yêu cầu
```

Trong ví dụ này không có entry/exit riêng nên bỏ hai dòng đó. Dấu gạch phân ngăn là ký hiệu minh họa văn bản, khi vẽ dùng compartment của state. Không đặt toàn bộ câu “do / đọc dữ liệu…” làm tên state như một action box.

**Mẫu nhãn cạnh:** `Nhận phản hồi nguồn [truy vấn hoàn tất] / Chuyển kết quả sang kiểm tra`. Phân biệt:

- Trigger: sự kiện xảy ra, ví dụ nhận phản hồi hoặc DA gửi kết luận.
- Guard: điều kiện Boolean tại thời điểm xét chuyển, đặt trong `[...]`; thiếu evidence phải có cách xử lý riêng.
- Effect: hành vi khi transition được thực hiện, đặt sau `/`; không gọi effect trên cạnh là doActivity của state.
- Completion transition: có thể không ghi trigger; ghi guard/effect nếu cần khi behavior của state hoàn tất. Không bịa sự kiện người dùng cho bước chuyển nội bộ.

**Nhận xét cụ thể từ PDF:** Hình 134–135 có nhiều ô chứa `do/`, cạnh chứa điều kiện trong ngoặc vuông và một số cạnh cũng ghi `do/`. Đây là cách trình bày quan sát được trong mẫu, không được sao chép đồng loạt: W19.10 dành `do /` cho behavior trong state, còn hành vi trên transition viết sau `/` trong nhãn trigger/guard/effect. Hình 122–123 có nhiều node đặt tên giống thao tác; bản PharmaFlow phải giữ tên trạng thái và chủ thể rõ để tránh trùng Activity. Không coi `entry`, `exit`, composite state, history hay parallel region là thành phần đã có trong các hình mẫu đã xem.

### 2.3. Hồ sơ nội dung cho toàn bộ state node

Hồ sơ mỗi state gồm `ID; chủ thể; tên; ý nghĩa/invariant; entry; do; exit; transition vào/ra; nguồn UC/FR`. Ý nghĩa/invariant đã ghi ở các bảng §3–5; bảng sau xác định nội dung behavior dự kiến trong hình. Mọi entry/exit để trống trong mô hình tối thiểu vì chưa có hành vi riêng được chốt. Dấu `—` nghĩa là bỏ compartment/dòng khi vẽ, không phải yêu cầu bổ sung chức năng.

| Machine/state | Tên state | `do /` đề xuất | `entry /` và `exit /` |
|---|---|---|---|
| ST-SD-01/V1 | Đang kiểm tra yêu cầu | Kiểm tra phạm vi hỗ trợ và quyền áp dụng | — |
| ST-SD-01/V2 | Đang đọc dữ liệu | Đọc facts/output và metadata có sẵn | — |
| ST-SD-01/V3 | Đang kiểm tra kết quả | Kiểm tra ngữ nghĩa, điều kiện hiển thị và phần thiếu/lỗi | — |
| ST-SD-01/V4 | Đã trả phản hồi | —; phản hồi đã được trình bày là điều kiện của state | — |
| ST-SD-01/V5 | Lỗi tải kết thúc yêu cầu | —; thông báo lỗi thuộc effect chuyển vào | — |
| ST-SD-01/V6 | Yêu cầu bị từ chối | —; thông báo từ chối thuộc effect chuyển vào | — |
| ST-SD-02/K1 | Đang đối soát đầu vào | DA đối chiếu nguồn/contract/UOM/mapping/coverage với hỗ trợ của hệ thống | — |
| ST-SD-02/K2 | Đang xem xét evaluation | DA kiểm temporal validity và xem xét comparability/metric có căn cứ | — |
| ST-SD-02/K3 | Đang ghi kết luận | DA nhập nhận xét/căn cứ và gắn reference hiện có | — |
| ST-SD-02/K4 | Đang gửi lưu | Thực hiện lần gửi lưu theo ST-SD-03 | — |
| ST-SD-02/K5 | Hoàn tất có kết luận đã lưu | —; phản hồi lưu thành công là điều kiện của state | — |
| ST-SD-02/K6 | Kết thúc lần lưu không thành công | —; nguyên nhân chưa lưu được giữ theo kết quả lần gửi | — |
| ST-SD-02/K7 | Gián đoạn do sự cố truy cập | —; ghi nhận/chuyển đầu mối thuộc effect chuyển vào | — |
| ST-SD-03/L1 | Đang kiểm tra nội dung | Kiểm trạng thái/căn cứ bắt buộc, reference và quyền áp dụng | — |
| ST-SD-03/L2 | Đang lưu | Gửi nội dung lưu và chờ phản hồi của nơi lưu | — |
| ST-SD-03/L3 | Đã lưu | —; có phản hồi lưu thành công | — |
| ST-SD-03/L4 | Chưa lưu do nội dung chưa đạt | —; đã nhận lý do validation/quyền | — |
| ST-SD-03/L5 | Lưu thất bại | —; đã nhận phản hồi lỗi lưu | — |

Các state K1–K3 mô tả trạng thái phiên tương tác, không phải hệ thống tự thực hiện thay DA. Các state V4–V6/K5–K7/L3–L5 là state kết quả trước final, không phải ký hiệu final. Khi dựng hình, chỉ giữ state kết quả nếu cần đọc outcome; final không thay cho tên outcome.

### 2.4. Quy tắc dùng bảng transition khi dựng hình

1. Dùng bảng §3.2/4.2/5.2 xác định đích, event và guard; dùng §2.3 xác định behavior trong state. Mỗi tác vụ chỉ đặt một lần: nếu behavior đã là `do /` của state đích thì effect trên cạnh chỉ chuyển/giao context, không khởi chạy cùng tác vụ lần nữa.
2. Với T01 ở mỗi machine, thao tác người dùng/điều kiện có quyền là trigger khởi tạo machine ở bên ngoài; cạnh từ Initial tới state đầu chỉ là default transition, không đặt trigger hoặc guard trên cạnh đó.
3. Từ state active, phân biệt “đã hoàn tất kiểm tra” (completion) với “DA xác nhận/gửi” (sự kiện tương tác). Không biến cả hai thành cùng một nút action của Activity.
4. Bảng này mô tả state đơn của chủ thể tương tác. Chưa có căn cứ thêm composite state, history, orthogonal region, timer hoặc event defer. ST-SD-03 là mô hình chi tiết được tham chiếu, chưa tự khai báo nó là submachine UML có entry/exit point đã chốt.
5. Không dùng màu sắc, bo góc hoặc nhãn `do/` để thay cho kiểm tra ngữ nghĩa state. Phải đọc được “chủ thể đang ở tình trạng gì” ngay từ tên state.

## 3. ST-SD-01 — Trạng thái một yêu cầu xem Sales/Forecast

**Chủ thể:** một yêu cầu xem trong phạm vi và loại chức năng cố định; thay bộ lọc/gửi lại là yêu cầu khác. **Actor:** Người dùng được quyền xem Sales/Forecast, thuộc một trong mười role MD-01 nêu tại UC-SD/US. **Truy vết:** UC-SD-01–04/06; FR-SD-01–04/06; SEQ-SD-01–04; ACT-SD-01–04; TC-SD-02/03/04/06/07/11/12/13/14/15.

**Biên:** bắt đầu khi người dùng gửi phạm vi, kết thúc khi phản hồi của lần đó được trình bày hoặc bị từ chối. Không mô tả lifecycle của model, bản ghi Sales hay forecast run.

### 3.1. Danh sách trạng thái

| State | Ý nghĩa | Điều kiện/hoạt động trong trạng thái |
|---|---|---|
| V1 — Đang kiểm tra yêu cầu | Đã nhận phạm vi; kiểm `sales:read` hoặc `forecast:read` tương ứng, scope assignment, SoD áp dụng và phạm vi được hỗ trợ trước khi đọc | Không trả dữ liệu ngoài quyền; không tự sửa lựa chọn |
| V2 — Đang đọc dữ liệu | Yêu cầu hợp lệ để truy vấn | Đọc facts/output và metadata có sẵn |
| V3 — Đang kiểm tra kết quả | Đã có phản hồi nguồn để kiểm ngữ nghĩa/điều kiện | Phân biệt phần hợp lệ/thiếu/lỗi, UOM/grain/location/provenance |
| V4 — Đã trả phản hồi | Phản hồi business đã được trình bày | Phản hồi có thể đủ, một phần, không có dữ liệu hoặc chưa so sánh/kết luận được |
| V5 — Lỗi tải kết thúc yêu cầu | Không tạo được phản hồi dữ liệu tin cậy cho lần xem | Thông báo lỗi khác no record/zero; giữ nguồn nguyên vẹn |
| V6 — Yêu cầu bị từ chối | Không đủ quyền hoặc phạm vi không được hỗ trợ | Nêu lý do phù hợp quyền; không phát sinh dữ liệu thay thế |

V4 không có nghĩa forecast/evaluation hợp lệ. Một yêu cầu trả thành công thông báo “chưa có forecast” vẫn có outcome dữ liệu là thiếu. Lỗi một phần có thể được trình bày trong V4 với từng phần được phân biệt; V5 dành cho thất bại tải khiến lần yêu cầu không có phản hồi dữ liệu tin cậy.

### 3.2. Bảng transition

| Mã | Từ → Đến | Event [guard] / action | Căn cứ |
|---|---|---|---|
| T01 | Initial → V1 | Default transition, không trigger/guard; machine bắt đầu sau khi tiếp nhận phạm vi | Normal Flow UC-SD-01–04 |
| T02 | V1 → V2 | Hoàn tất kiểm tra [`sales:read` hoặc `forecast:read` tương ứng; scope/SoD áp dụng đạt; phạm vi được hỗ trợ] / đọc nguồn | FR-SD-01–04; NFR-SD-07; TC-SD-14 |
| T03 | V1 → V6 | Xác định thiếu permission, scope ngoài phạm vi hoặc phạm vi không hỗ trợ / audit outcome, từ chối và không trả payload | TC-SD-14; UC-SD-01/2a; UC-SD-04/2a; NFR-SD-07 |
| T04 | V2 → V3 | Nguồn trả dữ liệu hoặc kết quả không có bản ghi / kiểm kết quả | UC-SD-01/3a; UC-SD-04/3a |
| T05 | V2 → V5 | Nhận lỗi tải không xử lý được trong phản hồi một phần / báo lỗi | NFR-SD-09; TC-SD-13 |
| T06 | V3 → V4 | Hoàn tất kiểm tra / hiển thị số liệu có căn cứ hoặc trạng thái tương ứng và UC-SD-06 | UC-SD-02/3a,3b,4a; UC-SD-03/3a,3b,5a; UC-SD-04/3a,3b,4a,4b |
| T07 | V3 → V5 | Xảy ra lỗi tải bổ sung khiến không hoàn tất phản hồi tin cậy / báo lỗi | NFR-SD-09 |
| T08 | V4 → Final | Hoàn tất trình bày / kết thúc lần xem | Post-conditions UC-SD-01–04 |
| T09 | V5 → Final | Đã báo lỗi / kết thúc lần yêu cầu lỗi | TC-SD-13 |
| T10 | V6 → Final | Đã trả từ chối / kết thúc lần yêu cầu | TC-SD-14; nhánh không hỗ trợ |

### 3.3. Invariant và đường không được suy diễn

| Tình huống | Quy tắc |
|---|---|
| V2 gặp lỗi → trả số 0 như dữ liệu | Không được: lỗi tải khác zero, NFR-SD-09 |
| V3 thiếu output → tự train model | Không được trong phạm vi FR-SD-04 |
| V4 → “forecast approved/published” | Không có policy; trạng thái phản hồi không cấp quyền phát hành |
| V5 → V2 tự động retry | Chưa được định nghĩa; retry phải theo flow được chốt, không tự thêm |
| V6 → V4 trả dữ liệu ngoài quyền | Không được theo permission/scope policy tại tab 2 |

**Kiểm thử chấp nhận mô hình:** zero từ bản ghi vẫn tới V4; thiếu forecast tới V4 với outcome thiếu; lỗi tải tới V5; series không tương thích tới V4 với lý do không so sánh được; dữ liệu mô phỏng tới V4 phải có nhãn. Không so output success của yêu cầu với chất lượng prediction.

## 4. ST-SD-02 — Trạng thái phiên kiểm định forecast

**Chủ thể:** một phiên tương tác kiểm định với snapshot/run reference xác định. Đây không phải vòng đời bền vững của forecast run. **Actor:** Data admin. **Truy vết:** UC-SD-05/08/09/10 và các UC con; FR-SD-05; SEQ-SD-05/07/08/09; ACT-SD-05/07/08/09; TC-SD-08/09/10/17.

### 4.1. Danh sách trạng thái

| State | Ý nghĩa | Bất biến |
|---|---|---|
| K1 — Đang kiểm tra quyền và đối soát đầu vào | DA kiểm `forecast_evaluation:read`, scope và SoD áp dụng trước khi đọc/đối chiếu nguồn, contract, UOM, mapping, coverage | Không trả payload ngoài quyền; không sửa source facts |
| K2 — Đang xem xét evaluation | Đủ điều kiện mở phần temporal validity/comparability | Được mở phần kiểm tra không có nghĩa evaluation đã hợp lệ |
| K3 — Đang ghi kết luận | Đã có kết quả kiểm tra hoặc lý do chưa đánh giá được | DA chịu trách nhiệm nhận xét, evidence thiếu phải ghi rõ |
| K4 — Đang gửi lưu | Đã gửi nội dung kết luận; đang thực hiện ST-SD-03 | Chưa báo đã lưu khi chưa có xác nhận |
| K5 — Hoàn tất có kết luận đã lưu | Nơi lưu đã phản hồi thành công | Có thể lưu kết luận invalid/not assessable; không tự publish forecast |
| K6 — Kết thúc lần lưu không thành công | Lần gửi bị từ chối validation hoặc lưu thất bại | Không xác nhận có kết luận mới đã lưu |
| K7 — Bị chặn hoặc gián đoạn do quyền/truy cập | Thiếu permission/scope/SoD áp dụng trước khi đọc hoặc có sự cố cản trở tương tác | Không trả payload ngoài quyền; audit outcome; sự cố dịch vụ/job chuyển IT, DA không tự restart |

K6 mô tả kết quả lần gửi trong phiên, không khẳng định UI bị đóng hoặc mất nội dung. Không thiết kế giữ nháp hoặc tự khôi phục. Chính sách tiếp tục sau thất bại phải được chốt trước khi thêm đường quay lại.

### 4.2. Bảng transition

| Mã | Từ → Đến | Event [guard] / action | Căn cứ |
|---|---|---|---|
| T01 | Initial → K1 | Yêu cầu mở phiên; K1 kiểm permission, scope và SoD áp dụng trước khi đọc hồ sơ | UC-SD-05/1–3; NFR-SD-07 |
| T02 | K1 → K2 | DA xác nhận đối soát [forecast_evaluation:read, scope/SoD áp dụng đạt; dữ liệu/protocol đủ điều kiện] / mở phần evaluation | UC-SD-05/4; UC-SD-08/5; NFR-SD-07 |
| T03 | K1 → K3 | Hoàn tất ghi nhận đối soát [quyền/scope hợp lệ nhưng evidence hoặc protocol chưa đủ] / giữ lý do, bỏ so sánh phụ thuộc | UC-SD-05/3a; UC-SD-08/5a |
| T04 | K2 → K3 | Hoàn tất xem xét hoặc phát hiện điều kiện chặn / mang metric hợp lệ hoặc lý do invalid/chưa đánh giá được sang kết luận | UC-SD-05/4a,4b,5a; UC-SD-09/2a–5a |
| T05 | K3 → K4 | DA gửi kết luận [forecast_evaluation:record, scope và SoD áp dụng đạt] / thực hiện ST-SD-03, nơi lưu kiểm lại trước persistence | UC-SD-10/3–6; NFR-SD-07 |
| T06 | K4 → K5 | Nhận phản hồi lưu thành công / xác nhận đã lưu cùng reference có sẵn | UC-SD-10/6 |
| T07 | K4 → K6 | Validation bị từ chối hoặc lưu thất bại / báo chưa lưu và lý do phù hợp | UC-SD-10/5a,6a |
| T08 | K1 → K7 | Thiếu permission/scope/SoD áp dụng trước khi đọc hoặc sự cố truy cập / không trả payload; audit outcome khi bị từ chối, chuyển IT nếu là sự cố dịch vụ | NFR-SD-07; UC-SD-05/7b |
| T09 | K2 → K7 | Sự cố truy cập cản trở evaluation / chuyển IT theo quy trình | UC-SD-05/7b |
| T10 | K3 → K7 | Không truy cập được hồ sơ cần ghi căn cứ / ghi nhận reference đang có, báo chưa hoàn tất | UC-SD-05/7b |
| T11 | K5 → Final | Đã hiển thị xác nhận lưu / kết thúc phiên trong phạm vi mô hình | Post-conditions UC-SD-05 |
| T12 | K6 → Final | Đã báo chưa lưu / kết thúc phạm vi lần thực hiện đang mô tả | UC-SD-05/7a |
| T13 | K7 → Final | Đã báo gián đoạn/chuyển đầu mối / chưa có kết luận hoàn tất được khẳng định | UC-SD-05/7b |

K1 là bước kiểm policy trước khi đọc payload; từ chối quyền/scope không được coi là thiếu evidence và không đi vào K3. Nếu lỗi truy cập xảy ra trước khi mở được hồ sơ thì không tạo phiên kiểm định giả. Lỗi truy cập tại K4 được ST-SD-03 xử lý như lỗi lưu; không có hai transition cạnh tranh cho cùng sự kiện.

### 4.3. Điều kiện không được suy diễn

| Đường/diễn giải | Ràng buộc |
|---|---|
| K1 → K5 bỏ qua ghi kết luận/lưu | Không đủ căn cứ xác nhận đã lưu |
| K2 phát hiện leakage → kết luận Prediction Quality hợp lệ | Không được theo BR-SD-07/TC-SD-08 |
| K5 → model đã được duyệt phát hành | Không có publication workflow trong UC-SD-05/10 |
| K6/K7 → tự restart job hoặc tự chạy backtest | Ngoài phạm vi, quyền/quy trình chưa xác nhận |
| K5 → sửa/xóa kết luận hoặc mở lại phiên | Policy version/reopen/retention còn TBD; không thiết lập transition |

**Kiểm thử chấp nhận mô hình:** K1 bị chặn vẫn đến K3 và có thể K5 với kết luận chưa đánh giá được; K2 phát hiện leakage vẫn có thể lưu kết luận invalid; K4 lỗi không đến K5. K5 không chứng minh prediction tốt hoặc quyết định tồn kho tốt.

## 5. ST-SD-03 — Trạng thái một lần gửi lưu kết luận

**Chủ thể:** một lần gửi nội dung kết luận, không phải toàn bộ vòng đời bản ghi kết luận. **Truy vết:** UC-SD-10/10.1; FR-SD-05; SEQ-SD-09; ACT-SD-09; TC-SD-17.

### 5.1. Danh sách trạng thái

| State | Ý nghĩa |
|---|---|
| L1 — Đang kiểm tra nội dung | Đã nhận lần gửi; kiểm trạng thái/căn cứ bắt buộc, references và quyền áp dụng |
| L2 — Đang lưu | Nội dung đủ điều kiện gửi lưu theo policy; chưa xác nhận persistence |
| L3 — Đã lưu | Nhận phản hồi lưu thành công |
| L4 — Chưa lưu do nội dung chưa đạt | Thiếu trường bắt buộc/reference cần xác nhận hoặc không đủ quyền theo policy |
| L5 — Lưu thất bại | Đã gửi lưu nhưng nhận lỗi, chưa có xác nhận thành công |

### 5.2. Bảng transition

| Mã | Từ → Đến | Event [guard] / action | Căn cứ |
|---|---|---|---|
| T01 | Initial → L1 | Default transition, không trigger/guard; machine được khởi tạo bởi lần gửi nội dung của DA | UC-SD-10/3–5 |
| T02 | L1 → L2 | Hoàn tất validation [đạt policy áp dụng] / gắn actor/thời điểm, gửi lưu | UC-SD-10/5–6 |
| T03 | L1 → L4 | Hoàn tất validation [thiếu bắt buộc/reference chưa hợp lệ hoặc bị từ chối quyền] / yêu cầu bổ sung hoặc báo từ chối | UC-SD-10/5a; UC-SD-10.1/2a; NFR-SD-07 |
| T04 | L2 → L3 | Nơi lưu phản hồi thành công / xác nhận đã lưu | UC-SD-10/6 |
| T05 | L2 → L5 | Nơi lưu phản hồi thất bại / báo chưa lưu | UC-SD-10/6a |
| T06 | L3 → Final | Đã trình bày kết quả / trả thành công cho K4 của ST-SD-02 | UC-SD-05/7 |
| T07 | L4 → Final | Đã trình bày lý do / trả chưa lưu cho phiên cha | UC-SD-10/5a |
| T08 | L5 → Final | Đã trình bày lỗi / trả chưa lưu cho phiên cha | UC-SD-10/6a |

Thiếu evidence reference phải được ghi rõ, nhưng không tự đồng nghĩa validation bị chặn: phụ thuộc field/policy bắt buộc được xác nhận. Kết luận “chưa đánh giá được” có thể đạt L2/L3 với bằng chứng còn thiếu được mô tả trung thực. Reference đã biết không hợp lệ không được nhận là hợp lệ hoặc truy vết đầy đủ.

Không tự định nghĩa timeout, xử lý mất phản hồi sau khi server có thể đã lưu, retry/idempotency, duplicate submissions hoặc rollback. Đây là khoảng trống cần chốt; không có phản hồi thành công thì UI không báo “đã lưu”, nhưng cũng không khẳng định database chắc chắn chưa ghi nếu contract không chứng minh điều đó.

### 5.3. Đường không được suy diễn

| Đường/diễn giải | Ràng buộc |
|---|---|
| L1 → L3 không có xác nhận nơi lưu | Không đủ căn cứ báo đã lưu |
| L4/L5 → L3 chỉ vì UI đóng thông báo lỗi | Không được; cần một lần gửi và phản hồi lưu thành công |
| L5 → L2 tự retry | Chưa có policy; không tự thêm |
| L3 → “forecast chất lượng tốt” | Persistence thành công không đánh giá Prediction Quality |
| Gửi lại sau bổ sung | Là lần gửi mới theo quy trình được chốt, không làm lần gửi cũ tự thành công |

**Kiểm thử chấp nhận mô hình:** thiếu trạng thái bắt buộc dẫn L4; reference sai dẫn L4; invalid/not assessable với nội dung hợp lệ vẫn có thể L3; lỗi persistence dẫn L5; facts và score nguyên vẹn trong mọi đường.

## 6. Các trạng thái dữ liệu phải mô tả bằng điều kiện riêng

### 6.1. Kết quả đối soát và evaluation

| Trục | Các ý nghĩa cần phân biệt | Evidence cần có | Không suy diễn |
|---|---|---|---|
| Đối soát đầu vào | Phù hợp; phát hiện sai lệch; chưa xác định | Snapshot, contract, UOM/mapping, phạm vi và kết quả kiểm tra | Không dùng thiếu contract làm bằng chứng dữ liệu đạt |
| Temporal validity | Có căn cứ hợp lệ; có leakage; chưa đủ căn cứ | Thời điểm dữ liệu/features theo từng origin | Không lấy một cutoff đơn lẻ thay chứng cứ đầy đủ |
| Comparability | Tương thích; không tương thích; chưa đủ metadata | Target/grain/unit/horizon/origins/actuals/protocol/evaluation period | Không xếp hạng trực tiếp các phạm vi khác nhau |
| Khả năng đọc metric | Đủ căn cứ; chưa xác định được; chưa chốt định nghĩa | Actuals/coverage và metric definition | Không tạo score thay thế hoặc tự chọn MAE/RMSE/WAPE/Bias làm bộ nghiệm thu |
| Kết luận DA | Hợp lệ; không hợp lệ; chưa đánh giá được theo scope | Actor/thời điểm, kết quả kiểm tra, lý do và references | Kết luận hợp lệ của kiểm định không mặc định model tốt hoặc model được phát hành |

Nguồn dùng các từ invalid/not assessable/not evaluable trong ngữ cảnh khác nhau; đây chưa là enum database chuẩn hóa. Không vẽ đường “invalid → valid” chỉ do chờ đủ thời gian. Cần evidence mới và policy tái kiểm định/versioning trước khi đặc tả transition bền vững.

### 6.2. Khả dụng forecast theo một cặp location/kỳ

| Điều kiện kiểm tra | Cách trình bày | Căn cứ |
|---|---|---|
| Có output và đủ điều kiện hợp lệ | Hiển thị Forecast Sales Quantity cùng business context | UC-SD-04 Normal Flow |
| Không có output | Chưa có forecast đúng location/kỳ; không điền zero | UC-SD-04/3a |
| Output/run chưa hợp lệ hoặc chưa hoàn tất | Không công bố số đó, giữ lý do kỹ thuật nội bộ | UC-SD-04/3b |
| Đơn vị chưa xác nhận | Ghi chưa xác định hoặc ẩn đơn vị; không tự đoán | UC-SD-04/4a |
| Synthetic | Nhãn dữ liệu mô phỏng | UC-SD-04/4b |
| Lỗi đọc | Thông báo lỗi riêng với không có forecast | NFR-SD-09 |

Synthetic là provenance, unit chưa rõ là metadata, có output là availability: các trục có thể đồng thời tồn tại, không nối thành chuỗi “synthetic → valid → available”. Chưa có trạng thái publish/approve/reject lifecycle của forecast output trong contract.

### 6.3. Job/run và độ mới telemetry

| Trục | Cách sử dụng | Căn cứ |
|---|---|---|
| Execution status | Hiển thị đang chạy/hoàn tất/lỗi khi nguồn contract cung cấp | UC-SD-11/11.1 |
| Evidence availability | Thiếu telemetry thì trạng thái quan sát là chưa biết; không chứng minh job chưa chạy | UC-SD-11.1/2a |
| Freshness | Hiển thị timestamp cuối và cảnh báo cũ theo rule đã chốt | UC-SD-11.1/3a; UC-SD-11.2/3a |
| Schedule availability | Có lịch hoặc chưa được cung cấp; thao tác xem không thay lịch | UC-SD-11.2 |

“Telemetry cũ” không phải execution state mới của job. Chưa vẽ lifecycle queued → running → success/failed hoặc failed → retry: thiếu scheduler/state contract, quyền retry/restart và policy stale. Mẫu state diagram quản trị tài khoản không cung cấp những quy tắc này cho PharmaFlow.

## 7. Ma trận liên kết và quyết định mở

| Nhóm hoạt động | State thích hợp | Phạm vi |
|---|---|---|
| UC-SD-01/02/03/04/06; ACT-SD-01–04 | ST-SD-01 và §6.2 | Trạng thái một yêu cầu xem, không phải vòng đời dữ liệu |
| UC-SD-05/08/09 và UC con; ACT-SD-05/07/08 | ST-SD-02 và §6.1 | Tiến trình tương tác kiểm định và outcome/evidence tách riêng |
| UC-SD-10/10.1; ACT-SD-09 | ST-SD-03, K3–K6 của ST-SD-02 | Một lần gửi lưu; chưa quy định lifecycle sửa/phát hành kết luận |
| UC-SD-07/11/11.1/11.2/12; ACT-SD-06/10 | §6.3; chưa chốt state machine execution | Chỉ quan sát telemetry và log; không quản lý scheduler |

| Quyết định cần chốt | Ảnh hưởng |
|---|---|
| Các chủ thể tương tác đề xuất có được chấp nhận làm phạm vi state diagram không? | Tên và biên ST-SD-01–03; chưa khẳng định entity thiết kế đã khóa |
| Bộ mã/ý nghĩa kết luận, gate kiểm định và evidence bắt buộc | Guards K1/K2/K3 và validation L1 |
| Lưu nháp, sửa/version kết luận, tiếp tục/reopen sau lỗi | Chưa có transition quay lại từ K5/K6/K7 |
| Timeout, unknown save outcome, idempotency và retry | Chưa có cơ chế tự phục hồi L5; không giả database chắc chắn chưa ghi |
| Output/run selection và điều kiện công bố forecast | Chưa có lifecycle publish hoặc chính sách latest run |
| Execution state contract, quyền restart/cancel và stale threshold | Chưa có state diagram quản lý job |
| Authentication mechanism, enforcement DB/RLS, audit retention/implementation và masking chi tiết | Role/scope/SoD/audit fields đã theo tab 2; chi tiết triển khai còn chốt |

Checklist trước dựng hình: mỗi state có chủ thể và ý nghĩa tồn tại trong thời gian; mỗi transition có event/guard/action; không nối các trục độc lập thành lifecycle; nhánh lỗi không tự đi thành công; final không xóa đối tượng; không biến Proposed thành deployed; Prediction Quality/Decision Quality và observed/synthetic luôn tách riêng. Khi dựng hình theo skill diagram-design, chốt style/layout và chia hình theo mức độ phức tạp; bản này chưa chứa hình.

## Addendum — permission guards và ST-SD-04 (2026-11-07)

### Permission guard chung

Các state machine đọc Sales/Forecast chỉ đi vào trạng thái đọc dữ liệu sau khi permission tương ứng và data scope được chấp nhận. Mất quyền trước khi trả dữ liệu dẫn tới state từ chối hiện có V6; không trả payload ngoài quyền. Phiên kiểm định Data Admin và truy cập job/log IT Admin dùng quyền kỹ thuật riêng, không đồng nhất với quyền nghiệp vụ MD-01. Các điều kiện SoD chỉ áp dụng khi có thao tác thuộc policy SoD; không tự thêm quy trình duyệt forecast. Permission guard không tuyên bố auth implementation đã tồn tại.

### ST-SD-04 — Trạng thái một lần gửi lưu forecast adjustment

**Chủ thể:** một lần gửi lưu bản điều chỉnh cho một forecast reference/coordinate; đây không phải lifecycle của model run, approval hay forecast publication. **Actor:** Supply Chain Planner. **Trigger:** Planner xác nhận lưu một giá trị điều chỉnh. **Truy vết:** UC-SD-13; FR-SD-10; SEQ-SD-11; ACT-SD-11.

| State | Ý nghĩa/bất biến |
|---|---|
| A1 — Đang kiểm tra yêu cầu | Đã nhận submission; chưa tạo version |
| A2 — Đang kiểm tra reference và quyền | Kiểm permission, scope, reference, coordinate, unit |
| A3 — Yêu cầu chưa hợp lệ | Thiếu quyền/reference/unit/lý do hoặc giá trị sai; không persistence |
| A4 — Đang chờ xác nhận | Đã trình model output, giá trị mới, chênh lệch, unit, lý do |
| A5 — Đang lưu version | Permission/reference được kiểm lại; ghi version riêng và audit |
| A6 — Đã lưu version | Version có actor/thời điểm/reference; model output và score gốc không đổi |
| A7 — Lưu thất bại | Không có version mới; output gốc không đổi; cho phép người dùng xử lý lại bằng submission mới |
| A8 — Không có thay đổi | Giá trị mới trùng model value; không tạo version |
| A9 — Bị từ chối | Permission bị thu hồi hoặc scope không hợp lệ; không tiết lộ resource ngoài scope |

| Transition | From → To | Trigger/guard/action |
|---|---|---|
| T01 | Initial → A1 | Default transition khi nhận submission |
| T02 | A1 → A2 | Có input để kiểm tra |
| T03 | A2 → A3 | Thiếu permission, scope, reference, coordinate, unit hoặc SoD áp dụng không đạt |
| T04 | A2 → A4 | Reference và quyền hợp lệ; giá trị/lý do đạt validation |
| T05 | A4 → A8 | Planner xác nhận nhưng giá trị không đổi |
| T06 | A4 → A9 | Quyền bị thu hồi/reference không còn trong scope khi xác nhận |
| T07 | A4 → A5 | Planner xác nhận; quyền/reference được kiểm tra lại thành công |
| T08 | A5 → A6 | Version riêng và audit được ghi thành công |
| T09 | A5 → A7 | Persistence thất bại; không tạo version quan sát được |
| T10 | A3/A7/A8/A9 → Final | Trả outcome tương ứng; mọi retry là submission mới |
| T11 | A6 → Final | Trả xác nhận version đã lưu; model output vẫn là lựa chọn mặc định |

Không có state approved/published/active-by-default. Model output là lựa chọn mặc định kể cả khi A6; adjusted version chỉ được chọn tường minh.

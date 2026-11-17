# Kiến trúc hệ thống PharmaFlow

## Mục tiêu và trạng thái

PharmaFlow là Decision Support System (DSS) cho chuỗi cung ứng dược phẩm. Tài liệu này mô tả kiến trúc đích đã được nhóm định hướng và phân biệt nó với những phần đã có trong repository. Đây không phải bằng chứng Databricks, Weather API, S3 hay web platform đã được triển khai.

PharmaFlow hỗ trợ người dùng theo chuỗi `DATA → FORECAST → RISK → DECISION → OPERATIONAL OUTCOME`. Hệ thống nguồn nghiệp vụ vẫn chịu trách nhiệm ghi nhận vận hành. Khuyến nghị quan trọng cần người có thẩm quyền xem xét.

## Bối cảnh và hai luồng dữ liệu

Trong một môi trường doanh nghiệp, DSS có thể tiếp nhận dữ liệu từ POS, ERP, WMS, OMS, API và hồ sơ nghiệp vụ. Đồ án chưa có kết nối tới các hệ thống doanh nghiệp đó, nên dùng PostgreSQL và MongoDB trong `src/synthetic_data_source/` làm môi trường nguồn đầu vào giả lập.

Phải phân biệt hai luồng:

1. **Chuẩn bị nguồn thực nghiệm:** dataset, crawler, mapping và generator cung cấp nguyên liệu để chuẩn bị dữ liệu trong PostgreSQL/MongoDB.
2. **Xử lý dữ liệu DSS:** nguồn PostgreSQL/MongoDB cùng các nguồn ngoài đi qua ingestion vào Databricks; các sản phẩm dữ liệu sau đó được ứng dụng DSS sử dụng.

Dataset và crawler không phải là hệ thống nguồn vận hành mà kiến trúc DSS truy vấn trực tiếp. Chúng là công cụ dựng môi trường nghiên cứu.

## Sơ đồ

![Sơ đồ kiến trúc đích PharmaFlow](../../artifacts/diagrams/architecture/pharmaflow-system-overview.png)

Mở [sơ đồ HTML tự chứa](../../artifacts/diagrams/architecture/pharmaflow-system-overview.html) để xem bản tương tác và phần chú giải đầy đủ.

## Các tầng và ranh giới

| Thành phần | Trách nhiệm trong kiến trúc đích | Trạng thái trong repo |
|---|---|---|
| **Nguồn PostgreSQL** | Cung cấp dữ liệu quan hệ như catalog, địa điểm và dữ kiện Sales/POS theo contract nguồn | Có package source và run evidence. Dữ liệu đã chuẩn bị hiện tập trung vào Sales & Demand; kiểm tra package README để biết chính xác từng nguồn/grain. |
| **Nguồn MongoDB** | Cung cấp tài liệu dạng document/bán cấu trúc; contract hiện tại giữ product knowledge snapshot | Có importer, contract và bằng chứng verify. Không có replication hoặc FK xuyên database được khai báo. |
| **Weather API** | Bổ sung dữ liệu thời tiết theo địa điểm và thời gian khi use case cần | Dự kiến; chưa có đường ingestion trong repo. |
| **Tender object storage** | Giữ file hồ sơ gốc và version/metadata liên quan để xử lý, truy xuất | Dự kiến dùng S3; chưa có bucket hoặc pipeline được xác minh. |
| **Ingestion** | Trích xuất có kiểm soát từ database/API/file, kèm metadata và lịch sử run | Đích thiết kế; chưa có pipeline Databricks được xác minh. Không mặc định CDC hoặc streaming. |
| **Databricks Bronze** | Giữ bản nạp gốc cùng metadata nguồn để truy vết và tái xử lý | Chưa triển khai trong repo. |
| **Databricks Silver** | Chuẩn hóa, kiểm tra chất lượng và bảo toàn provenance/ngữ nghĩa nguồn | Chưa triển khai trong repo. |
| **Databricks Gold / data products** | Công bố datamart, KPI và sản phẩm dữ liệu phù hợp module/consumer | Chưa triển khai trong repo. Tên bảng/schema chưa được chốt. |
| **Backend/API DSS** | Xác thực request, cấp quyền, điều phối ứng dụng và phục vụ giao diện bằng hợp đồng dữ liệu đã công bố | Đích thiết kế; chưa có backend theo kiến trúc này. |
| **Database ứng dụng** | Lưu trạng thái ứng dụng như review, quyền, scenario và audit theo thiết kế sau này | Đích thiết kế riêng, khác database nguồn; chưa có schema hay deployment được chốt. |
| **Web frontend** | Hiển thị monitoring, insight, cảnh báo, kịch bản và quy trình human review theo module sẵn sàng | Sản phẩm ưu tiên; chưa có web platform theo kiến trúc đích. Mobile là giai đoạn sau. |

### PostgreSQL và MongoDB

Hai database cùng là nguồn đầu vào trong mô hình đồ án, đồng thời thể hiện tiếp nhận dữ liệu đa dạng. Một phần dữ liệu được đặt trong MongoDB để chia tải lưu trữ và chứng minh khả năng xử lý dạng document/bán cấu trúc. Đây là lý do thiết kế; hiện chưa có benchmark để kết luận hiệu năng tương đối giữa hai công nghệ.

Mô tả đúng dữ liệu đang có: PostgreSQL source chứa các bảng quan hệ và dữ liệu chuẩn bị theo package; MongoDB contract hiện lưu snapshot tri thức sản phẩm Long Châu. Không suy ra MongoDB là bản sao của PostgreSQL hoặc là một ERP/WMS/OMS đầy đủ. Mỗi record cần giữ provenance quan sát, mô phỏng hoặc chưa xác minh.

### Databricks cung cấp dữ liệu cho ứng dụng

Databricks chịu trách nhiệm xử lý và cung cấp dữ liệu phân tích. Bronze, Silver và Gold là các mức tinh chỉnh trong lakehouse, không phải ba hệ thống nghiệp vụ và không đại diện tiến độ triển khai.

Các consumer có thể đọc sản phẩm dữ liệu theo contract phù hợp. Gold thường phục vụ data product đã mô hình hóa theo nghiệp vụ; Silver chi tiết có thể là đầu vào cho feature hoặc trainset. Không ép mọi consumer đọc Gold, cũng không giả định backend web kết nối trực tiếp Bronze/Silver.

Backend/API và database ứng dụng là các thành phần riêng. Database ứng dụng giữ trạng thái tác nghiệp của chính DSS như review, scenario và audit; không ghi khuyến nghị thành PO hoặc transfer thật khi chưa có tích hợp và quyết định riêng.

## Các đường ingestion bổ sung

### Weather API

Theo quyết định Weather Ingestion v1.0 ngày 2026-11-07: locations đọc từ Neon → Open-Meteo Forecast lúc 06:00 Asia/Ho_Chi_Minh với `forecast_days=16`, hoặc Historical Forecast backfill theo yêu cầu → một S3 raw landing cùng metadata → Databricks đọc qua External Volume → Bronze/Silver và sản phẩm phân tích/feature khi có căn cứ. Đây là policy và plan, chưa phải bằng chứng deployment. Xem [kế hoạch triển khai Weather v1](pharmaflow-weather-ingestion-v1-implementation-plan.md).

Giữ location, timezone, thời điểm dự báo và thời điểm thông tin thực sự khả dụng. Historical Forecast stitched series khác các forecast snapshots được thu mỗi sáng; backfill không khôi phục đầy đủ forecast 16 ngày từng biết ở cutoff cũ. Backtest chỉ dùng thông tin có thể biết tại thời điểm dự báo; địa điểm mô phỏng phải giữ nhãn giả định. Hai endpoint và lịch đã chốt trong Weather v1; model cụ thể, variable contract chi tiết, cohort, quota budget và cấu hình AWS còn phải xác minh theo plan.

### Tender object storage

Đường dự kiến: file tender → object storage (S3 được cân nhắc) → trích xuất nội dung và metadata có liên kết về file/version → ingestion → Databricks → sản phẩm dữ liệu cho module Tender.

Object storage giữ bản gốc; dữ liệu phân tích lưu thông tin cần truy vấn và tham chiếu ngược phù hợp. Có file không tự tạo facts về cơ hội thầu, bid, award, cam kết hoặc fulfillment. Các facts và trạng thái này cần contract nghiệp vụ được xác định từ nguồn có căn cứ; tài liệu này không tự đặt ra chúng.

## Phạm vi nghiệp vụ và cách mở rộng

Databricks và ứng dụng hướng tới năm miền Sales; Inventory & Expiry; Procurement & Supply; Distribution & Store Network; Tender & Contract Fulfillment. Business Monitoring, Business Insight, Business Optimization, Human Approval và Operational Outcome là năng lực xuyên miền.

Các pipeline có thể phát triển độc lập hoặc song song. Một miền được tích hợp lên web khi dữ liệu nguồn, sản phẩm dữ liệu và chức năng cần thiết đã sẵn sàng. Không có yêu cầu mỗi miền phải là một microservice, một database hoặc một pipeline riêng.

Hiện dữ liệu đã chuẩn bị tập trung vào Sales & Demand, kèm product knowledge. Dữ liệu cho những miền còn lại sẽ được synthetic sau. Schema source có các bảng nghiệp vụ khác không chứng minh chúng đã được nạp hoặc module tương ứng đã hoạt động. Tham khảo [data-product map](pharmaflow-data-products.md) và [domain/module map](pharmaflow-domain-module-map.md).

## Quyết định đã chốt và chưa chốt

**Đã chốt về hướng kiến trúc:** nguồn nghiệp vụ giả lập được đặt trước luồng DSS; dataset/crawler dùng để dựng nguồn; Databricks cung cấp data products; ứng dụng web có backend/API và database riêng; web trước mobile; phát triển theo mức sẵn sàng của từng miền; giữ human approval và provenance.

**Chưa chốt về chi tiết triển khai:** Databricks cloud/edition và workspace; connector, lịch/tần suất ingestion của các nguồn khác; cách xác thực/network; mô hình triển khai backend/frontend; framework web; vị trí chạy forecast/simulation; schema database ứng dụng; cấu hình/bucket S3; model, variables, cohort và budget Weather sau probe. Open-Meteo cùng hai luồng/lịch Weather v1 đã có quyết định riêng; các đề xuất AWS trong plan chưa được coi là deployment hoặc lựa chọn hạ tầng đã chốt.

## Tài liệu liên quan

- [Landscape](../Landscape/) — phạm vi business domain và KPI.
- [Domain & Module Map](pharmaflow-domain-module-map.md) — ranh giới miền và bằng chứng.
- [Data Products](pharmaflow-data-products.md) — nhu cầu dữ liệu của từng miền.
- [Source data model](../data-model/Relations-DataSource/README.md) — contract và lịch sử schema nguồn.
- [PostgreSQL source package](../../src/synthetic_data_source/pharmaflow_source_postgre/README.md).
- [MongoDB product knowledge package](../../src/synthetic_data_source/mongodb/README.md).

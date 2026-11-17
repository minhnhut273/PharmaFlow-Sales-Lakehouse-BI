# PharmaFlow PostgreSQL Source Model and Data Dictionary

Tài liệu này hợp nhất phạm vi mô hình source, từ điển cột PostgreSQL, ranh giới dữ liệu và contract workflow nhà thuốc. **Current source v2** là database nguồn riêng phục vụ catalog, địa điểm và giao dịch/quan sát bán hàng cho nghiên cứu forecast; phần source v1, downstream DSS và workflow proposal bên dưới được giữ làm lịch sử/ngữ cảnh, không mặc nhiên là trạng thái triển khai hiện nay.

<a id="index"></a>
## Mục lục

- [Current source v2 — schema và deployment](#source-v2-current)
- [Đối chiếu tên file trước khi hợp nhất](#source-file-map)
- [Source v1 (lịch sử): phạm vi, grain và provenance](#source-v1)
- [Data dictionary source: 5 schema, 24 bảng, 212 cột](#source-dictionary)
- [Contract workflow v2 — đề xuất](#proposal-v2)
- [Downstream DSS — DDL local, 50 bảng/452 cột](#downstream-dss)
- [Ngoài PostgreSQL và ranh giới nghiệp vụ](#non-postgres-contracts)
- [ERD PostgreSQL source — physical schema](PharmaFlow_PostgreSQL_ERD.drawio)
- [EERD PostgreSQL source — Chen notation](PharmaFlow_PostgreSQL_EERD.drawio)

<a id="source-v2-current"></a>
## Current source v2 — schema và deployment (2026-11-05)

`src/synthetic_data_source/pharmaflow_source_postgre/schema_full.sql` là bootstrap chuẩn cho PostgreSQL source simulator v2. Đây là một nguồn đầu vào của DSS, không phải kho xử lý Databricks hay database của ứng dụng web. Bốn dataset đã được chuẩn bị cho Sales & Demand; các bảng/domain khác trong schema không đồng nghĩa đã được nạp. Neon deployment, migration và full-source reconciliation có bằng chứng trong [package runbook](../../../src/synthetic_data_source/pharmaflow_source_postgre/README.md) và run artifacts; dùng báo cáo theo run để đọc số dòng hiện hành vì số lượng thay đổi khi chạy lại nạp dữ liệu.

Sơ đồ khái niệm v2 và luồng facts nằm ở [forecast schema overview](../../../src/synthetic_data_source/pharmaflow_source_postgre/forecast_schema_overview.html); [physical schema v2](../../../src/synthetic_data_source/pharmaflow_source_postgre/forecast_source_schema_v2.html) thể hiện các bảng nguồn trọng tâm, SQL type và key constraints. Runbook, source mapping, manifest, migration và báo cáo nằm tại [package PostgreSQL source](../../../src/synthetic_data_source/pharmaflow_source_postgre/README.md). Phần EERD/dictionary source 24 bảng bên dưới là tài liệu v1 được giữ để truy vết, không phải bảng kê đầy đủ DDL v2. Kiến trúc đích tiếp tục từ hai source store sang Databricks, rồi công bố data products cho từng module; xem [System Architecture](../../architecture/pharmaflow-system-architecture.md) và [Data Products](../../architecture/pharmaflow-data-products.md).

### Phần source v2 được thay đổi

| Nhóm | Contract hiện tại và lý do |
| --- | --- |
| `catalog.product` | Product master gọn gồm mã nguồn, tên, `brand_name`, `manufacturer_id`, `base_uom_code`, trạng thái và một `source`. Không đưa logo hay các thuộc tính mô tả/dược học vào lõi catalog tối giản. Manufacturer không được suy ra từ brand. |
| `catalog.product_category`, `catalog.product_category_assignment` | Giữ cây cha–con và phép gán nhiều-nhiều; taxonomy được định danh riêng (`LONGCHAU_PUBLIC`, `PHARMAFLOW_BUSINESS`, `ATC`, `IRPD_CATEGORY`, `IRPD_DRUG_CLASS`, `ONYX_CATEGORY`) để không nhập nhằng danh mục thương mại với nhóm dữ liệu nguồn/ATC. |
| `catalog.product_source_reference` | Mapping compact giữa `source` + mã ngoài và product canonical; capture thô/giá/ảnh/url/attributes vẫn nằm trong dataset evidence, không phình bảng lõi. Mã sản phẩm nguồn không tự động đồng nghĩa cùng một thuốc giữa hai nguồn. |
| `catalog.product_packaging` | Giữ nhãn hộp/vỉ/viên hay dạng đóng gói từ nguồn; `package_uom_code` và `quantity_in_base_uom` chỉ dùng khi có căn cứ quy đổi. Dòng POS có FK ghép để packaging bắt buộc thuộc đúng product. |
| `org.store` | Dùng chung cho location quan sát và location mô phỏng; có quốc gia, tọa độ, IANA timezone và `source`. `source`/manifest phân biệt location công khai với điểm mô phỏng; tọa độ Onyx bị nhiễu hoặc tọa độ mô phỏng không được trình bày như tọa độ quan sát. |
| `org.warehouse` | Tạo 122 location warehouse giả lập cho các store xuất hiện trong dữ liệu giao dịch; `data_origin='SYNTHETIC'`. Chỉ là điểm tham chiếu mô phỏng, không chứng minh có tồn kho/receipt và không tự gán thành fulfillment của đơn. |
| `pos.sales_order`, `pos.sales_order_line` | Grain giao dịch hóa đơn/dòng thuốc; kênh bán và điểm fulfill nullable khi nguồn không xác nhận; lưu tiền tệ và amount nullable theo nguồn. `source` phân biệt hóa đơn IRPD với đơn synthetic sinh từ Onyx/Pharma Sales. |
| `pos.sales_observation` | Grain nguồn aggregate (ví dụ ngày × pharmacy × product hoặc ngày × ATC group) được giữ riêng; một observation gắn đúng một product **hoặc** một category. Không ép đại lượng aggregate thành SKU hay hóa đơn được quan sát. |

Các bảng procurement, inventory, transfer, request, return, recall, quality-control và phần proposal được giữ nguyên trong bootstrap; chúng không được nạp hay suy ra từ bốn bộ dữ liệu bán hàng. Warehouse synthetic không tạo movement, balance, receipt hay fulfillment. Việc này chỉ hoàn thiện nguồn cho forecast/KPI/monitoring về sau, không triển khai forecast, tối ưu tồn hay logistics.

### Nguồn và ranh giới dữ liệu v2

| Nguồn | Dữ liệu được giữ | Phần mô phỏng và giới hạn |
| --- | --- | --- |
| Long Châu | Catalog, taxonomy công khai và location public | Không có sales/dispensing/stock. Location public chưa được xem là tọa độ độc lập kiểm chứng. |
| IRPD Indonesia | Hóa đơn, dòng thuốc, ngày giờ local, quantity/unit và line total nguồn | Một pharmacy giả lập ở Central Java với điểm tọa độ deterministic; không nạp stock files hoặc tự quy đổi đơn vị. |
| Onyx Pharmacy Sales | Daily fact theo pharmacy × product; giữ quantity, EUR revenue/cost/margin ở observation | Sinh POS synthetic lúc 12:00 địa phương để có transaction-shaped data; provenance thực/giả và tọa độ nhiễu chưa xác minh. |
| Pharma Sales Data | Daily aggregate theo tám nhóm ATC; UOM gốc để null | Location Niš và SKU candidate/đơn synthetic chỉ là giả lập theo scale 10; nhóm chưa map đủ căn cứ ở lại category observation. |

Mẫu nghiệm thu bị giới hạn: Long Châu 50 SKU/20 store; IRPD hóa đơn đủ của 7 ngày đầu; Onyx tối đa 5 pharmacy × 14 ngày dữ liệu mỗi pharmacy; Pharma Sales 28 ngày. Bản full v2 được nạp sau khi kiểm tra sample tách biệt. Không điền các ngày không có bản ghi thành zero; không cộng observation với đơn synthetic tương ứng thành hai luồng sales quan sát.

Evidence khác nhau theo lớp: SQL ở package là local schema source of truth; Neon v2 là database đã triển khai và nạp full theo kết quả kiểm tra. Trạng thái Neon hiện chỉ còn một branch `production` và một database v2; nhánh test là lịch sử đã xóa sau acceptance, không còn là môi trường hiện hành. Snapshot mới từng bị Neon từ chối vì giới hạn quota; snapshot sẵn có và logical `pg_dump` của DB cũ được giữ nguyên. Sau lần nghiệm thu ban đầu, DB cũ và `neondb` đã xóa; Neon Auth đã tắt theo yêu cầu giữ một môi trường.

<a id="source-file-map"></a>
## Đối chiếu tên file trước khi hợp nhất

Bảng này giữ locator dễ tra cứu cho các tài liệu audit hoặc ghi chú cũ vẫn lưu tên file ban đầu. Nội dung chuẩn hiện nằm trong README này.

| File cũ | Nội dung tương ứng trong README |
| --- | --- |
| `pharmaflow_source_schema_v1.md` | [Hướng dẫn source v1](#source-v1), [dictionary source](#source-dictionary) và [ranh giới ngoài PostgreSQL](#non-postgres-contracts). |
| `postgresql_data_dictionary.md` | [Dictionary source](#source-dictionary) và [phụ lục downstream DSS](#downstream-dss). |
| `pharmaflow_retail_workflow_contract_v2.md` | [Contract workflow v2 — đề xuất](#proposal-v2). |
| `src/synthetic_data_source/pharmaflow_source_postgre/schema_v1.sql` (locator trong audit cũ) | [Baseline DDL đã lưu trong archive](../../../archive/2026-11-03-source-sql-history/schema_v1.sql). `schema_full.sql` là bootstrap riêng có migration proposal 03, không phải snapshot production. |

<a id="source-v1"></a>
## Source v1 (lịch sử trước v2): phạm vi, grain và provenance

### Chốt phạm vi

Ở thời điểm source v1, `pharmaflow_source_postgre` trên Neon PostgreSQL được mô tả là mô hình nguồn vận hành **giả lập** cho chuỗi nhà thuốc bán lẻ, lấy Long Châu làm ví dụ nghiệp vụ. Thiết kế 24 bảng gồm catalog, location, bán hàng, mua hàng/nhận hàng và tồn kho theo lô; đây là contract/schema lịch sử, không phải inventory dữ liệu v2 hiện tại. Các ghi chú MongoDB/S3 bên dưới cũng là bối cảnh thiết kế v1; vai trò hiện tại được cập nhật ở [Current source v2](#source-v2-current) và [Ngoài PostgreSQL](#non-postgres-contracts). Đây không phải bản sao ERP/WMS nội bộ Long Châu hay hệ thống thay thế DSS.

Mô hình có 5 schema nghiệp vụ và 24 bảng. Danh mục sản phẩm có thể biểu diễn các nhóm hàng Long Châu như thuốc, thực phẩm chức năng, thiết bị y tế và nhóm khác. Dữ liệu hiện có chỉ hỗ trợ một snapshot công khai giới hạn; khả năng biểu diễn toàn bộ danh mục không đồng nghĩa đã thu thập hoặc xác minh toàn bộ sản phẩm/cửa hàng.

### Trạng thái PostgreSQL

Base DDL được áp dụng ngày 2026-09-30 lên database source của Neon project `round-brook-76208048`, branch `production`. Artifact cleanup sau đó ghi tên database là `pharmaflow_source`; tại lần kiểm tra migration 03/11, Neon liệt kê database hiện tại là `pharmaflow_source_postgre`. Migration [20261103_04](../../../archive/2026-11-03-source-sql-history/migrations/20261103_04_pos_demand_fulfillment_locations.sql) đã được thử trên nhánh tạm và áp dụng lên database hiện tại này, tách vị trí phát sinh demand và kho fulfill trong `pos.sales_order`. Schema hiện có 5 schema (`catalog`, `org`, `pos`, `procurement`, `inventory`), 24 bảng và 212 cột; kiểm tra đủ 24 bảng xác nhận 0 dòng. Database `neondb` và các bảng `neon_auth` không nằm trong migration. Trong `.env`, các biến `DATABASE_URL*` vẫn trỏ tới `neondb`; muốn kết nối ứng dụng tới source database cần dùng connection URL có database name là `pharmaflow_source_postgre`.

Audit và snapshot sau migration 04 ghi 24 bảng/212 cột cho source v1. Một bằng chứng cleanup riêng ghi database_name=pharmaflow_source và 24 bảng/211 cột; chưa có căn cứ để đồng nhất record này với pharmaflow_source_postgre, nên giữ đúng phạm vi từng artifact và không lấy số 211 làm metadata của ERD source v1. Xem [snapshot 212 cột sau migration 04](../../../artifacts/data-model/reviews/2026-11-03/dictionary-recheck/live-source-columns-post-pos-migration.json), [audit dictionary](../../../artifacts/data-model/reviews/2026-11-03/dictionary-recheck/dictionary-audit-pos-migration.json) và [bằng chứng cleanup database pharmaflow_source](../../../artifacts/data-model/reviews/2026-11-03/dictionary-recheck/source-cleanup-result.json).

Migration `20260930_02_lot_expiry_contract.sql` đã được kiểm tra trong transaction rollback, **chưa áp dụng thường trực** lên Neon.

`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql` là prototype downstream DSS local (`meta`, `core`, `stg`, `model`, `sim`, `mart`), không phải database đang được chọn làm serving platform. Baseline source v1 nằm tại `archive/2026-11-03-source-sql-history/schema_v1.sql`. Ghi chú pipeline/raw/curated trong phần lịch sử không phải kiến trúc hiện hành: dataset/crawler chuẩn bị PostgreSQL/MongoDB source stores; luồng DSS mục tiêu ingest các source stores vào Databricks theo [kiến trúc hệ thống](../../architecture/pharmaflow-system-architecture.md).

### POS: demand location và fulfillment warehouse

`pos.sales_order.demand_location_id` là FK bắt buộc tới `org.store.store_id`, dùng để ghi cửa hàng/địa bàn phục vụ nơi demand được ghi nhận. `fulfillment_location_id` là FK nullable tới `org.warehouse.warehouse_id`, dùng cho kho vật lý đã fulfill đơn; nếu là kho tại cửa hàng thì `org.warehouse.store_id` nối kho về cửa hàng. Ví dụ khách ở Q7 được giữ ở demand store Q7 trong khi đơn được xuất từ warehouse tại Q4. Schema lưu vị trí fulfill đã được chọn, không thực hiện định tuyến và không khẳng định hệ thống luôn chọn cửa hàng gần nhất/còn hàng. Mỗi đơn hỗ trợ một fulfillment warehouse ở header; chia đơn giữa nhiều kho cần allocation riêng theo line.

Migration đã thử trên nhánh Neon tạm trước khi áp dụng production. Bằng chứng trạng thái và kiểm tra production được lưu tại [kết quả triển khai](../../../artifacts/data-model/reviews/2026-11-03/pos-demand-fulfillment-deployment/result.json).

### Contract v2 proposal (2026-10-24)

Tại thời điểm tài liệu proposal được viết ngày 2026-10-24, source v1 là baseline và migration `20261024_03` chưa áp dụng. Đây là mốc lịch sử của proposal, không mô tả database source v2 hiện nay; xem [Current source v2](#source-v2-current).

### Bằng chứng và giới hạn dữ liệu

- Báo cáo `ATTRIBUTE_CATALOG.md` cũ mô tả một pilot 30 trang; knowledgebase hiện đã có thêm các product-note từ các lần chạy sau. Có 47 file Markdown dưới các thư mục `products`, nhưng đây không đồng nghĩa với 47 SKU duy nhất (một số ghi chú có thể xuất hiện trong nhiều đường danh mục). Trường được ghi nhận thay đổi theo loại hàng và snapshot: tên/SKU, brand, producer/manufacturer, đăng ký, thành phần, dạng dùng, đối tượng, quy cách, giá/khuyến mãi, tình trạng niêm yết, ảnh và bằng chứng crawl. Dữ liệu trang công khai không phải hồ sơ nội bộ, tồn kho chi nhánh hay giao dịch.
- `pharma-sales-data` có 2.106 dòng ngày và 8 chuỗi nhóm ATC, nhưng không có mã thuốc/SKU, cửa hàng, kênh bán; đơn vị của đại lượng bán không được xác định. Mô tả nguồn nói đến 57 thuốc nhưng các tệp đã tải là aggregate theo nhóm ATC.
- Do đó không có căn cứ để gán trực tiếp số lượng gốc của một nhóm ATC thành doanh số SKU Long Châu. Các bảng POS trong source simulator là dữ liệu tổng hợp/synthetic; chúng chỉ có thể dùng Pharma Sales để neo hình dạng thời gian hoặc phân bổ có trọng số đã khai báo, không được gọi là doanh số Long Châu quan sát được.
- Dataset Pharma Sales có điều kiện phi thương mại CC BY-NC 4.0 theo `dataset/README.md`; cần giữ ghi công và điều kiện giấy phép khi tái sử dụng.
- Không có dữ liệu công khai đã rà soát về supplier, PO, receipt, batch/expiry, on-hand, transfer hay store-level POS của Long Châu. Các facts đó phải mang `SYNTHETIC` trừ khi sau này có nguồn được xác minh.

### Bộ schema và 24 bảng

| Schema | Số bảng | Bảng | Grain/chức năng chính |
| --- | ---: | --- | --- |
| `catalog` | 7 | `product`, `product_category`, `product_category_assignment`, `product_source_reference`, `product_packaging`, `manufacturer`, `unit_of_measure` | Một sản phẩm; một nút trong một taxonomy; một gán sản phẩm–taxonomy; một quan sát/mapping sản phẩm nguồn; một quy cách; một nhà sản xuất; một đơn vị đo. |
| `org` | 2 | `store`, `warehouse` | Một cửa hàng; một điểm giữ hàng. Kho cửa hàng liên kết về store, kho trung tâm có thể không gắn store. |
| `pos` | 3 | `sales_channel`, `sales_order`, `sales_order_line` | Một kênh; một đơn bán (có `customer_ref` logic nullable); một dòng sản phẩm của đơn. Không lưu profile khách trong PostgreSQL. |
| `procurement` | 5 | `supplier`, `purchase_order`, `purchase_order_line`, `goods_receipt`, `goods_receipt_line` | Một nhà cung cấp; một PO; một dòng PO; một lần nhận; một dòng nhận gắn với dòng PO và lô. Dòng nhận tách lượng chấp nhận và từ chối; chỉ lượng chấp nhận tăng tồn. Nhà sản xuất và nhà cung cấp là hai khái niệm riêng. |
| `inventory` | 7 | `batch_lot`, `inventory_balance`, `inventory_movement`, `stock_transfer`, `stock_transfer_line`, `stock_take`, `stock_take_line` | Một lô của sản phẩm; một số dư kho × lô; một biến động có dấu; một phiếu chuyển; một dòng chuyển; một đợt kiểm kê; một dòng kiểm kê theo lô. |
| **Tổng** | **24** |  |  |

#### Quy ước taxonomy và khớp sản phẩm

`catalog.product_category.taxonomy_scheme` giữ riêng ba phân loại: `LONGCHAU_PUBLIC` (danh mục quan sát từ website), `PHARMAFLOW_BUSINESS` (taxonomy nghiệp vụ dự án), và `ATC` (nhóm của Pharma Sales). Không gộp tên nhóm khác nguồn thành một taxonomy duy nhất. Sản phẩm có thể có nhiều category assignments; assignment lưu trạng thái và căn cứ. Nhóm ATC chỉ gắn vào sản phẩm khi có căn cứ nhận dạng đủ mạnh; tên na ná hoặc cùng công dụng không tự động được xem là match.

`catalog.product` là master sản phẩm duy nhất dùng làm đích FK cho POS, mua hàng và tồn kho. Grain là một mặt hàng/SKU có thể bán; các quy cách khác SKU hoặc khác dung lượng được giữ thành sản phẩm riêng khi nguồn định danh riêng. `product_code` là mã nội bộ; mã Long Châu hoặc mã ngoài khác nằm trong `external_product_key` theo namespace nguồn.

`product_source_reference` có grain **một mã sản phẩm nguồn × một thời điểm quan sát**. Bảng giữ tên/đường taxonomy, URL nguồn và URL canonical, giá niêm yết/giá cuối, tiền tệ, trạng thái niêm yết và `observed_attributes` dạng JSONB. `product_id` được để rỗng khi chưa đủ căn cứ match; `match_status` tách biệt với việc trang có dữ liệu hay không. Giá và availability mô tả snapshot trang công khai, không phải giá POS, tồn kho chi nhánh hay giá mua nhà cung cấp.

Các thuộc tính chung, ổn định và cần join/filter thường xuyên dùng cột có kiểu rõ ràng trên `catalog.product` (ví dụ `brand_name`, `dosage_form`, `strength_text`, nhà sản xuất, dạng hàng, số đăng ký, đơn vị cơ sở). `dosage_form` chỉ được điền khi nguồn xác nhận và để rỗng khi thiếu. Các trường thưa hoặc khác nhau theo nhóm hàng được giữ trong `observed_attributes` trên từng snapshot: thuốc có thành phần nhiều chất và cảnh báo; thực phẩm bổ sung có thành phần dinh dưỡng, đối tượng sử dụng và hướng dẫn dùng; thiết bị y tế có công dụng, lứa tuổi, xuất xứ hoặc bảo hành. Các facet như đối tượng sử dụng có thể có nhiều giá trị và taxonomy riêng theo ngành hàng; giữ raw value + source evidence trước, chuẩn hóa key/value khi ingest. Nếu một facet được xác nhận ổn định và thường xuyên lọc trong phân tích, có thể promote thành typed field/bridge ở lớp CORE mà không phải nhồi mọi thuộc tính vào bảng nguồn. Ảnh, nội dung dài, claim, chương trình khuyến mãi và các trường nguồn biến động cũng nằm ở observation hoặc file snapshot, không nhồi thành cột `product` chung.

Các đoạn thiết kế source v1 từng cân nhắc giữ hồ sơ sản phẩm trong PostgreSQL và landing file ở object storage. Trong kiến trúc hiện tại, MongoDB là nguồn document riêng cho snapshot tri thức sản phẩm; product master quan hệ vẫn ở PostgreSQL. HTML gốc vẫn nằm trong knowledgebase local theo package hiện hành; S3 cho tender là hướng tương lai. `observed_attributes` JSONB ở phần dictionary v1 là thiết kế lịch sử, không phải cột có sẵn trong DDL hoặc Neon v2 hiện tại.

#### Trạng thái MongoDB và tham chiếu lịch sử

Contract MongoDB hiện hành là `pharmaflow_product_knowledge.product_snapshots`, do package riêng chuẩn bị/nạp/verify; xem [MongoDB package README](../../../src/synthetic_data_source/mongodb/README.md). Các migration và dictionary v1 có nhắc customer là bằng chứng lịch sử, không phải collection contract hiện tại. MongoDB không sao chép dữ liệu PostgreSQL và không có khóa ngoại xuyên database.

Rà soát payload thành phần/bảo quản và các lựa chọn landing: [báo cáo 2026-11-05](../../../artifacts/data-model/reviews/2026-11-05/longchau-product-attributes/README.md), kèm bảng kết quả cho từng hồ sơ. Đây là đánh giá thiết kế; chưa triển khai nơi lưu mới.

Mô hình source v1 này được lưu trong [archive](../../../archive/2026-11-03-source-sql-history/schema_v1.sql). File [schema_full.sql](../../../src/synthetic_data_source/pharmaflow_source_postgre/schema_full.sql) và runbook liên quan mô tả source v2 hiện hành ở phần đầu tài liệu. Các migration source v1 được lưu trong [archive](../../../archive/2026-11-03-source-sql-history/CLEANUP_LOG.md) để truy vết, không tự áp dụng lên database hiện có.

#### S3 file source và raw landing

S3 tách `source/config/` và `source/datasets/` khỏi `raw/external/`, `raw/api/` và `raw/streaming/` dự kiến. API như Weather/openFDA/FX vẫn là nguồn; S3 chỉ lưu phản hồi nguyên bản cùng manifest provenance. Dataset giữ checksum, version, license, URL, grain và semantics đo lường. File config không chứa secret. Bucket `pharmaflow-data-lab` và prefix là proposal, chưa phải hạ tầng đã triển khai; bộ hiện hành không có JSON Schema riêng cho manifest; prefix và sidecar được mô tả ở mức proposal. Chi tiết collection và key convention: [MongoDB/S3 source design](#non-postgres-contracts).

Các thuộc tính dạng bào chế, hoạt chất, hàm lượng, tình trạng kê đơn, số đăng ký, GTIN, brand, nhà sản xuất và quy đổi bao gói để nullable vì coverage không đồng đều. `active_ingredient_text` là bản tóm tắt đã rà soát, có thể chứa nhiều hoạt chất; không phải quan hệ ingredient chuẩn hóa. Thành phần nguyên bản từ mỗi nguồn được bảo toàn trong JSONB. Không suy diễn từ tên hàng. Các loại sản phẩm phi thuốc vẫn được lưu bằng `product_kind`; không bắt buộc có ATC, hoạt chất hoặc trạng thái kê đơn.

#### Vì sao các diagram không lặp `product` và `NO ACTION`

Mọi quan hệ bán hàng, mua hàng và tồn kho trỏ về cùng một `catalog.product`. Các ER nghiệp vụ chỉ vẽ entity sản phẩm một lần trong cụm catalog; ở cụm khác, `product_id` được ghi là FK về bảng này, không vẽ thêm một entity Product khác.

Các FK trong DDL không khai báo `ON DELETE`, nên PostgreSQL dùng mặc định `NO ACTION`: không cho xóa dòng cha nếu còn dòng con tham chiếu; không xóa dây chuyền. Đây giúp giữ lịch sử bán/nhập/tồn và tham chiếu sản phẩm. Diagram ghi quy tắc này một lần ở chú giải, không dán lặp trên từng connector. Chi tiết constraint vẫn nằm trong DDL.

### Provenance: biết mỗi dòng là loại dữ liệu gì

Các bảng mang facts/reference có cột `data_origin` với miền giá trị thống nhất:

- `OBSERVED_PUBLIC`: quan sát trực tiếp từ trang công khai (kèm thời điểm/URL hoặc `source_ref`).
- `OBSERVED_DATASET`: record được đọc từ một dataset có sẵn.
- `DERIVED`: kết quả làm sạch/chuẩn hóa/tổng hợp có thể truy về nguồn.
- `SYNTHETIC`: tạo bởi simulator hoặc scenario.

Với POS line phát sinh từ Pharma Sales, lưu thêm `source_dataset_code`, `source_record_key`, `derivation_method`, `derivation_config_ref` và `provenance_ref`. `source_record_key` phải xác định record ATC/ngày gốc; config phải có version, tập sản phẩm đủ điều kiện, trọng số, cách chuẩn hóa pattern và scale synthetic. Các trường lineage này cũng có thể để trống với kịch bản synthetic không dựa trên dataset. Không đổi `data_origin` thành `OBSERVED_DATASET` chỉ vì đầu vào của simulator là dữ liệu quan sát: dòng SKU/store được tạo ra vẫn là `SYNTHETIC`.

### Cách đưa Pharma Sales vào bài toán Long Châu

1. Giữ các dòng nguồn Pharma Sales trong raw/observation riêng ở grain **ngày × ATC group**. Giữ nguyên giá trị, lịch sử xử lý, đơn vị `UNSPECIFIED` nếu chưa xác minh, checksum và giấy phép. Không đưa dòng tổng hợp này vào `pos.sales_order_line` như một SKU thật.
2. Nạp snapshot Long Châu vào danh mục với `OBSERVED_PUBLIC`, giữ ngày quan sát và đường danh mục; bổ sung `product_kind`/thuộc tính chỉ khi trang hoặc nguồn có bằng chứng. Bao phủ được các nhánh danh mục nhưng snapshot hiện tại mới là một phần nhỏ.
3. Tạo mapping có kiểm soát từ một ATC group sang tập sản phẩm Long Châu đủ điều kiện dựa trên hoạt chất/định danh đã kiểm chứng. Ghi candidate hoặc unmatched nếu chưa đủ bằng chứng; không ép mọi sản phẩm vào một nhóm.
4. Nếu cần SKU-level sales để chạy demo, sinh các dòng POS **synthetic** theo pattern thời gian đã chuẩn hóa và trọng số trong config version. Không dùng trực tiếp magnitude của Pharma Sales làm số lượng SKU vì nguồn không có SKU và thiếu đơn vị đo. Scale và UOM của dữ liệu giả lập phải tự khai báo.
5. So sánh dự báo trên series quan sát ở đúng grain với baseline phù hợp. Đánh giá tồn kho/quyết định trên simulator riêng; không diễn giải kết quả mô phỏng như hiệu quả vận hành Long Châu.

Như vậy Pharma Sales có thể giúp neo pattern/seasonality và xây một tập scenario sản phẩm có căn cứ, nhưng không chứng minh doanh số thật của một sản phẩm Long Châu. Sản phẩm chưa khớp vẫn có trong catalog nhưng không tham gia phân bổ sales theo ATC.

### Grain và quan hệ tồn kho/chuyển kho, giữ gọn

- `inventory.batch_lot`: grain sản phẩm × mã lô; expiry là thuộc tính của lô, không phải của sản phẩm.
- `inventory.inventory_balance`: grain kho × lô, giữ on-hand và reserved; available được suy ra = on-hand − reserved. Đây là số dư/projection; `inventory.inventory_movement` là ledger biến động có dấu.
- `inventory.inventory_movement`: một lần tăng/giảm số lượng tại một kho cho một lô, theo đơn vị cơ sở của sản phẩm. Sale/receipt/transfer/count adjustment tham chiếu line nguồn tương ứng. Event đã post được sửa bằng reversal/điều chỉnh thay vì ghi đè lịch sử.
- `available_quantity` trong `inventory.inventory_balance` chỉ là **on-hand trừ reserved**, chưa trừ lô hết hạn, lô không rõ hạn hoặc các điều kiện được phép bán khác. Không dùng riêng cột này làm lượng có thể bán hay lượng phục vụ trong mô phỏng quyết định. Lô có hạn `NULL` được giữ là `UNKNOWN_EXPIRY`, không tự suy ra còn hạn.
- `inventory.lot_expiry_status(expiry_date, evaluation_date, warning_days)` phân loại `EXPIRED`, `EXPIRING_TODAY`, `NEAR_EXPIRY`, `IN_DATE` hoặc `UNKNOWN_EXPIRY` tại một ngày đánh giá cụ thể. Ngưỡng cận hạn do caller truyền vào theo kịch bản/loại sản phẩm, không cố định trong schema. Quy ước mô hình: ngày hết hạn đứng trước ngày đánh giá là `EXPIRED`; đúng ngày đánh giá được tách riêng để người phụ trách áp chính sách. FEFO chỉ chọn trong các lô đủ điều kiện sau bước kiểm tra này; không tự động bán hay hủy hàng.
- `EXPIRY_WRITE_OFF` là biến động giảm tồn có dấu âm, khác với việc một lô vừa bước sang trạng thái hết hạn. Xác định lô hết hạn không tự tạo giao dịch hủy; thao tác ghi giảm phải có quy trình và bằng chứng riêng.

Ví dụ truy vấn lô để đánh giá trong kịch bản có cửa sổ cảnh báo 30 ngày (không phải chính sách mặc định):

```sql
SELECT b.warehouse_id, b.batch_lot_id, l.product_id, l.expiry_date,
       b.as_of AS balance_as_of, b.on_hand_quantity, b.reserved_quantity,
       b.available_quantity AS unreserved_quantity,
       inventory.lot_expiry_status(l.expiry_date, DATE '2026-09-30', 30) AS expiry_status
FROM inventory.inventory_balance AS b
JOIN inventory.batch_lot AS l USING (batch_lot_id);
```

Baseline và migration hạn dùng 02 được giữ trong `archive/2026-11-03-source-sql-history/` để đối chiếu lịch sử. File gộp `src/synthetic_data_source/pharmaflow_source_postgre/schema_full.sql` dành cho database mới, rỗng và bao gồm proposal chưa triển khai. Quy tắc đủ điều kiện cấp phát và ngưỡng cận hạn vẫn cần được chốt theo nghiệp vụ.
- `procurement.goods_receipt_line.accepted_quantity` và `rejected_quantity` tách lượng nhận đạt và không đạt; `received_quantity` là tổng suy ra. Chỉ accepted quantity được đưa vào inventory movement.
- `stock_transfer` có kho đi và kho đến; mỗi `stock_transfer_line` có sản phẩm, số lượng yêu cầu/đã gửi/đã nhận và lô khi đã xác định. Nếu chia nhiều lô thì tạo nhiều dòng. Khi gửi/nhận ghi movement âm ở kho đi và movement dương ở kho đến. Không tạo route, shipment leg hoặc trạng thái vận tải riêng trong v1.
- `stock_take`/`stock_take_line` chỉ giữ snapshot số hệ thống và số đếm để sinh chênh lệch kiểm kê; đây là phần có thể triển khai sau transfer.
- Quy đổi bao gói chỉ dùng khi có `quantity_in_base_uom` được xác minh. Nếu chưa có conversion, lưu thông tin quan sát nhưng không phát sinh movement có vẻ chính xác giả tạo. Kiểm tra cùng sản phẩm giữa order line, lô và warehouse thực hiện ở ingest/service vì không thể diễn đạt đầy đủ bằng CHECK đơn bảng.

### Phân kỳ triển khai

- **Giai đoạn 1 — 20 bảng:** catalog, org, pos, procurement, cùng `batch_lot`, `inventory_balance`, `inventory_movement`. Dựng data simulator, lineage và ledger tối giản.
- **Giai đoạn 2 — thêm 2 bảng (22):** `stock_transfer`, `stock_transfer_line` để minh họa điều chuyển giữa kho trung tâm và cửa hàng.
- **Giai đoạn 3 — thêm 2 bảng (24):** `stock_take`, `stock_take_line` khi cần mô phỏng kiểm kê/chênh lệch.

Tổng thiết kế source v1 là 24 bảng; phân kỳ giúp không phải xây cả 24 luồng trước khi có use case. Phần này là thiết kế lịch sử; vai trò MongoDB hiện tại và kiến trúc downstream được cập nhật trong [mục ngoài PostgreSQL](#non-postgres-contracts) và [kiến trúc hệ thống](../../architecture/pharmaflow-system-architecture.md). Không đưa tender/contract, route vận tải, supplier performance, forecast, KPI hay recommendation vào source simulator này. Các nội dung DSS nằm downstream theo chuỗi `DATA → FORECAST → RISK → DECISION → OPERATIONAL OUTCOME`, với khuyến nghị nghiệp vụ có human review.

### Tài liệu liên quan

- [PostgreSQL source simulator base DDL](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)
- [Migration thêm customer_ref cho database hiện có](../../../archive/2026-11-03-source-sql-history/migrations/20260930_01_customer_ref_mongodb_link.sql)
- [PostgreSQL downstream DSS DDL](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)
- [MongoDB Atlas và S3 source contract](#non-postgres-contracts)
- [S3 object metadata JSON Schema](#non-postgres-contracts)
- [Data inventory và nguồn](../../../dataset/README.md)
- [Long Châu public source coverage](../../../dataset/longchau-knowledge/_meta/derived/SOURCE_COVERAGE.md)


## PostgreSQL column dictionary

> Từ điển này giải thích cấu trúc **database model → schema → table → column**, kiểu PostgreSQL và ý nghĩa từng trường. DDL là nguồn chuẩn cho cấu trúc SQL; ý nghĩa nghiệp vụ phải đối chiếu thêm nguồn nghiệp vụ và provenance. Một field/FK tồn tại không chứng minh workflow đã chạy hoặc dữ liệu đủ điều kiện sử dụng.

> Hai diagram draw.io cùng mô tả source v1 sau migration 04 ở hai mức: [EERD Chen](PharmaFlow_PostgreSQL_EERD.drawio) dùng entity/attribute/relationship và cardinality; [ERD physical schema](PharmaFlow_PostgreSQL_ERD.drawio) giữ SQL type cùng chi tiết cột. EERD bỏ SQL type có chủ đích; `product_kind` được giữ như thuộc tính vì DDL không khai báo subtype riêng. Trang 08 là EERD tổng hợp đầy đủ 24 entity, 212 thuộc tính và 41 quan hệ cho toàn bộ source schema; các trang 01–07 giữ cách chia theo miền để tiện theo dõi.

<a id="source-dictionary"></a>
### Phạm vi và trạng thái

PharmaFlow có hai mô hình PostgreSQL riêng, không phải hai schema trong cùng một database:

| Database/model | DDL | Schema | Vai trò và trạng thái |
|---|---|---|---|
| `pharmaflow_source_postgre` | [`schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql) | `catalog`, `org`, `pos`, `procurement`, `inventory` | Source simulator trên Neon branch `production`; migration POS demand/fulfillment 04 đã áp dụng ngày 2026-11-03. POS/mua/tồn mô phỏng không phải giao dịch Long Châu quan sát. |
| Downstream DSS (tên database chưa cố định trong DDL) | [`schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql) | `meta`, `core`, `stg`, `model`, `sim`, `mart` | DDL đích local cho observations, forecast, simulation và KPI; tài liệu dự án chưa xác nhận đã deploy. |

Phạm vi các bảng/cột dưới đây là **source: 24 bảng/212 cột** sau migration 04 và **downstream DDL: 50 bảng/452 cột**, tổng cộng 74 bảng/664 cột. Các cột được thêm qua `ALTER TABLE` được tính; proposal 03 chưa áp dụng không được tính là schema live. Xem [trạng thái source](#source-v1) và [workflow contract v2](#proposal-v2).

### Trạng thái dữ liệu Neon — 03/11/2026

Bằng chứng cleanup ngày 03/11 ghi database là `pharmaflow_source` và xác nhận 24 bảng/211 cột/0 dòng. Tại lần triển khai migration này, Neon liệt kê database source hiện tại là `pharmaflow_source_postgre`; đã kiểm tra trực tiếp đủ 24 bảng đều rỗng trước khi áp dụng. Migration [20261103_04](../../../archive/2026-11-03-source-sql-history/migrations/20261103_04_pos_demand_fulfillment_locations.sql) sau đó được áp dụng và xác minh: hiện có **24 bảng, 212 cột, 0 dòng**. Migration chỉ tách vị trí nhu cầu và kho fulfill trong `pos.sales_order`; không nạp hoặc gán lại dữ liệu đơn hàng. Tên database ghi trong cleanup artifact được giữ nguyên làm lịch sử; tài liệu này dùng tên hiện tại đã đọc từ Neon cho trạng thái sau migration.

> Cleanup artifact ghi nhận nhánh phục hồi `backup-source-before-clean-20261103` từng ở trạng thái ready với 43.099 dòng. Tuy nhiên, trong lần kiểm tra deployment hiện tại, Neon chỉ liệt kê branch `production` và lookup ID recovery branch trả `branch not found`; vì vậy không thể xác nhận bản backup còn truy cập được. Database `neondb` và schema `neon_auth` nằm ngoài migration. Xem [bằng chứng cleanup lúc tạo](../../../artifacts/data-model/reviews/2026-11-03/dictionary-recheck/source-cleanup-result.json) và [kết quả lookup hiện tại](../../../artifacts/data-model/reviews/2026-11-03/pos-demand-fulfillment-deployment/result.json).

#### Mốc kiểm tra lại 03/11/2026

Lần đối chiếu trước migration 04 so cột/type/nullability của source local với Neon project `round-brook-76208048`, branch `production` (`br-icy-lake-b3gg39qb`), database `pharmaflow_source_postgre`: 24 bảng/211 cột khớp ở các thuộc tính đã kiểm tra. Sau đó migration 04 được áp dụng và đọc lại production: `store_id` đã được thay bằng `demand_location_id`, `fulfillment_location_id` nullable được thêm, hai FK/index tương ứng có mặt, và source có 212 cột. Điều này **không có nghĩa mọi function/CHECK/migration local đã triển khai**: hàm `inventory.lot_expiry_status(date,date,integer)` và CHECK write-off âm trong local chưa có ở lần đọc live; các bảng bổ sung proposal 03 cũng chưa có. Downstream vẫn là thiết kế local, chưa xác nhận deployment.

Lượt rà này phát hiện và bổ sung `core.demand_series.sales_channel_id` bị bỏ sót vì nằm trong `ALTER TABLE`, đồng thời làm rõ các nghĩa dễ nhầm về tồn, min–max, review và metric. [Audit cấu trúc](../../../artifacts/data-model/reviews/2026-11-03/dictionary-recheck/dictionary-audit-after.json) và [snapshot cột production sau migration 04](../../../artifacts/data-model/reviews/2026-11-03/dictionary-recheck/live-source-columns-post-pos-migration.json) lưu bằng chứng cấu trúc; chúng không chứng minh toàn bộ CHECK/default hoặc workflow. Số dòng dữ liệu là trạng thái vận hành riêng, không được suy từ số bảng/cột hoặc bản dictionary này.

Sau khi áp dụng migration 04, metadata production được đọc lại bằng `pg_catalog.format_type` và đối chiếu cùng local DDL + dictionary: 74 bảng/664 cột, không phát hiện khác biệt inventory/type/nullability/PK/identity/unique/FK target trong phạm vi audit. Xem [audit sau migration](../../../artifacts/data-model/reviews/2026-11-03/dictionary-recheck/dictionary-audit-pos-migration.json) và [snapshot 212 cột source live](../../../artifacts/data-model/reviews/2026-11-03/dictionary-recheck/live-source-columns-post-pos-migration.json). Phép so không kiểm tra mọi CHECK/default, composite-FK pairing, quyền hay hành vi workflow.

#### Source v1 và proposal v2 là hai mốc khác nhau

Migration [20261024_03](../../../archive/2026-11-03-source-sql-history/migrations/20261024_03_retail_workflow_contract.sql) đề xuất thêm 10 bảng: `pos.customer_request`, `pos.customer_request_line`, `inventory.return_case`, `inventory.return_case_line`, `inventory.return_case_event`, `inventory.quality_control_event`, `inventory.recall_case`, `inventory.recall_scope_line`, `inventory.recall_action_event`, `inventory.recall_reconciliation`. Nếu áp dụng đầy đủ riêng bổ sung này, source có 34 bảng. Chúng không bị coi là bảng v1 còn thiếu trong inventory dưới đây.

V2 đổi `inventory.inventory_balance.available_quantity` thành `unreserved_quantity`, **giữ nguyên** công thức on-hand trừ reserved, và thêm `restricted_quantity` nullable. Chỉ request-line giữ một field `available_quantity` riêng theo thời điểm request. Quality release dùng `authorization_reference`, không có `authorized_by`. Các bổ sung trên hiện là proposal; danh sách này không xác nhận chúng đã triển khai và không phải hướng dẫn tự chạy migration.

MongoDB/S3 không có hierarchy PostgreSQL `schema.table.column`; xem [MongoDB/S3 contract](#non-postgres-contracts) và [S3 object metadata schema](#non-postgres-contracts).

### Kiểu dữ liệu và ràng buộc

| Kiểu/nhãn | Giải thích |
|---|---|
| `BIGINT`, `INTEGER`, `SMALLINT` | Số nguyên; ID `IDENTITY` được PostgreSQL cấp tự động. |
| `TEXT` | Chuỗi văn bản; chỉ bị giới hạn giá trị khi có CHECK/constraint. Mã có thể có số 0 đầu nên không ép thành số. |
| `CHAR(n)` | Chuỗi độ dài cố định n ký tự, thường dùng currency code/checksum. |
| `NUMERIC(p,s)` | Số thập phân chính xác; p là tổng chữ số, s là phần thập phân. |
| `BOOLEAN` | Cờ đúng/sai. |
| `DATE` | Ngày lịch, không có giờ/timezone. |
| `TIMESTAMPTZ` | Instant có timezone; PostgreSQL không giữ nguyên chuỗi timezone đầu vào. |
| `JSONB` | JSON có thể truy vấn; key bên trong theo contract của nguồn. |
| `PK` / `FK` | Khóa chính / khóa ngoại; FK không khai báo hành vi xóa riêng dùng mặc định PostgreSQL `NO ACTION`. |
| `NULL cho phép` | Giá trị có thể vắng mặt/chưa biết; NULL không phải 0, false hoặc “còn hạn”. |
| `generated STORED` | Giá trị do PostgreSQL tính theo biểu thức DDL và lưu lại. |

#### Nguyên tắc đọc dữ liệu

- `data_origin`/`evidence_status` thể hiện provenance hoặc mức bằng chứng; miền giá trị phụ thuộc CHECK của bảng. Record do simulator sinh vẫn là SYNTHETIC kể cả khi dùng dataset quan sát làm input.
- Quantity phải đọc cùng unit/UOM, grain và thời điểm. Ordered ≠ received; issued ≠ consumption; sales ≠ latent demand; on-hand ≠ saleable stock.
- `available_quantity` không đồng nghĩa lượng có thể bán: source chỉ trừ reserved; snapshot mô phỏng còn trừ quarantine, blocked và expired.
- `stg.*` lưu observations; `model.*` lưu forecast/evaluation; `sim.*` là synthetic scenario; KPI prediction và decision/operational là các lớp riêng. Tender hiện là KPI dimension planned, không có fact table tender trong DDL này.

### 1. Source simulator — `pharmaflow_source_postgre`

Base DDL định nghĩa 5 schema và 24 bảng. Đây là mô hình nguồn giả lập cho nhà thuốc, không phải bản sao ERP/WMS/POS của Long Châu.

#### `catalog` — Master sản phẩm, taxonomy, quy cách và snapshot nguồn.

<a id="table-catalog-manufacturer"></a>
##### `catalog.manufacturer`

**Vai trò/grain:** Danh mục nhà sản xuất; khác nhà cung cấp.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `manufacturer_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `manufacturer_code` | `TEXT` | NULL cho phép, UNIQUE | Mã nhà sản xuất; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `manufacturer_name` | `TEXT` | NOT NULL | Tên nhà sản xuất; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `country_code` | `TEXT` | NULL cho phép | Mã quốc gia; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `source_ref` | `TEXT` | NULL cho phép | Tham chiếu source/evidence; không nhất thiết FK. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm tạo bản ghi. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm cập nhật bản ghi. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-catalog-unit_of_measure"></a>
##### `catalog.unit_of_measure`

**Vai trò/grain:** Danh mục đơn vị đo; không tự quy đổi khi thiếu conversion đã xác minh.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `uom_code` | `TEXT` | PK, NOT NULL | Mã đơn vị đo; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `uom_name` | `TEXT` | NOT NULL | Tên đơn vị đo; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `uom_kind` | `TEXT` | NOT NULL, CHECK trong DDL | Loại đơn vị đo; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm tạo bản ghi. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-catalog-product_category"></a>
##### `catalog.product_category`

**Vai trò/grain:** Node category trong một taxonomy scheme riêng. Quan hệ cha–con là FK ghép `(parent_category_id, taxonomy_scheme) → (category_id, taxonomy_scheme)`, nên node cha phải cùng scheme.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `category_id` | `BIGINT` | PK, NOT NULL, UNIQUE ghép với `taxonomy_scheme`, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `taxonomy_scheme` | `TEXT` | FK → `catalog.product_category.taxonomy_scheme`, NOT NULL, UNIQUE ghép với `category_code`, UNIQUE ghép với `category_id`, CHECK trong DDL | Scheme taxonomy; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `category_code` | `TEXT` | NOT NULL, UNIQUE ghép với `taxonomy_scheme` | Mã danh mục; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `category_name` | `TEXT` | NOT NULL | Tên danh mục; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `parent_category_id` | `BIGINT` | FK → `catalog.product_category.category_id`, NULL cho phép | Khóa ngoại tới `catalog.product_category.category_id`. |
| `source_category_path` | `TEXT` | NULL cho phép | Category path thô; không gộp với taxonomy nghiệp vụ nếu chưa map. |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT `TRUE` | Cờ cho biết hoạt động có đúng/đang áp dụng hay không. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-catalog-product"></a>
##### `catalog.product`

**Vai trò/grain:** Master sản phẩm/SKU chuẩn dùng bởi POS, mua hàng và tồn kho source.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `product_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `product_code` | `TEXT` | NOT NULL, UNIQUE | Mã sản phẩm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `product_name` | `TEXT` | NOT NULL | Tên sản phẩm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `product_kind` | `TEXT` | NOT NULL, CHECK trong DDL | Loại sản phẩm theo controlled vocabulary trong DDL. |
| `brand_name` | `TEXT` | NULL cho phép | Tên brand; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `dosage_form` | `TEXT` | NULL cho phép | Dạng bào chế nếu source xác nhận; NULL khi thiếu evidence. |
| `active_ingredient_text` | `TEXT` | NULL cho phép | Tóm tắt text hoạt chất theo evidence, có thể nhiều thành phần; không phải bảng ingredient chuẩn hóa. |
| `strength_text` | `TEXT` | NULL cho phép | Văn bản hàm lượng theo source; không ép thành giá trị chuẩn nếu chưa verify. |
| `prescription_status` | `TEXT` | NULL cho phép, CHECK trong DDL | Trạng thái kê đơn; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `registration_number` | `TEXT` | NULL cho phép | Số đăng ký sản phẩm; giữ dưới dạng text. |
| `manufacturer_id` | `BIGINT` | FK → `catalog.manufacturer.manufacturer_id`, NULL cho phép | Khóa ngoại tới `catalog.manufacturer.manufacturer_id`. |
| `base_uom_code` | `TEXT` | FK → `catalog.unit_of_measure.uom_code`, NULL cho phép | Đơn vị cơ sở để diễn giải movement và quy đổi quy cách của sản phẩm; NULL là chưa xác lập đơn vị, không mặc định là hộp/viên. |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT `TRUE` | Cờ cho biết hoạt động có đúng/đang áp dụng hay không. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm tạo bản ghi. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm cập nhật bản ghi. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-catalog-product_category_assignment"></a>
##### `catalog.product_category_assignment`

**Vai trò/grain:** Quan hệ nhiều-nhiều product–category kèm trạng thái/căn cứ gán.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `product_id` | `BIGINT` | PK, FK → `catalog.product.product_id`, NOT NULL | Khóa ngoại tới `catalog.product.product_id`. |
| `category_id` | `BIGINT` | PK, FK → `catalog.product_category.category_id`, NOT NULL | Khóa ngoại tới `catalog.product_category.category_id`. |
| `assignment_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái assignment; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `assignment_basis` | `TEXT` | NOT NULL | Căn cứ assignment; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `assigned_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm được gán; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-catalog-product_source_reference"></a>
##### `catalog.product_source_reference`

**Vai trò/grain:** Mã và snapshot sản phẩm theo source tại một thời điểm; product match có thể chưa xác định.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `product_source_reference_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `product_id` | `BIGINT` | FK → `catalog.product.product_id`, NULL cho phép | Khóa ngoại tới `catalog.product.product_id`. |
| `source_system_key` | `TEXT` | NOT NULL, UNIQUE ghép với `external_product_key`, `observed_at` | Khóa nguồn hệ thống; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `external_product_key` | `TEXT` | NOT NULL, UNIQUE ghép với `source_system_key`, `observed_at` | Khóa ngoài sản phẩm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `observed_name` | `TEXT` | NULL cho phép | Tên quan sát; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `source_category_path` | `TEXT` | NULL cho phép | Category path thô; không gộp với taxonomy nghiệp vụ nếu chưa map. |
| `canonical_url` | `TEXT` | NULL cho phép | URL chuẩn; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `observed_list_price` | `NUMERIC(18,2)` | NULL cho phép, CHECK trong DDL | Giá niêm yết quan sát từ source; không phải supplier cost hay POS transaction. |
| `observed_sale_price` | `NUMERIC(18,2)` | NULL cho phép, CHECK trong DDL | Giá khuyến mãi/giá bán quan sát trên trang; không chứng minh giao dịch đã hoàn tất. |
| `price_currency` | `CHAR(3)` | NULL cho phép | Thông tin giá tiền tệ trong bảng `catalog.product_source_reference`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `availability_status` | `TEXT` | NULL cho phép | Trạng thái tính sẵn có; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `observed_attributes` | `JSONB` | NOT NULL, DEFAULT `'{}'::jsonb`, CHECK trong DDL | Thông tin quan sát attributes trong bảng `catalog.product_source_reference`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `source_url` | `TEXT` | NULL cho phép | URL nguồn; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `match_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái product-source mapping; candidate/unmatched không phải verified. |
| `match_basis` | `TEXT` | NULL cho phép | Căn cứ khớp; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `observed_at` | `TIMESTAMPTZ` | NOT NULL, UNIQUE ghép với `source_system_key`, `external_product_key` | Thời điểm quan sát snapshot/source record. |
| `source_record_key` | `TEXT` | NULL cho phép | Khóa record nguồn để lineage về dòng/đối tượng gốc. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-catalog-product_packaging"></a>
##### `catalog.product_packaging`

**Vai trò/grain:** Quy cách đóng gói, GTIN và hệ số sang base UOM nếu đã xác minh.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `product_packaging_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `product_id` | `BIGINT` | FK → `catalog.product.product_id`, NOT NULL, UNIQUE ghép với `packaging_code` | Khóa ngoại tới `catalog.product.product_id`. |
| `packaging_code` | `TEXT` | NOT NULL, UNIQUE ghép với `product_id` | Mã packaging; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `display_name` | `TEXT` | NOT NULL | Tên hiển thị; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `gtin` | `TEXT` | NULL cho phép, UNIQUE | Thông tin GTIN trong bảng `catalog.product_packaging`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `quantity_in_base_uom` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Số đơn vị cơ sở trong một đơn vị quy cách này, > 0 nếu biết; NULL là chưa biết hệ số. Cần hệ số áp dụng tại thời điểm giao dịch để quy đổi lịch sử. |
| `is_default_sales_unit` | `BOOLEAN` | NOT NULL, DEFAULT `FALSE` | Cờ cho biết mặc định bán hàng đơn vị có đúng/đang áp dụng hay không. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)


#### `org` — Cửa hàng và điểm giữ hàng.

<a id="table-org-store"></a>
##### `org.store`

**Vai trò/grain:** Cửa hàng/điểm bán của mô hình; không tự chứng minh có giao dịch hoặc hàng tồn.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `store_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `store_code` | `TEXT` | NOT NULL, UNIQUE | Mã cửa hàng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `store_name` | `TEXT` | NOT NULL | Tên cửa hàng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `city_name` | `TEXT` | NULL cho phép | Tên thành phố; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `region_name` | `TEXT` | NULL cho phép | Tên vùng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `store_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái cửa hàng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `source_ref` | `TEXT` | NULL cho phép | Tham chiếu source/evidence; không nhất thiết FK. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm tạo bản ghi. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-org-warehouse"></a>
##### `org.warehouse`

**Vai trò/grain:** Điểm giữ hàng gắn cửa hàng hoặc kho trung tâm.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `warehouse_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `warehouse_code` | `TEXT` | NOT NULL, UNIQUE | Mã kho; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `warehouse_name` | `TEXT` | NOT NULL | Tên kho; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `warehouse_kind` | `TEXT` | NOT NULL, CHECK trong DDL | Loại kho; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `store_id` | `BIGINT` | FK → `org.store.store_id`, NULL cho phép | Khóa ngoại tới `org.store.store_id`. |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT `TRUE` | Cờ cho biết hoạt động có đúng/đang áp dụng hay không. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)


#### `pos` — Đơn bán và các dòng hàng (dictionary v1 lịch sử).

<a id="table-pos-sales_channel"></a>
##### `pos.sales_channel`

**Vai trò/grain:** Danh mục kênh bán.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `sales_channel_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `channel_code` | `TEXT` | NOT NULL, UNIQUE | Mã kênh; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `channel_name` | `TEXT` | NOT NULL | Tên kênh; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-pos-sales_order"></a>
##### `pos.sales_order`

**Vai trò/grain:** Phần đầu đơn bán, gồm cửa hàng, kênh, thời điểm, trạng thái và provenance.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `sales_order_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `order_number` | `TEXT` | NOT NULL, UNIQUE | Thông tin đơn hàng số trong bảng `pos.sales_order`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `demand_location_id` | `BIGINT` | FK → `org.store.store_id`, NOT NULL | Cửa hàng/địa bàn phục vụ nơi phát sinh nhu cầu. Ví dụ đơn khách ở Quận 7 vẫn ghi store Q7 để demand không bị gộp sang điểm fulfill. |
| `fulfillment_location_id` | `BIGINT` | FK → `org.warehouse.warehouse_id`, NULL cho phép | Kho vật lý đã chọn để fulfill đơn. Kho tại cửa hàng nối về cửa hàng qua `org.warehouse.store_id`; NULL cho phép trước khi điểm fulfill được xác định. Đây là nơi fulfill thực tế đã ghi nhận, không phải luật định tuyến. |
| `sales_channel_id` | `BIGINT` | FK → `pos.sales_channel.sales_channel_id`, NOT NULL | Khóa ngoại tới `pos.sales_channel.sales_channel_id`. |
| `customer_ref` | `TEXT` | NULL cho phép | Tham chiếu logic trong dictionary v1 lịch sử; không xác định collection MongoDB hiện hành. |
| `ordered_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm đặt đơn; không tự đồng nghĩa thời điểm hoàn tất bán, giao hàng hoặc xuất kho. |
| `order_status` | `TEXT` | NOT NULL, CHECK trong DDL | CREATED, COMPLETED hoặc CANCELLED theo DDL; đây là tập giá trị được lưu, không phải cơ chế thực thi chuyển trạng thái. Tổng hợp sales phải xét phạm vi đơn phù hợp. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm tạo bản ghi. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-pos-sales_order_line"></a>
##### `pos.sales_order_line`

**Vai trò/grain:** Dòng sản phẩm trong đơn bán; lượng và giá có UOM/tiền tệ riêng.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `sales_order_line_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `sales_order_id` | `BIGINT` | FK → `pos.sales_order.sales_order_id`, NOT NULL, UNIQUE ghép với `line_number` | Khóa ngoại tới `pos.sales_order.sales_order_id`. |
| `line_number` | `INTEGER` | NOT NULL, UNIQUE ghép với `sales_order_id`, CHECK trong DDL | Thông tin dòng số trong bảng `pos.sales_order_line`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `product_id` | `BIGINT` | FK → `catalog.product.product_id`, NOT NULL | Khóa ngoại tới `catalog.product.product_id`. |
| `product_packaging_id` | `BIGINT` | FK → `catalog.product_packaging.product_packaging_id`, NULL cho phép | Quy cách được tham chiếu nếu biết. FK đơn hiện chỉ kiểm tra packaging tồn tại, chưa buộc packaging thuộc cùng product_id của line. |
| `sold_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Lượng của sales line, > 0, đọc cùng sales_uom_code và packaging; không tự là base-unit movement hoặc lượng cầu tiềm ẩn. |
| `sales_uom_code` | `TEXT` | FK → `catalog.unit_of_measure.uom_code`, NULL cho phép | Đơn vị lượng bán trên line; NULL là chưa xác định. Khi khác base UOM phải có quy tắc quy đổi có căn cứ. |
| `unit_price` | `NUMERIC(18,2)` | NULL cho phép, CHECK trong DDL | Giá đơn vị; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `currency_code` | `CHAR(3)` | NULL cho phép | Mã tiền tệ; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `source_dataset_code` | `TEXT` | NULL cho phép | Mã dataset nguồn của record/derivation. |
| `source_record_key` | `TEXT` | NULL cho phép | Khóa record nguồn để lineage về dòng/đối tượng gốc. |
| `derivation_method` | `TEXT` | NULL cho phép | Phương pháp biến đổi/sinh dữ liệu; cần đọc kèm config. |
| `derivation_config_ref` | `TEXT` | NULL cho phép | Tham chiếu version/config dùng để derive/sinh record. |
| `provenance_ref` | `TEXT` | NULL cho phép | Tham chiếu lineage/provenance bổ sung. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)


#### `procurement` — Nhà cung cấp, đơn mua và nhận hàng.

<a id="table-procurement-supplier"></a>
##### `procurement.supplier`

**Vai trò/grain:** Danh mục nhà cung cấp; không gộp với manufacturer.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `supplier_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `supplier_code` | `TEXT` | NOT NULL, UNIQUE | Mã nhà cung cấp; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `supplier_name` | `TEXT` | NOT NULL | Tên nhà cung cấp; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `country_code` | `TEXT` | NULL cho phép | Mã quốc gia; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT `TRUE` | Cờ cho biết hoạt động có đúng/đang áp dụng hay không. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `source_ref` | `TEXT` | NULL cho phép | Tham chiếu source/evidence; không nhất thiết FK. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-procurement-purchase_order"></a>
##### `procurement.purchase_order`

**Vai trò/grain:** Phần đầu đơn đặt mua; lượng đặt không phải lượng nhận.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `purchase_order_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `po_number` | `TEXT` | NOT NULL, UNIQUE | Thông tin po số trong bảng `procurement.purchase_order`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `supplier_id` | `BIGINT` | FK → `procurement.supplier.supplier_id`, NOT NULL | Khóa ngoại tới `procurement.supplier.supplier_id`. |
| `destination_warehouse_id` | `BIGINT` | FK → `org.warehouse.warehouse_id`, NOT NULL | Khóa ngoại tới `org.warehouse.warehouse_id`. |
| `ordered_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm đặt PO; điểm đầu có thể dùng cho lead time khi đã chốt rõ điểm cuối là nhận vật lý hay available-for-use. |
| `expected_delivery_date` | `DATE` | NULL cho phép | Ngày giao dự kiến ghi trên PO; không phải ngày nhận thật, xác nhận ETA cuối cùng hoặc ngày được phép sử dụng. |
| `po_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái po; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-procurement-purchase_order_line"></a>
##### `procurement.purchase_order_line`

**Vai trò/grain:** Dòng sản phẩm/số lượng đặt trong PO.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `purchase_order_line_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `purchase_order_id` | `BIGINT` | FK → `procurement.purchase_order.purchase_order_id`, NOT NULL, UNIQUE ghép với `line_number` | Khóa ngoại tới `procurement.purchase_order.purchase_order_id`. |
| `line_number` | `INTEGER` | NOT NULL, UNIQUE ghép với `purchase_order_id`, CHECK trong DDL | Thông tin dòng số trong bảng `procurement.purchase_order_line`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `product_id` | `BIGINT` | FK → `catalog.product.product_id`, NOT NULL | Khóa ngoại tới `catalog.product.product_id`. |
| `ordered_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Lượng đặt theo order_uom_code của PO line; không đồng nghĩa lượng đã nhận hoặc được release. |
| `order_uom_code` | `TEXT` | FK → `catalog.unit_of_measure.uom_code`, NULL cho phép | Đơn vị của ordered_quantity; phải được đối chiếu/quy đổi trước khi so với receipt hoặc movement theo base UOM. |
| `unit_cost` | `NUMERIC(18,2)` | NULL cho phép, CHECK trong DDL | Chi phí đơn vị khai trên dòng PO; giá synthetic là giả định, không phải giá mua thực. |
| `currency_code` | `CHAR(3)` | NULL cho phép | Mã tiền tệ; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-procurement-goods_receipt"></a>
##### `procurement.goods_receipt`

**Vai trò/grain:** Phần đầu một lần nhận gắn với PO.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `goods_receipt_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `receipt_number` | `TEXT` | NOT NULL, UNIQUE | Thông tin nhận hàng số trong bảng `procurement.goods_receipt`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `purchase_order_id` | `BIGINT` | FK → `procurement.purchase_order.purchase_order_id`, NOT NULL | Khóa ngoại tới `procurement.purchase_order.purchase_order_id`. |
| `received_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm tiếp nhận hàng theo receipt; không tự chứng minh đã post, kiểm tra chất lượng hoặc authorized release để sử dụng/bán. |
| `receipt_status` | `TEXT` | NOT NULL, CHECK trong DDL | OPEN, POSTED hoặc CANCELLED theo DDL; trạng thái receipt không thay thế bằng chứng quality release. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)


#### `inventory` — Lô, số dư, ledger movement, điều chuyển và kiểm kê.

<a id="table-inventory-batch_lot"></a>
##### `inventory.batch_lot`

**Vai trò/grain:** Lô của một sản phẩm cùng thông tin sản xuất/hạn dùng nếu biết.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `batch_lot_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `product_id` | `BIGINT` | FK → `catalog.product.product_id`, NOT NULL, UNIQUE ghép với `batch_number` | Khóa ngoại tới `catalog.product.product_id`. |
| `batch_number` | `TEXT` | NOT NULL, UNIQUE ghép với `product_id` | Thông tin lô số trong bảng `inventory.batch_lot`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `manufacture_date` | `DATE` | NULL cho phép | Ngày sản xuất; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `expiry_date` | `DATE` | NULL cho phép | Ngày hết hạn của lô nếu xác lập được. NULL là UNKNOWN_EXPIRY; không tự suy còn hạn hoặc đủ điều kiện FEFO/bán. |
| `first_received_date` | `DATE` | NULL cho phép | Ngày đầu tiên nhận; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-procurement-goods_receipt_line"></a>
##### `procurement.goods_receipt_line`

**Vai trò/grain:** Dòng nhận gắn PO line và lô; accepted khác rejected.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `goods_receipt_line_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `goods_receipt_id` | `BIGINT` | FK → `procurement.goods_receipt.goods_receipt_id`, NOT NULL, UNIQUE ghép với `line_number` | Khóa ngoại tới `procurement.goods_receipt.goods_receipt_id`. |
| `purchase_order_line_id` | `BIGINT` | FK → `procurement.purchase_order_line.purchase_order_line_id`, NOT NULL | PO line được ghi cho receipt line; FK đơn chưa bảo đảm PO line thuộc cùng PO mà receipt header tham chiếu. |
| `batch_lot_id` | `BIGINT` | FK → `inventory.batch_lot.batch_lot_id`, NOT NULL | Lô nhận được tham chiếu; hiện chưa có ràng buộc ghép bảo đảm product của lô khớp product trên PO line. |
| `line_number` | `INTEGER` | NOT NULL, UNIQUE ghép với `goods_receipt_id`, CHECK trong DDL | Thông tin dòng số trong bảng `procurement.goods_receipt_line`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `accepted_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Lượng được chấp nhận trong ghi nhận receipt; không phải bằng chứng authorized release vào saleable stock. UOM kế thừa/quy đổi phải có contract rõ. |
| `rejected_quantity` | `NUMERIC(18,4)` | NOT NULL, DEFAULT `0`, CHECK trong DDL | Lượng bị từ chối trong receipt, >= 0; không tự sinh movement hủy hoặc xác nhận đã trả supplier. |
| `received_quantity` | `NUMERIC(18,4)` | NULL cho phép, generated STORED | Generated = accepted_quantity + rejected_quantity theo DDL; là lượng tiếp nhận được biểu diễn, không đồng nghĩa lượng đủ điều kiện bán. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-inventory-inventory_balance"></a>
##### `inventory.inventory_balance`

**Vai trò/grain:** Số dư theo kho × lô; available chỉ là on-hand trừ reserved.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `inventory_balance_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `warehouse_id` | `BIGINT` | FK → `org.warehouse.warehouse_id`, NOT NULL, UNIQUE ghép với `batch_lot_id` | Khóa ngoại tới `org.warehouse.warehouse_id`. |
| `batch_lot_id` | `BIGINT` | FK → `inventory.batch_lot.batch_lot_id`, NOT NULL, UNIQUE ghép với `warehouse_id` | Khóa ngoại tới `inventory.batch_lot.batch_lot_id`. |
| `on_hand_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Số dư vật lý tại warehouse × lot theo snapshot nguồn; không tự là usable stock theo USAID, unreserved hoặc saleable stock. |
| `reserved_quantity` | `NUMERIC(18,4)` | NOT NULL, DEFAULT `0`, CHECK trong DDL | Lượng đang giữ chỗ trong snapshot, từ 0 đến on_hand_quantity theo CHECK; chưa có reservation-event history trong v1. |
| `available_quantity` | `NUMERIC(18,4)` | NULL cho phép, generated STORED | Generated v1 = on_hand_quantity − reserved_quantity. Nghĩa là chưa giữ chỗ, chưa xét expiry/quality. V2 chỉ đổi tên thành unreserved_quantity, không đổi công thức. |
| `as_of` | `TIMESTAMPTZ` | NOT NULL | Thời điểm hiệu lực của số dư kho × lô; UNIQUE chỉ giữ một row cho mỗi cặp, chưa phải chuỗi lịch sử phục vụ exposure/backtest. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-inventory-stock_transfer"></a>
##### `inventory.stock_transfer`

**Vai trò/grain:** Phần đầu điều chuyển giữa hai kho; không mô hình hóa tuyến vận tải.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `stock_transfer_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `transfer_number` | `TEXT` | NOT NULL, UNIQUE | Thông tin điều chuyển số trong bảng `inventory.stock_transfer`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `source_warehouse_id` | `BIGINT` | FK → `org.warehouse.warehouse_id`, NOT NULL | Khóa ngoại tới `org.warehouse.warehouse_id`. |
| `destination_warehouse_id` | `BIGINT` | FK → `org.warehouse.warehouse_id`, NOT NULL | Khóa ngoại tới `org.warehouse.warehouse_id`. |
| `requested_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm yêu cầu; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `dispatched_at` | `TIMESTAMPTZ` | NULL cho phép | Thời điểm xuất chuyển nếu ghi nhận; không phải ETA hoặc bằng chứng lượng còn trên đường chắc chắn tới trước kỳ review/resupply. |
| `received_at` | `TIMESTAMPTZ` | NULL cho phép | Thời điểm nhận của transfer header nếu biết; chưa lưu lịch sử từng lần nhận một phần theo line. |
| `transfer_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái điều chuyển; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-inventory-stock_transfer_line"></a>
##### `inventory.stock_transfer_line`

**Vai trò/grain:** Dòng sản phẩm/lô với lượng yêu cầu, gửi và nhận.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `stock_transfer_line_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `stock_transfer_id` | `BIGINT` | FK → `inventory.stock_transfer.stock_transfer_id`, NOT NULL, UNIQUE ghép với `line_number` | Khóa ngoại tới `inventory.stock_transfer.stock_transfer_id`. |
| `line_number` | `INTEGER` | NOT NULL, UNIQUE ghép với `stock_transfer_id`, CHECK trong DDL | Thông tin dòng số trong bảng `inventory.stock_transfer_line`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `product_id` | `BIGINT` | FK → `catalog.product.product_id`, NOT NULL | Khóa ngoại tới `catalog.product.product_id`. |
| `batch_lot_id` | `BIGINT` | FK → `inventory.batch_lot.batch_lot_id`, NULL cho phép | Khóa ngoại tới `inventory.batch_lot.batch_lot_id`. |
| `requested_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Số lượng yêu cầu; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `shipped_quantity` | `NUMERIC(18,4)` | NOT NULL, DEFAULT `0`, CHECK trong DDL | Lượng đã gửi theo line, không vượt requested_quantity; không đồng nghĩa đã nhận ở kho đích. |
| `received_quantity` | `NUMERIC(18,4)` | NOT NULL, DEFAULT `0`, CHECK trong DDL | Lượng nhận được ghi trên transfer line, không vượt shipped_quantity; shipped trừ received cần thêm trạng thái/evidence để diễn giải lượng đang đi. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-inventory-stock_take"></a>
##### `inventory.stock_take`

**Vai trò/grain:** Phần đầu đợt kiểm kê tại kho.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `stock_take_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `stock_take_number` | `TEXT` | NOT NULL, UNIQUE | Thông tin tồn kho kiểm kê số trong bảng `inventory.stock_take`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `warehouse_id` | `BIGINT` | FK → `org.warehouse.warehouse_id`, NOT NULL | Khóa ngoại tới `org.warehouse.warehouse_id`. |
| `started_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm bắt đầu; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `completed_at` | `TIMESTAMPTZ` | NULL cho phép | Thời điểm hoàn tất; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `stock_take_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái tồn kho kiểm kê; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-inventory-stock_take_line"></a>
##### `inventory.stock_take_line`

**Vai trò/grain:** Dòng kiểm kê theo lô; variance = lượng đếm − lượng sổ.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `stock_take_line_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `stock_take_id` | `BIGINT` | FK → `inventory.stock_take.stock_take_id`, NOT NULL, UNIQUE ghép với `batch_lot_id` | Khóa ngoại tới `inventory.stock_take.stock_take_id`. |
| `batch_lot_id` | `BIGINT` | FK → `inventory.batch_lot.batch_lot_id`, NOT NULL, UNIQUE ghép với `stock_take_id` | Khóa ngoại tới `inventory.batch_lot.batch_lot_id`. |
| `book_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Số lượng sổ; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `counted_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Số lượng đếm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `variance_quantity` | `NUMERIC(18,4)` | NULL cho phép, generated STORED | Generated = counted_quantity − book_quantity. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)

<a id="table-inventory-inventory_movement"></a>
##### `inventory.inventory_movement`

**Vai trò/grain:** Ledger biến động tồn có dấu theo kho × lô.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `inventory_movement_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `warehouse_id` | `BIGINT` | FK → `org.warehouse.warehouse_id`, NOT NULL | Khóa ngoại tới `org.warehouse.warehouse_id`. |
| `batch_lot_id` | `BIGINT` | FK → `inventory.batch_lot.batch_lot_id`, NOT NULL | Khóa ngoại tới `inventory.batch_lot.batch_lot_id`. |
| `movement_type` | `TEXT` | NOT NULL, CHECK trong DDL | Loại event nguồn v1. SALE_RETAIL/TRANSFER_OUT giảm; GOODS_RECEIPT/TRANSFER_IN tăng. EXPIRY_WRITE_OFF dành cho ghi giảm do hết hạn, không gộp mọi lý do disposal. |
| `quantity_delta` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Biến động có dấu theo base UOM của sản phẩm thuộc lô: dương tăng, âm giảm. Cần quy đổi từ line UOM; FK đơn không tự bảo đảm đúng product/lot/kho. |
| `occurred_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm sự kiện/giao dịch xảy ra theo record. |
| `sales_order_line_id` | `BIGINT` | FK → `pos.sales_order_line.sales_order_line_id`, NULL cho phép | Khóa ngoại tới `pos.sales_order_line.sales_order_line_id`. |
| `goods_receipt_line_id` | `BIGINT` | FK → `procurement.goods_receipt_line.goods_receipt_line_id`, NULL cho phép | Khóa ngoại tới `procurement.goods_receipt_line.goods_receipt_line_id`. |
| `stock_transfer_line_id` | `BIGINT` | FK → `inventory.stock_transfer_line.stock_transfer_line_id`, NULL cho phép | Khóa ngoại tới `inventory.stock_transfer_line.stock_transfer_line_id`. |
| `stock_take_line_id` | `BIGINT` | FK → `inventory.stock_take_line.stock_take_line_id`, NULL cho phép | Khóa ngoại tới `inventory.stock_take_line.stock_take_line_id`. |
| `adjustment_reason` | `TEXT` | NULL cho phép | Thông tin adjustment lý do trong bảng `inventory.inventory_movement`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-source-sql-history/schema_v1.sql`](../../../archive/2026-11-03-source-sql-history/schema_v1.sql)




<a id="proposal-v2"></a>
## Contract workflow v2 — đề xuất

**Ngày rà soát:** 24/10/2026<br>
**Trạng thái:** migration 20261024_03 và sửa downstream vẫn là đề xuất cục bộ, chưa chạy trên Neon. Việc tách demand/fulfillment của `pos.sales_order` được triển khai riêng qua migration 20261103_04 trên source v1; migration đó không triển khai các phần còn lại của contract này.

**Phạm vi:** phần dữ liệu cần để PharmaFlow hỗ trợ quyết định chuỗi cung ứng nhà thuốc. PharmaFlow vẫn là DSS; không thay POS/ERP/WMS/HIS.

### 1. Nguồn nào quyết định workflow

Workflow được dựng trước từ tài liệu nghiệp vụ. Contract/schema v1 chỉ được đối chiếu sau khi flow đã có nguồn; schema không phải bằng chứng cho actor, bước, thứ tự hay trạng thái nghiệp vụ.

| Flow | Nguồn chính và locator | Phần bổ sung | Ranh giới |
|---|---|---|---|
| Tiếp nhận và kiểm soát lô | **[A] WHO TRS 1025 Annex 7**, §§12.10–12.18, trang in 171 (PDF 15); cập nhật hồ sơ §13.1, trang in 174 (PDF 18). | WHO §§9.2–9.8 cho thuốc khách trả lại; §§13.2–13.4 cho đối chiếu tồn, chênh lệch và hư hỏng. | WHO nêu các kiểm tra, cách ly và điều kiện release. Không thêm approval, 3-way match, ASN hoặc SLA ngoài locator này. |
| Continuous review bổ sung tồn | **[B] USAID/DELIVER, The Logistics Handbook, 2nd ed.**, Ch.4 §4.4, trang in 58 (PDF 70); continuous review, trang in 61 (PDF 73). | [D] cho giới hạn khi sales bị kiểm duyệt bởi stock-out; [E] cho đánh giá forecast; [F–L] cho bằng chứng/phương pháp forecast thuốc và hàng gián đoạn. | Nguồn chính mô tả review mỗi lần issue và điều kiện min–max. Không đồng nhất issue với bán/lĩnh thuốc; không thêm bước duyệt, chuyển kho hay giao hàng vào flow này. |
| Yêu cầu đổi/trả của khách | **[C] Chính sách đổi trả Long Châu**, §§1–3, truy cập 24/10/2026; §2 Bước 1–4 là nguồn chính của flow. | [A] WHO §9 chỉ áp dụng khi thuốc được nhận lại thực tế và cần xử lý chất lượng. | Policy công khai mô tả quyền lợi/quy trình công bố; không chứng minh giao dịch trả hàng nội bộ nào đã xảy ra, thuốc đã vào tồn, được hoàn tiền hay được release. |
| Recall | **[A] WHO TRS 1025 Annex 7**, §§10.1–10.8, trang in 169 (PDF 13). | Không có bước bổ sung từ schema. | WHO yêu cầu chuẩn bị, thông báo, kiểm soát, hồ sơ và reconciliation. Các yêu cầu không tạo thành một chuỗi trạng thái tuyến tính; không tự đặt thứ tự giữa các hành động song song, SLA hay tỷ lệ đóng 100%. |

[ D ]–[ L ] là tài liệu nghiên cứu/phương pháp, không phải nguồn dựng luồng thao tác nhà thuốc. Bảy PDF trong `docs/references/PAPER` đã được đọc toàn văn đến trang cuối, gồm trang references. Các tài liệu chỉ được trích cho câu hỏi forecast/đánh giá; không dùng để suy ra quy trình nhận hàng, đổi trả hay recall. Việc một công trình xuất hiện trong bibliography của bài không được xem là đã đọc full text của công trình đó.

#### Cách đọc actor và mũi tên

- Actor trên sơ đồ được lấy trực tiếp từ nguồn của hành động; schema chỉ được dùng để đối chiếu field sau khi chốt flow.
- Mỗi mũi tên là quan hệ được nguồn mô tả hoặc được ghi rõ là tổng hợp có điều kiện từ hai nguồn. Mũi tên không tự có nghĩa là một trạng thái database, API call, transaction, SLA hoặc tích hợp đang chạy.
- Nguồn chính của từng flow được giữ riêng. Phần bổ sung chỉ giải thích đúng nhánh/hạn chế mà nguồn đó đề cập.

### 2. Đối chiếu baseline sau khi đã chốt flow

Nguồn [N] là baseline cấu trúc đang có, không phải nguồn quy trình:

- `pos.sales_order` và `pos.sales_order_line` lưu đơn/bán; không chứng minh mọi yêu cầu khách, unmet demand hay việc khách đã nhận thuốc.
- `pos.sales_order.demand_location_id` lưu cửa hàng/địa bàn nhu cầu và tham chiếu `org.store`; `fulfillment_location_id` tham chiếu `org.warehouse` để lưu kho fulfill đã chọn. Đây là contract v1 đã triển khai riêng, không phải thuật toán định tuyến.
- `procurement.goods_receipt_line` lưu số lượng nhận/chấp nhận/từ chối; `accepted_quantity` không chứng minh lô đã được người có thẩm quyền cho vào saleable stock.
- `inventory.inventory_balance.available_quantity` v1 được tính từ on-hand trừ reserved; chưa biểu diễn riêng phần quarantine/restricted.
- `pos.customer_request_line.available_quantity` là quantity ghi nhận tại thời điểm request và giữ nguyên tên trong migration. Migration `20261024_03` đổi tên projection của balance từ `inventory.inventory_balance.available_quantity` sang `unreserved_quantity`, đồng thời thêm `restricted_quantity`; hai trường `available_quantity` ở hai bảng là hai fact khác nhau.
- Source v1 không có hồ sơ return/recall đầy đủ. Các enum PO/receipt/transfer/sale hiện có chỉ là giá trị được phép lưu; DDL không chứng minh một quy trình chuyển trạng thái nào.
- Downstream schema có forecast, evaluation, simulation và review. Bản local này không phải bằng chứng đã triển khai hoặc dữ liệu Long Châu thật.

Migration `archive/2026-11-03-source-sql-history/migrations/20261024_03_retail_workflow_contract.sql` và các sửa đổi downstream dưới đây đều là **đề xuất từ flow đã có nguồn**. Chúng chưa áp dụng vào Neon. Migration POS location 04 không thay đổi trạng thái triển khai của proposal này.

### 3. Các sửa đổi contract được suy ra từ nguồn nghiệp vụ

| Nguồn/flow đã xác lập | Baseline thiếu gì | Đề xuất field/quan hệ | Căn cứ và giới hạn |
|---|---|---|---|
| [A] Nhận hàng/kiểm tra từng lô/release | Receipt-line có quantity nhưng không lưu kết quả kiểm tra và bằng chứng quyết định release riêng. | Event theo receipt line hoặc return line: action/observation dạng ghi nhận, thời điểm, quantity/UOM nếu có, authorization evidence, source locator và data origin. | [A] §§12.10–12.18. Không tạo status chain; giá trị được ghi phải khớp hành động được quan sát, không được tự sinh từ `accepted_quantity`. |
| [A] Cách ly và hồ sơ tồn | Balance v1 không tách lượng bị hạn chế; tên `available_quantity` dễ bị hiểu thành lượng có thể bán dù v1 chỉ trừ reserved. | Bổ sung `restricted_quantity`; giữ unknown là NULL; đổi tên projection v1 thành `unreserved_quantity`. Contract không định nghĩa phép tính `available_quantity`. | [A] §§12.12, 12.15–12.18 quy định quarantine/authorized release, không đưa công thức availability. V1 DDL ghi `available_quantity = on_hand_quantity − reserved_quantity` tại `schema_v1.sql` dòng 262; comment dòng 401–402 nói chưa xét eligibility [N]. Không tự gán restricted = 0 cho snapshot cũ. |
| [C] Policy đổi/trả; [A] chỉ khi nhận lại thuốc thật | V1 không lưu yêu cầu trả, hàng nhận, các lần kiểm tra/thông báo, hay disposition. | Thêm case, line và event log; lưu yêu cầu, quantity thực nhận nếu có, điều kiện quan sát dạng raw text, original sale link khi xác minh được, actor/evidence/source locator. Không có enum case status hoặc chuỗi transition mới. | [C] §2 Bước 1–4; [A] §9.2–9.8. Policy public được lưu riêng với `OBSERVED_PUBLIC`; không dùng policy page làm giao dịch trả hàng. Return receipt, refund và release là các facts riêng. |
| [A] Recall | V1 không phân biệt notice/scope công khai với hành động tại cơ sở. | Tách notice và scope (có thể `OBSERVED_PUBLIC`) khỏi action/reconciliation vận hành (không `OBSERVED_PUBLIC`). Reconciliation chỉ lưu số lượng đã phân phối/thu hồi nếu nguồn ghi, UOM, thời điểm, evidence. | [A] §§10.1–10.8. Không thêm enum lifecycle, “block sale” mặc định, quantity located/isolated/disposed không được nguồn xác lập, phần dư bằng phép trừ, SLA hoặc điều kiện đóng. |
| [B] Continuous review; [D–L] forecast | V1 lưu transaction/balance và downstream forecast/simulation, nhưng chưa đủ audit đầu vào min–max của từng recommendation. | Thêm bảng basis nối recommendation line trong mô phỏng với reviewed_at, issue reference nếu có, on-hand, min, max, quantity-on-order nếu đã xác nhận, UOM, công thức/locator và origin. | [B] Ch.4 §4.4 p.58 và continuous review p.61. Đây là đầu vào tính toán/đánh giá DSS; không ghi recommendation thành PO/transfer thật. Giữ review của người dùng trong `sim.recommendation_review`. |
| [D] Sales có thể bị censor bởi stock-out | Không phải mọi yêu cầu/stockout đều được phản ánh trong sales. V1 sales không tạo được request/outcome đã quan sát. | Request observation tùy chọn: requested quantity + UOM, quantity available tại thời điểm đo nếu có, fulfilled/unmet quantity độc lập và nullable, thời điểm/evidence/source. Không áp status enum, không ép equality. | [D] §1 pp.134–136; bài nghiên cứu là mô hình retail/news-vendor, không phải quy trình Long Châu. Chỉ ghi unmet khi dữ liệu ghi nhận; không suy ra từ forecast trừ sales. |

### 4. Contract dữ liệu đề xuất

#### 4.1 Nguồn source — proposal migration 20261024_03

- `pos.customer_request` / `pos.customer_request_line`: tùy chọn ghi một request thật có bằng chứng. `demand_location_id` tham chiếu `org.store` nơi request phát sinh; không suy ra kho fulfill từ trường này. Không lưu tên/số điện thoại khách trong contract này. Requested, `available_quantity` tại thời điểm quan sát, fulfilled và unmet có trường/UOM riêng theo dữ liệu nhận được; nullable nghĩa là chưa biết. Trường này không phải projection tồn kho. Sale line chỉ liên kết request khi linkage và product khớp đã được xác minh.
- `inventory.return_case`, `return_case_line`, `return_case_event`: facts về yêu cầu, sản phẩm/quantity thực nhận và event có chứng cứ. Lưu các bước policy theo locator [C] §2; khi thuốc được nhận lại, ghi quality event theo [A] §§9.2–9.8. Physical receipt, refund và quality release là các event riêng.
- `inventory.quality_control_event`: ghi observation/action ứng với receipt line hoặc return line, kèm `source_locator`, `evidence_ref`, `data_origin`. Action release phải có authorization evidence; actor chỉ được ghi khi nguồn của event nhận diện actor. Tên action dùng vocabulary bám điều khoản WHO; không coi các action như một thứ tự transition bắt buộc.
- `inventory.recall_case` / `recall_scope_line`: notice và scope; cho phép public evidence chỉ ở hai loại thông tin này. `recall_action_event` và `recall_reconciliation` là facts vận hành riêng, cần evidence và origin riêng.
- `inventory.inventory_balance.restricted_quantity`: nullable khi evidence không xác lập lượng restricted. Giữ projection v1 dưới tên `unreserved_quantity`; không suy ra `available_quantity` bằng công thức do nguồn workflow không quy định.
- Bảo vệ provenance: sales, purchase/receipt, lot, balance, transfer, stocktake, movement, request/return, quality actions và recall actions không nhận `OBSERVED_PUBLIC`. Notice/scope public không chứng minh thao tác nội bộ.

#### 4.2 Downstream DSS — proposal sửa schema local

- `stg.retail_demand_request_observation`: lưu từng quantity/availability/outcome quan sát độc lập; bỏ status enum và ràng buộc số học chung. Đây là optional modeling input, không phải flow.
- `stg.inventory_quality_event_observation`: event/action + locator/evidence cho thao tác đã ghi nhận; public recall notice chuyển sang staging notice riêng, không gộp với hành động tại kho/cửa hàng.
- `stg.recall_notice_observation`, `stg.recall_scope_observation` và `stg.recall_reconciliation_observation`: tách thông báo/scope được công bố khỏi reconciliation vận hành. Không tự tạo số lượng “unresolved”.
- `sim.replenishment_review_basis`: lưu input min–max, issue reference, cờ số lượng đang đặt dự kiến tới trước lần resupply kế tiếp, locator công thức và liên kết tùy chọn tới recommendation line. Các order/transfer sinh ra từ simulation vẫn là synthetic, không được báo cáo là thực tế.
- Giữ `model.forecast_run`, `model.forecast_point`, `model.forecast_evaluation` tách khỏi KPI vận hành/decision. PAPER hỗ trợ lựa chọn thiết kế thí nghiệm và giới hạn mô hình; không chứng minh kết quả kinh doanh ở Long Châu.

### 5. Công thức, đơn vị và mục đích

| Biểu thức / rule | Giải thích | Đơn vị cần | Dùng để | Nguồn và locator |
|---|---|---|---|---|
| maximum stock quantity = average monthly consumption × maximum stock level | Lấy lượng tiêu thụ trung bình mỗi tháng nhân với số tháng muốn duy trì tồn tối đa. Handbook minh họa: 100 condoms/month × 3 months = 300 condoms. | AMC: đơn vị hàng/tháng; max stock level: tháng; kết quả: đơn vị hàng. Cùng mặt hàng và UOM. | Chuyển mức bao phủ tồn theo tháng thành số lượng Max. | [B] Ch.4 §4.4, trang in 58 (PDF p.70). |
| Review mỗi lần issue; nếu stock ở Min hoặc thấp hơn thì order đủ đưa lên Max. | Issue kích hoạt review; điều kiện Min xác định lúc order và Max xác định mức cần đạt. | Stock, Min và Max phải cùng cách biểu diễn lượng cho cùng mặt hàng. | Xác định thời điểm kiểm tồn và trigger của continuous review. | [B] Ch.4 “Continuous review max-min system”, trang in 61 (PDF p.73). |
| maximum stock quantity − stock on hand − quantity on order = order quantity | Trừ tồn hiện có và lượng đang trên đường khỏi mức Max để tìm phần còn cần order. | Mọi quantity cùng UOM, mặt hàng và location. | Tính order quantity khi order/issue trước chưa tới nhưng cơ sở chắc chắn lượng đó sẽ tới trước lần resupply kế tiếp. | [B] Ch.4 §4.4, trang in 58 (PDF p.70); điều kiện áp dụng nằm cùng phần công thức. |
| e_(T+h) = y_(T+h) − ŷ_(T+h\|T) | y là quan sát; ŷ là forecast tạo tại origin T cho horizon T+h. Sai số dương khi quan sát lớn hơn forecast. | Quan sát và forecast cùng target, UOM, grain và horizon; error giữ đơn vị target. | Đo độ lệch có dấu trên từng điểm test trước khi tổng hợp metric. | [E] §5.8, “Forecast errors” và “Training and test sets”. |
| MAE = mean(abs(e_t)) | Lấy trị tuyệt đối từng error rồi tính trung bình. | Cùng đơn vị với target; cùng series/target khi so sánh. | Tóm tắt độ lớn sai lệch trung bình, không để sai số dương/âm triệt tiêu nhau. | [E] §5.8, “Scale-dependent errors”. |
| RMSE = √mean(e_t²) | Bình phương error, lấy trung bình rồi căn bậc hai; sai số lớn có ảnh hưởng mạnh hơn. | Sau khi lấy căn, RMSE cùng đơn vị với target. | Tóm tắt sai số và làm nổi bật các lần forecast lệch lớn. | [E] §5.8, “Scale-dependent errors”. |
| available_quantity_v1 = on_hand_quantity − reserved_quantity | Phép chiếu đang có trong source-v1 DDL, biểu diễn on-hand sau khi trừ reserved; đây là dữ kiện schema để đối chiếu contract. | Cùng UOM, item và location; kết quả giữ UOM. | Diễn giải projection v1; contract v2 dùng unreserved_quantity và lưu restricted_quantity riêng. | [N] schema_v1.sql dòng 262; comment dòng 401–402. |

WHO quarantine/authorized release là kiểm soát chất lượng, không phải công thức số lượng: [A] §§9.2–9.8, 12.15–12.17. Request, fulfilled và unmet quantity được lưu như các quan sát riêng; nghiên cứu [D] §1 pp.134–136 giải thích censoring khi stock-out nhưng không cung cấp identity áp dụng cho mọi request.

### 6. PAPER: đã đọc toàn văn và giới hạn sử dụng

Các PDF dưới đây trong `docs/references/PAPER` đã được đọc từ trang đầu đến hết references. Chỉ lấy căn cứ cho forecast, dữ liệu đầu vào và cách đánh giá. Không paper nào được dùng làm căn cứ thay WHO/Long Châu cho receipt, returns hoặc recall.

| Nguồn | Phần toàn văn/reference đã rà | Chỉ hỗ trợ điều gì trong contract |
|---|---|---|
| [F] Sbrana & Babai (2026), EJOR | §4.4 pp.8–9; references pp.12–13. | Tách forecast accuracy khỏi inventory-policy outcome; dataset không phải pharmacy/Long Châu. |
| [G] Eaa et al. (2024), Procedia Computer Science 242 | Toàn bộ methods/data/results/limitations; references p.8. | Grain/aggregation là lựa chọn thí nghiệm; dữ liệu dairy convenience store không phải dược. |
| [H] Burinskiene (2022), Frontiers in Medicine 9:582186 | Toàn văn pp.1–15; references pp.15–16. | Bằng chứng hẹp 8 pharmacy/13 tuần; không nâng imputation thành mặc định. |
| [I] Fourkiotis & Tsadiras (2024), Forecasting 6 | Toàn văn pp.1–15; references pp.16–17. | So sánh theo product/metric; một pharmacy, weekly, 57 sản phẩm/8 ATC, dữ liệu trước COVID. |
| [J] Ramadhan et al. (2026), ISI 31(1) | Toàn văn pp.1–10; references pp.10–13. | Bibliometric/review context; không dùng số lượng review để suy ra vận hành. |
| [K] Khan et al. (2026), Discover AI 6:838 | §§3–7, pp.4–18; references pp.19–20. | Giữ semantics của target và feature cutoff; NHSBSA aggregates không là store ordering policy. |
| [L] Abaci (2026), IEEE Access | Algorithm 2, PDF pp.10–11; references pp.22–23. | Lưu evaluation protocol/origin count; mẫu Istanbul một pharmacy, 4 monthly ATC series, 8 test observations quá hẹp để xếp hạng mô hình phổ quát. |

[ D ] Jain, Rudi & Wang (2015), *Operations Research* 63(1):134–150, DOI 10.1287/opre.2014.1326, là supplement về censoring, không có vai trò nguồn flow nhà thuốc. Chỉ áp dụng nhận định phù hợp mô hình/ngữ cảnh, không suy ra unmet demand Long Châu.

### 7. Nguồn

- **[A]** WHO (2020), TRS 1025 Annex 7. [PDF trong repo](../../../docs/references/trs1025-annex7-(1).pdf) · [WHO publication](https://www.who.int/publications/m/item/trs-1025-annex-7/).
- **[B]** USAID | DELIVER (2011), *The Logistics Handbook*, 2nd ed. [PDF trong repo](../../../docs/references/Logistics%20Handbook.pdf).
- **[C]** FPT Long Châu, “Chính sách đổi trả và hoàn tiền”, §§1–3, truy cập 24/10/2026. [Trang chính thức](https://nhathuoclongchau.com.vn/chinh-sach/chinh-sach-doi-tra).
- **[D]** Jain, Rudi & Wang (2015), “Demand Estimation and Ordering Under Censoring: Stock-Out Timing Is (Almost) All You Need”, *Operations Research* 63(1):134–150. [DOI](https://doi.org/10.1287/opre.2014.1326).
- **[E]** Hyndman & Athanasopoulos, *Forecasting: Principles and Practice*, 3rd ed., §§5.8, 5.10. [Accuracy](https://otexts.com/fpp3/accuracy.html) · [Time-series cross-validation](https://otexts.com/fpp3/tscv.html).
- **[F]** Sbrana & Babai (2026), EJOR. [PDF](../../../docs/references/PAPER/1-s2.0-S0377221726005412-main.pdf) · [DOI](https://doi.org/10.1016/j.ejor.2026.06.009).
- **[G]** Eaa et al. (2024), Procedia Computer Science 242:264–271. [PDF](../../../docs/references/PAPER/1-s2.0-S1877050924019586-main.pdf).
- **[H]** Burinskiene (2022), Frontiers in Medicine 9:582186. [PDF](../../../docs/references/PAPER/fmed-09-582186.pdf) · [DOI](https://doi.org/10.3389/fmed.2022.582186).
- **[I]** Fourkiotis & Tsadiras (2024), Forecasting 6:170–186. [PDF](../../../docs/references/PAPER/forecasting-06-00010.pdf) · [DOI](https://doi.org/10.3390/forecast6010010).
- **[J]** Ramadhan et al. (2026), ISI 31(1):179–191. [PDF](../../../docs/references/PAPER/isi_31.01_17.pdf) · [DOI](https://doi.org/10.18280/isi.310117).
- **[K]** Khan, Tahsin & Al Mamun (2026), Discover Artificial Intelligence 6:838. [PDF](../../../docs/references/PAPER/s44163-026-01956-z.pdf) · [DOI](https://doi.org/10.1007/s44163-026-01956-z).
- **[L]** Abaci (2026), IEEE Access 14. [PDF](../../../docs/references/PAPER/Statistical_Diagnostics_and_Forecast_Accuracy_Comparing_Time-Series_Machine-Learning_and_Hybrid_Models_for_Drug_Sales.pdf) · [DOI](https://doi.org/10.1109/ACCESS.2026.3685042).
- **[M]** PharmaFlow invariants: [AGENTS.md](../../../AGENTS.md). Chỉ là ranh giới kiến trúc dữ liệu/DSS, không phải chứng cứ workflow.
- **[N]** [Source v1 schema](../../../archive/2026-11-03-source-sql-history/schema_v1.sql) và [contract baseline](#source-v1). Chỉ để đối chiếu cấu trúc hiện có.
- **[O]** [Source coverage report](../../../dataset/longchau-knowledge/_meta/derived/SOURCE_COVERAGE.md). ERP/WMS/HIS nội bộ hiện không có nguồn kết nối.


<a id="downstream-dss"></a>
### 2. Downstream DSS model

DDL định nghĩa 6 schema và 50 bảng: metadata/ingest, canonical entities, staging observations, forecast, simulation và KPI ownership.

#### `meta` — Registry nguồn và lịch sử ingest.

<a id="table-meta-source_registry"></a>
##### `meta.source_registry`

**Vai trò/grain:** Metadata nguồn: grain, phạm vi, license và cảnh báo ngữ nghĩa.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `source_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `source_key` | `TEXT` | NOT NULL, UNIQUE | Khóa nguồn; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `source_name` | `TEXT` | NOT NULL | Tên nguồn; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `source_kind` | `TEXT` | NOT NULL, CHECK trong DDL | Loại nguồn; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `business_domain` | `TEXT` | NOT NULL | Thông tin nghiệp vụ miền trong bảng `meta.source_registry`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `geographic_scope` | `TEXT` | NULL cho phép | Thông tin địa lý phạm vi trong bảng `meta.source_registry`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `source_grain` | `TEXT` | NOT NULL | Mức chi tiết mà một record/series của nguồn đại diện. |
| `license_note` | `TEXT` | NULL cho phép | Ghi chú license của source; NULL không tự xác nhận quyền sử dụng. |
| `semantic_caveat` | `TEXT` | NOT NULL | Cảnh báo về diễn giải và điều không thể suy ra từ nguồn. |
| `source_uri` | `TEXT` | NULL cho phép | URI nguồn; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `registered_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm đăng ký metadata source. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-meta-ingestion_run"></a>
##### `meta.ingestion_run`

**Vai trò/grain:** Một lần nạp object của source, có checksum/version/trạng thái và số dòng.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `ingestion_run_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `source_id` | `BIGINT` | FK → `meta.source_registry.source_id`, NOT NULL | Khóa ngoại tới `meta.source_registry.source_id`. |
| `source_object_uri` | `TEXT` | NOT NULL | URI nguồn object; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `source_checksum_sha256` | `CHAR(64)` | NULL cho phép | SHA-256 object nguồn để định danh/kiểm tra toàn vẹn; không thay thế kiểm tra nội dung. |
| `schema_version` | `TEXT` | NULL cho phép | Thông tin schema phiên bản trong bảng `meta.ingestion_run`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `started_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm bắt đầu; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `finished_at` | `TIMESTAMPTZ` | NULL cho phép | Thời điểm kết thúc; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `run_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái lần chạy; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `rows_read` | `BIGINT` | NULL cho phép, CHECK trong DDL | Thông tin rows đọc trong bảng `meta.ingestion_run`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `rows_written` | `BIGINT` | NULL cho phép, CHECK trong DDL | Thông tin rows ghi trong bảng `meta.ingestion_run`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `error_summary` | `TEXT` | NULL cho phép | Tóm tắt lỗi; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)


#### `core` — Entity/master chuẩn hóa và định nghĩa chuỗi đo.

<a id="table-core-organisation"></a>
##### `core.organisation`

**Vai trò/grain:** Danh mục tổ chức chuẩn hóa, hỗ trợ cây cha–con.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `organisation_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `source_id` | `BIGINT` | FK → `meta.source_registry.source_id`, NULL cho phép, UNIQUE ghép với `external_code` | Khóa ngoại tới `meta.source_registry.source_id`. |
| `parent_organisation_id` | `BIGINT` | FK → `core.organisation.organisation_id`, NULL cho phép | Khóa ngoại tới `core.organisation.organisation_id`. |
| `external_code` | `TEXT` | NULL cho phép, UNIQUE ghép với `source_id` | Mã ngoài; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `organisation_name` | `TEXT` | NOT NULL | Tên tổ chức; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `organisation_type` | `TEXT` | NOT NULL, CHECK trong DDL | Loại tổ chức; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `evidence_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái bằng chứng; miền giá trị phụ thuộc CHECK của bảng. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-core-location"></a>
##### `core.location`

**Vai trò/grain:** Danh mục địa điểm chuẩn hóa, gắn tổ chức và cây địa điểm.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `location_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `organisation_id` | `BIGINT` | FK → `core.organisation.organisation_id`, NULL cho phép, UNIQUE ghép với `external_code` | Khóa ngoại tới `core.organisation.organisation_id`. |
| `parent_location_id` | `BIGINT` | FK → `core.location.location_id`, NULL cho phép | Khóa ngoại tới `core.location.location_id`. |
| `external_code` | `TEXT` | NULL cho phép, UNIQUE ghép với `organisation_id` | Mã ngoài; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `location_name` | `TEXT` | NOT NULL | Tên địa điểm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `location_type` | `TEXT` | NOT NULL, CHECK trong DDL | Loại địa điểm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `city` | `TEXT` | NULL cho phép | Thông tin thành phố trong bảng `core.location`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `region` | `TEXT` | NULL cho phép | Thông tin vùng trong bảng `core.location`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `evidence_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái bằng chứng; miền giá trị phụ thuộc CHECK của bảng. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-core-product"></a>
##### `core.product`

**Vai trò/grain:** Master sản phẩm downstream và căn cứ định danh.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `product_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `canonical_code` | `TEXT` | NULL cho phép, UNIQUE | Mã chuẩn; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `display_name` | `TEXT` | NOT NULL | Tên hiển thị; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `product_kind` | `TEXT` | NOT NULL, CHECK trong DDL | Loại sản phẩm theo controlled vocabulary trong DDL. |
| `identity_basis` | `TEXT` | NOT NULL | Căn cứ định danh canonical product; cần kiểm chứng trước khi xem match là xác nhận. |
| `record_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái bản ghi; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm tạo bản ghi. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-core-product_source_key"></a>
##### `core.product_source_key`

**Vai trò/grain:** Mã sản phẩm theo source và trạng thái khớp với master.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `product_source_key_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `source_id` | `BIGINT` | FK → `meta.source_registry.source_id`, NOT NULL, UNIQUE ghép với `external_product_code` | Khóa ngoại tới `meta.source_registry.source_id`. |
| `external_product_code` | `TEXT` | NOT NULL, UNIQUE ghép với `source_id` | Mã ngoài sản phẩm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `external_product_name` | `TEXT` | NULL cho phép | Tên ngoài sản phẩm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `external_product_url` | `TEXT` | NULL cho phép | URL ngoài sản phẩm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `product_id` | `BIGINT` | FK → `core.product.product_id`, NULL cho phép | Khóa ngoại tới `core.product.product_id`. |
| `match_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái product-source mapping; candidate/unmatched không phải verified. |
| `match_method` | `TEXT` | NULL cho phép | Thông tin khớp phương pháp trong bảng `core.product_source_key`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `match_confidence` | `NUMERIC(5,4)` | NULL cho phép, CHECK trong DDL | Điểm confidence 0–1; không thay thế trạng thái review/verified. |
| `verified_at` | `TIMESTAMPTZ` | NULL cho phép | Thời điểm verified; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-core-demand_series"></a>
##### `core.demand_series`

**Vai trò/grain:** Định nghĩa chuỗi, grain và ngữ nghĩa measure; giữ riêng issued/sales/request.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `series_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `source_id` | `BIGINT` | FK → `meta.source_registry.source_id`, NOT NULL, UNIQUE ghép với `series_key` | Khóa ngoại tới `meta.source_registry.source_id`. |
| `series_key` | `TEXT` | NOT NULL, UNIQUE ghép với `source_id` | Khóa series; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `series_level` | `TEXT` | NOT NULL, CHECK trong DDL | Grain được khai báo: TRUST_VMP_MONTH, ATC_GROUP_DAY, STORE_PRODUCT_DAY hoặc OTHER. Grain của series không tự mở rộng forecast-run monthly thành daily/weekly. |
| `measure_semantics` | `TEXT` | NOT NULL, CHECK trong DDL | Ngữ nghĩa measure, tách issued/sales/request/fulfilled/unmet. Enum hiện có COMMUNITY_ISSUED_QUANTITY_PROXY không mô tả đúng nguồn Finalised Secondary Care Medicines Data; cần sửa contract/mapping riêng nếu dùng cho SCMD, không tự gọi SCMD là community dispensing. |
| `external_organisation_code` | `TEXT` | NULL cho phép | Mã ngoài tổ chức; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `external_product_code` | `TEXT` | NULL cho phép | Mã ngoài sản phẩm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `product_source_key_id` | `BIGINT` | FK → `core.product_source_key.product_source_key_id`, NULL cho phép | Khóa ngoại tới `core.product_source_key.product_source_key_id`. |
| `product_id` | `BIGINT` | FK → `core.product.product_id`, NULL cho phép | Khóa ngoại tới `core.product.product_id`. |
| `organisation_id` | `BIGINT` | FK → `core.organisation.organisation_id`, NULL cho phép | Khóa ngoại tới `core.organisation.organisation_id`. |
| `location_id` | `BIGINT` | FK → `core.location.location_id`, NULL cho phép | Location của series nếu có mapping được xác lập; không tự tách demand location và fulfillment location của source order. |
| `unit_label` | `TEXT` | NULL cho phép | Nhãn UOM của series/quantity/metric; có thể chưa xác định. |
| `series_description` | `TEXT` | NOT NULL | Mô tả series; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `sales_channel_id` | `BIGINT` | FK → `core.sales_channel.sales_channel_id`, NULL cho phép | Kênh bán của chuỗi khi nguồn/mapping xác lập được; thêm bằng `ALTER TABLE` sau định nghĩa `core.sales_channel`. NULL không có nghĩa mặc định là bán tại quầy. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-core-business_taxonomy_node"></a>
##### `core.business_taxonomy_node`

**Vai trò/grain:** Node của taxonomy nghiệp vụ hoặc danh mục public; scheme không bị trộn. Quan hệ cha–con là FK ghép `(parent_node_id, taxonomy_scheme) → (taxonomy_node_id, taxonomy_scheme)`, nên node cha phải cùng scheme.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `taxonomy_node_id` | `BIGINT` | PK, NOT NULL, UNIQUE ghép với `taxonomy_scheme`, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `parent_node_id` | `BIGINT` | FK → `core.business_taxonomy_node.taxonomy_node_id`, NULL cho phép | Khóa ngoại tới `core.business_taxonomy_node.taxonomy_node_id`. |
| `taxonomy_scheme` | `TEXT` | FK → `core.business_taxonomy_node.taxonomy_scheme`, NOT NULL, UNIQUE ghép với `node_code`, UNIQUE ghép với `taxonomy_node_id`, CHECK trong DDL | Scheme taxonomy; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `node_code` | `TEXT` | NOT NULL, UNIQUE ghép với `taxonomy_scheme` | Mã node; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `node_name` | `TEXT` | NOT NULL | Tên node; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `node_level` | `TEXT` | NOT NULL, CHECK trong DDL | Mức node; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `evidence_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái bằng chứng; miền giá trị phụ thuộc CHECK của bảng. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-core-product_taxonomy_assignment"></a>
##### `core.product_taxonomy_assignment`

**Vai trò/grain:** Quan hệ product–taxonomy có hiệu lực và trạng thái xác minh.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `product_id` | `BIGINT` | PK, FK → `core.product.product_id`, NOT NULL | Khóa ngoại tới `core.product.product_id`. |
| `taxonomy_node_id` | `BIGINT` | PK, FK → `core.business_taxonomy_node.taxonomy_node_id`, NOT NULL | Khóa ngoại tới `core.business_taxonomy_node.taxonomy_node_id`. |
| `valid_from` | `DATE` | PK, NOT NULL | Thông tin hiệu lực from trong bảng `core.product_taxonomy_assignment`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `valid_to` | `DATE` | NULL cho phép | Thông tin hiệu lực to trong bảng `core.product_taxonomy_assignment`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `assignment_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái assignment; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `assigned_by` | `TEXT` | NULL cho phép | Thông tin được gán by trong bảng `core.product_taxonomy_assignment`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-core-sales_channel"></a>
##### `core.sales_channel`

**Vai trò/grain:** Danh mục kênh và trạng thái bằng chứng.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `sales_channel_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `channel_code` | `TEXT` | NOT NULL, UNIQUE | Mã kênh; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `channel_name` | `TEXT` | NOT NULL | Tên kênh; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `evidence_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái bằng chứng; miền giá trị phụ thuộc CHECK của bảng. |
| `source_id` | `BIGINT` | FK → `meta.source_registry.source_id`, NULL cho phép | Khóa ngoại tới `meta.source_registry.source_id`. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)


#### `stg` — Observation theo từng nguồn, giữ lineage và semantics gốc.

<a id="table-stg-issue_observation_monthly"></a>
##### `stg.issue_observation_monthly`

**Vai trò/grain:** Quan sát monthly issued quantity; có thể là proxy demand, không phải latent demand hay tồn kho.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `issue_observation_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `ingestion_run_id` | `BIGINT` | FK → `meta.ingestion_run.ingestion_run_id`, NOT NULL | Khóa ngoại tới `meta.ingestion_run.ingestion_run_id`. |
| `series_id` | `BIGINT` | FK → `core.demand_series.series_id`, NOT NULL, UNIQUE ghép với `measure_code`, `period_month` | Khóa ngoại tới `core.demand_series.series_id`. |
| `period_month` | `DATE` | NOT NULL, UNIQUE ghép với `series_id`, `measure_code`, CHECK trong DDL | Tháng quan sát; CHECK yêu cầu ngày đầu tháng. |
| `measure_code` | `TEXT` | NOT NULL, UNIQUE ghép với `series_id`, `period_month`, DEFAULT `'issued_quantity'` | Mã measure; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `issued_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Lượng issued theo source/series/UOM; DDL hiện chỉ nhận >= 0. SCMD gốc có lượng âm khi điều chỉnh/returns, nên cột này chưa biểu diễn nguyên trạng toàn bộ nguồn; không cắt âm thành 0 hoặc âm thầm bỏ dòng. |
| `unit_label` | `TEXT` | NULL cho phép | Nhãn UOM của series/quantity/metric; có thể chưa xác định. |
| `is_proxy_for_demand` | `BOOLEAN` | NOT NULL, DEFAULT `TRUE` | Cờ khai báo issued được dùng như proxy cho demand; default TRUE không chứng minh proxy phù hợp, không chuyển issued thành sales/consumption/latent demand. |
| `source_row_number` | `BIGINT` | NULL cho phép, CHECK trong DDL | Thông tin nguồn dòng số trong bảng `stg.issue_observation_monthly`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-stg-sales_observation_daily"></a>
##### `stg.sales_observation_daily`

**Vai trò/grain:** Quan sát sales tổng hợp theo ngày/series; không mặc định là POS SKU/cửa hàng.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `sales_observation_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `ingestion_run_id` | `BIGINT` | FK → `meta.ingestion_run.ingestion_run_id`, NOT NULL | Khóa ngoại tới `meta.ingestion_run.ingestion_run_id`. |
| `series_id` | `BIGINT` | FK → `core.demand_series.series_id`, NOT NULL, UNIQUE ghép với `sales_date` | Khóa ngoại tới `core.demand_series.series_id`. |
| `sales_date` | `DATE` | NOT NULL, UNIQUE ghép với `series_id` | Ngày bán hàng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `sales_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Giá trị sales theo grain của series; không tự suy ra SKU/store/UOM. |
| `quantity_unit` | `TEXT` | NULL cho phép | Đơn vị đi kèm quantity; không tự quy đổi nếu chưa có mapping. |
| `source_row_number` | `BIGINT` | NULL cho phép, CHECK trong DDL | Thông tin nguồn dòng số trong bảng `stg.sales_observation_daily`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-stg-retail_demand_request_observation"></a>
##### `stg.retail_demand_request_observation`

**Vai trò/grain:** Quan sát requested, available-at-check, fulfilled và unmet quantities riêng biệt.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `demand_request_observation_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `ingestion_run_id` | `BIGINT` | FK → `meta.ingestion_run.ingestion_run_id`, NOT NULL, UNIQUE ghép với `source_request_line_key` | Khóa ngoại tới `meta.ingestion_run.ingestion_run_id`. |
| `series_id` | `BIGINT` | FK → `core.demand_series.series_id`, NOT NULL | Khóa ngoại tới `core.demand_series.series_id`. |
| `source_request_line_key` | `TEXT` | NOT NULL, UNIQUE ghép với `ingestion_run_id` | Khóa nguồn yêu cầu dòng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `requested_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm yêu cầu; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `requested_quantity` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Lượng khách yêu cầu nếu quan sát, > 0; NULL là chưa biết. Không áp identity chung với fulfilled_quantity và unmet_quantity. |
| `requested_quantity_unit` | `TEXT` | NULL cho phép | Đơn vị yêu cầu số lượng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `availability_checked_at` | `TIMESTAMPTZ` | NULL cho phép | Thời điểm tính sẵn có checked; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `available_quantity_at_request` | `NUMERIC(18,4)` | NULL cho phép | Lượng availability quan sát tại availability_checked_at theo source; phải biết định nghĩa eligibility/UOM. Đây là snapshot một request, không phải balance projection hoặc exposure interval. |
| `available_quantity_unit` | `TEXT` | NULL cho phép | Đơn vị của available_quantity_at_request; không mặc định giống requested/fulfilled/unmet unit khi chưa đối chiếu. |
| `fulfilled_quantity` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Lượng được đáp ứng theo outcome source, >= 0 nếu biết; NULL khác 0 và không tự bằng sales_quantity của bảng khác. |
| `fulfilled_quantity_unit` | `TEXT` | NULL cho phép | Đơn vị đáp ứng số lượng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `unmet_quantity` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Lượng không đáp ứng được ghi nhận trực tiếp nếu có; NULL là không biết. Không suy bằng forecast trừ sales hoặc mặc định requested trừ fulfilled. |
| `unmet_quantity_unit` | `TEXT` | NULL cho phép | Đơn vị chưa đáp ứng số lượng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `resolved_at` | `TIMESTAMPTZ` | NULL cho phép | Thời điểm resolved; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `availability_observation` | `TEXT` | NULL cho phép | Mô tả availability khi kiểm tra; không tự chứng minh fulfillment. |
| `outcome_observation` | `TEXT` | NULL cho phép | Mô tả outcome từ source; đọc cùng fulfilled/unmet quantity. |
| `unmet_reason_observation` | `TEXT` | NULL cho phép | Lý do unmet nếu source ghi; không suy đoán khi thiếu. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `source_row_number` | `BIGINT` | NULL cho phép, CHECK trong DDL | Thông tin nguồn dòng số trong bảng `stg.retail_demand_request_observation`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `source_locator` | `TEXT` | NOT NULL | Locator để tìm lại evidence/source record. |
| `evidence_ref` | `TEXT` | NULL cho phép | Tham chiếu evidence theo pipeline contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-stg-medicaid_utilization_observation_quarterly"></a>
##### `stg.medicaid_utilization_observation_quarterly`

**Vai trò/grain:** Record utilization/reimbursement Medicaid theo bang/NDC/quý; không phải sales của một cửa hàng.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `medicaid_observation_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `ingestion_run_id` | `BIGINT` | FK → `meta.ingestion_run.ingestion_run_id`, NOT NULL, UNIQUE ghép với `source_row_number` | Khóa ngoại tới `meta.ingestion_run.ingestion_run_id`. |
| `source_row_number` | `BIGINT` | NOT NULL, UNIQUE ghép với `ingestion_run_id`, CHECK trong DDL | Thông tin nguồn dòng số trong bảng `stg.medicaid_utilization_observation_quarterly`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `utilization_type` | `TEXT` | NOT NULL, CHECK trong DDL | Loại sử dụng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `state_code` | `CHAR(2)` | NOT NULL | Mã bang; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `ndc_code` | `CHAR(11)` | NOT NULL | National Drug Code trong Medicaid; không tự map sang SKU PharmaFlow. |
| `labeler_code` | `TEXT` | NULL cho phép | Mã labeler; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `product_code` | `TEXT` | NULL cho phép | Mã sản phẩm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `package_size` | `TEXT` | NULL cho phép | Kích thước bao gói theo source; đơn vị phụ thuộc contract nguồn. |
| `report_year` | `SMALLINT` | NOT NULL, CHECK trong DDL | Thông tin báo cáo năm trong bảng `stg.medicaid_utilization_observation_quarterly`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `report_quarter` | `SMALLINT` | NOT NULL, CHECK trong DDL | Thông tin báo cáo quý trong bảng `stg.medicaid_utilization_observation_quarterly`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `suppression_code` | `TEXT` | NULL cho phép | Mã ẩn; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `reported_product_name` | `TEXT` | NULL cho phép | Tên reported sản phẩm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `units_reimbursed` | `NUMERIC(20,4)` | NULL cho phép | Số đơn vị được báo cáo/hoàn trả trong Medicaid; không phải on-hand inventory. |
| `unit_type` | `TEXT` | NULL cho phép | Loại đơn vị; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `reported_prescriptions` | `NUMERIC(20,4)` | NULL cho phép | Số prescription được báo cáo trong Medicaid; không phải số SKU bán. |
| `total_reimbursed_amount` | `NUMERIC(20,2)` | NULL cho phép | Giá trị tiền tổng hoàn trả; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `medicaid_reimbursed_amount` | `NUMERIC(20,2)` | NULL cho phép | Giá trị tiền Medicaid hoàn trả; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `non_medicaid_reimbursed_amount` | `NUMERIC(20,2)` | NULL cho phép | Giá trị tiền ngoài Medicaid hoàn trả; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `currency_code` | `CHAR(3)` | NOT NULL, DEFAULT `'USD'` | Mã tiền tệ; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-stg-longchau_product_observation"></a>
##### `stg.longchau_product_observation`

**Vai trò/grain:** Snapshot trang sản phẩm public tại thời điểm crawl; giá/availability không phải POS/inventory.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `product_observation_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `ingestion_run_id` | `BIGINT` | FK → `meta.ingestion_run.ingestion_run_id`, NOT NULL | Khóa ngoại tới `meta.ingestion_run.ingestion_run_id`. |
| `product_source_key_id` | `BIGINT` | FK → `core.product_source_key.product_source_key_id`, NOT NULL | Khóa ngoại tới `core.product_source_key.product_source_key_id`. |
| `observed_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm quan sát snapshot/source record. |
| `public_title` | `TEXT` | NOT NULL | Tiêu đề công khai; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `public_price_amount` | `NUMERIC(18,2)` | NULL cho phép, CHECK trong DDL | Giá public tại thời điểm snapshot; không phải giá POS, giá mua hay supplier cost. |
| `public_currency_code` | `CHAR(3)` | NULL cho phép | Mã công khai tiền tệ; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `public_brand_label` | `TEXT` | NULL cho phép | Nhãn công khai brand; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `public_manufacturer_label` | `TEXT` | NULL cho phép | Nhãn công khai nhà sản xuất; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `raw_snapshot_uri` | `TEXT` | NOT NULL | URI của capture thô liên quan. |
| `content_sha256` | `CHAR(64)` | NULL cho phép | SHA-256 của content snapshot liên quan. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-stg-product_category_observation"></a>
##### `stg.product_category_observation`

**Vai trò/grain:** Category node theo đường dẫn sản phẩm, giữ vị trí và mapping status. Cặp `(taxonomy_node_id, taxonomy_scheme)` tham chiếu ghép tới node taxonomy để giữ đúng scheme.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `product_observation_id` | `BIGINT` | PK, FK → `stg.longchau_product_observation.product_observation_id`, NOT NULL | Khóa ngoại tới `stg.longchau_product_observation.product_observation_id`. |
| `path_position` | `SMALLINT` | PK, NOT NULL, CHECK trong DDL | Thông tin đường dẫn vị trí trong bảng `stg.product_category_observation`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `public_category_label` | `TEXT` | NOT NULL | Nhãn công khai danh mục; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `public_category_slug` | `TEXT` | NULL cho phép | Slug category lấy từ đường dẫn/nguồn công khai; giữ nguyên để truy vết, không tự xem là taxonomy code đã chuẩn hóa. |
| `taxonomy_node_id` | `BIGINT` | FK → `core.business_taxonomy_node.taxonomy_node_id`, NULL cho phép | Khóa ngoại tới `core.business_taxonomy_node.taxonomy_node_id`. |
| `taxonomy_scheme` | `TEXT` | FK → `core.business_taxonomy_node.taxonomy_scheme`, NOT NULL, DEFAULT `'LONGCHAU_PUBLIC'`, CHECK trong DDL | Scheme taxonomy; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `mapping_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái mapping; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-stg-product_observation_attribute"></a>
##### `stg.product_observation_attribute`

**Vai trò/grain:** Thuộc tính thưa tên–giá trị của product observation.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `product_observation_id` | `BIGINT` | PK, FK → `stg.longchau_product_observation.product_observation_id`, NOT NULL | Khóa ngoại tới `stg.longchau_product_observation.product_observation_id`. |
| `attribute_name` | `TEXT` | PK, NOT NULL | Tên thuộc tính; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `attribute_value` | `TEXT` | NOT NULL | Giá trị thuộc tính; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-stg-longchau_store_observation"></a>
##### `stg.longchau_store_observation`

**Vai trò/grain:** Thông tin địa điểm public theo snapshot; không chứng minh trạng thái/tồn kho nội bộ.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `store_observation_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `ingestion_run_id` | `BIGINT` | FK → `meta.ingestion_run.ingestion_run_id`, NOT NULL | Khóa ngoại tới `meta.ingestion_run.ingestion_run_id`. |
| `location_id` | `BIGINT` | FK → `core.location.location_id`, NULL cho phép | Khóa ngoại tới `core.location.location_id`. |
| `external_store_code` | `TEXT` | NULL cho phép | Mã ngoài cửa hàng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `public_name` | `TEXT` | NOT NULL | Tên công khai; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `public_address` | `TEXT` | NULL cho phép | Địa chỉ public được quan sát; không phải bằng chứng tồn kho/giao dịch. |
| `public_opening_hours_text` | `TEXT` | NULL cho phép | Giờ mở cửa dạng text hiển thị trên trang; không xác nhận lịch hiện hành. |
| `public_source_url` | `TEXT` | NOT NULL | URL trang public quan sát. |
| `observed_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm quan sát snapshot/source record. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-stg-inventory_quality_event_observation"></a>
##### `stg.inventory_quality_event_observation`

**Vai trò/grain:** Observation sự kiện chất lượng với provenance/locator, không tự thành transaction tồn.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `quality_observation_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `ingestion_run_id` | `BIGINT` | FK → `meta.ingestion_run.ingestion_run_id`, NOT NULL, UNIQUE ghép với `source_event_key` | Khóa ngoại tới `meta.ingestion_run.ingestion_run_id`. |
| `source_event_key` | `TEXT` | NOT NULL, UNIQUE ghép với `ingestion_run_id` | Khóa nguồn event; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `event_action` | `TEXT` | NOT NULL | Thông tin event hành động trong bảng `stg.inventory_quality_event_observation`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `event_description` | `TEXT` | NULL cho phép | Mô tả event; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `product_id` | `BIGINT` | FK → `core.product.product_id`, NULL cho phép | Khóa ngoại tới `core.product.product_id`. |
| `location_id` | `BIGINT` | FK → `core.location.location_id`, NULL cho phép | Khóa ngoại tới `core.location.location_id`. |
| `source_lot_code` | `TEXT` | NULL cho phép | Mã nguồn lô; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `occurred_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm sự kiện/giao dịch xảy ra theo record. |
| `affected_quantity` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Số lượng bị ảnh hưởng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `quantity_unit` | `TEXT` | NULL cho phép | Đơn vị đi kèm quantity; không tự quy đổi nếu chưa có mapping. |
| `actor_description` | `TEXT` | NULL cho phép | Mô tả actor từ evidence nếu có; không phải FK tới hệ thống phân quyền. |
| `authorization_reference` | `TEXT` | NULL cho phép | Tham chiếu bằng chứng authorization; CHECK chỉ đòi NOT NULL cho action RELEASE_TO_SALEABLE_STOCK. Không tự xác minh actor có thẩm quyền hoặc chứng minh tồn đã được release. |
| `decision_basis` | `TEXT` | NULL cho phép | Căn cứ quyết định; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `evidence_ref` | `TEXT` | NULL cho phép | Tham chiếu evidence theo pipeline contract. |
| `source_locator` | `TEXT` | NOT NULL | Locator để tìm lại evidence/source record. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `source_row_number` | `BIGINT` | NULL cho phép, CHECK trong DDL | Thông tin nguồn dòng số trong bảng `stg.inventory_quality_event_observation`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-stg-recall_notice_observation"></a>
##### `stg.recall_notice_observation`

**Vai trò/grain:** Thông báo thu hồi theo nguồn và evidence.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `recall_notice_observation_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `ingestion_run_id` | `BIGINT` | FK → `meta.ingestion_run.ingestion_run_id`, NOT NULL, UNIQUE ghép với `source_notice_key` | Khóa ngoại tới `meta.ingestion_run.ingestion_run_id`. |
| `source_notice_key` | `TEXT` | NOT NULL, UNIQUE ghép với `ingestion_run_id` | Khóa nguồn thông báo; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `notice_issuer` | `TEXT` | NULL cho phép | Thông tin thông báo đơn vị phát hành trong bảng `stg.recall_notice_observation`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `notice_reference` | `TEXT` | NULL cho phép | Tham chiếu thông báo; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `notice_published_at` | `TIMESTAMPTZ` | NULL cho phép | Thời điểm thông báo công bố; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `notice_description` | `TEXT` | NOT NULL | Mô tả thông báo; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `source_locator` | `TEXT` | NOT NULL | Locator để tìm lại evidence/source record. |
| `evidence_ref` | `TEXT` | NULL cho phép | Tham chiếu evidence theo pipeline contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `source_row_number` | `BIGINT` | NULL cho phép, CHECK trong DDL | Thông tin nguồn dòng số trong bảng `stg.recall_notice_observation`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-stg-recall_scope_observation"></a>
##### `stg.recall_scope_observation`

**Vai trò/grain:** Phạm vi sản phẩm/lô được nêu trong recall notice.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `recall_scope_observation_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `recall_notice_observation_id` | `BIGINT` | FK → `stg.recall_notice_observation.recall_notice_observation_id`, NOT NULL, UNIQUE ghép với `source_scope_key` | Khóa ngoại tới `stg.recall_notice_observation.recall_notice_observation_id`. |
| `source_scope_key` | `TEXT` | NOT NULL, UNIQUE ghép với `recall_notice_observation_id` | Khóa nguồn phạm vi; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `product_id` | `BIGINT` | FK → `core.product.product_id`, NULL cho phép | Khóa ngoại tới `core.product.product_id`. |
| `product_description` | `TEXT` | NULL cho phép | Mô tả sản phẩm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `source_lot_code` | `TEXT` | NULL cho phép | Mã nguồn lô; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `affected_quantity` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Số lượng bị ảnh hưởng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `quantity_unit` | `TEXT` | NULL cho phép | Đơn vị đi kèm quantity; không tự quy đổi nếu chưa có mapping. |
| `scope_description` | `TEXT` | NOT NULL | Mô tả phạm vi; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `source_locator` | `TEXT` | NOT NULL | Locator để tìm lại evidence/source record. |
| `evidence_ref` | `TEXT` | NULL cho phép | Tham chiếu evidence theo pipeline contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-stg-recall_reconciliation_observation"></a>
##### `stg.recall_reconciliation_observation`

**Vai trò/grain:** Báo cáo đối soát lượng giao/thu hồi tại một thời điểm.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `recall_reconciliation_observation_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `ingestion_run_id` | `BIGINT` | FK → `meta.ingestion_run.ingestion_run_id`, NOT NULL, UNIQUE ghép với `source_report_key` | Khóa ngoại tới `meta.ingestion_run.ingestion_run_id`. |
| `recall_notice_observation_id` | `BIGINT` | FK → `stg.recall_notice_observation.recall_notice_observation_id`, NULL cho phép | Khóa ngoại tới `stg.recall_notice_observation.recall_notice_observation_id`. |
| `recall_scope_observation_id` | `BIGINT` | FK → `stg.recall_scope_observation.recall_scope_observation_id`, NULL cho phép | Khóa ngoại tới `stg.recall_scope_observation.recall_scope_observation_id`. |
| `source_report_key` | `TEXT` | NOT NULL, UNIQUE ghép với `ingestion_run_id` | Khóa nguồn báo cáo; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `as_of` | `TIMESTAMPTZ` | NOT NULL | Thông tin tại of trong bảng `stg.recall_reconciliation_observation`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `quantity_delivered` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Lượng được báo cáo đã giao. |
| `delivered_quantity_unit` | `TEXT` | NULL cho phép | Đơn vị đã giao số lượng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `quantity_recovered` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Lượng được báo cáo đã thu hồi. |
| `recovered_quantity_unit` | `TEXT` | NULL cho phép | Đơn vị đã thu hồi số lượng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `reported_by` | `TEXT` | NULL cho phép | Thông tin reported by trong bảng `stg.recall_reconciliation_observation`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `source_locator` | `TEXT` | NOT NULL | Locator để tìm lại evidence/source record. |
| `evidence_ref` | `TEXT` | NULL cho phép | Tham chiếu evidence theo pipeline contract. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-stg-store_admin_area_observation"></a>
##### `stg.store_admin_area_observation`

**Vai trò/grain:** Một cấp hành chính trong đường địa chỉ cửa hàng; path_position giữ thứ tự.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `store_observation_id` | `BIGINT` | PK, FK → `stg.longchau_store_observation.store_observation_id`, NOT NULL | Khóa ngoại tới `stg.longchau_store_observation.store_observation_id`. |
| `path_position` | `SMALLINT` | PK, NOT NULL, CHECK trong DDL | Thông tin đường dẫn vị trí trong bảng `stg.store_admin_area_observation`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `administrative_level` | `TEXT` | NULL cho phép | Mức hành chính; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `area_name` | `TEXT` | NOT NULL | Tên khu vực; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)


#### `mart` — Định nghĩa KPI, dimension và ownership.

<a id="table-mart-kpi_definition"></a>
##### `mart.kpi_definition`

**Vai trò/grain:** Định nghĩa KPI, quality layer, công thức, đơn vị, grain và caveat.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `kpi_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `kpi_code` | `TEXT` | NOT NULL, UNIQUE | Mã KPI; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `kpi_name` | `TEXT` | NOT NULL | Tên KPI; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `quality_layer` | `TEXT` | NOT NULL, CHECK trong DDL | Lớp KPI: PREDICTION, OPERATIONAL, DECISION hoặc DATA_QUALITY. Bảng kết quả phải dùng KPI đúng lớp; FK đơn tới kpi_id chưa tự kiểm tra sự phù hợp này. |
| `formula_definition` | `TEXT` | NOT NULL | Mô tả công thức KPI; không phải kết quả KPI. |
| `unit_code` | `TEXT` | NOT NULL | Mã đơn vị; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `temporal_grain` | `TEXT` | NOT NULL | Grain thời gian của định nghĩa KPI, ví dụ ngày/tháng theo contract cụ thể; phải khớp grain dữ liệu và kỳ đo. |
| `data_availability` | `TEXT` | NOT NULL, CHECK trong DDL | Mức bằng chứng dữ liệu: OBSERVED, PARTIAL, SYNTHETIC_ONLY, NOT_OBSERVED hoặc PLANNED; không phải cờ KPI đang tính thành công. |
| `caveat` | `TEXT` | NOT NULL | Thông tin cảnh báo trong bảng `mart.kpi_definition`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-mart-kpi_dimension_scope"></a>
##### `mart.kpi_dimension_scope`

**Vai trò/grain:** Dimension áp dụng cho KPI và tình trạng dữ liệu tương ứng.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `kpi_id` | `BIGINT` | PK, FK → `mart.kpi_definition.kpi_id`, NOT NULL | Khóa ngoại tới `mart.kpi_definition.kpi_id`. |
| `dimension_code` | `TEXT` | PK, NOT NULL, CHECK trong DDL | Mã dimension; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `availability_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái tính sẵn có; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `scope_note` | `TEXT` | NOT NULL | Ghi chú phạm vi; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-mart-organizational_unit"></a>
##### `mart.organizational_unit`

**Vai trò/grain:** Đơn vị tổ chức để quản lý KPI ownership; có thể còn proposed.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `organizational_unit_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `parent_unit_id` | `BIGINT` | FK → `mart.organizational_unit.organizational_unit_id`, NULL cho phép, UNIQUE ghép với `unit_name` | Khóa ngoại tới `mart.organizational_unit.organizational_unit_id`. |
| `unit_name` | `TEXT` | NOT NULL, UNIQUE ghép với `parent_unit_id` | Tên đơn vị; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `unit_type` | `TEXT` | NOT NULL, CHECK trong DDL | Loại đơn vị; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `confirmation_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái xác nhận; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-mart-kpi_owner_assignment"></a>
##### `mart.kpi_owner_assignment`

**Vai trò/grain:** Phân công role KPI cùng trạng thái và khoảng hiệu lực.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `owner_assignment_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `kpi_id` | `BIGINT` | FK → `mart.kpi_definition.kpi_id`, NOT NULL | Khóa ngoại tới `mart.kpi_definition.kpi_id`. |
| `organizational_unit_id` | `BIGINT` | FK → `mart.organizational_unit.organizational_unit_id`, NOT NULL | Khóa ngoại tới `mart.organizational_unit.organizational_unit_id`. |
| `responsible_role` | `TEXT` | NOT NULL | Thông tin chịu trách nhiệm vai trò trong bảng `mart.kpi_owner_assignment`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `accountability_type` | `TEXT` | NOT NULL, CHECK trong DDL | Loại trách nhiệm; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `assignment_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái assignment; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `valid_from` | `DATE` | NOT NULL | Thông tin hiệu lực from trong bảng `mart.kpi_owner_assignment`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `valid_to` | `DATE` | NULL cho phép | Thông tin hiệu lực to trong bảng `mart.kpi_owner_assignment`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)


#### `model` — Forecast run, forecast point và đánh giá dự báo.

<a id="table-model-forecast_run"></a>
##### `model.forecast_run`

**Vai trò/grain:** Một lần chạy forecast cùng cutoff, horizon, provenance và leakage review.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `forecast_run_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `model_name` | `TEXT` | NOT NULL | Tên mô hình; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `model_version` | `TEXT` | NOT NULL | Thông tin mô hình phiên bản trong bảng `model.forecast_run`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `data_origin` | `TEXT` | NOT NULL, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `training_cutoff_month` | `DATE` | NOT NULL | Tháng cutoff train, bắt buộc ngày đầu tháng. Lưu mốc chưa tự chứng minh toàn bộ train/features chống temporal leakage. |
| `feature_data_cutoff_at` | `TIMESTAMPTZ` | NOT NULL | Mốc cutoff feature, phải trước horizon_start_month theo CHECK. Pipeline còn phải kiểm tra thời điểm dữ liệu thực sự sẵn có, không chỉ event time. |
| `horizon_start_month` | `DATE` | NOT NULL | Tháng bắt đầu horizon, ngày đầu tháng và sau training_cutoff_month; contract run hiện hướng monthly. |
| `horizon_end_month` | `DATE` | NOT NULL | Tháng cuối horizon, ngày đầu tháng và không trước horizon_start_month; chưa phải contract horizon theo ngày/tuần. |
| `dataset_checksum_sha256` | `CHAR(64)` | NULL cho phép | Checksum dataset input của forecast run để truy vết. |
| `leakage_check_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái temporal leakage review; UNREVIEWED không phải PASS. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm tạo bản ghi. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-model-forecast_run_parameter"></a>
##### `model.forecast_run_parameter`

**Vai trò/grain:** Tham số name–value của forecast run.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `forecast_run_id` | `BIGINT` | PK, FK → `model.forecast_run.forecast_run_id`, NOT NULL | Khóa ngoại tới `model.forecast_run.forecast_run_id`. |
| `parameter_name` | `TEXT` | PK, NOT NULL | Tên tham số; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `parameter_value` | `TEXT` | NOT NULL | Giá trị tham số; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-model-forecast_point"></a>
##### `model.forecast_point`

**Vai trò/grain:** Một giá trị dự báo cho series/kỳ mục tiêu, tùy chọn khoảng/quantile.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `forecast_point_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `forecast_run_id` | `BIGINT` | FK → `model.forecast_run.forecast_run_id`, NOT NULL, UNIQUE ghép với `series_id`, `target_period_start` | Khóa ngoại tới `model.forecast_run.forecast_run_id`. |
| `series_id` | `BIGINT` | FK → `core.demand_series.series_id`, NOT NULL, UNIQUE ghép với `forecast_run_id`, `target_period_start` | Khóa ngoại tới `core.demand_series.series_id`. |
| `target_period_start` | `DATE` | NOT NULL, UNIQUE ghép với `forecast_run_id`, `series_id` | Ngày bắt đầu kỳ dự báo của series. DDL chưa kiểm tra point nằm trong horizon của forecast_run hoặc khớp grain series. |
| `predicted_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Lượng dự báo không âm cho series/kỳ; cần đọc cùng point_statistic, unit và measure_semantics, không mặc định là latent demand. |
| `point_statistic` | `TEXT` | NOT NULL, DEFAULT `'UNSPECIFIED'`, CHECK trong DDL | Loại thống kê điểm forecast như mean/median; UNSPECIFIED nếu chưa nêu. |
| `lower_bound_quantity` | `NUMERIC(18,4)` | NULL cho phép | Cận dưới forecast nếu có. |
| `upper_bound_quantity` | `NUMERIC(18,4)` | NULL cho phép | Cận trên forecast nếu có. |
| `lower_quantile_level` | `NUMERIC(6,5)` | NULL cho phép, CHECK trong DDL | Mức xác suất của cận dưới trong [0,1], đi cặp lower_bound_quantity; không phải độ chính xác mô hình. |
| `upper_quantile_level` | `NUMERIC(6,5)` | NULL cho phép, CHECK trong DDL | Mức xác suất của cận trên trong [0,1], đi cặp upper_bound_quantity và lớn hơn mức dưới khi có cả hai. |
| `unit_label` | `TEXT` | NULL cho phép | Nhãn UOM của series/quantity/metric; có thể chưa xác định. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-model-forecast_evaluation"></a>
##### `model.forecast_evaluation`

**Vai trò/grain:** Metric đánh giá forecast theo protocol và khoảng thời gian.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `forecast_evaluation_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `forecast_run_id` | `BIGINT` | FK → `model.forecast_run.forecast_run_id`, NOT NULL, UNIQUE ghép với `series_id`, `kpi_id`, `evaluation_start`, `evaluation_end` | Khóa ngoại tới `model.forecast_run.forecast_run_id`. |
| `series_id` | `BIGINT` | FK → `core.demand_series.series_id`, NOT NULL, UNIQUE ghép với `forecast_run_id`, `kpi_id`, `evaluation_start`, `evaluation_end` | Khóa ngoại tới `core.demand_series.series_id`. |
| `kpi_id` | `BIGINT` | FK → `mart.kpi_definition.kpi_id`, NOT NULL, UNIQUE ghép với `forecast_run_id`, `series_id`, `evaluation_start`, `evaluation_end` | Khóa ngoại tới `mart.kpi_definition.kpi_id`. |
| `evaluation_source_id` | `BIGINT` | FK → `meta.source_registry.source_id`, NOT NULL | Khóa ngoại tới `meta.source_registry.source_id`. |
| `evaluation_start` | `DATE` | NOT NULL, UNIQUE ghép với `forecast_run_id`, `series_id`, `kpi_id`, `evaluation_end` | Thông tin đánh giá start trong bảng `model.forecast_evaluation`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `evaluation_end` | `DATE` | NOT NULL, UNIQUE ghép với `forecast_run_id`, `series_id`, `kpi_id`, `evaluation_start` | Thông tin đánh giá end trong bảng `model.forecast_evaluation`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `evaluation_protocol` | `TEXT` | NOT NULL, CHECK trong DDL | HOLDOUT, ROLLING_ORIGIN, OTHER hoặc UNSPECIFIED theo DDL; ghi tên protocol không thay thế kết quả kiểm chứng cách chia train/test. |
| `evaluation_origin_count` | `INTEGER` | NOT NULL, CHECK trong DDL | Số forecast origins được dùng để đánh giá, > 0; không phải số SKU, số test points hay số lần huấn luyện mặc định. |
| `metric_definition_snapshot` | `TEXT` | NOT NULL | Snapshot định nghĩa metric tại thời điểm evaluation. |
| `metric_value` | `NUMERIC(20,6)` | NOT NULL | Giá trị KPI/metric; đọc cùng unit và định nghĩa KPI. |
| `evaluated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm ghi nhận evaluation. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)


#### `sim` — Kịch bản synthetic, tồn/mua/điều chuyển mô phỏng và khuyến nghị.

<a id="table-sim-scenario_registry"></a>
##### `sim.scenario_registry`

**Vai trò/grain:** Đăng ký kịch bản/version/seed; dữ liệu mô phỏng được gắn provenance.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `scenario_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `scenario_key` | `TEXT` | NOT NULL, UNIQUE | Khóa kịch bản; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `scenario_name` | `TEXT` | NOT NULL | Tên kịch bản; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `source_id` | `BIGINT` | FK → `meta.source_registry.source_id`, NULL cho phép | Khóa ngoại tới `meta.source_registry.source_id`. |
| `scenario_version` | `TEXT` | NOT NULL | Thông tin kịch bản phiên bản trong bảng `sim.scenario_registry`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `random_seed` | `BIGINT` | NULL cho phép | Thông tin ngẫu nhiên seed trong bảng `sim.scenario_registry`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `data_origin` | `TEXT` | NOT NULL, DEFAULT `'SYNTHETIC'`, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm tạo bản ghi. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-scenario_assumption"></a>
##### `sim.scenario_assumption`

**Vai trò/grain:** Một giả định cấu hình scenario và đơn vị của nó.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `scenario_id` | `BIGINT` | PK, FK → `sim.scenario_registry.scenario_id`, NOT NULL | Khóa ngoại tới `sim.scenario_registry.scenario_id`. |
| `assumption_name` | `TEXT` | PK, NOT NULL | Tên giả định; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `assumption_value` | `TEXT` | NOT NULL | Giá trị giả định; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `unit_label` | `TEXT` | NULL cho phép | Nhãn UOM của series/quantity/metric; có thể chưa xác định. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-demand_request"></a>
##### `sim.demand_request`

**Vai trò/grain:** Nhu cầu theo ngày × location × product trong simulation; request/fulfilled/unmet tách riêng.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `demand_request_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `scenario_id` | `BIGINT` | FK → `sim.scenario_registry.scenario_id`, NOT NULL, UNIQUE ghép với `location_id`, `product_id`, `demand_date` | Khóa ngoại tới `sim.scenario_registry.scenario_id`. |
| `location_id` | `BIGINT` | FK → `core.location.location_id`, NOT NULL, UNIQUE ghép với `scenario_id`, `product_id`, `demand_date` | Khóa ngoại tới `core.location.location_id`. |
| `product_id` | `BIGINT` | FK → `core.product.product_id`, NOT NULL, UNIQUE ghép với `scenario_id`, `location_id`, `demand_date` | Khóa ngoại tới `core.product.product_id`. |
| `demand_date` | `DATE` | NOT NULL, UNIQUE ghép với `scenario_id`, `location_id`, `product_id` | Ngày demand; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `anchor_issue_observation_id` | `BIGINT` | FK → `stg.issue_observation_monthly.issue_observation_id`, NULL cho phép | Khóa ngoại tới `stg.issue_observation_monthly.issue_observation_id`. |
| `forecast_point_id` | `BIGINT` | FK → `model.forecast_point.forecast_point_id`, NULL cho phép | Khóa ngoại tới `model.forecast_point.forecast_point_id`. |
| `demand_request_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Lượng nhu cầu được yêu cầu trước khi giới hạn bởi khả năng đáp ứng. |
| `fulfilled_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Phần lượng yêu cầu đã đáp ứng; không gộp với request/unmet. |
| `unmet_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Phần lượng yêu cầu chưa đáp ứng; không gộp với fulfilled. |
| `data_origin` | `TEXT` | NOT NULL, DEFAULT `'SYNTHETIC'`, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-supplier"></a>
##### `sim.supplier`

**Vai trò/grain:** Nhà cung cấp tham chiếu trong simulation, có evidence status.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `supplier_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `source_id` | `BIGINT` | FK → `meta.source_registry.source_id`, NULL cho phép, UNIQUE ghép với `external_supplier_code` | Khóa ngoại tới `meta.source_registry.source_id`. |
| `external_supplier_code` | `TEXT` | NULL cho phép, UNIQUE ghép với `source_id` | Mã ngoài nhà cung cấp; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `supplier_name` | `TEXT` | NOT NULL | Tên nhà cung cấp; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `evidence_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái bằng chứng; miền giá trị phụ thuộc CHECK của bảng. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-simulated_purchase_order"></a>
##### `sim.simulated_purchase_order`

**Vai trò/grain:** Đơn mua giả lập; không phải PO thực.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `simulated_purchase_order_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `scenario_id` | `BIGINT` | FK → `sim.scenario_registry.scenario_id`, NOT NULL, UNIQUE ghép với `simulated_order_ref` | Khóa ngoại tới `sim.scenario_registry.scenario_id`. |
| `supplier_id` | `BIGINT` | FK → `sim.supplier.supplier_id`, NOT NULL | Khóa ngoại tới `sim.supplier.supplier_id`. |
| `destination_location_id` | `BIGINT` | FK → `core.location.location_id`, NOT NULL | Khóa ngoại tới `core.location.location_id`. |
| `simulated_order_ref` | `TEXT` | NOT NULL, UNIQUE ghép với `scenario_id` | Tham chiếu mô phỏng đơn hàng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `ordered_at` | `DATE` | NOT NULL | Thời điểm đặt đơn. |
| `expected_delivery_date` | `DATE` | NULL cho phép | Ngày giao dự kiến; không chứng minh đã nhận. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-simulated_purchase_order_line"></a>
##### `sim.simulated_purchase_order_line`

**Vai trò/grain:** Dòng hàng/lượng/chi phí giả lập của PO.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `simulated_purchase_order_line_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `simulated_purchase_order_id` | `BIGINT` | FK → `sim.simulated_purchase_order.simulated_purchase_order_id`, NOT NULL, UNIQUE ghép với `line_number` | Khóa ngoại tới `sim.simulated_purchase_order.simulated_purchase_order_id`. |
| `line_number` | `INTEGER` | NOT NULL, UNIQUE ghép với `simulated_purchase_order_id`, CHECK trong DDL | Thông tin dòng số trong bảng `sim.simulated_purchase_order_line`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `product_id` | `BIGINT` | FK → `core.product.product_id`, NOT NULL | Khóa ngoại tới `core.product.product_id`. |
| `ordered_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Số lượng đặt; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `simulated_unit_cost` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Chi phí đơn vị giả lập trong scenario. |
| `currency_code` | `CHAR(3)` | NULL cho phép | Mã tiền tệ; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-simulated_goods_receipt"></a>
##### `sim.simulated_goods_receipt`

**Vai trò/grain:** Phần đầu lần nhận giả lập.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `simulated_goods_receipt_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `simulated_purchase_order_id` | `BIGINT` | FK → `sim.simulated_purchase_order.simulated_purchase_order_id`, NOT NULL, UNIQUE ghép với `receipt_reference` | Khóa ngoại tới `sim.simulated_purchase_order.simulated_purchase_order_id`. |
| `receipt_reference` | `TEXT` | NOT NULL, UNIQUE ghép với `simulated_purchase_order_id` | Tham chiếu nhận hàng; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `received_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm nhận hàng/receipt. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-simulated_goods_receipt_line"></a>
##### `sim.simulated_goods_receipt_line`

**Vai trò/grain:** Dòng nhận giả lập theo order line/lô.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `simulated_goods_receipt_line_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `simulated_goods_receipt_id` | `BIGINT` | FK → `sim.simulated_goods_receipt.simulated_goods_receipt_id`, NOT NULL, UNIQUE ghép với `line_number` | Khóa ngoại tới `sim.simulated_goods_receipt.simulated_goods_receipt_id`. |
| `simulated_purchase_order_line_id` | `BIGINT` | FK → `sim.simulated_purchase_order_line.simulated_purchase_order_line_id`, NOT NULL | Khóa ngoại tới `sim.simulated_purchase_order_line.simulated_purchase_order_line_id`. |
| `line_number` | `INTEGER` | NOT NULL, UNIQUE ghép với `simulated_goods_receipt_id`, CHECK trong DDL | Thông tin dòng số trong bảng `sim.simulated_goods_receipt_line`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `batch_code` | `TEXT` | NOT NULL | Mã lô; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `received_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Ở goods_receipt_line source: generated = accepted + rejected; ở bảng receipt mô phỏng: lượng nhận ghi cho dòng. |
| `expiry_date` | `DATE` | NULL cho phép | Ngày hết hạn nếu biết; NULL nghĩa là chưa có ngày xác nhận, không có nghĩa còn hạn. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-inventory_lot"></a>
##### `sim.inventory_lot`

**Vai trò/grain:** Lô tồn kho thuộc scenario/location/product.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `inventory_lot_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `scenario_id` | `BIGINT` | FK → `sim.scenario_registry.scenario_id`, NOT NULL, UNIQUE ghép với `product_id`, `location_id`, `batch_code` | Khóa ngoại tới `sim.scenario_registry.scenario_id`. |
| `product_id` | `BIGINT` | FK → `core.product.product_id`, NOT NULL, UNIQUE ghép với `scenario_id`, `location_id`, `batch_code` | Khóa ngoại tới `core.product.product_id`. |
| `location_id` | `BIGINT` | FK → `core.location.location_id`, NOT NULL, UNIQUE ghép với `scenario_id`, `product_id`, `batch_code` | Khóa ngoại tới `core.location.location_id`. |
| `batch_code` | `TEXT` | NOT NULL, UNIQUE ghép với `scenario_id`, `product_id`, `location_id` | Mã lô; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `received_date` | `DATE` | NULL cho phép | Ngày nhận; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `expiry_date` | `DATE` | NULL cho phép | Ngày hết hạn nếu biết; NULL nghĩa là chưa có ngày xác nhận, không có nghĩa còn hạn. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-stock_transfer"></a>
##### `sim.stock_transfer`

**Vai trò/grain:** Điều chuyển mô phỏng giữa locations.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `stock_transfer_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `scenario_id` | `BIGINT` | FK → `sim.scenario_registry.scenario_id`, NOT NULL, UNIQUE ghép với `transfer_reference` | Khóa ngoại tới `sim.scenario_registry.scenario_id`. |
| `transfer_reference` | `TEXT` | NOT NULL, UNIQUE ghép với `scenario_id` | Tham chiếu điều chuyển; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `source_location_id` | `BIGINT` | FK → `core.location.location_id`, NOT NULL | Khóa ngoại tới `core.location.location_id`. |
| `destination_location_id` | `BIGINT` | FK → `core.location.location_id`, NOT NULL | Khóa ngoại tới `core.location.location_id`. |
| `planned_dispatch_date` | `DATE` | NULL cho phép | Ngày planned gửi; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `transfer_status` | `TEXT` | NOT NULL, CHECK trong DDL | Trạng thái điều chuyển; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-stock_transfer_line"></a>
##### `sim.stock_transfer_line`

**Vai trò/grain:** Dòng product/lô/lượng của simulated transfer.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `stock_transfer_line_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `stock_transfer_id` | `BIGINT` | FK → `sim.stock_transfer.stock_transfer_id`, NOT NULL, UNIQUE ghép với `line_number` | Khóa ngoại tới `sim.stock_transfer.stock_transfer_id`. |
| `line_number` | `INTEGER` | NOT NULL, UNIQUE ghép với `stock_transfer_id`, CHECK trong DDL | Thông tin dòng số trong bảng `sim.stock_transfer_line`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `product_id` | `BIGINT` | FK → `core.product.product_id`, NOT NULL | Khóa ngoại tới `core.product.product_id`. |
| `inventory_lot_id` | `BIGINT` | FK → `sim.inventory_lot.inventory_lot_id`, NULL cho phép | Khóa ngoại tới `sim.inventory_lot.inventory_lot_id`. |
| `transfer_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Số lượng điều chuyển; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-inventory_transaction"></a>
##### `sim.inventory_transaction`

**Vai trò/grain:** Ledger giao dịch tồn mô phỏng; dấu quantity phải theo transaction type.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `inventory_transaction_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `scenario_id` | `BIGINT` | FK → `sim.scenario_registry.scenario_id`, NOT NULL | Khóa ngoại tới `sim.scenario_registry.scenario_id`. |
| `inventory_lot_id` | `BIGINT` | FK → `sim.inventory_lot.inventory_lot_id`, NOT NULL | Khóa ngoại tới `sim.inventory_lot.inventory_lot_id`. |
| `transaction_type` | `TEXT` | NOT NULL, CHECK trong DDL | Loại giao dịch; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `quantity_delta` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Biến động tồn có dấu; dương tăng, âm giảm. Loại transaction/movement quyết định diễn giải. |
| `occurred_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm sự kiện/giao dịch xảy ra theo record. |
| `demand_request_id` | `BIGINT` | FK → `sim.demand_request.demand_request_id`, NULL cho phép | Khóa ngoại tới `sim.demand_request.demand_request_id`. |
| `simulated_receipt_line_id` | `BIGINT` | FK → `sim.simulated_goods_receipt_line.simulated_goods_receipt_line_id`, NULL cho phép | Khóa ngoại tới `sim.simulated_goods_receipt_line.simulated_goods_receipt_line_id`. |
| `stock_transfer_line_id` | `BIGINT` | FK → `sim.stock_transfer_line.stock_transfer_line_id`, NULL cho phép | Khóa ngoại tới `sim.stock_transfer_line.stock_transfer_line_id`. |
| `transaction_note` | `TEXT` | NULL cho phép | Ghi chú giao dịch; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-inventory_balance_snapshot"></a>
##### `sim.inventory_balance_snapshot`

**Vai trò/grain:** Snapshot tồn lô; available trừ reserved/quarantine/blocked/expired.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `inventory_balance_snapshot_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `scenario_id` | `BIGINT` | FK → `sim.scenario_registry.scenario_id`, NOT NULL | Khóa ngoại tới `sim.scenario_registry.scenario_id`. |
| `inventory_lot_id` | `BIGINT` | FK → `sim.inventory_lot.inventory_lot_id`, NOT NULL, UNIQUE ghép với `snapshot_at` | Khóa ngoại tới `sim.inventory_lot.inventory_lot_id`. |
| `snapshot_at` | `TIMESTAMPTZ` | NOT NULL, UNIQUE ghép với `inventory_lot_id` | Thời điểm snapshot; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `physical_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Lượng vật lý trong scenario trước khi trừ reserved/quarantine/blocked/expired. |
| `reserved_quantity` | `NUMERIC(18,4)` | NOT NULL, DEFAULT `0`, CHECK trong DDL | Lượng đã reserve; phải cùng đơn vị với lượng tồn liên quan. |
| `quarantine_quantity` | `NUMERIC(18,4)` | NOT NULL, DEFAULT `0`, CHECK trong DDL | Lượng cách ly; bị trừ khỏi simulated available_quantity. |
| `blocked_quantity` | `NUMERIC(18,4)` | NOT NULL, DEFAULT `0`, CHECK trong DDL | Lượng bị chặn; bị trừ khỏi simulated available_quantity. |
| `expired_quantity` | `NUMERIC(18,4)` | NOT NULL, DEFAULT `0`, CHECK trong DDL | Lượng hết hạn; bị trừ khỏi simulated available_quantity. |
| `available_quantity` | `NUMERIC(18,4)` | NULL cho phép, generated STORED | Generated = physical − reserved − quarantine − blocked − expired theo mô hình mô phỏng. Cần quy ước bucket không đếm chồng; công thức không tự chứng minh mọi lô đủ eligibility. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-recommendation"></a>
##### `sim.recommendation`

**Vai trò/grain:** Khuyến nghị hành động trong scenario; cần human review.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `recommendation_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `scenario_id` | `BIGINT` | FK → `sim.scenario_registry.scenario_id`, NOT NULL | Khóa ngoại tới `sim.scenario_registry.scenario_id`. |
| `forecast_run_id` | `BIGINT` | FK → `model.forecast_run.forecast_run_id`, NULL cho phép | Khóa ngoại tới `model.forecast_run.forecast_run_id`. |
| `recommendation_type` | `TEXT` | NOT NULL, CHECK trong DDL | Loại khuyến nghị; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `rationale` | `TEXT` | NOT NULL | Thông tin rationale trong bảng `sim.recommendation`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm tạo bản ghi. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-recommendation_line"></a>
##### `sim.recommendation_line`

**Vai trò/grain:** Một dòng hành động mua/transfer/FEFO cho product và location.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `recommendation_line_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `recommendation_id` | `BIGINT` | FK → `sim.recommendation.recommendation_id`, NOT NULL, UNIQUE ghép với `line_number` | Khóa ngoại tới `sim.recommendation.recommendation_id`. |
| `line_number` | `INTEGER` | NOT NULL, UNIQUE ghép với `recommendation_id`, CHECK trong DDL | Thông tin dòng số trong bảng `sim.recommendation_line`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `line_action` | `TEXT` | NOT NULL, CHECK trong DDL | Thông tin dòng hành động trong bảng `sim.recommendation_line`; đọc theo grain/vai trò của bảng và ràng buộc DDL. |
| `product_id` | `BIGINT` | FK → `core.product.product_id`, NOT NULL | Khóa ngoại tới `core.product.product_id`. |
| `source_location_id` | `BIGINT` | FK → `core.location.location_id`, NULL cho phép | Khóa ngoại tới `core.location.location_id`. |
| `destination_location_id` | `BIGINT` | FK → `core.location.location_id`, NULL cho phép | Khóa ngoại tới `core.location.location_id`. |
| `supplier_id` | `BIGINT` | FK → `sim.supplier.supplier_id`, NULL cho phép | Khóa ngoại tới `sim.supplier.supplier_id`. |
| `inventory_lot_id` | `BIGINT` | FK → `sim.inventory_lot.inventory_lot_id`, NULL cho phép | Khóa ngoại tới `sim.inventory_lot.inventory_lot_id`. |
| `recommended_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Lượng được đề xuất, > 0; chưa phải lượng được con người duyệt hoặc lượng đã thực thi. |
| `need_by_date` | `DATE` | NULL cho phép | Ngày need by; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-replenishment_review_basis"></a>
##### `sim.replenishment_review_basis`

**Vai trò/grain:** Căn cứ rà soát bổ sung: trigger, tồn, min–max, on-order và calculation locator.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `replenishment_review_basis_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `scenario_id` | `BIGINT` | FK → `sim.scenario_registry.scenario_id`, NOT NULL | Khóa ngoại tới `sim.scenario_registry.scenario_id`. |
| `recommendation_line_id` | `BIGINT` | FK → `sim.recommendation_line.recommendation_line_id`, NULL cho phép, UNIQUE | Khóa ngoại tới `sim.recommendation_line.recommendation_line_id`. |
| `location_id` | `BIGINT` | FK → `core.location.location_id`, NOT NULL | Khóa ngoại tới `core.location.location_id`. |
| `product_id` | `BIGINT` | FK → `core.product.product_id`, NOT NULL | Khóa ngoại tới `core.product.product_id`. |
| `reviewed_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm review trong scenario, không phải bằng chứng một engine đang chạy theo mỗi issue ở production. |
| `trigger_issue_reference` | `TEXT` | NULL cho phép | Reference của issue kích hoạt review nếu có; là TEXT, không phải FK tự xác minh movement tồn tại. |
| `stock_on_hand_quantity` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Lượng stock dùng làm input review. Khi viện USAID phải nêu mapping sang usable stock; không lấy mặc định physical on-hand chứa hàng cách ly/hỏng/hết hạn. |
| `stock_on_hand_unit` | `TEXT` | NULL cho phép | Đơn vị của stock_on_hand_quantity; cần cùng cơ sở lượng với min/max/on-order trước khi tính toán. |
| `minimum_stock_quantity` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Ngưỡng Min đã biểu diễn thành quantity của mặt hàng; không phải số tháng min stock level. Cần rule/config và thời điểm hiệu lực để giải trình. |
| `minimum_stock_unit` | `TEXT` | NULL cho phép | Đơn vị hàng của minimum_stock_quantity, không phải mặc định tháng hoặc ngày. |
| `maximum_stock_quantity` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Mức Max đã chuyển thành quantity; nếu tính từ AMC × max stock level cần truy vết AMC/window/UOM và rule dùng. |
| `maximum_stock_unit` | `TEXT` | NULL cho phép | Đơn vị hàng của maximum_stock_quantity; phải quy đổi tương thích các input khác. |
| `quantity_on_order` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Lượng incoming đang đặt được ghi trong basis; không đồng nghĩa đã nhận hoặc toàn bộ PO/transfer đều được phép trừ. |
| `quantity_on_order_unit` | `TEXT` | NULL cho phép | Đơn vị của quantity_on_order; cần quy đổi cùng Min/Max/stock trước phép trừ. |
| `quantity_on_order_expected_before_next_resupply` | `BOOLEAN` | NULL cho phép | Cờ theo contract dự án về incoming dự kiến trước lần resupply tiếp theo. TRUE cần evidence/ETA; không suy từ DISPATCHED. NULL là chưa xác lập điều kiện. |
| `calculated_order_quantity` | `NUMERIC(18,4)` | NULL cho phép, CHECK trong DDL | Kết quả phép tính theo basis/locator và UOM đã đối chiếu; không phải approved quantity hoặc PO thực. |
| `calculated_order_unit` | `TEXT` | NULL cho phép | Đơn vị của calculated_order_quantity, phải khớp cơ sở quy đổi dùng trong phép tính. |
| `calculation_locator` | `TEXT` | NOT NULL | Locator tới quy tắc/công thức/bằng chứng dùng khi review; giúp người duyệt tra cứu. |
| `reviewed_by` | `TEXT` | NULL cho phép | Định danh/mô tả người ghi review basis nếu có; không tự thay thế decision approval ở recommendation_review. |
| `data_origin` | `TEXT` | NOT NULL, DEFAULT `'SYNTHETIC'`, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-recommendation_line_execution"></a>
##### `sim.recommendation_line_execution`

**Vai trò/grain:** Liên kết recommendation line với PO/transfer line giả lập.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `recommendation_line_execution_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `recommendation_line_id` | `BIGINT` | FK → `sim.recommendation_line.recommendation_line_id`, NOT NULL | Khóa ngoại tới `sim.recommendation_line.recommendation_line_id`. |
| `execution_type` | `TEXT` | NOT NULL, CHECK trong DDL | Loại thực thi; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `simulated_purchase_order_line_id` | `BIGINT` | FK → `sim.simulated_purchase_order_line.simulated_purchase_order_line_id`, NULL cho phép | Khóa ngoại tới `sim.simulated_purchase_order_line.simulated_purchase_order_line_id`. |
| `stock_transfer_line_id` | `BIGINT` | FK → `sim.stock_transfer_line.stock_transfer_line_id`, NULL cho phép | Khóa ngoại tới `sim.stock_transfer_line.stock_transfer_line_id`. |
| `linked_quantity` | `NUMERIC(18,4)` | NOT NULL, CHECK trong DDL | Lượng gắn recommendation line với simulated PO/transfer line, > 0. DDL chưa ràng buộc tổng lượng này vào approved quantity hoặc decision version. |
| `linked_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm liên kết; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, DEFAULT `'SYNTHETIC'`, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-recommendation_review"></a>
##### `sim.recommendation_review`

**Vai trò/grain:** Bản ghi role/người rà soát và phản hồi recommendation.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `recommendation_review_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `recommendation_id` | `BIGINT` | FK → `sim.recommendation.recommendation_id`, NOT NULL | Khóa ngoại tới `sim.recommendation.recommendation_id`. |
| `organizational_unit_id` | `BIGINT` | FK → `mart.organizational_unit.organizational_unit_id`, NULL cho phép | Khóa ngoại tới `mart.organizational_unit.organizational_unit_id`. |
| `reviewer_role` | `TEXT` | NOT NULL | Vai trò người phản hồi recommendation; TEXT không xác minh danh tính hoặc quyền phê duyệt. |
| `reviewer_action_description` | `TEXT` | NOT NULL | Mô tả tự do hành động/phản hồi. Chưa có review_status, approved_quantity, override_reason hoặc reviewer ID dạng contract như US-12. |
| `reviewed_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` | Thời điểm ghi review; bản ghi tồn tại chưa chứng minh execution đã được approval gate kiểm soát. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="table-sim-decision_metric_result"></a>
##### `sim.decision_metric_result`

**Vai trò/grain:** Kết quả KPI operational/decision trong scenario và kỳ đo.

| Cột | Kiểu PostgreSQL | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `decision_metric_result_id` | `BIGINT` | PK, NOT NULL, IDENTITY | Khóa chính định danh dòng trong bảng. |
| `scenario_id` | `BIGINT` | FK → `sim.scenario_registry.scenario_id`, NOT NULL | Khóa ngoại tới `sim.scenario_registry.scenario_id`. |
| `kpi_id` | `BIGINT` | FK → `mart.kpi_definition.kpi_id`, NOT NULL | Khóa ngoại tới `mart.kpi_definition.kpi_id`. |
| `product_id` | `BIGINT` | FK → `core.product.product_id`, NULL cho phép | Khóa ngoại tới `core.product.product_id`. |
| `location_id` | `BIGINT` | FK → `core.location.location_id`, NULL cho phép | Khóa ngoại tới `core.location.location_id`. |
| `period_start` | `DATE` | NOT NULL | Ngày bắt đầu kỳ đo kết quả decision/operational trong scenario; cần cùng horizon/grain khi so sánh phương án. |
| `period_end` | `DATE` | NOT NULL | Ngày cuối kỳ đo, không trước period_start; boundary inclusive/exclusive cần theo định nghĩa metric cụ thể. |
| `metric_value` | `NUMERIC(20,6)` | NOT NULL | Giá trị KPI/metric; đọc cùng unit và định nghĩa KPI. |
| `unit_code` | `TEXT` | NOT NULL | Mã đơn vị; miền giá trị/ý nghĩa chi tiết theo DDL và source contract. |
| `data_origin` | `TEXT` | NOT NULL, DEFAULT `'SYNTHETIC'`, CHECK trong DDL | Nhãn provenance; các giá trị hợp lệ do CHECK của bảng quy định. Dữ liệu sinh từ simulator vẫn là SYNTHETIC dù input có thể là dataset quan sát. |

**DDL:** [`archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql`](../../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql)

<a id="non-postgres-contracts"></a>
### Ngoài PostgreSQL

- MongoDB Atlas hiện giữ snapshot tri thức sản phẩm nguồn công khai tại `pharmaflow_product_knowledge.product_snapshots`; xem [Mongo package contract](../../../src/synthetic_data_source/mongodb/README.md). Đây là document-shaped source, không phải nguồn sales, dispensing hay inventory.
- Weather API → Databricks là đường ingest dự kiến, chưa triển khai. S3-compatible/object storage là đích dự kiến cho file hồ sơ tender và metadata/phiên bản; không phải API source hoặc sổ giao dịch vận hành.
- Public catalog không chứng minh giá POS, tồn kho chi nhánh, supplier, procurement hay fulfillment thực tế.

### Ranh giới nghiệp vụ cần giữ khi dùng dictionary

| Nhu cầu / nguồn | Đọc đúng model hiện tại | Khoảng trống hoặc quyết định còn cần |
|---|---|---|
| US-01: demand vs fulfillment | `pos.sales_order.demand_location_id` → `org.store`; `fulfillment_location_id` → `org.warehouse`. Migration 04 đã triển khai trên Neon. | Header hỗ trợ một kho fulfill cho mỗi đơn. Đơn chia hàng từ nhiều kho cần allocation theo line; schema không xác định luật chọn kho gần nhất/còn hàng. |
| US-02/08/11: cập nhật kho sau operation | Có ledger/balance và proposal quality/return. | Chưa xác minh writer atomic, idempotency, chống oversell hoặc quarantine enforcement. Generated column không tự sinh movement. |
| WHO §§9, 12.17; US-08/09 | Physical, unreserved và saleable là các nghĩa riêng. | V2 không định nghĩa công thức ATS; restricted/expiry/quality unknown không mặc định bằng 0 hoặc đạt chuẩn. |
| USAID Table 2-1 p.19; US-05/06 | Handbook dùng stock on hand theo nghĩa **usable stock**; source physical on-hand có thể gồm hàng chưa đủ điều kiện dùng. | Cần mapping/basis nêu rõ lượng được dùng cho min–max; không lấy thẳng physical balance rồi gọi là quantity chuẩn USAID. Usable cũng chưa tự quyết định cách trừ reservation/commitment của dự án. |
| USAID Ch.4 pp.56–61 | Min/max level có thể biểu diễn bằng tháng; min/max quantity là lượng hàng sau chuyển đổi. | Basis lưu quantity/UOM, không phải số tháng. AMC, cửa sổ lịch sử, rule/version và incoming evidence cần được lưu hoặc truy vết. |
| USAID pp.13–14; các series | Issues giữa facilities có thể làm proxy khi thiếu consumption. | Không đổi issued, dispensed, sales thành latent demand hoặc patient adherence. |
| USAID p.57 và WHO §12.17 | `received_at` là nhận vật lý; available-for-use có thể muộn hơn. | Phân biệt receipt lead time với usable-supply lead time; chưa có model timestamp release đầy đủ trong v1. |
| US-04: exposure | Request snapshot và current balance không phải lịch sử đủ coverage. | Chưa có `stockout_exposure_minutes`, lịch mở cửa, availability intervals và rule phân biệt physical stockout với quality restriction. |
| US-10: nhận hàng | PO, receipt và lot được tách; WHO hỗ trợ đối chiếu chứng từ và xử lý từng batch. | Chưa có ASN; three-way match là bổ sung của US, chưa được WHO locator chứng minh. |
| US-12: human review | Review hiện là role + free-text action theo recommendation. | Chưa có approved quantity/status/reviewer identity dạng contract, line decision version hoặc approval gate gắn execution. |
| US-13: dual metrics | Hai bảng kết quả riêng tham chiếu `mart.kpi_definition`. | FK tới `kpi_id` chưa kiểm tra quality layer; evaluator phải kiểm tra đúng lớp/đơn vị/grain. |
| Temporal backtesting | Model lưu cutoff, horizon, protocol và số origin. | DDL không tự chứng minh feature sẵn có ở cutoff, forecast point nằm đúng horizon hoặc benchmark chống leakage. |
| Fidelity của SCMD | Raw có thể có signed net-issued quantity; nguồn là Secondary Care Medicines Data ở grain Trust–tháng–VMP–UOM. | `issued_quantity >= 0` và enum COMMUNITY_ISSUED_QUANTITY_PROXY cần được xem lại trước ingest; preprocessing positive-only của một paper không phải quy tắc xóa dữ liệu khỏi STAGING. |
| Các `sim.*` | Mọi kết quả được diễn giải trong scenario mô phỏng. | Các FK độc lập chưa bảo đảm tất cả lot/request/recommendation/execution đều thuộc cùng `scenario_id`; writer/validation phải kiểm tra. |

Các khoảng trống ở đây là nhận xét về contract/triển khai dựa trên nguồn được dẫn tại từng mục; chúng không thêm cột giả vào các bảng mô tả bên trên.

### Tài liệu liên quan

- [Data model overview/ERD](#index)
- [Source schema v1 và grain nghiệp vụ](#source-v1)
- [Retail workflow contract v2 proposal](#proposal-v2)
- [MongoDB/S3 ownership và provenance](#non-postgres-contracts)
- [SQL theo vai trò dữ liệu](../../../src/synthetic_data_source/pharmaflow_source_postgre/schema_full.sql)

---

**Cập nhật theo DDL trong repository.** Khi DDL thay đổi, cần rà lại schema/table/column/type/constraint và sửa data dictionary; tài liệu này không phải migration hoặc bằng chứng deployment.

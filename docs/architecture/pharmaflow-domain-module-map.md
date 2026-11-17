# PharmaFlow Domain & Module Map

## Purpose and status

This document translates the [PharmaFlow Data & Business Analytics Landscape](../Landscape/PharmaFlow_Data_Business_Analytics_Landscape_KPI_Fixed.pdf) into business-module boundaries for project planning. It is the shared domain reference for architecture and module work; it is not a deployment design, a claim that the workflows are live, or a decision to create separate services.

The landscape is the source for business scope. The local data model, workflow contracts, source code, and tests determine what is modeled or implemented. Keep those evidence levels distinct.

For the target data platform and application boundary, see [System Architecture](pharmaflow-system-architecture.md). For source availability, Silver preparation, and proposed products by domain, see [Data Products](pharmaflow-data-products.md). PostgreSQL and MongoDB under `src/synthetic_data_source/` are the project-side source stores that the DSS is intended to ingest; datasets and crawlers prepare those stores.

## Two complementary views of the product

The project processing view is `DATA -> FORECAST -> RISK -> DECISION -> OPERATIONAL OUTCOME`. The landscape business-capability view is `Business Monitoring -> Business Insight -> Business Optimization -> Human Approval -> Operational Outcome`. The first describes how evidence is transformed; the second describes what business users monitor and decide. They complement each other and are not competing module taxonomies.

| Landscape capability | Meaning in PharmaFlow |
|---|---|
| Business Monitoring | Current business measures with lineage to domain, Category, SubCategory, and KPI. An observed KPI is not a forecast. |
| Business Insight | Forecasts, risks, and opportunities derived from available evidence. Forecast and risk are capabilities used by multiple domains. |
| Business Optimization | Candidate actions or scenarios under explicit business constraints, including replenishment, transfer/rebalancing, FEFO priority, tender participation/bid quantity, or no action. |
| Human Approval | Authorized review of operationally important recommendations. Approval does not mean an action was executed. |
| Operational Outcome | Observed or simulated service, cost, inventory, expiry/waste, and fulfillment results, labeled by provenance. |

## Business modules and boundaries

The five rows below are business domains in the landscape. They are candidate business-module boundaries; they do not require five deployed services.

| Business module | Scope in the landscape | Boundary to preserve | Current local evidence and status |
|---|---|---|---|
| **Sales** | Product/category and channel sales measures; sales and demand insight, including forecast sales quantity and patterns. | Sales is observed quantity sold; demand is the quantity that needed to be served and may be unobserved or censored during stockout. Do not infer unmet demand by subtracting sales from a forecast. | The current PostgreSQL source package prepares Sales & Demand inputs from several datasets with differing grain and provenance. Generated product-level POS remains synthetic. No Databricks forecasting pipeline or DSS forecasting application is established by the source data. |
| **Inventory & Expiry** | Inventory state, batch/lot, expiry, stock movement, stockout/excess, near-expiry, FEFO, and replenishment insight. | Keep lot, expiry, on-hand, reserved/unreserved, restricted, and saleable eligibility distinct. Unknown expiry or quality status does not imply saleability. | Source schema includes modeled inventory concepts, but the current source loads do not establish populated inventory balances/lots or an operational inventory workflow. Additional synthetic data and module data products are planned. |
| **Procurement & Supply** | Supplier, Purchase Order, Goods Receipt, delivery performance, lead time, Supplier Scorecard, and incoming-supply insight. | This is the inbound purchase path. Ordered quantity and received quantity are separate facts; supplier is not manufacturer. Supplier Scorecard summarizes supplier KPIs; it does not collapse ordered and received quantities. | Source schema includes procurement concepts, but the current Sales & Demand preparation does not populate procurement facts. Additional synthetic data and module data products are planned. |
| **Distribution & Store Network** | Inventory by location, transfer, in-transit quantity, Route / Trip, Carrier, lead time, route and trip cost visibility, and network rebalancing insight. | This is a distinct business view across locations, but it can use the shared inventory and transfer facts. Do not create a second inventory balance merely to represent the network domain. Route / Trip and Carrier provide scope for transport route and trip-cost analysis; they do not imply an established logistics optimizer. | Source schema includes locations/transfers, but populated transfer and in-transit evidence is not established by current Sales & Demand data. The landscape does not define an optimization objective, constraints, horizon, or solver. |
| **Tender & Contract Fulfillment** | Tender opportunity, bid qualification, bid and award, delivery commitment, and contract fulfillment. The landscape treats the pharmacy chain as bidder and, after award, the supplier responsible to the buyer. | This is an outbound commitment path, separate from inbound Procurement & Supply. Assess a commitment alongside retail forecast, current stock, incoming supply, and lead time. The landscape's numeric example is a scenario, not observed business data. | Tender is Landscape scope and a planned data/application capability. Local evidence reviewed for this map does not establish a tender source contract, bid/award facts, or executable workflow. S3/object storage is a target direction, not a deployment claim. |

## Cross-domain scenarios

### Retail replenishment and FEFO

Use sales/request evidence with its actual grain and semantics; monitor current stock and lot/expiry state; produce forecast, shortage/overstock, and expiry insight; compare replenishment, transfer, FEFO priority, and no-action scenarios where supported; route important recommendations for human review; evaluate prediction quality separately from decision outcomes.

### Network transfer and rebalancing

Use location-level inventory and transfer/in-transit evidence; surface imbalance and transfer scenarios; evaluate the resulting service, inventory, expiry, cost, and transfer measures. The exact objective and constraints for an “optimal” network plan remain to be established from project evidence or an explicit decision.

### Tender award and fulfillment commitment

Represent the landscape sequence `Tender Opportunity -> Bid Qualification -> Bid & Award -> Contract Fulfillment` as an outbound business path. For proposed participation, compare requested quantities with retail demand forecast, current stock, incoming supply, and lead time; present options for human review. In the current Module 05 design, a user records the official awarded quantity by item after checking the result source, and delivery batches are compared with that confirmed quantity. Contract-level fulfillment measures remain a broader Landscape capability and require a separately defined source contract/evidence model; they are not implied by the Module 05 delivery-tracking use case.

These are landscape-level decision-support scenarios. They do not establish API calls, database state transitions, real purchase orders, real transfers, or a deployed tender workflow.

## Implementation and evidence status

Use these labels when discussing a module or capability:

1. **Landscape scope** — named or shown in the business landscape.
2. **Modeled locally** — represented in a local schema, contract, or simulation; not necessarily deployed.
3. **Implemented locally** — executable application code and relevant tests exist.
4. **Verified deployed** — direct evidence confirms the deployed resource or workflow.

As of the current local source map, `src/common/`, `src/pipeline/`, `src/forecasting/`, and `src/optimization/` remain scaffolds; current tests cover crawler and URL behavior, not DSS domain modules. PostgreSQL source data and MongoDB product snapshots have package-level preparation/load evidence, but this does not establish Databricks pipelines or a web DSS. The old downstream PostgreSQL DDL is a local prototype, not the selected target serving platform or deployment evidence. Tender remains Landscape scope without a local contract domain. Update these statuses only after inspecting the owning sources and dated run evidence.

## Source documents

- [Landscape PDF](../Landscape/PharmaFlow_Data_Business_Analytics_Landscape_KPI_Fixed.pdf) and [revised landscape transcript](../Landscape/PharmaFlow_Landscape_Transcript_Revised.html) — domain hierarchy, KPI lineage, insights, optimization, approval, tender-to-inventory scenario, and semantics.
- [System Architecture](pharmaflow-system-architecture.md) and [Data Products](pharmaflow-data-products.md) — target platform boundary and proposed source-to-module data mapping.
- [Data-model and workflow contracts](../data-model/Relations-DataSource/README.md) — local schema status, evidence limits, observed/synthetic boundaries, and the explicit planned-only status of Tender.
- [Retail workflow contract v2](../data-model/Relations-DataSource/README.md#proposal-v2) — evidence-based retail flows and the limits of what schema can establish.
- [Source-v1 schema](../../archive/2026-11-03-source-sql-history/schema_v1.sql) and [downstream DSS schema](../../archive/2026-11-03-downstream-dss-temporary/pharmaflow_downstream/schema.sql) — local modeled entities and their simulation/provenance labels.
- [PostgreSQL source package](../../src/synthetic_data_source/pharmaflow_source_postgre/README.md), [MongoDB source package](../../src/synthetic_data_source/mongodb/README.md), and [tests map](../../tests/README.md) — source preparation evidence and current test scope.

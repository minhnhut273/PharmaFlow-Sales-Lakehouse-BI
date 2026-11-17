# Pharma Sales ATC candidate expansion — 2026-11-05

This run adds four Long Châu product-page candidates for Pharma Sales ATC groups that previously had no SKU candidate. It changes prepared source data and mappings only; it does not change DDL or populate inventory/logistics facts.

## Added candidate products

| ATC group | ATC ingredient code | Long Châu SKU | Product | Mapping evidence |
|---|---|---|---|---|
| M01AB | M01AB05 | `00018530` | Fenaflam DHG, diclofenac potassium 25 mg, box 2 blisters × 10 tablets | [Long Châu product page](https://nhathuoclongchau.com.vn/thuoc/fenaflam-25mg-dhg-2x10-19845.html), [WHO ATC M01AB](https://atcddd.fhi.no/atc_ddd_index/?code=M01AB05&showdescription=no) |
| N02BA | N02BA01 | `00000904` | Aspirin pH8 Mekophar, acetylsalicylic acid 500 mg, box 20 blisters × 10 tablets | [Long Châu product page](https://nhathuoclongchau.com.vn/thuoc/aspirin-ph8-4670.html), [WHO ATC N02BA](https://atcddd.fhi.no/atc_ddd_index/?code=N02BA01&showdescription=no) |
| N05B | N05BX03 | `00006931` | Stresam Biocodex, etifoxine 50 mg, box 3 blisters × 20 capsules | [Long Châu product page](https://nhathuoclongchau.com.vn/thuoc/stresam-2156.html), [WHO ATC N05BX](https://atcddd.fhi.no/atc_ddd_index/?code=N05BX03&showdescription=no) |
| N05C | N05CF04 | `00048631` | Eszopiclone Minh Dân, eszopiclone 2 mg, box 3 blisters × 10 tablets | [Long Châu product page](https://nhathuoclongchau.com.vn/thuoc/eszopiclone-2-mg-minh-dan-3-x10.html), [WHO ATC N05CF](https://atcddd.fhi.no/atc_ddd_index/?code=N05CF04&showdescription=no) |

The official page references, SKU keys, and observation timestamp are stored in `catalog.product_source_reference`. Each ATC assignment remains `CANDIDATE`; it is not pharmacist-verified. The products have `brand_name`, manufacturer links, and `LC_BOX` packaging descriptions. `base_uom_code` and `quantity_in_base_uom` remain null because the Pharma Sales source does not define its sales unit and these product pages do not document the source transaction unit.

## Row impact

- Long Châu catalog preparation: 2,478 → 2,482 products; 2,450 → 2,454 packages; 4,928 → 4,936 source references.
- Pharma Sales candidate map: 10 → 14 products, covering 8/8 ATC groups.
- Pharma Sales observations remain 16,848 daily ATC-group facts; source quantity UOM remains null.
- Synthetic Pharma Sales POS: 2,080 orders remain; lines increase from 18,701 to 25,534 (+6,833). The multiplier remains ×10 and line UOM remains `SIM_PHARMA_SALES_UNIT`.
- Live source reconciliation passed for Long Châu, Pharma Sales, and all four full-source loads. Neon still has one `production` branch and one database, `pharmaflow_source_postgre_v2`.

These synthetic order lines allocate ATC-group totals to candidate products. They are not observed SKU sales, and `SIM_PHARMA_SALES_UNIT` does not mean tablets or boxes.

## Evidence files

- [Machine-readable expansion report](expansion-report.json)
- [Pre-expansion baseline and checksums](baseline/README.md)
- [Curated product candidate input](../../config/mappings/pharma_sales_longchau_candidates.csv)

# Data Quality Report

Generated at (UTC): `2026-07-27T07:24:17Z`
Dataset: UCI Machine Learning Repository — Online Retail (dataset 352)

## Source and provenance

- Official record: [https://archive.ics.uci.edu/dataset/352/online-retail](https://archive.ics.uci.edu/dataset/352/online-retail)
- Download URL: [https://archive.ics.uci.edu/static/public/352/online+retail.zip](https://archive.ics.uci.edu/static/public/352/online+retail.zip)
- License: CC BY 4.0 (as stated on the UCI dataset record)
- Local archive: `data/raw/online-retail.zip`
- Archive SHA-256: `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b`
- Workbook SHA-256: `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`
- Source rows: **541,909**; source columns: `InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country`

## Layer row counts

| Layer/output | Rows | Policy |
|---|---:|---|
| Raw workbook | 541,909 | Source preserved locally in the archive |
| Cleaned transactions | 536,641 | Exact duplicates and structurally invalid rows removed; anomalies retained |
| Curated sales fact | 524,878 | Positive quantity and price, non-cancelled lines only |
| Curated order fact | 19,960 | One row per positive-sales invoice |
| Customer dimension | 4,338 | Hashed customer keys with at least one curated order |
| Product dimension | 3,922 | One row per curated stock code |

## Automated checks

| Check | Status | Observed | Expected | Note |
|---|---|---:|---|---|
| source_schema | **PASS** | ['InvoiceNo', 'StockCode', 'Description', 'Quantity', 'InvoiceDate', 'UnitPrice', 'CustomerID', 'Country'] | the eight UCI columns |  |
| source_row_count | **PASS** | 541909 | 541909 |  |
| archive_checksum | **PASS** | f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b | f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b | WARN permits a refreshed but schema-compatible source archive. |
| exact_duplicates | **WARN** | 5268 | 0 preferred; removed before cleaned layer | Duplicates are reported, then first occurrence is retained. |
| missing_customer_id | **WARN** | 132186 | 0 preferred | Anonymous customer ID is absent for some valid lines; those lines remain in sales totals but not customer repeat-rate denominators. |
| invalid_dates | **PASS** | 0 | 0 |  |
| negative_quantity | **WARN** | 10587 | 0 preferred | Negative quantity is retained as return/cancellation evidence and excluded from fact_sales. |
| non_positive_unit_price | **WARN** | 2512 | 0 preferred | Non-positive prices are retained for audit and excluded from fact_sales. |
| line_amount_outliers | **WARN** | 42624 | 0 preferred; IQR upper fence <= 38.40 | Outliers are flagged, not silently removed. |
| cleaned_no_exact_duplicates | **PASS** | 0 | 0 |  |
| curated_positive_sales | **PASS** | 524878 | all rows quantity > 0, unit price > 0, non-cancelled |  |

Summary: **0 FAIL**, **5 WARN**, **6 PASS**.

## Missingness and anomaly counts

| Measure | Count |
|---|---:|
| Exact duplicate rows removed | 5,268 |
| Structurally invalid rows removed | 0 |
| Negative-quantity rows | 10,587 |
| Non-positive unit-price rows | 2,512 |
| Cancelled invoice rows | 9,251 |
| Positive sales lines missing customer key | 132,186 |

## Transformation assumptions

1. Exact duplicate rows are source-level repeats; only the first copy is retained in `cleaned_transactions.csv`.
2. Cancellation is identified by an `InvoiceNo` beginning with `C`; negative quantity is also treated as return/cancellation evidence.
3. `fact_sales.csv` excludes cancellations, negative/zero quantities, and non-positive unit prices. These rows are not deleted from the cleaned audit layer.
4. Missing `CustomerID` is allowed in sales totals. Repeat-customer metrics must use only orders with a non-null deterministic `customer_key`.
5. Customer keys are truncated SHA-256 digests of a configurable salt and source ID. This is pseudonymisation, not a guarantee of anonymity.
6. No product category exists in the source schema; StockCode/product performance is used as the product-level analysis grain.
7. IQR outliers are surfaced as WARN and are not removed automatically.

## Privacy

The source archive is a local input artifact and is not redistributed by the processed outputs. The raw `CustomerID` column is absent from all processed CSVs; only the deterministic `customer_key` is emitted.

## Output files

- `data/raw/source_manifest.json`
- `data/processed/cleaned_transactions.csv`
- `data/processed/fact_sales.csv`, `fact_orders.csv`
- `data/processed/dim_customer.csv`, `dim_product.csv`
- `data/processed/agg_monthly_sales.csv`, `agg_country_sales.csv`

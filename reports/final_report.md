# Public E-Commerce Data Reliability & Insights Platform

## Phase 3 Final Report

**Prepared:** 2026-07-27
**Evidence basis:** accepted KPI artifact commit `6a9489b828940480858badb830b6e59a0b176b95`
**Canonical data handoff:** `91202f5a62b8b7646a30eef0b83bbb9c0bed5efb`
**Dataset:** UCI Machine Learning Repository — Online Retail, dataset 352
**Currency:** GBP (£)

## Executive summary

The curated, non-cancelled sales layer contains **£10,642,110.80** across
**19,960 orders**, with an average order value of **£533.17**. Repeat buying is
material: **65.58%** of identified customers placed more than one order, and
repeat buyers generated **93.09% of known-customer (attributed) revenue**.

The 93.09% figure is intentionally not a share of all revenue: guest orders are
excluded from its denominator. Guest orders contribute **£1,754,901.91**, or
**16.49% of total valid revenue**, and are therefore a material measurement and
conversion opportunity. The United Kingdom contributes **£9,001,744.09
(84.59%)**, creating geographic concentration risk.

Revenue peaks in **November 2011 (£1,503,866.78)**. The source ends on
**2011-12-09**, so December is a partial month and should not be compared with
complete months without adjustment. The highest-retail-revenue product, after
excluding service/administrative codes `DOT`, `POST`, and `M`, is
**REGENCY CAKESTAND 3 TIER** at **£174,156.54**.

The data-quality handoff records **6 PASS, 5 WARN, and 0 FAIL** checks. The
warnings are explainable data characteristics—duplicates, guest customer IDs,
negative quantities, non-positive prices, and line-value outliers—and are
preserved in the audit layer rather than silently discarded.

## Scope and reliability position

| Layer or measure | Value | Interpretation |
|---|---:|---|
| Raw source rows | 541,909 | Source workbook rows |
| Cleaned transactions | 536,641 | Exact duplicates removed; anomalies retained |
| Curated sales lines | 524,878 | Positive quantity, positive price, non-cancelled lines |
| Curated orders | 19,960 | One row per positive-sales invoice |
| Customer dimension | 4,338 | Salted, truncated customer keys with curated orders |
| Product dimension | 3,922 | StockCode-level product grain |
| Source period | 2010-12-01 to 2011-12-09 | December 2011 is incomplete |

The source schema has no product category field, so product performance is
reported at StockCode/description grain. Raw CustomerID is not present in
processed outputs; downstream customer analysis uses deterministic salted keys.

## KPI scorecard

| KPI | Result | Definition and denominator |
|---|---:|---|
| Total revenue | **£10,642,110.80** | `Quantity × UnitPrice` on valid, non-cancelled sales lines |
| Total orders | **19,960** | Distinct non-cancelled positive-sales invoices |
| Average order value | **£533.17** | Total revenue ÷ total orders |
| Repeat purchase rate | **65.58%** | Identified customers with more than one order ÷ identified customers |
| Returning-customer revenue share | **93.09%** | Returning known-customer revenue ÷ all known-customer revenue |
| Returning-customer revenue | **£8,273,219.33** | Revenue from known customers with more than one order |
| Attributed revenue base | **£8,887,208.89** | Valid non-cancelled revenue with a non-null customer key |
| Guest revenue | **£1,754,901.91 (16.49%)** | Valid non-cancelled revenue with a null customer key |
| Cancellation invoice rate | **16.12%** | Cancelled invoice count ÷ all invoice count |

The machine-readable values and definitions are retained in
`reports/analysis/kpi_results.json` and `reports/metric_definitions.md`.

## Revenue trend

| Month | Revenue | MoM change |
|---|---:|---:|
| 2010-12 | £821,452.73 | — |
| 2011-01 | £689,811.61 | -16.03% |
| 2011-02 | £522,545.56 | -24.25% |
| 2011-03 | £716,215.26 | +37.06% |
| 2011-04 | £536,968.49 | -25.03% |
| 2011-05 | £769,296.61 | +43.27% |
| 2011-06 | £760,547.01 | -1.14% |
| 2011-07 | £718,076.12 | -5.58% |
| 2011-08 | £757,841.38 | +5.54% |
| 2011-09 | £1,056,435.19 | +39.40% |
| 2011-10 | £1,151,263.73 | +8.98% |
| 2011-11 | **£1,503,866.78** | +30.63% |
| 2011-12* | £637,790.33 | -57.59% |

\* December covers only the first nine days of the source period. The apparent
December decline is not a valid full-month seasonality signal.

## Product and market mix

### Top retail products by revenue

Service/administrative codes `DOT`, `POST`, and `M` are excluded from this
ranking.

| Rank | StockCode | Product | Revenue |
|---:|---|---|---:|
| 1 | 22423 | REGENCY CAKESTAND 3 TIER | £174,156.54 |
| 2 | 23843 | PAPER CRAFT , LITTLE BIRDIE | £168,469.60 |
| 3 | 85123A | WHITE HANGING HEART T-LIGHT HOLDER | £104,462.75 |
| 4 | 47566 | PARTY BUNTING | £99,445.23 |
| 5 | 85099B | JUMBO BAG RED RETROSPOT | £94,159.81 |

### Top countries by revenue

| Rank | Country | Revenue | Orders |
|---:|---|---:|---:|
| 1 | United Kingdom | £9,001,744.09 | 18,019 |
| 2 | Netherlands | £285,446.34 | 94 |
| 3 | EIRE | £283,140.52 | 288 |
| 4 | Germany | £228,678.40 | 457 |
| 5 | France | £209,625.37 | 392 |

## Recommended actions

1. **Prioritise retention experiments.** Use the high repeat-customer share to
   test loyalty, replenishment, and re-engagement journeys for identified
   customers. Track incremental revenue and repeat rate by treatment group;
   the current data does not contain campaign cost or causal lift.

2. **Convert guest demand into attributable relationships.** Guest orders are
   16.49% of valid revenue. Improve consent-based account capture and customer
   identification at checkout, then monitor the guest-revenue share and the
   change in attributed revenue without counting forced or duplicate identities.

3. **Plan inventory and operating capacity for September–November.** Revenue
   accelerates from September and peaks in November. Use complete-month
   comparisons and refreshed data before setting a December target.

4. **Reduce geographic concentration.** The United Kingdom contributes 84.59%
   of revenue. Validate product fit, shipping economics, tax requirements, and
   customer retention in the strongest secondary markets before investing in
   expansion.

5. **Investigate cancellations before claiming net revenue recovery.** The
   cancellation invoice rate is 16.12%. Match cancellation invoices to their
   originals and quantify net revenue impact, units returned, and recoverable
   stock; the current KPI is an invoice-count rate, not a matched return-value
   rate.

## Assumptions and known risks

- Revenue is `Quantity × UnitPrice` in GBP; the source has no tax or shipping
  fields, and no currency conversion is applied.
- Cancellation invoices are identified by an `InvoiceNo` prefix of `C`.
  Negative quantities and non-positive prices are retained for audit but
  excluded from the curated sales fact.
- Guest orders remain in total revenue and order metrics. They are excluded
  from repeat-customer denominators and from the attributed-revenue KPI.
- Customer keys are salted SHA-256 digests truncated to 32 hex characters.
  They are pseudonymous identifiers, not a guarantee of anonymity.
- `DOT`, `POST`, and `M` are treated as service/administrative codes rather
  than retail products in product rankings.
- The source has no product taxonomy; StockCode is the product-analysis grain.
- IQR line-value outliers are flagged as warnings, not removed automatically.
- Cancellation invoices are not matched back to original invoices, so the
  cancellation KPI should not be read as net-return value.
- The source period ends on 2011-12-09; December trend interpretation is
  therefore incomplete.

## Reproducibility and artifact inventory

The final report is a read-only synthesis of the accepted Phase 2 outputs. The
following files are the evidence chain:

- `data/raw/source_manifest.json` — source, checksum, schema, and row count.
- `reports/data_quality_report.md` — transformation policy and automated
  quality checks: 6 PASS, 5 WARN, 0 FAIL.
- `reports/metric_definitions.md` — KPI definitions and SQL scope, including
  the attributed-revenue denominator.
- `reports/analysis/kpi_results.json` — strict JSON KPI output (`null` for the
  first month without a prior-month growth value).
- `reports/analysis/insights.md` — generated business insights.
- `reports/analysis/kpi_summary.csv` — Phase 3 portable KPI scorecard.
- `reports/final_report.md` — this decision-ready synthesis.

To reproduce the underlying pipeline and KPI output from a local source archive:

```bash
python -m unittest discover -s tests -t . -v
python reports/analysis/kpi_analysis.py
python -m json.tool reports/analysis/kpi_results.json >/dev/null
```

The pipeline and `data/processed/curated.duckdb` are unchanged by Phase 3.

# Public E-Commerce Data Reliability & Insights Platform

This repository contains the accepted data-quality handoff and the Phase 3
decision artifacts for the UCI Online Retail dataset. The final integration
surface is deliberately local-only: no remote is configured, and the dashboard
does not download data or rerun the transformation pipeline.

## Quick start

From the repository root, run the single dashboard build command:

```bash
python3 reports/dashboard/build_dashboard.py
```

Expected output:

```text
Wrote reports/dashboard/index.html (6 rendered SVG charts)
Source: reports/analysis/kpi_results.json
Pipeline and curated data were not modified.
```

Open `reports/dashboard/index.html` in a browser. It is a self-contained HTML
file with inline SVG charts and requires no package installation or network
connection. To validate an already-built file without rewriting it, run:

```bash
python3 reports/dashboard/build_dashboard.py --check
```

## Data source, attribution and license

This project uses the [UCI Online Retail dataset (dataset 352)](https://archive.ics.uci.edu/dataset/352/online-retail).
Please cite: Chen, D. (2015). *Online Retail*. UCI Machine Learning Repository.
[DOI: 10.24432/C5BW33](https://doi.org/10.24432/C5BW33). The UCI dataset record
states that the dataset is available under the [Creative Commons Attribution 4.0
International license](https://creativecommons.org/licenses/by/4.0/).

Raw source archives and workbooks, processed CSV/DuckDB payloads, customer
identifiers or keys, and other data payloads are local inputs/evidence only and
are not included in this public repository. `data/raw/source_manifest.json`
preserves provenance metadata without shipping the source payload.

## Delivered artifacts

- `reports/dashboard/index.html` — static dashboard with six rendered charts:
  monthly revenue, month-over-month movement, revenue composition, top retail
  products, top countries, and data-quality status.
- `reports/dashboard/build_dashboard.py` — deterministic standard-library
  builder and local validation command.
- `reports/final_project_report.md` — decision-oriented project report with
  KPI denominators, recommendations, assumptions, and known risks.
- `reports/final_report.md` — earlier Phase 3 synthesis retained as evidence.
- `reports/analysis/kpi_results.json` — accepted strict JSON KPI artifact;
  treated as read-only input by the dashboard builder.

## Evidence and scope

The dashboard is based on accepted KPI commit
`6a9489b828940480858badb830b6e59a0b176b95` and the canonical data handoff
`91202f5a62b8b7646a30eef0b83bbb9c0bed5efb`. Revenue is `Quantity × UnitPrice`
for positive, non-cancelled sales lines in GBP. Guest revenue remains in total
revenue, while returning-customer revenue share uses only the attributed
revenue denominator.

The Phase 3 additions are limited to this README, the exact-name project
report, and `reports/dashboard/`. The pipeline, SQL, tests, raw/curated data,
and accepted KPI JSON are not edited by the dashboard build.

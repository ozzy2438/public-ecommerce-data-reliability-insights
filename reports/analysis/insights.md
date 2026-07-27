# Business Insights — Public E-Commerce Platform

_Generated from KPI analysis. All figures in GBP (£)._

---

## Insight 1 — Seasonal Revenue Peak

**Observation:** Revenue peaks in **2011-11** at £1,503,866.78, while the lowest month is **2011-02** at £522,545.56.

**Evidence:** Monthly revenue table from `curated.fact_sales`.

**Business implication:** The business exhibits strong Q4 seasonality (pre-Christmas gifting). Inventory, staffing, and marketing budgets should be front-loaded to October–November.

---

## Insight 2 — High Repeat-Purchase Rate Indicates Loyal Core

**Observation:** 65.6% of identified customers placed more than one order.

**Evidence:** `curated.dim_customers.order_count > 1` / total identified customers.

**Business implication:** The majority of revenue comes from returning buyers. Retention programs (loyalty rewards, re-engagement campaigns) likely have higher ROI than acquisition. Guest checkouts (null CustomerID) are excluded — the true repeat rate may differ.

---

## Insight 3 — Geographic Concentration Risk

**Observation:** **United Kingdom** accounts for a disproportionate share of total revenue (£9,001,744.09 from 18,019 orders).

**Evidence:** `curated.dim_countries` ordered by `total_revenue DESC`.

**Business implication:** Heavy reliance on a single market creates FX, regulatory, and logistics concentration risk. The data shows clear secondary markets (see top-10 country table) that represent expansion opportunities with existing product catalogue.

---

## Summary KPIs

| KPI | Value |
|-----|-------|
| Total Revenue | £10,642,110.80 |
| Total Orders | 19,960 |
| Average Order Value | £533.17 |
| Repeat Purchase Rate | 65.6% |
| Cancellation Rate | 16.1% |

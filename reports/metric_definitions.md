# Metric Definitions — Public E-Commerce Data Reliability & Insights Platform

**Dataset:** UCI Online Retail (2010–2011)  
**Source:** UCI Machine Learning Repository  
**Schema:** InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country  
**Author:** Bumble (Phase 2 — Data Modeling & Analytics)

---

## Business Questions

1. What is the total revenue and order volume over the period?
2. What is the average value of a single order?
3. What share of customers return to buy again?
4. How does revenue grow month-over-month?
5. Which products and categories drive the most (and least) revenue?
6. How significant are cancellations and returns, and where are they concentrated?

---

## Data Scope & Exclusion Rules

| Rule | Detail |
|------|--------|
| Exclude cancellations | InvoiceNo starting with `C` are cancellation invoices; excluded from revenue KPIs but tracked separately |
| Exclude negative/zero Quantity | Negative quantities outside cancellation invoices indicate data anomalies; excluded after logging |
| Exclude zero/negative UnitPrice | Price ≤ 0 likely represents adjustments or test rows; excluded after logging |
| Exclude null CustomerID | Guest transactions cannot contribute to repeat-purchase analysis; retained for revenue KPIs but flagged |
| Revenue definition | `Quantity × UnitPrice` (GBP) per line item; no tax or shipping data available |

---

## KPI Definitions

### KPI 1 — Total Revenue

| Field | Value |
|-------|-------|
| **Definition** | Sum of `Quantity × UnitPrice` for all valid (non-cancelled) line items |
| **Source columns** | `Quantity`, `UnitPrice`, `InvoiceNo` |
| **Filter** | InvoiceNo NOT LIKE 'C%', Quantity > 0, UnitPrice > 0 |
| **Unit** | GBP (£) |
| **Table** | `curated.fact_sales` |

```sql
SELECT SUM(quantity * unit_price) AS total_revenue
FROM curated.fact_sales
WHERE is_cancelled = FALSE;
```

---

### KPI 2 — Total Order Count

| Field | Value |
|-------|-------|
| **Definition** | Count of distinct InvoiceNo values (one invoice = one order) |
| **Source columns** | `InvoiceNo` |
| **Filter** | InvoiceNo NOT LIKE 'C%' |
| **Unit** | Orders |
| **Table** | `curated.fact_orders` |

```sql
SELECT COUNT(DISTINCT invoice_no) AS total_orders
FROM curated.fact_orders
WHERE is_cancelled = FALSE;
```

---

### KPI 3 — Average Order Value (AOV)

| Field | Value |
|-------|-------|
| **Definition** | Total Revenue ÷ Total Order Count |
| **Source columns** | `Quantity`, `UnitPrice`, `InvoiceNo` |
| **Filter** | Same as KPI 1 and KPI 2 |
| **Unit** | GBP (£) per order |
| **Table** | `curated.fact_orders` |

```sql
SELECT SUM(order_revenue) / COUNT(DISTINCT invoice_no) AS avg_order_value
FROM curated.fact_orders
WHERE is_cancelled = FALSE;
```

---

### KPI 4 — Repeat Purchase Rate

| Field | Value |
|-------|-------|
| **Definition** | Percentage of customers who placed more than one order |
| **Source columns** | `CustomerID`, `InvoiceNo` |
| **Filter** | CustomerID IS NOT NULL, InvoiceNo NOT LIKE 'C%' |
| **Unit** | Percentage (%) |
| **Table** | `curated.dim_customers` |
| **Caveat** | Customers with null CustomerID (guest checkouts) are excluded; this understates repeat rate slightly |

```sql
WITH customer_orders AS (
    SELECT customer_id, COUNT(DISTINCT invoice_no) AS order_count
    FROM curated.fact_orders
    WHERE is_cancelled = FALSE AND customer_id IS NOT NULL
    GROUP BY customer_id
)
SELECT
    ROUND(100.0 * SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) / COUNT(*), 2)
        AS repeat_purchase_rate_pct
FROM customer_orders;
```

---

### KPI 5 — Monthly Revenue Growth

| Field | Value |
|-------|-------|
| **Definition** | Month-over-month percentage change in total revenue |
| **Source columns** | `InvoiceDate`, `Quantity`, `UnitPrice` |
| **Filter** | InvoiceNo NOT LIKE 'C%', Quantity > 0, UnitPrice > 0 |
| **Unit** | Percentage (%) |
| **Table** | `curated.fact_sales` |

```sql
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', invoice_date) AS month,
        SUM(quantity * unit_price) AS revenue
    FROM curated.fact_sales
    WHERE is_cancelled = FALSE
    GROUP BY 1
)
SELECT
    month,
    revenue,
    LAG(revenue) OVER (ORDER BY month) AS prev_month_revenue,
    ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
          / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 2) AS mom_growth_pct
FROM monthly
ORDER BY month;
```

---

### KPI 6 — Top / Bottom Products by Revenue

| Field | Value |
|-------|-------|
| **Definition** | Revenue rank per StockCode / Description (retail products only) |
| **Source columns** | `StockCode`, `Description`, `Quantity`, `UnitPrice` |
| **Filter** | InvoiceNo NOT LIKE 'C%', Quantity > 0, UnitPrice > 0; service/admin codes excluded |
| **Unit** | GBP (£) |
| **Table** | `curated.dim_products` |
| **Exclusions** | `stock_code NOT IN ('DOT', 'POST', 'M')` — these are service/admin codes (DOTCOM POSTAGE, POSTAGE, Manual) not retail products |

```sql
SELECT
    stock_code,
    description,
    total_revenue,
    total_quantity_sold
FROM curated.dim_products
WHERE stock_code NOT IN ('DOT', 'POST', 'M')
ORDER BY total_revenue DESC
LIMIT 10;
```

---

### KPI 7 — Cancellation / Return Rate

| Field | Value |
|-------|-------|
| **Definition** | Cancelled invoice count as a percentage of all invoice count (including cancellations) |
| **Source columns** | `InvoiceNo` |
| **Filter** | None (includes all invoices) |
| **Unit** | Percentage (%) |
| **Table** | `curated.fact_orders` |

```sql
SELECT
    ROUND(100.0 * SUM(CASE WHEN is_cancelled THEN 1 ELSE 0 END)
          / COUNT(DISTINCT invoice_no), 2) AS cancellation_rate_pct
FROM curated.fact_orders;
```

---

## Curated Table Schema

### `curated.fact_sales` (line-item grain)

| Column | Type | Description |
|--------|------|-------------|
| `invoice_no` | VARCHAR | Invoice identifier |
| `stock_code` | VARCHAR | Product code |
| `description` | VARCHAR | Product description |
| `quantity` | INTEGER | Units sold (positive only) |
| `invoice_date` | TIMESTAMP | Date and time of invoice |
| `unit_price` | DECIMAL(10,2) | Price per unit in GBP |
| `customer_id` | VARCHAR | Hashed customer key (NULL = guest) |
| `country` | VARCHAR | Customer country |
| `line_revenue` | DECIMAL(12,2) | `quantity * unit_price` |
| `is_cancelled` | BOOLEAN | TRUE if InvoiceNo starts with C |

### `curated.fact_orders` (invoice grain)

| Column | Type | Description |
|--------|------|-------------|
| `invoice_no` | VARCHAR | Invoice identifier (PK) |
| `invoice_date` | TIMESTAMP | Invoice date |
| `customer_id` | VARCHAR | Hashed customer key |
| `country` | VARCHAR | Customer country |
| `order_revenue` | DECIMAL(12,2) | Sum of line revenues |
| `line_count` | INTEGER | Number of distinct line items |
| `is_cancelled` | BOOLEAN | TRUE if cancellation invoice |

### `curated.dim_products`

| Column | Type | Description |
|--------|------|-------------|
| `stock_code` | VARCHAR | Product code (PK) |
| `description` | VARCHAR | Most frequent description for this stock_code |
| `total_revenue` | DECIMAL(12,2) | Lifetime revenue |
| `total_quantity_sold` | INTEGER | Total units sold |

### `curated.dim_customers`

| Column | Type | Description |
|--------|------|-------------|
| `customer_id` | VARCHAR | Hashed customer key (PK) |
| `country` | VARCHAR | Most frequent country for customer |
| `first_order_date` | DATE | First order date |
| `last_order_date` | DATE | Last order date |
| `order_count` | INTEGER | Total orders placed |
| `total_spend` | DECIMAL(12,2) | Total lifetime spend |

### `curated.dim_countries`

| Column | Type | Description |
|--------|------|-------------|
| `country` | VARCHAR | Country name (PK) |
| `total_revenue` | DECIMAL(12,2) | Revenue from this country |
| `order_count` | INTEGER | Orders from this country |
| `customer_count` | INTEGER | Distinct customers from this country |

---

### KPI 4b — Returning Customer Revenue Share

| Field | Value |
|-------|-------|
| **Definition** | Share of non-cancelled order revenue attributable to customers who placed more than one order |
| **Source columns** | `order_revenue`, `customer_id`, `order_count` |
| **Filter** | `fact_orders.is_cancelled = FALSE`; customers matched via `dim_customers` LEFT JOIN |
| **Unit** | Percentage (%) and GBP (£) |
| **Table** | `curated.fact_orders`, `curated.dim_customers` |
| **Caveat** | Guest orders (null `customer_id`) cannot be joined; they are excluded from both returning and one-time segments |

```sql
SELECT
    ROUND(100.0 * SUM(CASE WHEN dc.order_count > 1 THEN fo.order_revenue ELSE 0 END)
          / NULLIF(SUM(fo.order_revenue), 0), 2) AS returning_customer_revenue_pct,
    ROUND(SUM(CASE WHEN dc.order_count > 1 THEN fo.order_revenue ELSE 0 END), 2)
        AS returning_customer_revenue_gbp
FROM curated.fact_orders fo
LEFT JOIN curated.dim_customers dc ON fo.customer_id = dc.customer_id
WHERE NOT fo.is_cancelled;
```

---

## Assumptions

1. **Revenue currency:** All values are GBP (£); no FX conversion applied.
2. **Cancellation identification:** InvoiceNo prefix `C` is the sole cancellation signal — no matching against original invoices.
3. **Guest customers:** Rows with null CustomerID are included in revenue KPIs but excluded from customer-level (repeat-purchase) analysis.
4. **Stock descriptions:** Where the same StockCode has multiple descriptions, the most frequent description is used in `dim_products`.
5. **Date range:** 2010-12-01 to 2011-12-09 (per known dataset bounds); any rows outside this window are flagged.
6. **Negative quantities outside cancellations:** Treated as anomalies, logged, and excluded from revenue calculations.
7. **Non-product stock codes:** DOT, POST, M are excluded from product revenue rankings as they represent postage and manual/administrative adjustments, not retail products.

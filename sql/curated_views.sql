-- DuckDB/ANSI-compatible reference SQL for the files produced by src/pipeline.py.
-- The default local runner uses pandas so it has no database service requirement.

CREATE OR REPLACE VIEW curated_sales AS
SELECT * FROM read_csv_auto('data/processed/fact_sales.csv');

CREATE OR REPLACE VIEW curated_orders AS
SELECT * FROM read_csv_auto('data/processed/fact_orders.csv');

CREATE OR REPLACE VIEW monthly_sales AS
SELECT * FROM read_csv_auto('data/processed/agg_monthly_sales.csv');

-- Example KPI query: total sales, orders, and average order value.
SELECT
  ROUND(SUM(sales_amount), 2) AS total_sales,
  COUNT(*) AS order_count,
  ROUND(SUM(sales_amount) / NULLIF(COUNT(*), 0), 2) AS average_order_value
FROM curated_orders;

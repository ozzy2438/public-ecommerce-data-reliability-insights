from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src.pipeline import CURATED_DB_PATH, EXPECTED_COLUMNS, EXPECTED_ROWS, MANIFEST_PATH, PROCESSED_DIR, QUALITY_REPORT_PATH, run  # noqa: E402


class PipelineOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run()
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.cleaned = pd.read_csv(PROCESSED_DIR / "cleaned_transactions.csv")
        cls.sales = pd.read_csv(PROCESSED_DIR / "fact_sales.csv", dtype={"InvoiceNo": "string"})
        cls.orders = pd.read_csv(PROCESSED_DIR / "fact_orders.csv", dtype={"InvoiceNo": "string"})

    def test_source_manifest_shape(self) -> None:
        self.assertEqual(self.manifest["row_count"], EXPECTED_ROWS)
        self.assertEqual(self.manifest["columns"], EXPECTED_COLUMNS)

    def test_cleaned_layer_has_no_raw_customer_id_or_exact_duplicates(self) -> None:
        self.assertNotIn("CustomerID", self.cleaned.columns)
        self.assertEqual(int(self.cleaned.duplicated().sum()), 0)
        self.assertGreater(len(self.cleaned), 0)

    def test_curated_sales_policy(self) -> None:
        self.assertTrue((self.sales["Quantity"] > 0).all())
        self.assertTrue((self.sales["UnitPrice"] > 0).all())
        self.assertTrue(~self.sales["InvoiceNo"].astype(str).str.startswith("C").any())
        self.assertAlmostEqual(float(self.sales["sales_amount"].sum()), self.result["quality"]["positive_sales_amount"], places=2)

    def test_order_totals_reconcile_to_sales(self) -> None:
        self.assertEqual(self.sales["InvoiceNo"].nunique(), len(self.orders))
        self.assertAlmostEqual(float(self.sales["sales_amount"].sum()), float(self.orders["sales_amount"].sum()), places=2)

    def test_quality_report_and_outputs_exist(self) -> None:
        self.assertTrue(QUALITY_REPORT_PATH.exists())
        report = QUALITY_REPORT_PATH.read_text(encoding="utf-8")
        self.assertIn("# Data Quality Report", report)
        self.assertIn("exact_duplicates", report)
        for name in ["dim_customer.csv", "dim_product.csv", "agg_monthly_sales.csv", "agg_country_sales.csv", "quality_metrics.json"]:
            self.assertTrue((PROCESSED_DIR / name).exists(), name)

    def test_curated_duckdb_schema_is_privacy_safe_and_reconciled(self) -> None:
        import duckdb

        self.assertTrue(CURATED_DB_PATH.exists())
        with duckdb.connect(str(CURATED_DB_PATH), read_only=True) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
                ).fetchall()
            }
            self.assertEqual(
                tables,
                {"fact_sales", "fact_orders", "dim_products", "dim_customers", "dim_countries", "quality_summary"},
            )
            sales_columns = {
                row[0]
                for row in connection.execute("DESCRIBE curated.fact_sales").fetchall()
            }
            self.assertNotIn("CustomerID", sales_columns)
            self.assertIn("customer_id", sales_columns)
            sales_total, order_total = connection.execute(
                "SELECT SUM(line_revenue), "
                "(SELECT SUM(order_revenue) FROM curated.fact_orders WHERE NOT is_cancelled) "
                "FROM curated.fact_sales"
            ).fetchone()
            self.assertAlmostEqual(float(sales_total), float(order_total), places=2)


if __name__ == "__main__":
    unittest.main()

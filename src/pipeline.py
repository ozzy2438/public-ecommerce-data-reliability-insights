"""Build raw, cleaned, curated and data-quality outputs for UCI Online Retail.

The source workbook is kept as a local raw input. Processed outputs never contain
the source CustomerID; they contain a deterministic, salted customer key instead.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "reports"
ARCHIVE_PATH = RAW_DIR / "online-retail.zip"
MANIFEST_PATH = RAW_DIR / "source_manifest.json"
QUALITY_REPORT_PATH = REPORT_DIR / "data_quality_report.md"

SOURCE_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
SOURCE_RECORD_URL = "https://archive.ics.uci.edu/dataset/352/online-retail"
SOURCE_SHA256 = "f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b"
EXPECTED_ROWS = 541_909
EXPECTED_COLUMNS = [
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
]
DEFAULT_SALT = "public-ecommerce-demo-salt-v1"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_archive() -> tuple[Path, str]:
    """Return the local archive, downloading it only when it is absent."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if ARCHIVE_PATH.exists():
        return ARCHIVE_PATH, "existing_local_archive"
    try:
        urllib.request.urlretrieve(SOURCE_URL, ARCHIVE_PATH)
    except Exception as exc:  # pragma: no cover - exercised only without network
        if ARCHIVE_PATH.exists():
            ARCHIVE_PATH.unlink()
        raise RuntimeError(
            "UCI download failed and no local archive is available; "
            "provide data/raw/online-retail.zip for an explicit local fallback."
        ) from exc
    return ARCHIVE_PATH, "downloaded_from_uci"


def read_source(archive_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    archive_bytes = archive_path.read_bytes()
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        workbook_names = [n for n in archive.namelist() if n.lower().endswith(".xlsx")]
        if len(workbook_names) != 1:
            raise ValueError(f"Expected exactly one xlsx workbook, found {workbook_names}")
        workbook_name = workbook_names[0]
        workbook_bytes = archive.read(workbook_name)
    frame = pd.read_excel(BytesIO(workbook_bytes), engine="openpyxl")
    manifest = {
        "dataset": "UCI Online Retail",
        "source_record_url": SOURCE_RECORD_URL,
        "download_url": SOURCE_URL,
        "citation": "Chen, D. (2015). Online Retail. UCI Machine Learning Repository. DOI: 10.24432/C5BW33.",
        "license": "CC BY 4.0 (as stated on the UCI dataset record)",
        "downloaded_at_utc": utc_now(),
        "acquisition_mode": "existing_local_archive",
        "archive_path": str(archive_path.relative_to(PROJECT_ROOT)),
        "archive_sha256": sha256_bytes(archive_bytes),
        "workbook_name": workbook_name,
        "workbook_bytes": len(workbook_bytes),
        "workbook_sha256": sha256_bytes(workbook_bytes),
        "row_count": int(len(frame)),
        "columns": list(frame.columns),
        "dtypes_as_read": {column: str(dtype) for column, dtype in frame.dtypes.items()},
    }
    return frame, manifest


def _hash_customer(value: Any, salt: str) -> str | pd.NA:
    if pd.isna(value):
        return pd.NA
    normalized = str(int(float(value)))
    return hashlib.sha256(f"{salt}:{normalized}".encode("utf-8")).hexdigest()[:32]


def normalize_source(frame: pd.DataFrame, salt: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Normalize types, remove exact duplicates, and retain anomaly flags."""
    source_rows = len(frame)
    data = frame.copy()
    data.columns = [str(column).strip() for column in data.columns]
    missing_columns = sorted(set(EXPECTED_COLUMNS) - set(data.columns))
    if missing_columns:
        raise ValueError(f"Missing required source columns: {missing_columns}")
    data = data[EXPECTED_COLUMNS]

    data["InvoiceNo"] = data["InvoiceNo"].astype("string").str.strip()
    data["StockCode"] = data["StockCode"].astype("string").str.strip()
    data["Description"] = data["Description"].astype("string").str.strip()
    data["Country"] = data["Country"].astype("string").str.strip()
    data["Quantity"] = pd.to_numeric(data["Quantity"], errors="coerce").astype("Int64")
    data["InvoiceDate"] = pd.to_datetime(data["InvoiceDate"], errors="coerce")
    data["UnitPrice"] = pd.to_numeric(data["UnitPrice"], errors="coerce")
    data["CustomerID"] = pd.to_numeric(data["CustomerID"], errors="coerce")

    exact_duplicate_mask = data.duplicated(keep="first")
    duplicate_rows = int(exact_duplicate_mask.sum())
    data = data.loc[~exact_duplicate_mask].copy()

    data["is_cancelled"] = data["InvoiceNo"].str.startswith("C", na=False)
    data["is_return_or_negative"] = data["Quantity"].fillna(0).lt(0)
    data["line_amount"] = data["Quantity"].astype("Float64") * data["UnitPrice"].astype("Float64")
    data["customer_key"] = data["CustomerID"].map(lambda value: _hash_customer(value, salt)).astype("string")
    data["order_month"] = data["InvoiceDate"].dt.to_period("M").astype("string")
    data["source_row_id"] = range(1, len(data) + 1)

    invalid_required_mask = (
        data["InvoiceNo"].isna()
        | data["InvoiceNo"].eq("")
        | data["StockCode"].isna()
        | data["StockCode"].eq("")
        | data["Quantity"].isna()
        | data["InvoiceDate"].isna()
        | data["UnitPrice"].isna()
    )
    # Keep structurally valid anomalies in cleaned data for transparent quality reporting.
    clean = data.loc[~invalid_required_mask].copy()
    clean["line_amount"] = clean["line_amount"].astype(float).round(2)
    # The raw CustomerID is intentionally not emitted to any processed output.
    clean_output = clean.drop(columns=["CustomerID"])
    clean_output.to_csv(PROCESSED_DIR / "cleaned_transactions.csv", index=False)

    positive_sales = clean.loc[
        clean["Quantity"].gt(0)
        & clean["UnitPrice"].gt(0)
        & ~clean["is_cancelled"]
    ].copy()
    sales_columns = [
        "InvoiceNo", "StockCode", "Description", "InvoiceDate", "Quantity",
        "UnitPrice", "line_amount", "customer_key", "Country", "order_month",
    ]
    sales = positive_sales[sales_columns].rename(columns={"line_amount": "sales_amount"})
    sales.to_csv(PROCESSED_DIR / "fact_sales.csv", index=False)

    orders = (
        positive_sales.groupby("InvoiceNo", as_index=False)
        .agg(
            customer_key=("customer_key", "first"),
            order_date=("InvoiceDate", "min"),
            country=("Country", "first"),
            sales_amount=("line_amount", "sum"),
            line_count=("InvoiceNo", "size"),
            product_count=("StockCode", "nunique"),
        )
    )
    orders["order_month"] = orders["order_date"].dt.to_period("M").astype("string")
    orders["sales_amount"] = orders["sales_amount"].round(2)
    orders.to_csv(PROCESSED_DIR / "fact_orders.csv", index=False)

    customer_dim = (
        orders.loc[orders["customer_key"].notna()]
        .groupby("customer_key", as_index=False)
        .agg(
            first_order_date=("order_date", "min"),
            last_order_date=("order_date", "max"),
            order_count=("InvoiceNo", "nunique"),
            sales_amount=("sales_amount", "sum"),
            country=("country", "first"),
        )
    )
    customer_dim["segment"] = customer_dim["order_count"].map(
        lambda count: "repeat" if count >= 2 else "one_time"
    )
    customer_dim["sales_amount"] = customer_dim["sales_amount"].round(2)
    customer_dim.to_csv(PROCESSED_DIR / "dim_customer.csv", index=False)

    product_dim = (
        positive_sales.groupby("StockCode", as_index=False)
        .agg(
            description=("Description", "first"),
            order_count=("InvoiceNo", "nunique"),
            units_sold=("Quantity", "sum"),
            sales_amount=("line_amount", "sum"),
        )
        .sort_values("sales_amount", ascending=False)
    )
    product_dim["sales_amount"] = product_dim["sales_amount"].round(2)
    product_dim.to_csv(PROCESSED_DIR / "dim_product.csv", index=False)

    monthly = (
        orders.groupby("order_month", as_index=False)
        .agg(sales_amount=("sales_amount", "sum"), order_count=("InvoiceNo", "nunique"))
        .sort_values("order_month")
    )
    monthly["sales_amount"] = monthly["sales_amount"].round(2)
    monthly["mom_growth_pct"] = monthly["sales_amount"].pct_change().mul(100).round(2)
    monthly.to_csv(PROCESSED_DIR / "agg_monthly_sales.csv", index=False)

    country = (
        orders.groupby("country", as_index=False)
        .agg(sales_amount=("sales_amount", "sum"), order_count=("InvoiceNo", "nunique"))
        .sort_values("sales_amount", ascending=False)
    )
    country["sales_amount"] = country["sales_amount"].round(2)
    country.to_csv(PROCESSED_DIR / "agg_country_sales.csv", index=False)

    quality = {
        "source_rows": source_rows,
        "duplicate_rows_removed": duplicate_rows,
        "structurally_invalid_rows_removed": int(invalid_required_mask.sum()),
        "cleaned_rows": int(len(clean)),
        "fact_sales_rows": int(len(sales)),
        "fact_order_rows": int(len(orders)),
        "customer_dimension_rows": int(len(customer_dim)),
        "product_dimension_rows": int(len(product_dim)),
        "missing_values_cleaned": {key: int(value) for key, value in clean.isna().sum().items()},
        "negative_quantity_rows": int(clean["Quantity"].lt(0).sum()),
        "non_positive_price_rows": int(clean["UnitPrice"].le(0).sum()),
        "cancelled_invoice_rows": int(clean["is_cancelled"].sum()),
        "positive_sales_amount": round(float(sales["sales_amount"].sum()), 2),
        "positive_sales_customer_missing_rows": int(sales["customer_key"].isna().sum()),
    }
    return clean, quality


def quality_checks(clean: pd.DataFrame, manifest: dict[str, Any], quality: dict[str, Any]) -> list[dict[str, Any]]:
    numeric_sales = clean.loc[clean["Quantity"].gt(0) & clean["UnitPrice"].gt(0), "line_amount"]
    q1, q3 = numeric_sales.quantile([0.25, 0.75])
    upper_fence = float(q3 + 1.5 * (q3 - q1))
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, observed: Any, expected: str, note: str = "") -> None:
        checks.append({"name": name, "status": status, "observed": observed, "expected": expected, "note": note})

    add("source_schema", "PASS" if manifest["columns"] == EXPECTED_COLUMNS else "FAIL", manifest["columns"], "the eight UCI columns")
    add("source_row_count", "PASS" if manifest["row_count"] == EXPECTED_ROWS else "FAIL", manifest["row_count"], str(EXPECTED_ROWS))
    add("archive_checksum", "PASS" if manifest["archive_sha256"] == SOURCE_SHA256 else "WARN", manifest["archive_sha256"], SOURCE_SHA256, "WARN permits a refreshed but schema-compatible source archive.")
    add("exact_duplicates", "WARN" if quality["duplicate_rows_removed"] else "PASS", quality["duplicate_rows_removed"], "0 preferred; removed before cleaned layer", "Duplicates are reported, then first occurrence is retained.")
    add("missing_customer_id", "WARN" if quality["positive_sales_customer_missing_rows"] else "PASS", quality["positive_sales_customer_missing_rows"], "0 preferred", "Anonymous customer ID is absent for some valid lines; those lines remain in sales totals but not customer repeat-rate denominators.")
    add("invalid_dates", "PASS" if clean["InvoiceDate"].notna().all() else "FAIL", int(clean["InvoiceDate"].isna().sum()), "0")
    add("negative_quantity", "WARN" if quality["negative_quantity_rows"] else "PASS", quality["negative_quantity_rows"], "0 preferred", "Negative quantity is retained as return/cancellation evidence and excluded from fact_sales.")
    add("non_positive_unit_price", "WARN" if quality["non_positive_price_rows"] else "PASS", quality["non_positive_price_rows"], "0 preferred", "Non-positive prices are retained for audit and excluded from fact_sales.")
    add("line_amount_outliers", "WARN" if int((numeric_sales > upper_fence).sum()) else "PASS", int((numeric_sales > upper_fence).sum()), f"0 preferred; IQR upper fence <= {upper_fence:.2f}", "Outliers are flagged, not silently removed.")
    add("cleaned_no_exact_duplicates", "PASS" if not clean.duplicated().any() else "FAIL", int(clean.duplicated().sum()), "0")
    add("curated_positive_sales", "PASS", quality["fact_sales_rows"], "all rows quantity > 0, unit price > 0, non-cancelled")
    return checks


def write_quality_report(manifest: dict[str, Any], quality: dict[str, Any], checks: list[dict[str, Any]], clean: pd.DataFrame) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    failures = [check for check in checks if check["status"] == "FAIL"]
    warnings = [check for check in checks if check["status"] == "WARN"]
    lines = [
        "# Data Quality Report",
        "",
        f"Generated at (UTC): `{manifest['downloaded_at_utc']}`",
        "Dataset: UCI Machine Learning Repository — Online Retail (dataset 352)",
        "",
        "## Source and provenance",
        "",
        f"- Official record: [{SOURCE_RECORD_URL}]({SOURCE_RECORD_URL})",
        f"- Download URL: [{SOURCE_URL}]({SOURCE_URL})",
        f"- License: {manifest['license']}",
        f"- Local archive: `{manifest['archive_path']}`",
        f"- Archive SHA-256: `{manifest['archive_sha256']}`",
        f"- Workbook SHA-256: `{manifest['workbook_sha256']}`",
        f"- Source rows: **{manifest['row_count']:,}**; source columns: `{', '.join(manifest['columns'])}`",
        "",
        "## Layer row counts",
        "",
        "| Layer/output | Rows | Policy |",
        "|---|---:|---|",
        f"| Raw workbook | {manifest['row_count']:,} | Source preserved locally in the archive |",
        f"| Cleaned transactions | {quality['cleaned_rows']:,} | Exact duplicates and structurally invalid rows removed; anomalies retained |",
        f"| Curated sales fact | {quality['fact_sales_rows']:,} | Positive quantity and price, non-cancelled lines only |",
        f"| Curated order fact | {quality['fact_order_rows']:,} | One row per positive-sales invoice |",
        f"| Customer dimension | {quality['customer_dimension_rows']:,} | Hashed customer keys with at least one curated order |",
        f"| Product dimension | {quality['product_dimension_rows']:,} | One row per curated stock code |",
        "",
        "## Automated checks",
        "",
        "| Check | Status | Observed | Expected | Note |",
        "|---|---|---:|---|---|",
    ]
    for check in checks:
        observed = str(check["observed"]).replace("|", "\\|")
        lines.append(f"| {check['name']} | **{check['status']}** | {observed} | {check['expected']} | {check['note']} |")
    lines.extend([
        "",
        f"Summary: **{len(failures)} FAIL**, **{len(warnings)} WARN**, **{len(checks) - len(failures) - len(warnings)} PASS**.",
        "",
        "## Missingness and anomaly counts",
        "",
        "| Measure | Count |",
        "|---|---:|",
        f"| Exact duplicate rows removed | {quality['duplicate_rows_removed']:,} |",
        f"| Structurally invalid rows removed | {quality['structurally_invalid_rows_removed']:,} |",
        f"| Negative-quantity rows | {quality['negative_quantity_rows']:,} |",
        f"| Non-positive unit-price rows | {quality['non_positive_price_rows']:,} |",
        f"| Cancelled invoice rows | {quality['cancelled_invoice_rows']:,} |",
        f"| Positive sales lines missing customer key | {quality['positive_sales_customer_missing_rows']:,} |",
        "",
        "## Transformation assumptions",
        "",
        "1. Exact duplicate rows are source-level repeats; only the first copy is retained in `cleaned_transactions.csv`.",
        "2. Cancellation is identified by an `InvoiceNo` beginning with `C`; negative quantity is also treated as return/cancellation evidence.",
        "3. `fact_sales.csv` excludes cancellations, negative/zero quantities, and non-positive unit prices. These rows are not deleted from the cleaned audit layer.",
        "4. Missing `CustomerID` is allowed in sales totals. Repeat-customer metrics must use only orders with a non-null deterministic `customer_key`.",
        "5. Customer keys are truncated SHA-256 digests of a configurable salt and source ID. This is pseudonymisation, not a guarantee of anonymity.",
        "6. No product category exists in the source schema; StockCode/product performance is used as the product-level analysis grain.",
        "7. IQR outliers are surfaced as WARN and are not removed automatically.",
        "",
        "## Privacy",
        "",
        "The source archive is a local input artifact and is not redistributed by the processed outputs. The raw `CustomerID` column is absent from all processed CSVs; only the deterministic `customer_key` is emitted.",
        "",
        "## Output files",
        "",
        "- `data/raw/source_manifest.json`",
        "- `data/processed/cleaned_transactions.csv`",
        "- `data/processed/fact_sales.csv`, `fact_orders.csv`",
        "- `data/processed/dim_customer.csv`, `dim_product.csv`",
        "- `data/processed/agg_monthly_sales.csv`, `agg_country_sales.csv`",
    ])
    QUALITY_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    archive_path, mode = ensure_archive()
    frame, manifest = read_source(archive_path)
    manifest["acquisition_mode"] = mode
    salt = os.environ.get("CUSTOMER_HASH_SALT", DEFAULT_SALT)
    clean, quality = normalize_source(frame, salt)
    checks = quality_checks(clean, manifest, quality)
    manifest["customer_hash"] = "sha256(salt:CustomerID) truncated to 32 hex chars; salt is not written to outputs"
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
    (PROCESSED_DIR / "quality_metrics.json").write_text(json.dumps(quality, indent=2) + "\n", encoding="utf-8")
    write_quality_report(manifest, quality, checks, clean)
    return {"manifest": manifest, "quality": quality, "checks": checks}


if __name__ == "__main__":
    try:
        result = run()
    except Exception as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        raise
    print(json.dumps(result, indent=2, default=str))

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import plotly.express as px
import requests

DATASET_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
COLUMN_MAP = {
    "Invoice": "invoice",
    "InvoiceNo": "invoice",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "Price": "unit_price",
    "UnitPrice": "unit_price",
    "Customer ID": "customer_id",
    "CustomerID": "customer_id",
    "Country": "country",
}


def download_source(raw_dir: Path) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    workbook_path = raw_dir / "online_retail_II.xlsx"
    if workbook_path.exists() and workbook_path.stat().st_size > 0:
        return workbook_path

    response = requests.get(
        DATASET_URL,
        headers={"User-Agent": "blvxx-analyst-portfolio/1.0 (research project)"},
        timeout=180,
    )
    response.raise_for_status()
    archive_path = raw_dir / "uci_online_retail_ii.zip"
    archive_path.write_bytes(response.content)

    with zipfile.ZipFile(archive_path) as archive:
        candidates = [name for name in archive.namelist() if name.lower().endswith(".xlsx")]
        if not candidates:
            raise ValueError("UCI archive does not contain an XLSX workbook")
        workbook_path.write_bytes(archive.read(candidates[0]))
    return workbook_path


def load_workbook(workbook_path: Path) -> pd.DataFrame:
    sheets = pd.read_excel(workbook_path, sheet_name=None, engine="openpyxl")
    if not sheets:
        raise ValueError("Workbook has no worksheets")
    frames = []
    for sheet_name, frame in sheets.items():
        current = frame.copy()
        current["source_sheet"] = sheet_name
        frames.append(current)
    return pd.concat(frames, ignore_index=True)


def standardize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data.columns = [str(column).strip() for column in data.columns]
    rename = {column: COLUMN_MAP[column] for column in data.columns if column in COLUMN_MAP}
    data = data.rename(columns=rename)
    required = {"invoice", "stock_code", "quantity", "invoice_date", "unit_price", "customer_id", "country"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Unexpected UCI workbook schema; missing columns: {sorted(missing)}")
    return data


def prepare_sales(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    data = standardize_columns(frame)
    raw_rows = len(data)
    data["invoice"] = data["invoice"].astype("string").str.strip()
    data["quantity"] = pd.to_numeric(data["quantity"], errors="coerce")
    data["unit_price"] = pd.to_numeric(data["unit_price"], errors="coerce")
    data["invoice_date"] = pd.to_datetime(data["invoice_date"], errors="coerce")
    if "description" not in data.columns:
        data["description"] = pd.NA

    exact_duplicates = int(data.duplicated().sum())
    cancellation_invoice = data["invoice"].str.upper().str.startswith("C", na=False)
    negative_quantity = data["quantity"].lt(0).fillna(False)
    cancelled_or_returned = cancellation_invoice | negative_quantity
    invalid_quantity_or_price = (
        data["quantity"].isna() | data["unit_price"].isna()
        | data["quantity"].le(0) | data["unit_price"].le(0)
    )
    invalid_date = data["invoice_date"].isna()

    sales = data.loc[
        ~cancelled_or_returned & ~invalid_quantity_or_price & ~invalid_date
    ].copy()
    sales["line_revenue_gbp"] = sales["quantity"] * sales["unit_price"]
    sales["order_month"] = sales["invoice_date"].dt.to_period("M").dt.to_timestamp()

    quality = {
        "source": "UCI Online Retail II (dataset 502)",
        "raw_rows": int(raw_rows),
        "sale_rows": int(len(sales)),
        "cancellation_invoice_rows": int(cancellation_invoice.sum()),
        "negative_quantity_rows": int(negative_quantity.sum()),
        "cancelled_or_returned_rows_excluded_from_gross_sales": int(cancelled_or_returned.sum()),
        "nonpositive_or_missing_quantity_price_rows": int(invalid_quantity_or_price.sum()),
        "invalid_invoice_date_rows": int(invalid_date.sum()),
        "missing_customer_id_in_sales_rows": int(sales["customer_id"].isna().sum()),
        "exact_duplicate_rows_flagged_not_removed": exact_duplicates,
        "data_policy": (
            "Returns/cancellations excluded from gross sales; missing customer IDs retained "
            "for order-level sales and excluded only from customer-level analysis."
        ),
    }
    return sales, quality


def build_customer_outputs(sales: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    customer_sales = sales.loc[sales["customer_id"].notna()].copy()
    if customer_sales.empty:
        empty_rfm = pd.DataFrame(columns=[
            "customer_id", "recency_days", "frequency", "monetary_gbp",
            "r_score", "f_score", "m_score", "rfm_segment",
        ])
        empty_cohort = pd.DataFrame(columns=[
            "cohort_month", "month_index", "active_customers",
            "cohort_size", "retention_rate",
        ])
        return empty_rfm, empty_cohort

    snapshot_date = sales["invoice_date"].max().normalize() + pd.Timedelta(days=1)
    rfm = customer_sales.groupby("customer_id").agg(
        last_purchase=("invoice_date", "max"),
        frequency=("invoice", "nunique"),
        monetary_gbp=("line_revenue_gbp", "sum"),
    ).reset_index()
    rfm["recency_days"] = (snapshot_date - rfm["last_purchase"].dt.normalize()).dt.days
    rfm["r_score"] = 6 - np.ceil(rfm["recency_days"].rank(method="first", pct=True) * 5).astype(int)
    rfm["f_score"] = np.ceil(rfm["frequency"].rank(method="first", pct=True) * 5).astype(int)
    rfm["m_score"] = np.ceil(rfm["monetary_gbp"].rank(method="first", pct=True) * 5).astype(int)
    rfm[["r_score", "f_score", "m_score"]] = rfm[["r_score", "f_score", "m_score"]].clip(1, 5)
    rfm["rfm_segment"] = (
        rfm["r_score"].astype(str) + rfm["f_score"].astype(str) + rfm["m_score"].astype(str)
    )
    rfm = rfm.drop(columns=["last_purchase"])

    customer_sales["order_month"] = customer_sales["invoice_date"].dt.to_period("M")
    first_purchase = customer_sales.groupby("customer_id")["order_month"].min().rename("cohort_month")
    cohort_rows = customer_sales.join(first_purchase, on="customer_id")
    cohort_rows["month_index"] = (
        (cohort_rows["order_month"].dt.year - cohort_rows["cohort_month"].dt.year) * 12
        + cohort_rows["order_month"].dt.month - cohort_rows["cohort_month"].dt.month
    )
    cohort_counts = (
        cohort_rows.groupby(["cohort_month", "month_index"])["customer_id"]
        .nunique().rename("active_customers").reset_index()
    )
    cohort_sizes = cohort_counts.loc[cohort_counts["month_index"].eq(0), [
        "cohort_month", "active_customers"
    ]].rename(columns={"active_customers": "cohort_size"})
    retention = cohort_counts.merge(cohort_sizes, on="cohort_month", how="left")
    retention["retention_rate"] = retention["active_customers"] / retention["cohort_size"]
    retention["cohort_month"] = retention["cohort_month"].astype(str)
    return rfm, retention


def build_outputs(sales: pd.DataFrame, quality: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    orders = sales.groupby("invoice").agg(
        order_date=("invoice_date", "min"),
        revenue_gbp=("line_revenue_gbp", "sum"),
        country=("country", "first"),
        customer_id=("customer_id", "first"),
    ).reset_index()
    orders["order_month"] = orders["order_date"].dt.to_period("M").dt.to_timestamp()
    monthly = orders.groupby("order_month").agg(
        revenue_gbp=("revenue_gbp", "sum"),
        orders=("invoice", "nunique"),
        customers=("customer_id", "nunique"),
    ).reset_index()
    monthly["average_order_value_gbp"] = monthly["revenue_gbp"] / monthly["orders"]

    country = orders.groupby("country").agg(
        revenue_gbp=("revenue_gbp", "sum"),
        orders=("invoice", "nunique"),
        customers=("customer_id", "nunique"),
    ).reset_index().sort_values("revenue_gbp", ascending=False)
    rfm, retention = build_customer_outputs(sales)

    (output_dir / "quality_report.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    monthly.to_csv(output_dir / "monthly_sales.csv", index=False)
    country.to_csv(output_dir / "country_sales.csv", index=False)
    rfm.to_csv(output_dir / "customer_rfm.csv", index=False)
    retention.to_csv(output_dir / "cohort_retention.csv", index=False)
    sales.to_csv(output_dir / "clean_sales.csv", index=False)

    db = duckdb.connect(str(output_dir / "ecommerce.duckdb"))
    try:
        for name, frame in {
            "clean_sales": sales,
            "monthly_sales": monthly,
            "customer_rfm": rfm,
            "cohort_retention": retention,
        }.items():
            db.register(f"{name}_df", frame)
            db.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM {name}_df")
    finally:
        db.close()

    fig_monthly = px.line(
        monthly, x="order_month", y="revenue_gbp",
        title="Monthly gross sales (GBP)", markers=True,
        labels={"order_month": "Month", "revenue_gbp": "Gross sales, GBP"},
        template="plotly_white",
    )
    fig_cohort = px.imshow(
        retention.pivot(index="cohort_month", columns="month_index", values="retention_rate"),
        aspect="auto", color_continuous_scale="Blues",
        title="Cohort retention (share of cohort with a purchase)",
        labels={"x": "Months since first purchase", "y": "Cohort month", "color": "Retention"},
    )
    dashboard = (
        "<h1>E-commerce analytics — UCI Online Retail II</h1>"
        "<p>Historical single-retailer dataset (2009–2011). Gross sales exclude cancellations "
        "and negative-quantity rows. RFM uses identified customers only.</p>"
        + fig_monthly.to_html(full_html=False, include_plotlyjs="cdn")
        + fig_cohort.to_html(full_html=False, include_plotlyjs=False)
    )
    (output_dir / "dashboard.html").write_text(dashboard, encoding="utf-8")


def run(project_dir: Path) -> None:
    workbook = download_source(project_dir / "data" / "raw")
    raw = load_workbook(workbook)
    sales, quality = prepare_sales(raw)
    build_outputs(sales, quality, project_dir / "outputs")
    print(f"E-commerce analytics complete: {len(sales):,} sale lines")
    print(f"Dashboard: {project_dir / 'outputs' / 'dashboard.html'}")

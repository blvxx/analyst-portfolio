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
    # Zero-price lines can represent free samples/promotions; keep them and count zero revenue.
    invalid_quantity_or_price = (
        data["quantity"].isna() | data["unit_price"].isna()
        | data["quantity"].le(0) | data["unit_price"].lt(0)
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
        "missing_description_in_sales_rows": int(sales["description"].isna().sum()),
        "zero_price_sales_rows_retained": int(sales["unit_price"].eq(0).sum()),
        "exact_duplicate_rows_flagged_not_removed": exact_duplicates,
        "sales_gross_revenue_gbp": float(sales["line_revenue_gbp"].sum()),
        "sales_row_reconciliation": bool(
            len(sales) + int(cancelled_or_returned.sum())
            + int((~cancelled_or_returned & (invalid_quantity_or_price | invalid_date)).sum())
            == raw_rows
        ),
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
    max_month = customer_sales["order_month"].max()
    complete_rows = []
    for cohort_month in retention["cohort_month"].drop_duplicates():
        cohort_period = pd.Period(cohort_month, freq="M")
        last_index = (
            (max_month.year - cohort_period.year) * 12
            + max_month.month - cohort_period.month
        )
        cohort_part = retention.loc[retention["cohort_month"].eq(cohort_month)].set_index("month_index")
        for month_index in range(last_index + 1):
            existing = cohort_part.loc[month_index] if month_index in cohort_part.index else None
            active_customers = int(existing["active_customers"]) if existing is not None else 0
            cohort_size = int(cohort_part["cohort_size"].iloc[0])
            complete_rows.append({
                "cohort_month": str(cohort_month),
                "month_index": month_index,
                "active_customers": active_customers,
                "cohort_size": cohort_size,
                "retention_rate": active_customers / cohort_size if cohort_size else 0.0,
            })
    retention = pd.DataFrame(complete_rows)
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
    rfm_segments = (
        rfm.groupby("rfm_segment", dropna=False)
        .agg(customers=("customer_id", "nunique"), average_recency_days=("recency_days", "mean"),
             average_orders=("frequency", "mean"), average_customer_revenue_gbp=("monetary_gbp", "mean"))
        .reset_index()
        .sort_values("customers", ascending=False)
    )

    if not np.isclose(monthly["revenue_gbp"].sum(), sales["line_revenue_gbp"].sum()):
        raise ValueError("Monthly sales do not reconcile to gross sales")
    if int(monthly["orders"].sum()) != int(sales["invoice"].nunique()):
        raise ValueError("Monthly order count does not reconcile to distinct invoices")
    if not retention.empty and not retention.loc[retention["month_index"].eq(0), "retention_rate"].eq(1.0).all():
        raise ValueError("Cohort month-zero retention must equal 100%")

    (output_dir / "quality_report.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    monthly.to_csv(output_dir / "monthly_sales.csv", index=False)
    country.to_csv(output_dir / "country_sales.csv", index=False)
    rfm.to_csv(output_dir / "customer_rfm.csv", index=False)
    retention.to_csv(output_dir / "cohort_retention.csv", index=False)
    rfm_segments.to_csv(output_dir / "rfm_segment_summary.csv", index=False)
    sales.to_csv(output_dir / "clean_sales.csv", index=False)

    db = duckdb.connect(str(output_dir / "ecommerce.duckdb"))
    try:
        for name, frame in {
            "clean_sales": sales,
            "monthly_sales": monthly,
            "customer_rfm": rfm,
            "cohort_retention": retention,
            "rfm_segment_summary": rfm_segments,
        }.items():
            db.register(f"{name}_df", frame)
            db.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM {name}_df")
        sql_monthly = db.execute("""
            SELECT
                DATE_TRUNC('month', invoice_date) AS order_month,
                SUM(line_revenue_gbp) AS revenue_gbp,
                COUNT(DISTINCT invoice) AS orders
            FROM clean_sales
            GROUP BY 1
            ORDER BY 1
        """).fetchdf()
        sql_rfm = db.execute("""
            SELECT rfm_segment, COUNT(DISTINCT customer_id) AS customers
            FROM customer_rfm
            GROUP BY rfm_segment
        """).fetchdf()
    finally:
        db.close()

    monthly_check = monthly[["order_month", "revenue_gbp", "orders"]].merge(
        sql_monthly, on="order_month", suffixes=("_pandas", "_sql")
    )
    if (
        len(monthly_check) != len(monthly)
        or not np.allclose(monthly_check["revenue_gbp_pandas"], monthly_check["revenue_gbp_sql"])
        or not monthly_check["orders_pandas"].equals(monthly_check["orders_sql"])
    ):
        raise ValueError("SQL/Python reconciliation failed for e-commerce monthly metrics")
    rfm_check = rfm_segments[["rfm_segment", "customers"]].merge(
        sql_rfm, on="rfm_segment", suffixes=("_pandas", "_sql")
    )
    if (
        len(rfm_check) != len(rfm_segments)
        or not rfm_check["customers_pandas"].equals(rfm_check["customers_sql"])
    ):
        raise ValueError("SQL/Python reconciliation failed for RFM segment counts")
    (output_dir / "sql_reconciliation.json").write_text(
        json.dumps({
            "passed": True,
            "monthly_rows": int(len(monthly_check)),
            "gross_sales_gbp": float(monthly_check["revenue_gbp_sql"].sum()),
            "orders": int(monthly_check["orders_sql"].sum()),
            "rfm_segments": int(len(rfm_check)),
        }, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    gross_sales = float(sales["line_revenue_gbp"].sum())
    distinct_orders = int(sales["invoice"].nunique())
    identified_customers = int(sales["customer_id"].nunique())
    repeated_customers = int((rfm["frequency"] > 1).sum())
    repeat_rate = repeated_customers / identified_customers if identified_customers else 0.0
    missing_customer_share = (
        float(sales["customer_id"].isna().mean()) if len(sales) else 0.0
    )
    first_month = monthly.loc[monthly["revenue_gbp"].idxmax()] if not monthly.empty else None
    leading_country = country.iloc[0] if not country.empty else None
    month_one = retention.loc[retention["month_index"].eq(1)]
    weighted_month_one_retention = (
        float(month_one["active_customers"].sum() / month_one["cohort_size"].sum())
        if not month_one.empty and month_one["cohort_size"].sum() else None
    )
    summary = {
        "source": "UCI Online Retail II (dataset 502), CC BY 4.0",
        "raw_rows": int(quality["raw_rows"]),
        "valid_positive_sales_rows": int(len(sales)),
        "gross_sales_gbp": gross_sales,
        "distinct_invoices": distinct_orders,
        "identified_customers": identified_customers,
        "repeat_customers": repeated_customers,
        "repeat_customer_rate": repeat_rate,
        "missing_customer_id_share_of_sales_rows": missing_customer_share,
        "highest_sales_month": str(first_month["order_month"]) if first_month is not None else None,
        "highest_sales_month_revenue_gbp": float(first_month["revenue_gbp"]) if first_month is not None else None,
        "highest_sales_country": str(leading_country["country"]) if leading_country is not None else None,
        "highest_sales_country_revenue_gbp": float(leading_country["revenue_gbp"]) if leading_country is not None else None,
        "weighted_month_1_cohort_retention": weighted_month_one_retention,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    segment_lines = [
        f"- {row.rfm_segment}: {int(row.customers):,} customers"
        for row in rfm_segments.itertuples(index=False)
    ]
    findings = [
        "# E-commerce analytics — generated findings",
        "",
        "> Source: UCI Online Retail II (2009–2011), CC BY 4.0. These findings describe one historical retailer, not the current e-commerce market.",
        "",
        "## Sales and customer base",
        "",
        f"- Source rows: {summary['raw_rows']:,}.",
        f"- Valid positive sale lines: {summary['valid_positive_sales_rows']:,}.",
        f"- Gross sales (excluding cancellations and negative-quantity rows): £{gross_sales:,.2f}.",
        f"- Distinct invoices: {distinct_orders:,}.",
        f"- Identified customers: {identified_customers:,}.",
        f"- Repeat customers: {repeated_customers:,} ({repeat_rate:.2%} of identified customers).",
        f"- Sales rows without Customer ID: {missing_customer_share:.2%}.",
        "",
        "## Sales concentration and retention",
        "",
    ]
    if first_month is not None:
        findings.append(
            f"- Highest-gross-sales month: {first_month['order_month']:%Y-%m} (£{first_month['revenue_gbp']:,.2f})."
        )
    if leading_country is not None:
        findings.append(
            f"- Highest-gross-sales country: {leading_country['country']} (£{leading_country['revenue_gbp']:,.2f})."
        )
    findings.append(
        f"- Weighted month-1 cohort retention: {weighted_month_one_retention:.2%}."
        if weighted_month_one_retention is not None
        else "- Month-1 cohort retention cannot be calculated from available cohorts."
    )
    findings.extend(["", "## RFM segments", "", *segment_lines, "", "## Interpretation and limitations", ""])
    findings.extend([
        "- RFM scores are relative to this dataset and observation window; they are descriptive labels, not predicted churn probabilities.",
        "- Gross sales are before refunds; cancellation and negative-quantity lines are excluded rather than matched to each original sale.",
        "- Missing Customer IDs remain in sales totals but are excluded from customer-level calculations.",
        "- The dataset is historical (2009–2011), contains many wholesalers and does not contain cost, margin, ad spend or acquisition channel.",
        "- No claims about modern market performance, profit, CAC or ROAS can be made from these data.",
        "",
        "## SQL/Python validation",
        "",
        "- Monthly sales, invoice counts and RFM segment counts reconcile between DuckDB SQL and pandas.",
    ])
    (output_dir / "findings.md").write_text("\n".join(findings) + "\n", encoding="utf-8")

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
    fig_rfm = px.bar(
        rfm_segments, x="rfm_segment", y="customers",
        title="Customer segments (RFM)",
        hover_data=["average_recency_days", "average_orders", "average_customer_revenue_gbp"],
        labels={"rfm_segment": "RFM segment", "customers": "Customers"},
        template="plotly_white",
    )
    dashboard = (
        "<h1>E-commerce analytics — UCI Online Retail II</h1>"
        "<p>Historical single-retailer dataset (2009–2011). Gross sales exclude cancellations "
        "and negative-quantity rows. RFM uses identified customers only.</p>"
        + fig_monthly.to_html(full_html=False, include_plotlyjs="cdn")
        + fig_cohort.to_html(full_html=False, include_plotlyjs=False)
        + fig_rfm.to_html(full_html=False, include_plotlyjs=False)
    )
    (output_dir / "dashboard.html").write_text(dashboard, encoding="utf-8")


def run(project_dir: Path) -> None:
    workbook = download_source(project_dir / "data" / "raw")
    raw = load_workbook(workbook)
    sales, quality = prepare_sales(raw)
    build_outputs(sales, quality, project_dir / "outputs")
    print(f"E-commerce analytics complete: {len(sales):,} sale lines")
    print(f"Dashboard: {project_dir / 'outputs' / 'dashboard.html'}")

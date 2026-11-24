import importlib.util
from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ecommerce_pipeline", PROJECT_DIR / "pipeline.py")
ecommerce_pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ecommerce_pipeline)


def test_cancellations_and_returns_are_excluded_but_missing_customer_is_kept():
    raw = pd.DataFrame({
        "Invoice": ["10001", "C10002", "10003", "10004"],
        "StockCode": ["A", "A", "B", "C"],
        "Description": ["one", "one", "two", "three"],
        "Quantity": [2, 1, -1, 3],
        "InvoiceDate": [
            "2011-01-01 10:00:00", "2011-01-01 11:00:00",
            "2011-01-02 10:00:00", "2011-01-03 10:00:00",
        ],
        "Price": [5.0, 5.0, 2.0, 3.0],
        "Customer ID": [12345, 12345, 12345, None],
        "Country": ["United Kingdom"] * 4,
    })
    sales, report = ecommerce_pipeline.prepare_sales(raw)
    assert len(sales) == 2
    assert sales["customer_id"].isna().sum() == 1
    assert report["cancellation_invoice_rows"] == 1
    assert report["negative_quantity_rows"] == 1
    assert report["missing_customer_id_in_sales_rows"] == 1
    assert report["sales_row_reconciliation"] is True


def test_zero_price_lines_are_retained():
    raw = pd.DataFrame({
        "Invoice": ["10001"],
        "StockCode": ["A"],
        "Description": ["free sample"],
        "Quantity": [1],
        "InvoiceDate": ["2011-01-01 10:00:00"],
        "Price": [0.0],
        "Customer ID": [12345],
        "Country": ["United Kingdom"],
    })
    sales, report = ecommerce_pipeline.prepare_sales(raw)
    assert len(sales) == 1
    assert sales.iloc[0]["line_revenue_gbp"] == 0
    assert report["zero_price_sales_rows_retained"] == 1


def test_rfm_and_cohort_outputs_are_consistent():
    sales = pd.DataFrame({
        "customer_id": [1, 1, 2, 2],
        "invoice": ["A", "B", "C", "D"],
        "invoice_date": pd.to_datetime([
            "2020-01-10", "2020-02-10", "2020-01-20", "2020-03-20"
        ]),
        "line_revenue_gbp": [10.0, 15.0, 20.0, 25.0],
        "country": ["UK"] * 4,
    })
    rfm, retention = ecommerce_pipeline.build_customer_outputs(sales)
    assert len(rfm) == 2
    assert set(rfm["customer_id"]) == {1, 2}
    assert set(rfm["rfm_segment"]).issubset({
        "Champions", "Loyal customers", "Potential loyalists",
        "At risk", "New customers", "Hibernating",
    })
    assert retention.loc[retention["month_index"].eq(0), "retention_rate"].eq(1.0).all()
    assert (retention["retention_rate"].between(0, 1)).all()
    feb_customer_2 = retention.loc[
        retention["cohort_month"].eq("2020-01") & retention["month_index"].eq(1)
    ]
    assert feb_customer_2["active_customers"].iloc[0] == 1


def test_zero_activity_cohort_month_is_explicit_zero():
    sales = pd.DataFrame({
        "customer_id": [1, 1],
        "invoice": ["A", "B"],
        "invoice_date": pd.to_datetime(["2020-01-10", "2020-03-10"]),
        "line_revenue_gbp": [10.0, 15.0],
        "country": ["UK", "UK"],
    })
    _, retention = ecommerce_pipeline.build_customer_outputs(sales)
    feb = retention.loc[
        retention["cohort_month"].eq("2020-01") & retention["month_index"].eq(1)
    ]
    assert len(feb) == 1
    assert feb.iloc[0]["active_customers"] == 0
    assert feb.iloc[0]["retention_rate"] == 0.0

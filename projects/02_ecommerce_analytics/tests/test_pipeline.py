import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import build_customer_outputs, prepare_sales


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
    sales, report = prepare_sales(raw)
    assert len(sales) == 2
    assert sales["customer_id"].isna().sum() == 1
    assert report["cancellation_invoice_rows"] == 1
    assert report["negative_quantity_rows"] == 1
    assert report["missing_customer_id_in_sales_rows"] == 1


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
    rfm, retention = build_customer_outputs(sales)
    assert len(rfm) == 2
    assert set(rfm["customer_id"]) == {1, 2}
    assert retention.loc[retention["month_index"].eq(0), "retention_rate"].eq(1.0).all()
    assert (retention["retention_rate"].between(0, 1)).all()

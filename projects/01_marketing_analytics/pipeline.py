from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from scipy.stats import chi2_contingency

DATASET_URL = "https://archive.ics.uci.edu/static/public/468/online+shoppers+purchasing+intention+dataset.zip"
REQUIRED_COLUMNS = {
    "administrative", "administrative_duration", "informational",
    "informational_duration", "product_related", "product_related_duration",
    "bounce_rates", "exit_rates", "page_values", "special_day", "month",
    "operating_systems", "browser", "region", "traffic_type",
    "visitor_type", "weekend", "revenue",
}


def download_source(raw_dir: Path) -> Path:
    """Download the UCI archive once and extract the original CSV."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    csv_path = raw_dir / "online_shoppers_intention.csv"
    if csv_path.exists() and csv_path.stat().st_size > 0:
        return csv_path

    response = requests.get(
        DATASET_URL,
        headers={"User-Agent": "blvxx-analyst-portfolio/1.0 (research project)"},
        timeout=90,
    )
    response.raise_for_status()
    archive_path = raw_dir / "uci_online_shoppers.zip"
    archive_path.write_bytes(response.content)
    with zipfile.ZipFile(archive_path) as archive:
        candidates = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not candidates:
            raise ValueError("UCI archive does not contain a CSV file")
        csv_path.write_bytes(archive.read(candidates[0]))
    return csv_path


def load_and_clean(csv_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = pd.read_csv(csv_path)
    raw_rows = len(raw)
    data = raw.copy()
    data.columns = (
        data.columns.str.strip()
        .str.replace(r"([a-z])([A-Z])", r"\1_\2", regex=True)
        .str.lower()
    )
    missing_columns = REQUIRED_COLUMNS.difference(data.columns)
    if missing_columns:
        raise ValueError(f"Unexpected UCI schema; missing columns: {sorted(missing_columns)}")

    # Identical sessions can be legitimate independent observations; report them but retain them.
    duplicate_rows = int(data.duplicated().sum())
    data["revenue"] = (
        data["revenue"].astype(str).str.strip().str.lower()
        .map({"true": True, "false": False, "1": True, "0": False})
    )
    invalid_target_rows = int(data["revenue"].isna().sum())
    data = data.loc[data["revenue"].notna()].copy()
    data["revenue"] = data["revenue"].astype(bool)

    numeric_columns = [
        "administrative", "administrative_duration", "informational",
        "informational_duration", "product_related", "product_related_duration",
        "bounce_rates", "exit_rates", "page_values", "special_day",
        "operating_systems", "browser", "region", "traffic_type",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    # Outliers remain in the analytical dataset; the flag makes the tail inspectable.
    duration_columns = [
        "administrative_duration", "informational_duration", "product_related_duration"
    ]
    duration_total = data[duration_columns].sum(axis=1, min_count=1)
    threshold = float(duration_total.quantile(0.99))
    data["duration_upper_1pct_flag"] = duration_total > threshold
    data["invalid_rate_range_flag"] = (
        ~data["bounce_rates"].between(0, 1)
        | ~data["exit_rates"].between(0, 1)
    )
    data["negative_duration_flag"] = data[duration_columns].lt(0).any(axis=1)
    data["negative_page_value_flag"] = data["page_values"].lt(0)

    quality = {
        "source": "UCI Online Shoppers Purchasing Intention Dataset (dataset 468)",
        "raw_rows": int(raw_rows),
        "exact_duplicate_rows_flagged_not_removed": duplicate_rows,
        "invalid_revenue_rows_removed": invalid_target_rows,
        "clean_rows": int(len(data)),
        "missing_values_after_cleaning": {
            key: int(value) for key, value in data.isna().sum().items() if value
        },
        "duration_upper_1pct_threshold_seconds": threshold,
        "duration_upper_1pct_rows_flagged_not_removed": int(data["duration_upper_1pct_flag"].sum()),
        "invalid_bounce_or_exit_rate_rows_flagged": int(data["invalid_rate_range_flag"].sum()),
        "negative_duration_rows_flagged": int(data["negative_duration_flag"].sum()),
        "negative_page_value_rows_flagged": int(data["negative_page_value_flag"].sum()),
        "outlier_policy": (
            "Exact duplicates and statistical outliers are reported, not silently removed. "
            "Negative durations/page values and rates outside [0, 1] are flagged for review."
        ),
    }
    return data, quality


def conversion_table(data: pd.DataFrame, dimension: str) -> pd.DataFrame:
    result = (
        data.groupby(dimension, dropna=False)
        .agg(sessions=("revenue", "size"), purchases=("revenue", "sum"))
        .reset_index()
    )
    result["conversion_rate"] = result["purchases"] / result["sessions"]
    return result.sort_values("sessions", ascending=False)


def calculate_statistics(data: pd.DataFrame) -> dict[str, Any]:
    contingency = pd.crosstab(data["visitor_type"], data["revenue"])
    if contingency.shape[0] >= 2 and contingency.shape[1] >= 2:
        chi2, p_value, _, _ = chi2_contingency(contingency)
        n = int(contingency.to_numpy().sum())
        denominator = min(contingency.shape) - 1
        cramers_v = float(np.sqrt(chi2 / (n * denominator))) if denominator > 0 else 0.0
    else:
        chi2, p_value, cramers_v = float("nan"), float("nan"), float("nan")
    return {
        "visitor_type_revenue_chi2": float(chi2),
        "visitor_type_revenue_p_value": float(p_value),
        "visitor_type_revenue_cramers_v": cramers_v,
        "interpretation": "Association test only; it does not establish a causal effect.",
    }


def build_outputs(data: pd.DataFrame, quality: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    overall = {
        "sessions": int(len(data)),
        "purchases": int(data["revenue"].sum()),
        "conversion_rate": float(data["revenue"].mean()) if len(data) else 0.0,
        "dataset_purchase_rate_is_not_campaign_roi": True,
    }
    if len(data) == 0 or overall["purchases"] > overall["sessions"]:
        raise ValueError("Marketing KPI reconciliation failed: invalid session or purchase totals")
    visitor = conversion_table(data, "visitor_type")
    traffic = conversion_table(data, "traffic_type")
    month = conversion_table(data, "month")

    (output_dir / "overall_metrics.json").write_text(
        json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "quality_report.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "statistical_tests.json").write_text(
        json.dumps(calculate_statistics(data), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    visitor.to_csv(output_dir / "conversion_by_visitor.csv", index=False)
    traffic.to_csv(output_dir / "conversion_by_traffic.csv", index=False)
    month.to_csv(output_dir / "conversion_by_month.csv", index=False)
    segment_summary = (
        data.groupby("visitor_type", dropna=False)
        .agg(sessions=("revenue", "size"), purchases=("revenue", "sum"))
        .reset_index()
    )
    segment_summary["conversion_rate"] = segment_summary["purchases"] / segment_summary["sessions"]
    if int(segment_summary["sessions"].sum()) != len(data):
        raise ValueError("Visitor segment counts do not reconcile to total sessions")
    data.to_csv(output_dir / "clean_sessions.csv", index=False)

    db = duckdb.connect(str(output_dir / "marketing.duckdb"))
    try:
        db.register("sessions_df", data)
        db.execute("CREATE OR REPLACE TABLE sessions AS SELECT * FROM sessions_df")
        db.register("traffic_df", traffic)
        db.execute("CREATE OR REPLACE TABLE conversion_by_traffic AS SELECT * FROM traffic_df")
    finally:
        db.close()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=visitor["visitor_type"].astype(str),
        y=visitor["conversion_rate"],
        name="Conversion rate",
        text=(visitor["conversion_rate"] * 100).round(2).astype(str) + "%",
        textposition="outside",
    ))
    fig.update_layout(
        title="Conversion rate by visitor type",
        xaxis_title="Visitor type",
        yaxis_title="Purchase conversion rate",
        yaxis_tickformat=".0%",
        template="plotly_white",
    )
    fig2 = px.bar(
        traffic.sort_values("traffic_type"),
        x="traffic_type",
        y="conversion_rate",
        hover_data=["sessions", "purchases"],
        title="Conversion rate by TrafficType (encoded category)",
        labels={"traffic_type": "TrafficType code", "conversion_rate": "Conversion rate"},
        template="plotly_white",
    )
    html = (
        "<h1>Marketing analytics — Online Shoppers</h1>"
        "<p>Research dataset. TrafficType is an encoded category, not an ad platform. "
        "Associations are not causal effects; advertising cost and revenue are unavailable.</p>"
        + fig.to_html(full_html=False, include_plotlyjs="cdn")
        + fig2.to_html(full_html=False, include_plotlyjs=False)
    )
    (output_dir / "dashboard.html").write_text(html, encoding="utf-8")


def run(project_dir: Path) -> None:
    raw_path = download_source(project_dir / "data" / "raw")
    data, quality = load_and_clean(raw_path)
    build_outputs(data, quality, project_dir / "outputs")
    print(f"Marketing analytics complete: {len(data):,} clean sessions")
    print(f"Dashboard: {project_dir / 'outputs' / 'dashboard.html'}")

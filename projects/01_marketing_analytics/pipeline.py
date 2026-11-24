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
    "administrative",
    "administrative_duration",
    "informational",
    "informational_duration",
    "productrelated",
    "productrelated_duration",
    "bouncerates",
    "exitrates",
    "pagevalues",
    "specialday",
    "month",
    "operatingsystems",
    "browser",
    "region",
    "traffictype",
    "visitortype",
    "weekend",
    "revenue",
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
        member = candidates[0]
        csv_path.write_bytes(archive.read(member))
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

    duplicate_rows = int(data.duplicated().sum())
    data = data.drop_duplicates().copy()

    data["revenue"] = (
        data["revenue"].astype(str).str.strip().str.lower()
        .map({"true": True, "false": False, "1": True, "0": False})
    )
    invalid_target_rows = int(data["revenue"].isna().sum())
    data = data.loc[data["revenue"].notna()].copy()
    data["revenue"] = data["revenue"].astype(bool)

    numeric_columns = [
        "administrative", "administrative_duration", "informational",
        "informational_duration", "productrelated", "productrelated_duration",
        "bouncerates", "exitrates", "pagevalues", "specialday",
        "operatingsystems", "browser", "region", "traffictype",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    # Keep outliers; flag the upper tail instead of silently deleting potentially valid sessions.
    duration_columns = [
        "administrative_duration", "informational_duration", "productrelated_duration"
    ]
    duration_total = data[duration_columns].sum(axis=1, min_count=1)
    threshold = float(duration_total.quantile(0.99))
    data["duration_upper_1pct_flag"] = duration_total > threshold

    quality = {
        "source": "UCI Online Shoppers Purchasing Intention Dataset (dataset 468)",
        "raw_rows": raw_rows,
        "exact_duplicate_rows_removed": duplicate_rows,
        "invalid_revenue_rows_removed": invalid_target_rows,
        "clean_rows": int(len(data)),
        "missing_values_after_cleaning": {
            key: int(value) for key, value in data.isna().sum().items() if value
        },
        "duration_upper_1pct_threshold_seconds": threshold,
        "duration_upper_1pct_rows_flagged_not_removed": int(data["duration_upper_1pct_flag"].sum()),
        "outlier_policy": "Flag only; no automatic deletion or winsorisation.",
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
        "interpretation": (
            "Association test only; it does not establish a causal effect."
        ),
    }


def build_outputs(data: pd.DataFrame, quality: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    overall = {
        "sessions": int(len(data)),
        "purchases": int(data["revenue"].sum()),
        "conversion_rate": float(data["revenue"].mean()) if len(data) else 0.0,
        "dataset_purchase_rate_is_not_campaign_roi": True,
    }
    visitor = conversion_table(data, "visitortype")
    traffic = conversion_table(data, "traffictype")
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
        x=visitor["visitortype"].astype(str),
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
        traffic.sort_values("traffictype"),
        x="traffictype",
        y="conversion_rate",
        hover_data=["sessions", "purchases"],
        title="Conversion rate by TrafficType (encoded category)",
        labels={"traffictype": "TrafficType code", "conversion_rate": "Conversion rate"},
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

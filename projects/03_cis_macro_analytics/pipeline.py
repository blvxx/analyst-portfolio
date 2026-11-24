from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import plotly.express as px
import requests

API_BASE = "https://api.worldbank.org/v2"
COUNTRIES = {
    "RUS": "Russian Federation",
    "KAZ": "Kazakhstan",
    "BLR": "Belarus",
    "UZB": "Uzbekistan",
    "ARM": "Armenia",
    "KGZ": "Kyrgyz Republic",
}
INDICATORS = {
    "NY.GDP.PCAP.CD": "gdp_per_capita_current_usd",
    "IT.NET.USER.ZS": "internet_users_pct",
    "FP.CPI.TOTL.ZG": "inflation_cpi_annual_pct",
    "SL.UEM.TOTL.ZS": "unemployment_ilo_pct",
}


def parse_api_payload(payload: list[Any], indicator_code: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError("Unexpected World Bank API response shape")
    observations = payload[1]
    if observations is None:
        return []
    if not isinstance(observations, list):
        raise ValueError("World Bank API observations are not a list")

    rows = []
    for item in observations:
        country = item.get("country") or {}
        rows.append({
            "country_code": (country.get("id") or "").upper(),
            "country_name": country.get("value"),
            "year": int(item["date"]),
            "indicator_code": indicator_code,
            "indicator_name": (item.get("indicator") or {}).get("value"),
            "value": item.get("value"),
        })
    return rows


def fetch_indicator(
    indicator_code: str,
    start_year: int,
    end_year: int,
    timeout: int = 60,
) -> tuple[list[dict[str, Any]], list[Any]]:
    country_path = ";".join(COUNTRIES)
    url = f"{API_BASE}/country/{country_path}/indicator/{indicator_code}"
    response = requests.get(
        url,
        params={
            "format": "json",
            "date": f"{start_year}:{end_year}",
            "per_page": 20000,
            "source": 2,
        },
        headers={"User-Agent": "blvxx-analyst-portfolio/1.0 (open-data research)"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    rows = parse_api_payload(payload, indicator_code)
    return rows, payload


def build_panel(
    observations: pd.DataFrame,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    index = pd.MultiIndex.from_product(
        [COUNTRIES.keys(), range(start_year, end_year + 1)],
        names=["country_code", "year"],
    )
    grid = index.to_frame(index=False)
    country_names = pd.DataFrame(
        [{"country_code": code, "country_name": name} for code, name in COUNTRIES.items()]
    )
    grid = grid.merge(country_names, on="country_code", how="left")

    if observations.empty:
        pivot = pd.DataFrame(columns=["country_code", "year"])
    else:
        observations = observations.copy()
        observations["value"] = pd.to_numeric(observations["value"], errors="coerce")
        pivot = observations.pivot_table(
            index=["country_code", "year"],
            columns="indicator_code",
            values="value",
            aggfunc="first",
        ).reset_index()
    # Keep the expected schema even if an indicator has no observations in the selected window.
    for indicator_code in INDICATORS:
        if indicator_code not in pivot.columns:
            pivot[indicator_code] = pd.NA
    pivot = pivot[["country_code", "year", *INDICATORS.keys()]]
    panel = grid.merge(pivot, on=["country_code", "year"], how="left")
    panel = panel.rename(columns=INDICATORS)
    return panel.sort_values(["country_code", "year"]).reset_index(drop=True)


def calculate_trends(observations: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if observations.empty:
        return pd.DataFrame(columns=[
            "country_code", "country_name", "indicator_code", "indicator_name",
            "first_year", "first_value", "last_year", "last_value", "absolute_change",
        ])
    for (country_code, indicator_code), group in observations.groupby(
        ["country_code", "indicator_code"]
    ):
        valid = group.loc[group["value"].notna()].sort_values("year")
        if valid.empty:
            continue
        first = valid.iloc[0]
        last = valid.iloc[-1]
        rows.append({
            "country_code": country_code,
            "country_name": last["country_name"],
            "indicator_code": indicator_code,
            "indicator_name": last["indicator_name"],
            "first_year": int(first["year"]),
            "first_value": float(first["value"]),
            "last_year": int(last["year"]),
            "last_value": float(last["value"]),
            "absolute_change": float(last["value"] - first["value"]),
        })
    return pd.DataFrame(rows)


def build_outputs(
    observations: pd.DataFrame,
    start_year: int,
    end_year: int,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    panel = build_panel(observations, start_year, end_year)
    trends = calculate_trends(observations)

    latest_rows = []
    if not observations.empty:
        for (country_code, indicator_code), group in observations.groupby(
            ["country_code", "indicator_code"]
        ):
            valid = group.loc[group["value"].notna()].sort_values("year")
            if not valid.empty:
                latest_rows.append(valid.iloc[-1].to_dict())
    latest = pd.DataFrame(latest_rows)

    value_columns = list(INDICATORS.values())
    correlations = panel[value_columns].corr(method="pearson", min_periods=3)
    correlations.index.name = "indicator"
    correlations.to_csv(output_dir / "indicator_correlations.csv")

    missing_counts = {
        column: int(panel[column].isna().sum()) for column in value_columns
    }
    quality = {
        "source": "World Bank Indicators API v2, World Development Indicators (source=2)",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "countries": COUNTRIES,
        "indicators": INDICATORS,
        "start_year": start_year,
        "end_year": end_year,
        "long_observation_rows": int(len(observations)),
        "panel_rows": int(len(panel)),
        "missing_values_by_indicator_in_country_year_grid": missing_counts,
        "missing_policy": "No interpolation or imputation; gaps remain null.",
    }
    (output_dir / "quality_report.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    observations.to_csv(output_dir / "indicator_long.csv", index=False)
    panel.to_csv(output_dir / "macro_panel.csv", index=False)
    trends.to_csv(output_dir / "indicator_trends.csv", index=False)
    latest.to_csv(output_dir / "latest_snapshot.csv", index=False)

    db = duckdb.connect(str(output_dir / "cis_macro.duckdb"))
    try:
        for name, frame in {
            "macro_panel": panel,
            "indicator_long": observations,
            "indicator_trends": trends,
        }.items():
            db.register(f"{name}_df", frame)
            db.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM {name}_df")
    finally:
        db.close()

    html_parts = [
        "<h1>CIS macro and digital development analytics</h1>",
        "<p>World Bank WDI. Missing values are not imputed. Country and indicator "
        "coverage can differ. GDP per capita is current USD and is not real GDP growth.</p>",
    ]
    for column, label in INDICATORS.items():
        value_col = label
        fig = px.line(
            panel.loc[panel[value_col].notna()],
            x="year",
            y=value_col,
            color="country_name",
            markers=True,
            title=label.replace("_", " ").title(),
            labels={"year": "Year", value_col: label.replace("_", " "), "country_name": "Country"},
            template="plotly_white",
        )
        html_parts.append(fig.to_html(
            full_html=False, include_plotlyjs="cdn" if len(html_parts) == 2 else False
        ))
    (output_dir / "dashboard.html").write_text("\n".join(html_parts), encoding="utf-8")


def run(project_dir: Path) -> None:
    start_year = int(os.getenv("WB_START_YEAR", "2000"))
    end_year = int(os.getenv("WB_END_YEAR", "2024"))
    if start_year > end_year:
        raise ValueError("WB_START_YEAR must be less than or equal to WB_END_YEAR")

    raw_dir = project_dir / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for indicator_code in INDICATORS:
        indicator_rows, payload = fetch_indicator(indicator_code, start_year, end_year)
        rows.extend(indicator_rows)
        safe_name = indicator_code.replace(".", "_")
        (raw_dir / f"{safe_name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    observations = pd.DataFrame(rows, columns=[
        "country_code", "country_name", "year", "indicator_code", "indicator_name", "value"
    ])
    build_outputs(observations, start_year, end_year, project_dir / "outputs")
    print(f"World Bank analytics complete: {len(observations):,} observations")
    print(f"Dashboard: {project_dir / 'outputs' / 'dashboard.html'}")

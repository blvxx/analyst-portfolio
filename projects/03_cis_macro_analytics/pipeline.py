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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_BASE = "https://api.worldbank.org/v2"
COUNTRIES = {
    "RUS": "Russian Federation",
    "KAZ": "Kazakhstan",
    "BLR": "Belarus",
    "UZB": "Uzbekistan",
    "ARM": "Armenia",
    "KGZ": "Kyrgyz Republic",
}
ISO2_TO_ISO3 = {
    "RU": "RUS",
    "KZ": "KAZ",
    "BY": "BLR",
    "UZ": "UZB",
    "AM": "ARM",
    "KG": "KGZ",
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
        country_code = (
            item.get("countryiso3code")
            or country.get("id")
            or ""
        ).upper()
        country_code = ISO2_TO_ISO3.get(country_code, country_code)
        rows.append({
            "country_code": country_code,
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
    session = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    params = {
        "format": "json",
        "date": f"{start_year}:{end_year}",
        "per_page": 20000,
        "source": 2,
    }
    headers = {"User-Agent": "blvxx-analyst-portfolio/1.0 (open-data research)"}
    payloads: list[Any] = []
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        response = session.get(
            url, params={**params, "page": page}, headers=headers, timeout=timeout
        )
        response.raise_for_status()
        payload = response.json()
        page_rows = parse_api_payload(payload, indicator_code)
        rows.extend(page_rows)
        payloads.append(payload)
        if not payload or not isinstance(payload[0], dict):
            raise ValueError(f"World Bank API returned invalid pagination metadata for {indicator_code}")
        page_count = int(payload[0].get("pages") or 1)
        if page >= page_count:
            break
        page += 1
    session.close()
    return rows, payloads


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
        if observations.duplicated(["country_code", "year", "indicator_code"]).any():
            raise ValueError("Duplicate country-year-indicator observations returned by World Bank API")
        pivot = observations.pivot_table(
            index=["country_code", "year"],
            columns="indicator_code",
            values="value",
            aggfunc="first",
        ).reset_index()
    # Keep the expected numeric schema even if an indicator has no observations in the selected window.
    for indicator_code in INDICATORS:
        if indicator_code not in pivot.columns:
            pivot[indicator_code] = pd.Series(index=pivot.index, dtype="float64")
        else:
            pivot[indicator_code] = pd.to_numeric(pivot[indicator_code], errors="coerce")
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
    observations = observations.copy()
    observations["value"] = pd.to_numeric(observations["value"], errors="coerce")
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
            "relative_change_pct": (
                float((last["value"] / first["value"] - 1) * 100)
                if float(first["value"]) != 0 else None
            ),
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
    pair_counts = panel[value_columns].notna().astype(int).T.dot(
        panel[value_columns].notna().astype(int)
    )
    pair_counts.index.name = "indicator"
    pair_counts.to_csv(output_dir / "correlation_pair_counts.csv")

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
        "duplicate_country_year_indicator_rows": int(
            observations.duplicated(["country_code", "year", "indicator_code"]).sum()
        ),
        "panel_rows": int(len(panel)),
        "missing_values_by_indicator_in_country_year_grid": missing_counts,
        "non_null_observations_by_indicator": {
            code: int(observations.loc[observations["indicator_code"].eq(code), "value"].notna().sum())
            for code in INDICATORS
        },
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
        sql_panel_rows = db.execute("SELECT COUNT(*) FROM macro_panel").fetchone()[0]
        sql_long_rows = db.execute("SELECT COUNT(*) FROM indicator_long").fetchone()[0]
        sql_non_null = db.execute(
            "SELECT COUNT(*) FROM indicator_long WHERE value IS NOT NULL"
        ).fetchone()[0]
    finally:
        db.close()

    if int(sql_panel_rows) != len(panel) or int(sql_long_rows) != len(observations):
        raise ValueError("SQL/Python reconciliation failed for macro panel row counts")
    if panel.duplicated(["country_code", "year"]).any():
        raise ValueError("Macro country-year panel contains duplicate keys")
    (output_dir / "sql_reconciliation.json").write_text(
        json.dumps({
            "passed": True,
            "panel_rows": int(sql_panel_rows),
            "long_observation_rows": int(sql_long_rows),
            "non_null_values": int(sql_non_null),
        }, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    findings = [
        "# CIS macro analytics — generated findings",
        "",
        "> Source: World Bank World Development Indicators API v2. Values are country-level aggregates; observation coverage differs by indicator and country.",
        "",
        "## Coverage and data quality",
        "",
        f"- Countries: {len(COUNTRIES)}.",
        f"- Full country-year panel: {len(panel):,} rows ({start_year}–{end_year}).",
        f"- API observations including null values: {len(observations):,}.",
    ]
    for column, missing_count in missing_counts.items():
        total = len(panel)
        findings.append(
            f"- {column}: {total - missing_count:,}/{total:,} observed ({(total - missing_count) / total:.1%}); {missing_count:,} gaps."
        )
    findings.extend(["", "## First-to-last available changes", ""])
    if trends.empty:
        findings.append("- No non-null indicator observations were returned for the requested period.")
    else:
        for row in trends.sort_values(["indicator_code", "country_code"]).itertuples(index=False):
            relative = (
                f", relative change {row.relative_change_pct:.2f}%"
                if pd.notna(row.relative_change_pct) else ""
            )
            findings.append(
                f"- {row.country_name}, {row.indicator_code}: {row.first_year} {row.first_value:,.2f} "
                f"→ {row.last_year} {row.last_value:,.2f} "
                f"(absolute change {row.absolute_change:,.2f}{relative})."
            )
    findings.extend([
        "",
        "## Interpretation limits",
        "",
        "- GDP per capita is in current US dollars and includes exchange-rate and price effects; it is not real GDP growth.",
        "- Unemployment is a modeled ILO estimate. Latest available year varies by indicator and country.",
        "- Pairwise correlations depend on overlapping non-null years; inspect correlation_pair_counts.csv before interpreting a coefficient.",
        "- Country-level correlation does not establish causality and must not be interpreted as an individual-level relationship.",
        "- Missing years are not interpolated or filled.",
        "",
        "## SQL/Python validation",
        "",
        "- DuckDB table row counts reconcile with the source DataFrames; country-year uniqueness is checked.",
    ])
    (output_dir / "findings.md").write_text("\n".join(findings) + "\n", encoding="utf-8")

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
        indicator_rows, payloads = fetch_indicator(indicator_code, start_year, end_year)
        rows.extend(indicator_rows)
        safe_name = indicator_code.replace(".", "_")
        (raw_dir / f"{safe_name}.json").write_text(
            json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    observations = pd.DataFrame(rows, columns=[
        "country_code", "country_name", "year", "indicator_code", "indicator_name", "value"
    ])
    if not observations.empty:
        invalid = (
            ~observations["country_code"].isin(COUNTRIES)
            | ~observations["indicator_code"].isin(INDICATORS)
            | ~observations["year"].between(start_year, end_year)
        )
        if invalid.any():
            details = {
                "invalid_rows": int(invalid.sum()),
                "country_codes": sorted(observations["country_code"].dropna().astype(str).unique().tolist()),
                "indicator_codes": sorted(observations["indicator_code"].dropna().astype(str).unique().tolist()),
                "year_min": int(observations["year"].min()),
                "year_max": int(observations["year"].max()),
                "invalid_country_codes": sorted(
                    observations.loc[~observations["country_code"].isin(COUNTRIES), "country_code"]
                    .dropna().astype(str).unique().tolist()
                ),
                "invalid_indicator_codes": sorted(
                    observations.loc[~observations["indicator_code"].isin(INDICATORS), "indicator_code"]
                    .dropna().astype(str).unique().tolist()
                ),
            }
            raise ValueError(f"World Bank API returned out-of-scope observations: {details}")
        observations["value"] = pd.to_numeric(observations["value"], errors="coerce")
        if observations.duplicated(["country_code", "year", "indicator_code"]).any():
            raise ValueError("World Bank API returned duplicate country-year-indicator keys")
    if observations.empty or observations["value"].notna().sum() == 0:
        raise ValueError("World Bank API returned no usable indicator values for the requested period")
    build_outputs(observations, start_year, end_year, project_dir / "outputs")
    print(f"World Bank analytics complete: {len(observations):,} observations")
    print(f"Dashboard: {project_dir / 'outputs' / 'dashboard.html'}")

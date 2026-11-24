import importlib.util
from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("macro_pipeline", PROJECT_DIR / "pipeline.py")
macro_pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(macro_pipeline)


def test_parse_api_payload_preserves_null_observations():
    payload = [
        {"page": 1, "pages": 1, "total": 2},
        [
            {
                "country": {"id": "KAZ", "value": "Kazakhstan"},
                "date": "2020",
                "indicator": {"id": "IT.NET.USER.ZS", "value": "Individuals using the Internet (% of population)"},
                "value": 85.9,
            },
            {
                "country": {"id": "KAZ", "value": "Kazakhstan"},
                "date": "2019",
                "indicator": {"id": "IT.NET.USER.ZS", "value": "Individuals using the Internet (% of population)"},
                "value": None,
            },
        ],
    ]
    rows = macro_pipeline.parse_api_payload(payload, "IT.NET.USER.ZS")
    assert rows[0]["country_code"] == "KAZ"
    assert rows[0]["value"] == 85.9
    assert rows[1]["value"] is None


def test_panel_builds_full_country_year_grid_without_imputation():
    observations = pd.DataFrame([
        {
            "country_code": "RUS", "country_name": "Russian Federation",
            "year": 2020, "indicator_code": "IT.NET.USER.ZS",
            "indicator_name": "Internet users", "value": 85.0,
        }
    ])
    panel = macro_pipeline.build_panel(observations, 2020, 2021)
    assert len(panel) == len(macro_pipeline.COUNTRIES) * 2
    assert panel["internet_users_pct"].dtype.kind in "fi"
    russia_2020 = panel.loc[
        panel["country_code"].eq("RUS") & panel["year"].eq(2020)
    ].iloc[0]
    russia_2021 = panel.loc[
        panel["country_code"].eq("RUS") & panel["year"].eq(2021)
    ].iloc[0]
    assert russia_2020["internet_users_pct"] == 85.0
    assert pd.isna(russia_2021["internet_users_pct"])


def test_trends_use_first_and_last_non_null_observations():
    observations = pd.DataFrame([
        {"country_code": "ARM", "country_name": "Armenia", "year": 2018,
         "indicator_code": "X", "indicator_name": "Example", "value": 10.0},
        {"country_code": "ARM", "country_name": "Armenia", "year": 2019,
         "indicator_code": "X", "indicator_name": "Example", "value": None},
        {"country_code": "ARM", "country_name": "Armenia", "year": 2020,
         "indicator_code": "X", "indicator_name": "Example", "value": 14.0},
    ])
    trend = macro_pipeline.calculate_trends(observations).iloc[0]
    assert trend["first_year"] == 2018
    assert trend["last_year"] == 2020
    assert trend["absolute_change"] == 4.0
    assert abs(trend["relative_change_pct"] - 40.0) < 1e-10


def test_panel_preserves_expected_indicators_when_source_has_no_rows():
    panel = macro_pipeline.build_panel(pd.DataFrame(), 2021, 2021)
    for column in macro_pipeline.INDICATORS.values():
        assert column in panel.columns
        assert panel[column].isna().all()


def test_duplicate_country_year_indicator_key_is_rejected():
    observations = pd.DataFrame([
        {"country_code": "RUS", "country_name": "Russian Federation", "year": 2020,
         "indicator_code": "IT.NET.USER.ZS", "indicator_name": "Internet users", "value": 85.0},
        {"country_code": "RUS", "country_name": "Russian Federation", "year": 2020,
         "indicator_code": "IT.NET.USER.ZS", "indicator_name": "Internet users", "value": 85.0},
    ])
    try:
        macro_pipeline.build_panel(observations, 2020, 2020)
    except ValueError as exc:
        assert "Duplicate" in str(exc)
    else:
        raise AssertionError("Duplicate keys should be rejected")

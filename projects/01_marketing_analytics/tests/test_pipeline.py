import pandas as pd

from pipeline import calculate_statistics, conversion_table, load_and_clean


def test_conversion_table_uses_sessions_as_denominator():
    frame = pd.DataFrame({
        "visitortype": ["New", "New", "Returning", "Returning"],
        "revenue": [False, True, True, True],
    })
    result = conversion_table(frame, "visitortype").set_index("visitortype")
    assert result.loc["New", "sessions"] == 2
    assert result.loc["New", "purchases"] == 1
    assert result.loc["New", "conversion_rate"] == 0.5
    assert result.loc["Returning", "conversion_rate"] == 1.0


def test_statistics_are_defined_for_two_by_two_table():
    frame = pd.DataFrame({
        "visitor_type": ["New", "New", "Returning", "Returning"],
        "revenue": [False, True, False, True],
    })
    result = calculate_statistics(frame)
    assert 0 <= result["visitor_type_revenue_p_value"] <= 1
    assert 0 <= result["visitor_type_revenue_cramers_v"] <= 1
    assert "not establish" in result["interpretation"]


def test_cleaning_removes_exact_duplicates_and_preserves_outlier_flag(tmp_path):
    raw = {
        "Administrative": [0, 1],
        "Administrative_Duration": [0, 10],
        "Informational": [0, 0],
        "Informational_Duration": [0, 0],
        "ProductRelated": [1, 1],
        "ProductRelated_Duration": [10, 10000],
        "BounceRates": [0.2, 0.1],
        "ExitRates": [0.2, 0.1],
        "PageValues": [0.0, 5.0],
        "SpecialDay": [0.0, 0.0],
        "Month": ["Feb", "Feb"],
        "OperatingSystems": [2, 2],
        "Browser": [1, 1],
        "Region": [1, 1],
        "TrafficType": [2, 2],
        "VisitorType": ["New_Visitor", "Returning_Visitor"],
        "Weekend": [False, True],
        "Revenue": [False, True],
    }
    pd.DataFrame(raw).to_csv(tmp_path / "sample.csv", index=False)
    pd.concat([pd.DataFrame(raw), pd.DataFrame(raw).iloc[[0]]]).to_csv(
        tmp_path / "with_duplicate.csv", index=False
    )
    clean, report = load_and_clean(tmp_path / "with_duplicate.csv")
    assert len(clean) == 2
    assert report["exact_duplicate_rows_removed"] == 1
    assert "duration_upper_1pct_flag" in clean.columns

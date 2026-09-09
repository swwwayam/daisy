"""
Tests for agents.py (Data Cleaning + EDA agents) — covers only the
deterministic sense/act logic. The Gemini 'reason' step is not covered
here for the same reason as test_feature_engineering.py: no live network
access to Google's API from this environment.

Closes out Phase A item 4 (pytest suite for agents.py, resolves OD-8).
"""

import numpy as np
import pandas as pd
import pytest

from agents import (
    apply_cleaning_plan,
    parse_plan,
    profile_dataframe,
    profile_for_eda,
)


@pytest.fixture
def messy_df():
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "age": [25.0, np.nan, 35.0, 40.0, 25.0],
            "name": ["  Alice", "Bob  ", "Carol", "Dave", "Alice"],
            "score": [10, 20, 30, 1000, 20],  # 1000 is an outlier
        }
    )


class TestProfileDataframe:
    def test_basic_shape(self, messy_df):
        profile = profile_dataframe(messy_df)
        assert profile["n_rows"] == 5
        assert profile["n_columns"] == 4
        assert profile["total_nulls"] == 1

    def test_numeric_column_stats(self, messy_df):
        profile = profile_dataframe(messy_df)
        age_info = next(c for c in profile["columns"] if c["name"] == "age")
        assert age_info["null_count"] == 1
        assert age_info["min"] == 25.0
        assert age_info["max"] == 40.0

    def test_categorical_column_top_values(self, messy_df):
        profile = profile_dataframe(messy_df)
        name_info = next(c for c in profile["columns"] if c["name"] == "name")
        assert "top_values" in name_info

    def test_duplicate_detection(self):
        df = pd.DataFrame({"a": [1, 1, 2], "b": [1, 1, 2]})
        profile = profile_dataframe(df)
        assert profile["duplicate_rows"] == 1


class TestParsePlan:
    def test_parses_clean_json(self):
        plan = parse_plan('{"summary": "ok", "actions": []}')
        assert plan["actions"] == []

    def test_strips_markdown_fences(self):
        plan = parse_plan('```json\n{"summary": "ok", "actions": []}\n```')
        assert plan["summary"] == "ok"

    def test_rejects_missing_actions_key(self):
        with pytest.raises(ValueError):
            parse_plan('{"summary": "ok"}')


class TestApplyCleaningPlan:
    def test_drop_duplicates(self):
        df = pd.DataFrame({"a": [1, 1, 2], "b": [1, 1, 2]})
        result_df, steps = apply_cleaning_plan(df, [{"type": "drop_duplicates", "reasoning": "t"}])
        assert len(result_df) == 2
        assert steps[0]["status"] == "success"

    def test_impute_mean(self, messy_df):
        actions = [{"type": "impute", "column": "age", "strategy": "mean", "reasoning": "t"}]
        result_df, steps = apply_cleaning_plan(messy_df, actions)
        assert steps[0]["status"] == "success"
        assert result_df["age"].isna().sum() == 0

    def test_impute_constant(self, messy_df):
        actions = [
            {"type": "impute", "column": "age", "strategy": "constant", "value": 0, "reasoning": "t"}
        ]
        result_df, steps = apply_cleaning_plan(messy_df, actions)
        assert steps[0]["status"] == "success"
        assert result_df["age"].isna().sum() == 0

    def test_drop_column(self, messy_df):
        actions = [{"type": "drop_column", "column": "id", "reasoning": "t"}]
        result_df, steps = apply_cleaning_plan(messy_df, actions)
        assert "id" not in result_df.columns
        assert steps[0]["status"] == "success"

    def test_strip_whitespace(self, messy_df):
        actions = [{"type": "strip_whitespace", "column": "name", "reasoning": "t"}]
        result_df, steps = apply_cleaning_plan(messy_df, actions)
        assert steps[0]["status"] == "success"
        assert result_df["name"].iloc[0] == "Alice"  # leading space stripped
        assert result_df["name"].iloc[1] == "Bob"  # trailing space stripped

    def test_handle_outliers_iqr_clip(self, messy_df):
        actions = [{"type": "handle_outliers", "column": "score", "strategy": "iqr_clip", "reasoning": "t"}]
        result_df, steps = apply_cleaning_plan(messy_df, actions)
        assert steps[0]["status"] == "success"
        assert result_df["score"].max() < 1000  # outlier clipped

    def test_handle_outliers_on_non_numeric_fails_gracefully(self, messy_df):
        actions = [{"type": "handle_outliers", "column": "name", "strategy": "iqr_clip", "reasoning": "t"}]
        result_df, steps = apply_cleaning_plan(messy_df, actions)
        assert steps[0]["status"] == "failed"

    def test_unknown_action_skipped_not_crashed(self, messy_df):
        actions = [{"type": "levitate_column", "column": "age", "reasoning": "t"}]
        result_df, steps = apply_cleaning_plan(messy_df, actions)
        assert steps[0]["status"] == "skipped"
        assert len(result_df) == len(messy_df)

    def test_bad_column_fails_gracefully_not_crash(self, messy_df):
        actions = [{"type": "drop_column", "column": "nonexistent", "reasoning": "t"}]
        result_df, steps = apply_cleaning_plan(messy_df, actions)
        assert steps[0]["status"] == "failed"

    def test_original_df_not_mutated(self, messy_df):
        original_cols = list(messy_df.columns)
        apply_cleaning_plan(messy_df, [{"type": "drop_column", "column": "id", "reasoning": "t"}])
        assert list(messy_df.columns) == original_cols


class TestProfileForEda:
    def test_overview_fields(self, messy_df):
        report = profile_for_eda(messy_df)
        assert report["overview"]["rows"] == 5
        assert report["overview"]["missing_values"] == 1

    def test_numeric_and_categorical_split(self, messy_df):
        report = profile_for_eda(messy_df)
        assert "age" in report["numeric_columns"]
        assert "name" in report["categorical_columns"]

    def test_correlation_matrix_present(self, messy_df):
        report = profile_for_eda(messy_df)
        assert "id" in report["correlation"]

    def test_outlier_detection(self, messy_df):
        report = profile_for_eda(messy_df)
        assert report["outliers"]["score"] >= 1  # the 1000 value should be flagged

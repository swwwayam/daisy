"""
Tests for feature_engineering.py — covers only the deterministic
sense/act logic (profiling + action execution). The 'reason' step (Gemini
call) is NOT covered here since it requires live network access to
Google's API — see Handover.md / Test-Checklist.md for what's verified.
"""

import pandas as pd
import pytest

from feature_engineering import (
    apply_fallback_encoding,
    apply_feature_engineering_plan,
    parse_plan,
    profile_for_feature_engineering,
)


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "age": [25, 30, 35, 40, 25],
            "constant_col": [1, 1, 1, 1, 1],  # zero variance
            "category": ["a", "b", "a", "c", "b"],
            "signup_date": ["2023-01-15", "2023-02-20", "2023-03-10", "2023-04-05", "2023-05-01"],
            "correlated_a": [1, 2, 3, 4, 5],
            "correlated_b": [2, 4, 6, 8, 10],  # perfectly correlated with correlated_a
        }
    )


class TestProfileForFeatureEngineering:
    def test_basic_shape(self, sample_df):
        profile = profile_for_feature_engineering(sample_df)
        assert profile["n_rows"] == 5
        assert profile["n_columns"] == 6
        assert len(profile["columns"]) == 6

    def test_detects_low_variance_column(self, sample_df):
        profile = profile_for_feature_engineering(sample_df)
        constant_info = next(c for c in profile["columns"] if c["name"] == "constant_col")
        assert constant_info["is_numeric"] is True
        assert constant_info["variance"] == 0.0

    def test_detects_datetime_like_column(self, sample_df):
        profile = profile_for_feature_engineering(sample_df)
        date_info = next(c for c in profile["columns"] if c["name"] == "signup_date")
        assert date_info["is_datetime_like"] is True

    def test_does_not_flag_category_as_datetime(self, sample_df):
        profile = profile_for_feature_engineering(sample_df)
        cat_info = next(c for c in profile["columns"] if c["name"] == "category")
        assert cat_info["is_datetime_like"] is False

    def test_detects_high_correlation_pair(self, sample_df):
        profile = profile_for_feature_engineering(sample_df)
        pairs = profile["high_correlation_pairs"]
        assert len(pairs) == 1
        assert {pairs[0]["column_a"], pairs[0]["column_b"]} == {"correlated_a", "correlated_b"}
        assert pairs[0]["correlation"] >= 0.99


class TestParsePlan:
    def test_parses_clean_json(self):
        raw = '{"summary": "ok", "actions": []}'
        plan = parse_plan(raw)
        assert plan["summary"] == "ok"
        assert plan["actions"] == []

    def test_strips_markdown_fences(self):
        raw = '```json\n{"summary": "ok", "actions": []}\n```'
        plan = parse_plan(raw)
        assert plan["summary"] == "ok"

    def test_rejects_wrong_shape(self):
        with pytest.raises(ValueError):
            parse_plan('{"summary": "ok"}')  # missing "actions"


class TestApplyFeatureEngineeringPlan:
    def test_encode_categorical_onehot(self, sample_df):
        actions = [{"type": "encode_categorical", "column": "category", "strategy": "onehot", "reasoning": "test"}]
        result_df, steps = apply_feature_engineering_plan(sample_df, actions)
        assert steps[0]["status"] == "success"
        assert "category" not in result_df.columns
        assert "category_a" in result_df.columns

    def test_scale_numeric_standard(self, sample_df):
        actions = [{"type": "scale_numeric", "column": "age", "strategy": "standard", "reasoning": "test"}]
        result_df, steps = apply_feature_engineering_plan(sample_df, actions)
        assert steps[0]["status"] == "success"
        assert abs(result_df["age"].mean()) < 1e-9  # standardized mean ~0

    def test_extract_datetime_features(self, sample_df):
        actions = [{"type": "extract_datetime_features", "column": "signup_date", "reasoning": "test"}]
        result_df, steps = apply_feature_engineering_plan(sample_df, actions)
        assert steps[0]["status"] == "success"
        assert "signup_date" not in result_df.columns
        assert "signup_date_year" in result_df.columns
        assert result_df["signup_date_year"].iloc[0] == 2023

    def test_drop_low_variance_column(self, sample_df):
        actions = [{"type": "drop_low_variance_column", "column": "constant_col", "reasoning": "test"}]
        result_df, steps = apply_feature_engineering_plan(sample_df, actions)
        assert steps[0]["status"] == "success"
        assert "constant_col" not in result_df.columns

    def test_drop_high_correlation_column(self, sample_df):
        actions = [
            {
                "type": "drop_high_correlation_column",
                "column": "correlated_b",
                "column_b": "correlated_a",
                "reasoning": "test",
            }
        ]
        result_df, steps = apply_feature_engineering_plan(sample_df, actions)
        assert steps[0]["status"] == "success"
        assert "correlated_b" not in result_df.columns
        assert "correlated_a" in result_df.columns

    def test_unknown_action_type_is_skipped_not_crashed(self, sample_df):
        actions = [{"type": "teleport_column", "column": "age", "reasoning": "test"}]
        result_df, steps = apply_feature_engineering_plan(sample_df, actions)
        assert steps[0]["status"] == "skipped"
        assert len(result_df) == len(sample_df)  # untouched

    def test_bad_column_name_fails_gracefully(self, sample_df):
        actions = [{"type": "scale_numeric", "column": "does_not_exist", "strategy": "standard", "reasoning": "t"}]
        result_df, steps = apply_feature_engineering_plan(sample_df, actions)
        assert steps[0]["status"] == "failed"
        assert "not found" in steps[0]["message"]

    def test_original_dataframe_not_mutated(self, sample_df):
        original_columns = list(sample_df.columns)
        actions = [{"type": "drop_low_variance_column", "column": "constant_col", "reasoning": "test"}]
        apply_feature_engineering_plan(sample_df, actions)
        assert list(sample_df.columns) == original_columns  # caller's df untouched

    def test_multiple_actions_in_sequence(self, sample_df):
        actions = [
            {"type": "drop_low_variance_column", "column": "constant_col", "reasoning": "t"},
            {"type": "encode_categorical", "column": "category", "strategy": "label", "reasoning": "t"},
            {"type": "extract_datetime_features", "column": "signup_date", "reasoning": "t"},
        ]
        result_df, steps = apply_feature_engineering_plan(sample_df, actions)
        assert all(s["status"] == "success" for s in steps)
        assert "constant_col" not in result_df.columns
        assert "signup_date" not in result_df.columns
        assert "signup_date_year" in result_df.columns


class TestApplyFallbackEncoding:
    """Real scenario this addresses: Gemini's Feature Engineering plan
    doesn't encode every non-numeric column, and Model Training's own
    guardrail then correctly refuses to proceed. This fallback closes
    that gap deterministically and visibly, without loosening Model
    Training's intentional strictness."""

    def test_encodes_leftover_categorical_column(self, sample_df):
        # sample_df's 'category' column was never touched by any Gemini
        # plan here — simulating exactly what was observed live: a column
        # Gemini's plan simply didn't address.
        result_df, steps = apply_fallback_encoding(sample_df)
        assert "category" not in result_df.columns  # onehot-encoded away
        assert any(c.startswith("category_") for c in result_df.columns)
        assert len(steps) >= 1
        assert all(s["type"] == "auto_encode_remaining" for s in steps)

    def test_does_not_touch_already_numeric_columns(self, sample_df):
        already_numeric_df = sample_df.drop(columns=["category", "signup_date"])
        result_df, steps = apply_fallback_encoding(already_numeric_df)
        assert steps == []  # nothing needed fixing
        assert list(result_df.columns) == list(already_numeric_df.columns)

    def test_low_cardinality_uses_onehot(self):
        df = pd.DataFrame({"color": ["red", "blue", "red", "green"] * 5})
        result_df, steps = apply_fallback_encoding(df)
        assert "onehot" in steps[0]["reasoning"]
        assert "color_red" in result_df.columns

    def test_high_cardinality_uses_frequency(self):
        # 15 unique values > the 10-value onehot threshold
        df = pd.DataFrame({"city": [f"city_{i}" for i in range(15)] * 3})
        result_df, steps = apply_fallback_encoding(df)
        assert "frequency" in steps[0]["reasoning"]
        assert pd.api.types.is_numeric_dtype(result_df["city"])

    def test_original_dataframe_not_mutated(self, sample_df):
        original_columns = list(sample_df.columns)
        apply_fallback_encoding(sample_df)
        assert list(sample_df.columns) == original_columns

    def test_action_type_is_distinct_from_gemini_actions(self, sample_df):
        # This is the audit-trail guarantee: fallback actions must never
        # be indistinguishable from actions Gemini itself proposed.
        _, plan_steps = apply_feature_engineering_plan(sample_df, [])
        _, fallback_steps = apply_fallback_encoding(sample_df)
        gemini_action_types = {"encode_categorical", "scale_numeric", "extract_datetime_features",
                                "drop_low_variance_column", "drop_high_correlation_column"}
        for step in fallback_steps:
            assert step["type"] == "auto_encode_remaining"
            assert step["type"] not in gemini_action_types

    def test_fully_numeric_input_produces_no_steps(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0]})
        result_df, steps = apply_fallback_encoding(df)
        assert steps == []
        assert result_df.equals(df)

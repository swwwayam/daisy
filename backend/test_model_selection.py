"""
Tests for model_selection.py — covers the deterministic problem-type
detection and the validation guardrail. The Gemini 'reason' step is not
covered here for the same reason as the other agents' tests: no live
network access to Google's API from this environment.
"""

import pandas as pd
import pytest

from model_selection import (
    CLASSIFICATION_MODELS,
    REGRESSION_MODELS,
    detect_problem_type,
    parse_plan,
    profile_for_model_selection,
    validate_recommendations,
)


@pytest.fixture
def classification_df():
    return pd.DataFrame(
        {
            "age": [25, 30, 35, 40, 45, 50, 55, 60],
            "income": [30000, 40000, 50000, 60000, 70000, 80000, 90000, 100000],
            "purchased": [0, 0, 0, 1, 0, 1, 1, 1],  # binary target
        }
    )


@pytest.fixture
def regression_df():
    return pd.DataFrame(
        {
            "size_sqft": [800, 1000, 1200, 1500, 1800, 2000, 2200, 2500],
            "bedrooms": [1, 2, 2, 3, 3, 4, 4, 5],
            "price": [150000, 180000, 210000, 250000, 290000, 320000, 350000, 400000],  # continuous target
        }
    )


@pytest.fixture
def imbalanced_df():
    return pd.DataFrame(
        {
            "x": list(range(20)),
            "label": [0] * 18 + [1] * 2,  # heavily imbalanced binary target
        }
    )


class TestDetectProblemType:
    def test_binary_numeric_target_is_classification(self, classification_df):
        result = detect_problem_type(classification_df, "purchased")
        assert result["problem_type"] == "classification"

    def test_continuous_numeric_target_is_regression(self, regression_df):
        result = detect_problem_type(regression_df, "price")
        assert result["problem_type"] == "regression"

    def test_missing_target_column_raises(self, classification_df):
        with pytest.raises(ValueError):
            detect_problem_type(classification_df, "does_not_exist")

    def test_class_balance_reported_for_classification(self, classification_df):
        result = detect_problem_type(classification_df, "purchased")
        assert "class_balance" in result
        assert abs(sum(result["class_balance"].values()) - 1.0) < 1e-6

    def test_imbalance_flagged(self, imbalanced_df):
        result = detect_problem_type(imbalanced_df, "label")
        assert result["is_imbalanced"] is True

    def test_balanced_not_flagged(self, classification_df):
        result = detect_problem_type(classification_df, "purchased")
        assert result["is_imbalanced"] is False

    def test_regression_reports_min_max_mean(self, regression_df):
        result = detect_problem_type(regression_df, "price")
        assert result["target_min"] == 150000
        assert result["target_max"] == 400000


class TestProfileForModelSelection:
    def test_feature_counts_exclude_target(self, classification_df):
        profile = profile_for_model_selection(classification_df, "purchased")
        assert profile["n_features"] == 2  # age, income
        assert profile["n_numeric_features"] == 2


class TestParsePlan:
    def test_parses_clean_json(self):
        plan = parse_plan('{"summary": "ok", "recommendations": []}')
        assert plan["recommendations"] == []

    def test_strips_markdown_fences(self):
        plan = parse_plan('```json\n{"summary": "ok", "recommendations": []}\n```')
        assert plan["summary"] == "ok"

    def test_rejects_missing_recommendations_key(self):
        with pytest.raises(ValueError):
            parse_plan('{"summary": "ok"}')


class TestValidateRecommendations:
    def test_accepts_valid_classification_models(self):
        recs = [{"model": "random_forest_classifier", "rank": 1, "reasoning": "good fit"}]
        valid, rejected = validate_recommendations(recs, "classification")
        assert len(valid) == 1
        assert len(rejected) == 0
        assert valid[0]["status"] == "accepted"

    def test_rejects_hallucinated_model_name(self):
        recs = [{"model": "xgboost_super_model", "rank": 1, "reasoning": "sounds fancy"}]
        valid, rejected = validate_recommendations(recs, "classification")
        assert len(valid) == 0
        assert len(rejected) == 1
        assert rejected[0]["status"] == "rejected"

    def test_rejects_regression_model_for_classification_problem(self):
        # a real model name, but wrong vocabulary for the detected problem type
        recs = [{"model": "linear_regression", "rank": 1, "reasoning": "wrong bucket"}]
        valid, rejected = validate_recommendations(recs, "classification")
        assert len(valid) == 0
        assert len(rejected) == 1

    def test_mixed_valid_and_invalid(self):
        recs = [
            {"model": "logistic_regression", "rank": 1, "reasoning": "ok"},
            {"model": "made_up_model", "rank": 2, "reasoning": "not real"},
        ]
        valid, rejected = validate_recommendations(recs, "classification")
        assert len(valid) == 1
        assert len(rejected) == 1

    def test_all_classification_models_are_valid(self):
        recs = [{"model": m, "rank": i + 1, "reasoning": "t"} for i, m in enumerate(CLASSIFICATION_MODELS)]
        valid, rejected = validate_recommendations(recs, "classification")
        assert len(valid) == len(CLASSIFICATION_MODELS)
        assert len(rejected) == 0

    def test_all_regression_models_are_valid(self):
        recs = [{"model": m, "rank": i + 1, "reasoning": "t"} for i, m in enumerate(REGRESSION_MODELS)]
        valid, rejected = validate_recommendations(recs, "regression")
        assert len(valid) == len(REGRESSION_MODELS)
        assert len(rejected) == 0

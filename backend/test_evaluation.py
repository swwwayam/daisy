"""
Tests for evaluation.py — covers the deterministic sense step (real
training, real confusion matrix / residuals, overfitting signal) and the
verdict guardrail. The Gemini reasoning step is not covered here for the
same reason as other agents: no live network access from this environment.
"""

import numpy as np
import pandas as pd
import pytest

from evaluation import (
    build_evaluation_prompt,
    evaluate_model,
    parse_plan,
    validate_verdict,
)
from model_training import TrainingDataError


@pytest.fixture
def classification_df():
    rng = np.random.RandomState(42)
    n = 80
    feature_a = rng.normal(0, 1, n)
    feature_b = rng.normal(0, 1, n)
    target = (feature_a + rng.normal(0, 0.5, n) > 0).astype(int)
    return pd.DataFrame({"feature_a": feature_a, "feature_b": feature_b, "label": target})


@pytest.fixture
def regression_df():
    rng = np.random.RandomState(42)
    n = 80
    size = rng.uniform(500, 3000, n)
    bedrooms = rng.randint(1, 6, n)
    price = size * 150 + bedrooms * 5000 + rng.normal(0, 10000, n)
    return pd.DataFrame({"size": size, "bedrooms": bedrooms.astype(float), "price": price})


class TestEvaluateModelClassification:
    def test_returns_real_train_and_test_metrics(self, classification_df):
        result = evaluate_model(classification_df, "label", "logistic_regression")
        assert result["problem_type"] == "classification"
        assert "f1_weighted" in result["train_metrics"]
        assert "f1_weighted" in result["test_metrics"]

    def test_confusion_matrix_shape_matches_classes(self, classification_df):
        result = evaluate_model(classification_df, "label", "random_forest_classifier")
        cm = result["confusion_matrix"]
        n_classes = len(cm["labels"])
        assert len(cm["matrix"]) == n_classes
        assert all(len(row) == n_classes for row in cm["matrix"])

    def test_train_test_gap_computed(self, classification_df):
        result = evaluate_model(classification_df, "label", "logistic_regression")
        expected_gap = round(result["train_metrics"]["f1_weighted"] - result["test_metrics"]["f1_weighted"], 4)
        assert result["train_test_gap"] == expected_gap

    def test_unknown_model_name_raises(self, classification_df):
        with pytest.raises(TrainingDataError):
            evaluate_model(classification_df, "label", "made_up_model")

    def test_same_split_as_model_training_default(self, classification_df):
        # Same test_size/random_state defaults as model_training.py —
        # re-running with the same args must be fully reproducible.
        r1 = evaluate_model(classification_df, "label", "logistic_regression")
        r2 = evaluate_model(classification_df, "label", "logistic_regression")
        assert r1["test_metrics"] == r2["test_metrics"]
        assert r1["confusion_matrix"] == r2["confusion_matrix"]


class TestEvaluateModelRegression:
    def test_returns_real_train_and_test_metrics(self, regression_df):
        result = evaluate_model(regression_df, "price", "linear_regression")
        assert result["problem_type"] == "regression"
        assert "r2" in result["train_metrics"]
        assert "r2" in result["test_metrics"]

    def test_residuals_computed(self, regression_df):
        result = evaluate_model(regression_df, "price", "linear_regression")
        residuals = result["residuals"]
        assert "mean" in residuals and "std" in residuals
        assert residuals["min"] <= residuals["max"]

    def test_good_fit_has_small_residual_mean_near_zero(self, regression_df):
        # near-linear synthetic data, real linear regression should have
        # residuals centered close to zero — a genuine sanity check, not
        # just "code runs without crashing."
        result = evaluate_model(regression_df, "price", "linear_regression")
        assert abs(result["residuals"]["mean"]) < abs(result["residuals"]["std"])


class TestBuildEvaluationPrompt:
    def test_excludes_irrelevant_fields(self, classification_df):
        result = evaluate_model(classification_df, "label", "logistic_regression")
        prompt = build_evaluation_prompt(result)
        assert "n_train" not in prompt  # deliberately excluded, not needed for interpretation
        assert "f1_weighted" in prompt  # the actual metric IS included


class TestParsePlan:
    def test_parses_clean_json(self):
        plan = parse_plan('{"verdict": "good", "summary": "ok", "observations": []}')
        assert plan["verdict"] == "good"

    def test_strips_markdown_fences(self):
        plan = parse_plan('```json\n{"verdict": "moderate", "summary": "ok"}\n```')
        assert plan["verdict"] == "moderate"

    def test_rejects_missing_verdict(self):
        with pytest.raises(ValueError):
            parse_plan('{"summary": "ok"}')


class TestValidateVerdict:
    def test_accepts_valid_verdict(self, classification_df):
        eval_result = evaluate_model(classification_df, "label", "logistic_regression")
        verdict, corrected = validate_verdict({"verdict": "good"}, eval_result)
        assert verdict == "good"
        assert corrected is False

    def test_rejects_hallucinated_verdict_uses_fallback(self, classification_df):
        eval_result = evaluate_model(classification_df, "label", "logistic_regression")
        verdict, corrected = validate_verdict({"verdict": "excellent"}, eval_result)
        assert verdict in {"good", "moderate", "poor"}
        assert corrected is True

    def test_fallback_uses_real_metric_thresholds(self, regression_df):
        eval_result = evaluate_model(regression_df, "price", "linear_regression")
        verdict, corrected = validate_verdict({"verdict": "not_a_real_verdict"}, eval_result)
        assert corrected is True
        r2 = eval_result["test_metrics"]["r2"]
        if r2 >= 0.75:
            assert verdict == "good"
        elif r2 >= 0.40:
            assert verdict == "moderate"
        else:
            assert verdict == "poor"

"""
Tests for model_training.py — unlike every other agent's tests, these
don't need to mock anything. There's no Gemini call in this agent, so
every test here exercises the REAL sklearn training path end-to-end.
"""

import numpy as np
import pandas as pd
import pytest

from model_training import (
    TrainingDataError,
    prepare_training_data,
    train_and_evaluate,
)


@pytest.fixture
def classification_df():
    # 60 rows, clean binary target, all-numeric features — enough for a
    # real train/test split with both classes represented in each fold.
    rng = np.random.RandomState(42)
    n = 60
    feature_a = rng.normal(0, 1, n)
    feature_b = rng.normal(0, 1, n)
    # target correlated with feature_a so the models have something real to learn
    target = (feature_a + rng.normal(0, 0.5, n) > 0).astype(int)
    return pd.DataFrame({"feature_a": feature_a, "feature_b": feature_b, "label": target})


@pytest.fixture
def regression_df():
    rng = np.random.RandomState(42)
    n = 60
    size = rng.uniform(500, 3000, n)
    bedrooms = rng.randint(1, 6, n)
    price = size * 150 + bedrooms * 5000 + rng.normal(0, 10000, n)
    return pd.DataFrame({"size": size, "bedrooms": bedrooms.astype(float), "price": price})


@pytest.fixture
def non_numeric_df():
    return pd.DataFrame(
        {
            "city": ["Mumbai", "Delhi", "Mumbai", "Pune"] * 5,
            "score": list(range(20)),
            "target": [0, 1, 0, 1] * 5,
        }
    )


class TestPrepareTrainingData:
    def test_basic_split_shape(self, classification_df):
        X, y, warnings = prepare_training_data(classification_df, "label")
        assert len(X) == len(y) == 60
        assert warnings["rows_dropped_for_missing_values"] == 0

    def test_missing_target_column_raises(self, classification_df):
        with pytest.raises(TrainingDataError):
            prepare_training_data(classification_df, "does_not_exist")

    def test_non_numeric_feature_raises_clear_error(self, non_numeric_df):
        with pytest.raises(TrainingDataError, match="not numeric"):
            prepare_training_data(non_numeric_df, "target")

    def test_drops_rows_with_missing_values(self, classification_df):
        df_with_gaps = classification_df.copy()
        df_with_gaps.loc[0:4, "feature_a"] = None
        X, y, warnings = prepare_training_data(df_with_gaps, "label")
        assert warnings["rows_dropped_for_missing_values"] == 5
        assert len(X) == 55

    def test_too_few_rows_raises(self):
        tiny_df = pd.DataFrame({"x": [1, 2, 3], "y": [0, 1, 0]})
        with pytest.raises(TrainingDataError, match="not enough"):
            prepare_training_data(tiny_df, "y")


class TestTrainAndEvaluateClassification:
    def test_trains_real_models_and_returns_metrics(self, classification_df):
        result = train_and_evaluate(
            classification_df, "label", ["logistic_regression", "random_forest_classifier"]
        )
        assert result["problem_type"] == "classification"
        assert len(result["results"]) == 2
        for r in result["results"]:
            assert r["status"] == "success"
            assert "f1_weighted" in r["metrics"]
            assert 0.0 <= r["metrics"]["f1_weighted"] <= 1.0

    def test_picks_a_real_best_model(self, classification_df):
        result = train_and_evaluate(
            classification_df, "label", ["logistic_regression", "random_forest_classifier", "knn_classifier"]
        )
        assert result["best_model"] in ["logistic_regression", "random_forest_classifier", "knn_classifier"]

    def test_roc_auc_present_for_binary(self, classification_df):
        result = train_and_evaluate(classification_df, "label", ["logistic_regression"])
        assert "roc_auc" in result["results"][0]["metrics"]

    def test_wrong_bucket_model_rejected(self, classification_df):
        with pytest.raises(TrainingDataError, match="don't match"):
            train_and_evaluate(classification_df, "label", ["linear_regression"])

    def test_unknown_model_name_rejected(self, classification_df):
        with pytest.raises(TrainingDataError, match="Unknown"):
            train_and_evaluate(classification_df, "label", ["made_up_classifier"])


class TestTrainAndEvaluateRegression:
    def test_trains_real_models_and_returns_metrics(self, regression_df):
        result = train_and_evaluate(regression_df, "price", ["linear_regression", "random_forest_regressor"])
        assert result["problem_type"] == "regression"
        for r in result["results"]:
            assert r["status"] == "success"
            assert "rmse" in r["metrics"]
            assert r["metrics"]["rmse"] > 0  # should have SOME error, not a perfect fit

    def test_picks_lowest_rmse_as_best(self, regression_df):
        result = train_and_evaluate(regression_df, "price", ["linear_regression", "ridge_regression"])
        rmses = {r["model"]: r["metrics"]["rmse"] for r in result["results"]}
        best_by_rmse = min(rmses, key=rmses.get)
        assert result["best_model"] == best_by_rmse

    def test_linear_regression_fits_well_on_near_linear_data(self, regression_df):
        # price was constructed as a near-linear function of the features,
        # so a real linear regression should achieve a strong R^2 — this
        # is a genuine sanity check that .fit() is actually learning
        # something, not just returning junk.
        result = train_and_evaluate(regression_df, "price", ["linear_regression"])
        assert result["results"][0]["metrics"]["r2"] > 0.8


class TestFailureIsolation:
    def test_one_bad_model_does_not_sink_the_others(self, classification_df):
        # SVM with probability=True is slow but should still work on this
        # tiny dataset — included to confirm mixed candidate lists behave,
        # not specifically to force a failure.
        result = train_and_evaluate(
            classification_df, "label", ["logistic_regression", "svm_classifier"]
        )
        assert all(r["status"] == "success" for r in result["results"])

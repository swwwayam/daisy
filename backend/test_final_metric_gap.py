from unittest.mock import Mock, patch

import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeClassifier

from evaluation import _fallback_verdict
from model_training import score_final_model, TrainingDataError


@pytest.mark.parametrize("metric", ["mae", "rmse", "r2", "accuracy", "balanced_accuracy", "f1_macro", "f1_weighted"])
def test_final_gap_uses_selected_metric_and_positive_means_worse_test(metric):
    regression = metric in {"mae", "rmse", "r2"}
    if regression:
        X_train, X_test = pd.DataFrame({"x": range(40)}), pd.DataFrame({"x": range(40, 60)})
        y_train, y_test = X_train.x * 3 + 1, X_test.x * 3 + 11
        estimator = LinearRegression().fit(X_train, y_train)
    else:
        X_train, X_test = pd.DataFrame({"x": [0, 1] * 20}), pd.DataFrame({"x": [0, 1] * 10})
        y_train, y_test = X_train.x, 1 - X_test.x
        estimator = DecisionTreeClassifier(random_state=42).fit(X_train, y_train)
    with patch.object(estimator, "fit", side_effect=AssertionError("The saved winner must not be refitted")):
        report = score_final_model(estimator, "saved", "regression" if regression else "classification", X_train, X_test, y_train, y_test, {}, metric)
    assert report["primary_metric"] == metric
    assert report["train_test_gap"] > 0
    if metric in {"mae", "rmse"}:
        assert report["gap_definition"] == "test_minus_train"
        assert report["train_test_gap"] == pytest.approx(10)
    else:
        assert report["gap_definition"] == "train_minus_test"
        assert report["train_test_gap"] == pytest.approx(round(report["train_metrics"][metric] - report["test_metrics"][metric], 4))


def test_wrong_task_metric_is_rejected_before_scoring():
    winner = Mock()
    with pytest.raises(TrainingDataError, match="metric does not match"):
        score_final_model(winner, "saved", "regression", None, None, None, None, {}, "accuracy")
    winner.predict.assert_not_called()


def test_generic_verdict_does_not_apply_r2_thresholds_to_error_units():
    result = {"problem_type": "regression", "primary_metric": "mae", "test_metrics": {"mae": 100000, "r2": -1}}
    assert _fallback_verdict(result) == "poor"
    result["test_metrics"] = {"mae": 0.01, "r2": 0.9}
    assert _fallback_verdict(result) == "good"

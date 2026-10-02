from unittest.mock import patch
import numpy as np
import pandas as pd

import main
import model_training as training
from evaluation import evaluate_model


def data():
    rng = np.random.default_rng(5)
    x = rng.normal(size=100)
    return pd.DataFrame({"x": x, "target": x * 10 + rng.normal(size=100)})


def test_folds_are_disjoint_and_test_values_do_not_change_selection():
    frame = data()
    _, train, validation, test = training.reserved_partitions(frame)
    assert not set(train) & set(validation)
    assert not set(train) & set(test)
    assert not set(validation) & set(test)
    candidates = ["linear_regression", "ridge_regression"]
    original = training.train_and_evaluate(frame, "target", candidates, raw_df=frame)
    changed = frame.copy()
    changed.loc[test, "target"] += 1000000
    poisoned = training.train_and_evaluate(changed, "target", candidates, raw_df=changed)
    assert original["best_model"] == poisoned["best_model"]
    assert original["results"] != []
    assert [r["metrics"] for r in original["results"]] == [r["metrics"] for r in poisoned["results"]]
    assert original["final_test_metrics"] != poisoned["final_test_metrics"]
    assert original["baseline_test_metrics"] is not None


def test_only_the_winner_predicts_the_final_test_fold():
    frame = data()
    _, _, _, test = training.reserved_partitions(frame)
    calls = []
    class Estimator:
        def __init__(self, name): self.name = name
        def fit(self, X, y): self.mean = float(y.mean()); return self
        def predict(self, X):
            calls.append((self.name, set(X.index)))
            return np.full(len(X), self.mean)
    with patch.dict(training.MODEL_FACTORY, {"linear_regression": lambda: Estimator("linear"), "ridge_regression": lambda: Estimator("ridge")}):
        result = training.train_and_evaluate(frame, "target", ["linear_regression", "ridge_regression"], raw_df=frame)
    assert sum(indices == set(test) for _, indices in calls) == 1
    assert all(r["metric_scope"] == "validation" for r in result["results"])


def test_evaluation_reproduces_exported_winner_test_score():
    frame = data()
    result = training.train_and_evaluate(frame, "target", ["linear_regression"], raw_df=frame)
    evaluation = evaluate_model(frame, "target", result["best_model"], raw_df=frame)
    assert evaluation["test_metrics"] == result["final_test_metrics"]


def test_planning_cannot_see_reserved_validation_or_test_rows():
    frame = data()
    _, train, _, _ = training.reserved_partitions(frame)
    assert set(training.planning_frame(frame).index) == set(train)

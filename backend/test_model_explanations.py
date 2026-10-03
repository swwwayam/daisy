from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.linear_model import LinearRegression

import main
import model_training
from model_explanations import prepare_validation, explain_validation
from persistence import SQLiteStore


def test_api_explains_exact_model_without_refit_or_final_test(tmp_path, monkeypatch):
    monkeypatch.setenv("DAISY_MODEL_DIR", str(tmp_path / "models"))
    store = SQLiteStore(tmp_path / "state.db")
    rng = np.random.default_rng(1)
    raw = pd.DataFrame({"x": rng.normal(size=200), "noise": rng.normal(size=200)})
    raw["target"] = 10 * raw.x
    test_ids = set(model_training.reserved_partitions(raw)[3])
    seen = []
    original_predict = LinearRegression.predict
    def track(estimator, X):
        assert not set(X.index) & test_ids
        seen.append(set(X.index))
        return original_predict(estimator, X)
    track.__name__ = "predict"
    with patch.object(main, "resource_store", store), patch.object(main, "job_queue", None), patch.object(main, "validate_access_token", AsyncMock(side_effect=lambda token: {"id": token})), TestClient(main.app) as client:
        a, b = {"Authorization": "Bearer explanation-owner"}, {"Authorization": "Bearer outsider"}
        root = client.post("/upload-dataset", headers=a, files={"file": ("data.csv", raw.to_csv(index=False), "text/csv")}).json()["dataset_id"]
        trained = client.post("/agents/model-training", headers=a, json={"dataset_id": root, "target_column": "target", "candidate_models": ["linear_regression"]})
        assert trained.status_code == 200, trained.text
        identifier = trained.json()["output_summary"]["experiment_id"]
        with patch.object(LinearRegression, "predict", track), patch.object(LinearRegression, "fit", side_effect=AssertionError("Cannot refit saved winner")):
            response = client.post(f"/experiments/{identifier}/explain", headers=a, json={"features": ["x", "noise"]})
            assert response.status_code == 200, response.text
            report = response.json()
            assert len(seen) == 7 and len(set.union(*seen)) == 40
            assert report["features"][0]["feature"] == "x"
            assert report["features"][0]["score_decrease"] > 10
            assert abs(report["features"][1]["score_decrease"]) < 1e-10
            assert client.post(f"/experiments/{identifier}/explain", headers=a, json={"features": ["x", "noise"]}).json() == report
        assert client.post(f"/experiments/{identifier}/explain", headers=b, json={"features": ["x"]}).status_code == 404
        assert client.post(f"/experiments/{identifier}/explain", headers=a, json={"features": ["target"]}).status_code == 409
        assert client.post(f"/experiments/{identifier}/explain", headers=a, json={"features": ["x", "x"]}).status_code == 409
        assert client.post(f"/experiments/{identifier}/explain", headers=a, json={"features": []}).status_code == 422
        assert client.get(f"/experiments/{identifier}", headers=a).json()["final_evaluation"] is None
        assert main.experiment_registry.finalization(store, root, "explanation-owner") is None
        with store.connect() as db:
            count, rows = db.execute("SELECT count(*),sum(rows) FROM prediction_usage WHERE owner=?", ("explanation-owner",)).fetchone()
            assert count == 2 and rows == 40 * 7 * 2


@pytest.mark.parametrize("strategy", ["random", "group", "time"])
def test_validation_replays_frozen_split_and_samples_before_transform(strategy):
    raw = pd.DataFrame({"x": range(1500), "group": np.arange(1500) % 20,
                        "date": pd.date_range("2020-01-01", periods=1500), "target": np.arange(1500) * 3.2})
    config = {"target_column": "target", "problem_type": "regression", "split_strategy": strategy,
              "group_column": "group", "time_column": "date", "primary_metric": "mae"}
    source, train_ids, val_ids, test_ids = model_training.reserved_partitions(raw, configuration=config)
    estimator = LinearRegression().fit(source.loc[train_ids, ["x"]], source.loc[train_ids, "target"])
    bundle = {"estimator": estimator, "feature_columns": ["x"], "input_columns": ["x"], "target_column": "target", "preprocessing": []}
    metadata = {"test_size": .2, "random_state": 42, "training_config": config, "target_column": "target", "primary_metric": "mae",
                "dataset_fingerprint": model_training._dataset_fingerprint(source), "validation_index_hash": model_training._hash_index(val_ids), "artifact_id": "model"}
    X, y, total = prepare_validation(bundle, metadata, raw, ["x"])
    assert len(X) == 200 and total == len(val_ids)
    assert set(X.index) <= set(val_ids) and not set(X.index) & set(test_ids)
    report = explain_validation(bundle, metadata, X, y, ["x"], total)
    assert report["change_label"] == "Error increase" and report["baseline_metric_value"] < 1e-10
    assert report["features"][0]["score_decrease"] > 0
    with pytest.raises(ValueError, match="fingerprint"):
        prepare_validation(bundle, metadata, raw.assign(x=raw.x + 1), ["x"])
    with pytest.raises(ValueError, match="Validation rows"):
        prepare_validation(bundle, {**metadata, "validation_index_hash": "wrong"}, raw, ["x"])


@pytest.mark.parametrize("metric", ["accuracy", "balanced_accuracy", "f1_macro", "f1_weighted"])
def test_classification_explanation_uses_recorded_metric(metric):
    from sklearn.tree import DecisionTreeClassifier
    X = pd.DataFrame({"x": [0, 1] * 40})
    y = X.x
    estimator = DecisionTreeClassifier(random_state=42).fit(X, y)
    report = explain_validation({"estimator": estimator}, {"primary_metric": metric, "artifact_id": "model"}, X, y, ["x"], len(X))
    assert report["metric"] == metric and report["baseline_metric_value"] == 1
    assert report["features"][0]["score_decrease"] > .1

"""Measured SHAP additivity, bounds and aggregate-only plotting regressions."""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.linear_model import LinearRegression
from agents import distributions_for_eda, profile_for_eda
from model_explanations import explain_tree_shap, validate_shap_model
from persistence import SQLiteStore
import main


@pytest.mark.parametrize("classifier", [False, True])
@pytest.mark.parametrize("family", ["tree", "forest", "extra"])
def test_shap_reconstructs_frozen_model_output_without_fitting(classifier, family):
    X = pd.DataFrame({"signal": np.arange(80, dtype=float), "noise": np.tile([0., 1.], 40)})
    y = (X.signal > 40).astype(int) if classifier else X.signal * 4
    factories = {"tree": (DecisionTreeClassifier, DecisionTreeRegressor), "forest": (RandomForestClassifier, RandomForestRegressor), "extra": (ExtraTreesClassifier, ExtraTreesRegressor)}
    factory = factories[family][0 if classifier else 1]
    estimator = factory(max_depth=4, random_state=42, **({"n_estimators": 8} if family != "tree" else {})).fit(X, y)
    report = explain_tree_shap({"estimator": estimator}, {"artifact_id": "saved"}, X, ["signal"], 80)
    assert report["method"] == "tree_shap" and report["rows_evaluated"] == 64
    local = report["local"]
    assert local["base_value"] + sum(row["contribution"] for row in local["features"]) + local["other_features_contribution"] == pytest.approx(local["model_output"])
    assert report["features"][0]["mean_abs_shap"] > 0
    assert "Probability" in report["output_label"] if classifier else report["output_label"] == "Predicted target value"
    assert "feature_values" not in local


def test_distribution_labels_are_not_sent_to_ai():
    from ai_privacy import private_profile
    report = {"distributions": {"city": [{"label": "private-category", "value": 15}]}, "overview": {"rows": 15}}
    protected, _ = private_profile(report, ["city"])
    assert "distributions" not in protected and protected["overview"]["rows"] == 15


def test_unsupported_or_oversized_shap_models_are_rejected():
    X = pd.DataFrame({"x": range(40)})
    with pytest.raises(ValueError, match="permutation"):
        validate_shap_model(LinearRegression().fit(X, X.x), X)
    tree = DecisionTreeRegressor(max_depth=2).fit(X, X.x)
    with pytest.raises(ValueError, match="budget"):
        validate_shap_model(tree, pd.DataFrame(np.zeros((4, 257))))


def test_chart_aggregates_preserve_zeros_and_bound_category_and_column_counts():
    frame = pd.DataFrame({"value": [0., 0., 2., np.nan, np.inf], "category": ["a", "a", "b", None, "c"], "constant": [1.] * 5})
    charts = distributions_for_eda(frame)
    assert sum(row["value"] for row in charts["value"]) == 3
    assert sum(row["value"] for row in charts["category"]) == 4
    assert np.isnan(profile_for_eda(frame)["correlation"]["constant"]["constant"])
    assert len(distributions_for_eda(pd.DataFrame(np.ones((10, 50))))) == 20


def test_shap_api_reuses_owned_artifact_and_never_refits_or_finalizes(tmp_path, monkeypatch):
    monkeypatch.setenv("DAISY_MODEL_DIR", str(tmp_path / "models"))
    store = SQLiteStore(tmp_path / "state.db")
    raw = pd.DataFrame({"x": range(180), "noise": np.tile([0, 1], 90)})
    raw["target"] = raw.x * 3.0
    with patch.object(main, "resource_store", store), patch.object(main, "job_queue", None), patch.object(main, "validate_access_token", AsyncMock(side_effect=lambda token: {"id": token})), TestClient(main.app) as client:
        headers = {"Authorization": "Bearer shap-owner"}
        source = client.post("/upload-dataset", headers=headers, files={"file": ("test.csv", raw.to_csv(index=False), "text/csv")}).json()["dataset_id"]
        trained = client.post("/agents/model-training", headers=headers, json={"dataset_id": source, "target_column": "target", "candidate_models": ["decision_tree_regressor"]})
        assert trained.status_code == 200, trained.text
        identifier = trained.json()["output_summary"]["experiment_id"]
        with patch.object(DecisionTreeRegressor, "fit", side_effect=AssertionError("Do not refit")):
            report = client.post(f"/experiments/{identifier}/explain", headers=headers, json={"method": "shap", "features": ["x"]})
            assert report.status_code == 200, report.text
            assert report.json()["method"] == "tree_shap"
        assert client.post(f"/experiments/{identifier}/explain", headers={"Authorization": "Bearer other"}, json={"method": "shap", "features": ["x"]}).status_code == 404
        assert main.experiment_registry.finalization(store, source, "shap-owner") is None

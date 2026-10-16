import numpy as np
import pandas as pd
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
from persistence import SQLiteStore
from visualizations import build_plot
import main


def test_auto_and_full_dataset_aggregations_preserve_zeros():
    frame = pd.DataFrame({"x": [0., 0., 10., np.nan, np.inf], "city": ["a", "a", "b", "a", "a"], "y": [2., 4., 6., 8., 10.]})
    histogram = build_plot(frame, "x")
    assert histogram["kind"] == "histogram"
    assert sum(point["y"] for point in histogram["points"]) == 3
    assert histogram["excluded_rows"] == 2
    bars = build_plot(frame, "city", "y")
    assert bars["kind"] == "bar" and {p["x"]: p["y"] for p in bars["points"]} == {"a": 6., "b": 6.}
    summed = build_plot(frame, "city", "y", "bar", "sum")
    assert summed["points"][0] == {"x": "a", "y": 24.}
    assert build_plot(frame, "x", "y")["kind"] == "scatter"


def test_sampling_is_bounded_deterministic_and_lines_sorted():
    frame = pd.DataFrame({"x": np.arange(10000), "y": np.arange(10000) * 2})
    first = build_plot(frame, "x", "y", "line")
    assert first == build_plot(frame, "x", "y", "line")
    assert first["sampled"] and first["rows_used"] == 1000 and first["source_rows"] == 10000
    assert [p["x"] for p in first["points"]] == sorted(p["x"] for p in first["points"])
    assert len(build_plot(frame, "x", kind="bar")["points"]) == 20


@pytest.mark.parametrize("x,y,kind", [("missing", None, "auto"), ("text", None, "histogram"), ("text", "n", "scatter"), ("n", None, "line"), ("n", "text", "bar")])
def test_incompatible_axes_return_actionable_errors(x, y, kind):
    with pytest.raises(ValueError):
        build_plot(pd.DataFrame({"n": [0, 1], "text": ["a", "b"]}), x, y, kind)


def test_category_heatmap_counts_and_high_cardinality_bound():
    frame = pd.DataFrame({"actual": ["a", "a", "b"], "predicted": ["a", "b", "b"]})
    result = build_plot(frame, "actual", "predicted")
    assert result["kind"] == "heatmap" and sum(p["value"] for p in result["cells"]) == 3
    frame = pd.DataFrame({"a": [f"a{i}" for i in range(10000)], "b": [f"b{i}" for i in range(10000)]})
    assert len(build_plot(frame, "a", "b")["cells"]) == 225


@pytest.mark.parametrize("classification", [False, True])
def test_plot_api_ownership_frozen_predictions_and_no_final_test(tmp_path, monkeypatch, classification):
    monkeypatch.setenv("DAISY_MODEL_DIR", str(tmp_path / "models"))
    store = SQLiteStore(tmp_path / "plots.db")
    raw = pd.DataFrame({"x": range(180), "target": np.arange(180) * 3.})
    if classification:
        raw["target"] = np.where(raw.x > 90, "yes", "no")
    with patch.object(main, "resource_store", store), patch.object(main, "job_queue", None), patch.object(main, "validate_access_token", AsyncMock(side_effect=lambda token: {"id": token})), TestClient(main.app) as client:
        headers = {"Authorization": "Bearer plot-owner"}
        source = client.post("/upload-dataset", headers=headers, files={"file": ("plots.csv", raw.to_csv(index=False), "text/csv")}).json()["dataset_id"]
        route = f"/dataset/{source}/plot"
        assert client.post(route, headers=headers, json={"x": "x"}).status_code == 200
        assert client.post(route, headers={"Authorization": "Bearer other"}, json={"x": "x"}).status_code == 404
        assert client.post(route, headers=headers, json={"x": "missing"}).status_code == 400
        trained = client.post("/agents/model-training", headers=headers, json={"dataset_id": source, "target_column": "target", "candidate_models": ["decision_tree_classifier" if classification else "decision_tree_regressor"]})
        assert trained.status_code == 200, trained.text
        identifier = trained.json()["output_summary"]["experiment_id"]
        route = f"/experiments/{identifier}/plot"
        with patch.object(DecisionTreeClassifier if classification else DecisionTreeRegressor, "fit", side_effect=AssertionError("No refit")):
            result = client.post(route, headers=headers, json={"x": "predicted", "y": "actual" if classification else "residual"})
        assert result.status_code == 200, result.text
        report = result.json()
        assert report["validation_sample"] and report["rows_used"] <= 200
        assert report["kind"] == ("heatmap" if classification else "scatter")
        assert all(np.isfinite(p["y"]) for p in report["points"])
        assert client.post(route, headers={"Authorization": "Bearer other"}, json={"x": "actual"}).status_code == 404
        assert main.experiment_registry.finalization(store, source, "plot-owner") is None

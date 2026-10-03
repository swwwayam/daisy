from concurrent.futures import ThreadPoolExecutor
import io
import json
import zipfile
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import main
import model_training
from experiments import ExperimentRegistry, FinalizationConflict
from persistence import SQLiteStore, PersistenceError
import httpx
from persistence import SupabaseStore


def test_sqlite_claim_has_one_winner_and_survives_restart(tmp_path):
    path = tmp_path / "state.db"
    store = SQLiteStore(path)
    registry = ExperimentRegistry()
    def claim(identifier):
        try:
            return registry.claim(store, "source", "a", identifier)["experiment_id"]
        except FinalizationConflict:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        winners = list(pool.map(claim, ["first", "second", "third", "fourth"]))
    selected = next(winner for winner in winners if winner)
    assert sum(winner is not None for winner in winners) == 1
    registry.finish(store, "source", "a", selected, {"score": 1})
    assert ExperimentRegistry().claim(SQLiteStore(path), "source", "a", selected)["report"] == {"score": 1}
    assert registry.finish(store, "source", "a", selected, {"score": 2}) == {"score": 1}
    assert registry.finalization(store, "source", "b") is None


def test_experiment_cannot_be_overwritten(tmp_path):
    store = SQLiteStore(tmp_path / "state.db")
    registry = ExperimentRegistry()
    registry.create(store, "experiment", "a", {"winner": "first"})
    with pytest.raises(PersistenceError):
        registry.create(store, "experiment", "a", {"winner": "second"})
    with pytest.raises(PersistenceError):
        store.save("experiment", "a", "experiment", {"winner": "second"})
    assert registry.get(store, "experiment", "b") is None
    assert registry.get(store, "experiment", "a")["winner"] == "first"


def test_cloud_claim_uses_server_only_atomic_rpc():
    calls = []
    def handle(request):
        import json
        calls.append(request)
        assert request.headers["apikey"] == "sb_secret_test"
        assert "authorization" not in request.headers
        body = json.loads(request.content)
        assert body["p_owner"] == "owner" and body["p_source"] == "source"
        return httpx.Response(200, json={"experiment_id": "first", "report": None})
    store = SupabaseStore("https://test.supabase.co", "sb_secret_test", httpx.MockTransport(handle))
    registry = ExperimentRegistry()
    assert registry.claim(store, "source", "owner", "first")["report"] is None
    with pytest.raises(FinalizationConflict):
        registry.claim(store, "source", "owner", "second")
    assert all(request.url.path == "/rest/v1/rpc/daisy_claim_finalization" for request in calls)


def test_validation_only_training_never_predicts_test_rows():
    raw = pd.DataFrame({"x": range(100), "target": np.arange(100) * 5.1})
    test_ids = set(model_training.reserved_partitions(raw)[3])
    calls = []
    class Estimator:
        def fit(self, X, y): return self
        def predict(self, X):
            calls.append(set(X.index))
            return np.asarray(X.x) * 5.1
    with patch.dict(model_training.MODEL_FACTORY, {"linear_regression": Estimator}):
        result = model_training.train_and_evaluate(raw, "target", ["linear_regression"], raw_df=raw, finalize_test=False)
    assert calls and test_ids not in calls
    assert result["final_test_metrics"] is None and result["evaluation_data"] is None


def test_independent_attempts_finalize_exact_export_restart_and_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("DAISY_MODEL_DIR", str(tmp_path / "models"))
    store = SQLiteStore(tmp_path / "state.db")
    rng = np.random.default_rng(4)
    raw = pd.DataFrame({"x": rng.normal(size=100)})
    raw["target"] = raw.x * 7 + rng.normal(size=100)
    auth = AsyncMock(side_effect=lambda token: {"id": token})
    with patch.object(main, "resource_store", store), patch.object(main, "job_queue", None), patch.object(main, "experiment_registry", ExperimentRegistry()), patch.object(main, "validate_access_token", auth), TestClient(main.app) as client:
        a, b = {"Authorization": "Bearer a"}, {"Authorization": "Bearer b"}
        root = client.post("/upload-dataset", headers=a, files={"file": ("source.csv", raw.to_csv(index=False), "text/csv")}).json()["dataset_id"]
        reviewed = client.post(f"/dataset/{root}/review", headers=a, json={"training_config": {"target_column": "target", "problem_type": "regression", "split_strategy": "random", "primary_metric": "mae"}}).json()["dataset_id"]
        def train(name):
            response = client.post("/agents/model-training", headers=a, json={"dataset_id": reviewed, "target_column": "target", "candidate_models": [name]})
            assert response.status_code == 200, response.text
            result = response.json()["output_summary"]
            assert result["final_test_metrics"] is None
            assert result["model_artifact"] is not None
            return result["experiment_id"]
        first, second = train("linear_regression"), train("ridge_regression")
        assert first != second
        preview_card = client.get(f"/experiments/{first}/model-card/download", headers=a)
        with zipfile.ZipFile(io.BytesIO(preview_card.content)) as archive:
            assert "Not measured" in archive.read("model_card.md").decode()
            assert json.loads(archive.read("report.json"))["assessment"] == "validation_only"
        assert client.get(f"/experiments/{first}/model-card/download", headers=b).status_code == 404
        assert client.get(f"/experiments/{first}", headers=a).json()["training_result"]["best_model"] == "linear_regression"
        assert client.get(f"/experiments/{first}", headers=b).status_code == 404
        assert client.post(f"/experiments/{first}/finalize", headers=b).status_code == 404
        assert client.get("/experiments", headers=b).json()["experiments"] == []
        # Clear caches to require restoration of datasets, ownership and records.
        with patch.dict(main.DATASETS, {}, clear=True), patch.object(main, "experiment_registry", ExperimentRegistry()):
            final = client.post(f"/experiments/{first}/finalize", headers=a)
            assert final.status_code == 200, final.text
            measured = final.json()
            assert measured["artifact_id"] and "rmse" in measured["test_metrics"]
            assert measured["primary_metric"] == measured["selection_metric"] == "mae"
            assert measured["gap_definition"] == "test_minus_train"
            assert measured["train_test_gap"] == pytest.approx(round(measured["test_metrics"]["mae"] - measured["train_metrics"]["mae"], 4))
            assert measured["baseline_test_metrics"]["mae"] > measured["test_metrics"]["mae"]
            with patch.object(main, "evaluate_saved_winner", side_effect=AssertionError("must not score twice")):
                assert client.post(f"/experiments/{first}/finalize", headers=a).json() == measured
            assert client.post(f"/experiments/{second}/finalize", headers=a).status_code == 409
            assert client.post(f"/dataset/{root}/review", headers=a, json={}).status_code == 409
            assert client.get(f"/experiments/{first}/report/download", headers=a).json() == measured
            assert client.get(f"/experiments/{first}/report/download", headers=b).status_code == 404
            assert client.get(f"/experiments/{first}", headers=a).json()["final_evaluation"] == measured
            assert "evaluation_state" not in client.get(f"/experiments/{first}", headers=a).json()
            card = client.get(f"/experiments/{first}/model-card/download", headers=a)
            with zipfile.ZipFile(io.BytesIO(card.content)) as archive:
                assert json.loads(archive.read("report.json"))["final_evaluation"] == measured
                assert "Simple baseline" in archive.read("model_card.md").decode()
                assert "Train/test gap metric: mae" in archive.read("model_card.md").decode()


def test_history_is_compact_paginated_and_private(tmp_path):
    store = SQLiteStore(tmp_path / "state.db")
    registry = ExperimentRegistry()
    for number in range(23):
        registry.create(store, str(number), "a", {"created_at": str(number), "dataset_id": "dataset", "target_column": "target",
                                               "training_result": {"best_model": "ridge", "primary_metric": "mae"},
                                               "evaluation_state": {"train_row_ids": list(range(10000))}})
    first = registry.list(store, "a", 20, 0)
    second = registry.list(store, "a", 20, 20)
    assert len(first) == 20 and len(second) == 3
    assert not {row["id"] for row in first} & {row["id"] for row in second}
    assert "evaluation_state" not in json.dumps(first)
    assert len(json.dumps(first)) < 7000
    assert registry.list(store, "b", 20, 0) == []

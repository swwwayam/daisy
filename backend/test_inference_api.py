import io
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main
import feature_engineering
from daisy_predict import predict
from final_evaluation import load_server_package
from persistence import SQLiteStore
from prediction_usage import PredictionUsage


def test_prediction_matches_downloaded_model_and_never_persists_inputs(tmp_path, monkeypatch):
    monkeypatch.setenv("DAISY_MODEL_DIR", str(tmp_path / "models"))
    store = SQLiteStore(tmp_path / "state.db")
    raw_csv = "amount,code,region,target\n" + "\n".join(f"{i},{['001','002'][i%2]},{['NA','EU'][i%3==0]},{i*3.2+i%2*20}" for i in range(80))
    with patch.object(main, "resource_store", store), patch.object(main, "job_queue", None), patch.object(main, "validate_access_token", AsyncMock(side_effect=lambda token: {"id": token})), TestClient(main.app) as client:
        a, b = {"Authorization": "Bearer inference-owner"}, {"Authorization": "Bearer b"}
        root = client.post("/upload-dataset", headers=a, files={"file": ("source.csv", raw_csv, "text/csv")}).json()["dataset_id"]
        steps = list(main.DATASET_TRANSFORMS[root])
        frame, _ = feature_engineering.apply_feature_engineering_plan(main.DATASETS[root], [
            {"type": "encode_categorical", "column": "code", "strategy": "label"},
            {"type": "encode_categorical", "column": "region", "strategy": "onehot"},
        ], "target", fitted_steps=steps)
        derived = main.create_derived_dataset(root, "inference-owner", frame, steps)
        trained = client.post("/agents/model-training", headers=a, json={"dataset_id": derived, "target_column": "target", "candidate_models": ["linear_regression"]})
        assert trained.status_code == 200, trained.text
        artifact = trained.json()["output_summary"]["model_artifact"]["artifact_id"]
        new_csv = b"amount,code,region,unused\n100,001,NA,extra\n200,002,new,extra\n"
        with store.connect() as db:
            before = db.execute("SELECT count(*) FROM resources").fetchone()[0]
        response = client.post(f"/models/{artifact}/predict", headers=a, files={"file": ("new.csv", new_csv, "text/csv")})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["rows"] == 2 and result["diagnostics"]["input_rows_persisted"] is False
        assert result["diagnostics"]["unseen_category_counts"]["region"] == 1
        assert result["diagnostics"]["unseen_category_counts"]["code"] == 0
        assert result["diagnostics"]["extra_columns_ignored"] == ["unused"]
        exported, _ = load_server_package(main.owned_artifact_path(artifact, "inference-owner"), artifact)
        expected = predict(exported, pd.read_csv(io.BytesIO(new_csv), dtype=str, keep_default_na=False))
        output = pd.read_csv(io.StringIO(result["prediction_csv"]))
        np.testing.assert_allclose(output.prediction, expected)
        assert output.input_row.tolist() == [0, 1]
        with store.connect() as db:
            assert db.execute("SELECT count(*) FROM resources").fetchone()[0] == before
        assert client.post(f"/models/{artifact}/predict", headers=b, files={"file": ("new.csv", new_csv, "text/csv")}).status_code == 404
        assert client.post(f"/models/{artifact}/predict", headers=a, files={"file": ("new.csv", b"wrong\n1\n", "text/csv")}).status_code == 400
        assert client.post(f"/models/{artifact}/predict", headers=a, files={"file": ("new.csv", b"amount,amount\n1,2\n", "text/csv")}).status_code == 400
        too_many = b"amount,code,region\n" + b"1,001,NA\n" * 10001
        assert client.post(f"/models/{artifact}/predict", headers=a, files={"file": ("new.csv", too_many, "text/csv")}).status_code == 400


def test_atomic_prediction_quota_survives_restart_and_is_owner_specific(tmp_path):
    path = tmp_path / "state.db"
    store = SQLiteStore(path)
    usage = PredictionUsage()
    def reserve(_):
        try:
            usage.reserve(store, "a", 10000)
            return True
        except HTTPException as exc:
            assert exc.status_code == 429
            return False
    with ThreadPoolExecutor(4) as pool:
        accepted = list(pool.map(reserve, range(12)))
    assert sum(accepted) == 10
    with pytest.raises(HTTPException):
        PredictionUsage().reserve(SQLiteStore(path), "a", 1)
    PredictionUsage().reserve(SQLiteStore(path), "b", 1)


def test_prediction_rejects_excessive_encoded_cells_before_transform():
    import inference
    with pytest.raises(ValueError, match="encoding"):
        inference.read_csv(b"x\n1\n2\n", {"preprocessing": [], "feature_columns": range(500001)})

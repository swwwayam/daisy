import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pandas as pd
import pytest

import main
from input_review import InputReview, read_source
from persistence import SQLiteStore
from daisy_predict import normalize_input
import io
import subprocess
import sys
import zipfile
import numpy as np
import feature_engineering
import model_export
import model_training
from daisy_predict import load_model, predict


def test_literals_and_identifiers_are_preserved_until_review():
    raw = b"code,region,amount\n001,NA,0\n002,?,10\n003,-,\n"
    frame, policy = read_source(raw)
    assert frame.code.tolist() == ["001", "002", "003"]
    assert frame.region.tolist() == ["NA", "?", "-"]
    assert frame.amount.iloc[0] == 0
    assert pd.isna(frame.amount.iloc[2])
    reviewed, policy = read_source(raw, InputReview(column_tokens={"region": ["?"]}, column_types={"code": "text"}))
    assert reviewed.region.iloc[0] == "NA" and reviewed.region.iloc[2] == "-"
    assert pd.isna(reviewed.region.iloc[1])
    assert normalize_input(pd.DataFrame({"code": ["004"], "region": ["?"], "amount": ["0"]}), policy).code.iloc[0] == "004"


def test_review_and_original_download_survive_restart_and_are_private(tmp_path):
    raw = b"code,region,amount\n001,NA,0\n002,?,10\n"
    store = SQLiteStore(tmp_path / "state.db")
    with patch.object(main, "resource_store", store), patch.object(main, "validate_access_token", AsyncMock(side_effect=lambda token: {"id": token})), TestClient(main.app) as client:
        headers = {"Authorization": "Bearer a"}
        uploaded = client.post("/upload-dataset", headers=headers, files={"file": ("input.csv", raw, "text/csv")}).json()
        original = uploaded["dataset_id"]
        assert uploaded["preview"][0]["region"] == "NA"
        reviewed = client.post(f"/dataset/{original}/review", headers=headers, json={"column_tokens": {"region": ["?"]}, "column_types": {"code": "text"}})
        assert reviewed.status_code == 200
        identifier = reviewed.json()["dataset_id"]
        main.DATASETS.pop(identifier)
        restored = client.get(f"/dataset/{identifier}/summary", headers=headers)
        assert restored.json()["preview"][1]["region"] is None
        assert main.interpreted_source(identifier, "a").code.iloc[0] == "001"
        assert client.get(f"/dataset/{identifier}/source/download", headers=headers).content == raw
        other = {"Authorization": "Bearer b"}
        assert client.get(f"/dataset/{identifier}/source/download", headers=other).status_code == 404
        assert client.post(f"/dataset/{identifier}/review", headers=other, json={}).status_code == 404
        assert main.DATASETS[original].region.iloc[1] == "?"  # immutable interpretation source
        assert main.DATASET_TRANSFORMS[identifier][0]["column_tokens"] == {"region": ["?"]}


def test_invalid_reviews_do_not_silently_coerce_values():
    with pytest.raises(ValueError):
        read_source(b"x\nNA\n", InputReview(column_types={"x": "numeric"}))
    with pytest.raises(ValueError, match="unknown columns"):
        read_source(b"x\n1\n", InputReview(column_tokens={"wrong": ["NA"]}))


def test_downloaded_cli_preserves_literal_na_and_leading_zero_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("DAISY_MODEL_DIR", str(tmp_path / "exports"))
    raw, policy = read_source(("code,region,target\n" + "\n".join(
        f"{['001','002'][i % 2]},{['NA','EU'][i % 3 == 0]},{100 * (i % 2) + 10 * (i % 3 == 0) + i * .001}" for i in range(100))).encode())
    steps = [policy]
    engineered, _ = feature_engineering.apply_feature_engineering_plan(raw, [
        {"type": "encode_categorical", "column": "code", "strategy": "onehot"},
        {"type": "encode_categorical", "column": "region", "strategy": "onehot"},
    ], "target", fitted_steps=steps)
    fitted, operations = {}, []
    result = model_training.train_and_evaluate(engineered, "target", ["linear_regression"], raw_df=raw,
                                                preprocessing_steps=steps, fitted_models=fitted, fitted_preprocessing=operations)
    artifact = model_export.export_model(fitted[result["best_model"]], engineered, "target", operations, result, "data", "run", source_df=raw)
    standalone = tmp_path / "standalone"
    with zipfile.ZipFile(model_export.artifact_path(artifact["artifact_id"])) as archive:
        archive.extractall(standalone)
    new = pd.DataFrame({"code": ["001", "002"], "region": ["NA", "EU"]})
    expected = predict(load_model(standalone / "model.joblib"), new)
    new.to_csv(standalone / "new.csv", index=False)
    completed = subprocess.run([sys.executable, "daisy_predict.py", "new.csv", "predictions.csv"], cwd=standalone, capture_output=True, text=True, timeout=45)
    assert completed.returncode == 0, completed.stderr
    np.testing.assert_allclose(pd.read_csv(standalone / "predictions.csv").prediction, expected)

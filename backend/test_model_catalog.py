import io
import json
import zipfile
from unittest.mock import AsyncMock, patch

import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import main
import model_export
from model_catalog import MODEL_FACTORY, CLASSIFICATION_MODELS, REGRESSION_MODELS
from daisy_predict import predict


@pytest.mark.parametrize("name", list(MODEL_FACTORY))
def test_every_catalog_model_fits_and_exports_portable_predictions(name, tmp_path, monkeypatch):
    monkeypatch.setenv("DAISY_MODEL_DIR", str(tmp_path))
    rng = np.random.default_rng(42)
    frame = pd.DataFrame(rng.normal(size=(40, 3)), columns=["a", "b", "c"])
    classification = name in CLASSIFICATION_MODELS
    target = (frame.a > 0).astype(int) if classification else 4 * frame.a - frame.b
    estimator = MODEL_FACTORY[name]()
    estimator.fit(frame, target)
    frame["target"] = target
    result = {"best_model": name, "problem_type": "classification" if classification else "regression", "primary_metric": "f1_weighted" if classification else "rmse", "results": [], "n_train": 40, "n_test": 0, "test_size": .2, "random_state": 42}
    artifact = model_export.export_model(estimator, frame, "target", [], result, "dataset", "run", source_df=frame, owner_id="a")
    with zipfile.ZipFile(model_export.artifact_path(artifact["artifact_id"])) as archive:
        bundle = joblib.load(io.BytesIO(archive.read("model.joblib")))
    np.testing.assert_allclose(predict(bundle, frame), estimator.predict(frame.drop(columns="target")))


def test_catalog_api_requires_login_and_filters_task():
    assert len(MODEL_FACTORY) == len(CLASSIFICATION_MODELS) + len(REGRESSION_MODELS) == 27
    with patch.object(main, "validate_access_token", AsyncMock(return_value={"id": "a"})), TestClient(main.app) as client:
        assert client.get("/models/catalog").status_code == 401
        rows = client.get("/models/catalog?problem_type=regression", headers={"Authorization": "Bearer a"}).json()["models"]
        assert {row["name"] for row in rows} == set(REGRESSION_MODELS)
        assert client.get("/models/catalog?problem_type=unknown", headers={"Authorization": "Bearer a"}).status_code == 422

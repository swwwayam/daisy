import hashlib
import json
import zipfile
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import main
from final_evaluation import load_server_package
from persistence import SQLiteStore, PersistenceError


def test_failed_durable_export_is_not_advertised_and_local_files_are_removed(tmp_path, monkeypatch):
    directory = tmp_path / "models"
    monkeypatch.setenv("DAISY_MODEL_DIR", str(directory))
    class FailingStore(SQLiteStore):
        def save(self, identifier, owner, kind, metadata, blob=None):
            if kind == "artifact":
                raise PersistenceError("Storage write failed")
            return super().save(identifier, owner, kind, metadata, blob)
    store = FailingStore(tmp_path / "state.db")
    raw = pd.DataFrame({"x": range(80), "target": [i * 3.4 for i in range(80)]})
    with patch.object(main, "resource_store", store), patch.object(main, "job_queue", None), patch.object(main, "validate_access_token", AsyncMock(return_value={"id": "package-owner"})), TestClient(main.app) as client:
        headers = {"Authorization": "Bearer test"}
        root = client.post("/upload-dataset", headers=headers, files={"file": ("data.csv", raw.to_csv(index=False), "text/csv")}).json()["dataset_id"]
        response = client.post("/agents/model-training", headers=headers, json={"dataset_id": root, "target_column": "target", "candidate_models": ["linear_regression"]})
        assert response.status_code == 200, response.text
        output = response.json()["output_summary"]
        assert output["best_model"] == "linear_regression" and output["export_error"]
        assert output["model_artifact"] is None
        assert list(directory.iterdir()) == []
        experiment = client.get(f'/experiments/{output["experiment_id"]}', headers=headers).json()
        assert experiment["model_artifact"] is None
        assert client.post(f'/experiments/{output["experiment_id"]}/finalize', headers=headers).status_code == 409


@pytest.mark.parametrize("damage", ["not_zip", "missing", "duplicate", "oversized_metadata", "checksum", "bad_pickle"])
def test_package_failure_is_clear_and_preflight_precedes_deserialization(tmp_path, damage):
    path = tmp_path / "package.zip"
    payload = b"invalid-joblib"
    metadata = json.dumps({"artifact_id": "model"}).encode()
    checksums = {"files": {"model.joblib": hashlib.sha256(payload).hexdigest(), "metadata.json": hashlib.sha256(metadata).hexdigest()}}
    if damage == "not_zip":
        path.write_bytes(b"broken")
    else:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("checksums.json", json.dumps(checksums))
            if damage != "missing":
                archive.writestr("model.joblib", payload)
            archive.writestr("metadata.json", b"x" * (8 * 1024 * 1024 + 1) if damage == "oversized_metadata" else metadata)
            if damage == "duplicate":
                with pytest.warns(UserWarning, match="Duplicate"):
                    archive.writestr("metadata.json", metadata)
            if damage == "checksum":
                # Rewrite before loading to avoid confusing duplicate-member failure.
                checksums["files"]["model.joblib"] = "wrong"
        if damage == "checksum":
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("checksums.json", json.dumps(checksums))
                archive.writestr("model.joblib", payload)
                archive.writestr("metadata.json", metadata)
    if damage == "bad_pickle":
        with pytest.raises(ValueError, match="damaged or incompatible"):
            load_server_package(path, "model")
    else:
        with patch("final_evaluation.joblib.load", side_effect=AssertionError("Must reject before loading")) as loader:
            with pytest.raises(ValueError, match="package|integrity|members"):
                load_server_package(path, "model")
            loader.assert_not_called()

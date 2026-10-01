import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import main
from persistence import SQLiteStore, SupabaseStore, PersistenceError
from resource_access import ResourceOwners


def test_restart_restores_private_dataset_lineage_and_run():
    with tempfile.TemporaryDirectory() as directory, patch.object(main, "resource_store", SQLiteStore(Path(directory) / "state.db")), patch.object(main, "validate_access_token", AsyncMock(side_effect=lambda token: {"id": token})), TestClient(main.app) as client:
        a = {"Authorization": "Bearer user-a"}
        b = {"Authorization": "Bearer user-b"}
        parent = client.post("/upload-dataset", headers=a, files={"file": ("data.csv", "x,target\n0,0\n2,1\n3,0", "text/csv")}).json()["dataset_id"]
        child = main.create_derived_dataset(parent, "user-a", main.DATASETS[parent].copy(), [{"type": "normalize"}])
        main.save_pipeline_result(parent, "eda", {"summary": "Real analysis"}, child)
        run_id = str(uuid.uuid4())
        state = {"workflowId": run_id, "originalDatasetId": parent, "currentDatasetId": child}
        assert client.put(f"/runs/{run_id}", headers=a, json={"state": state}).json() == {"saved": True}
        # Clear all process-local state; the next requests must recover from disk.
        with patch.dict(main.DATASETS, {}, clear=True), patch.dict(main.DATASET_PARENTS, {}, clear=True), patch.dict(main.DATASET_TRANSFORMS, {}, clear=True), patch.dict(main.PIPELINE_CONTEXT, {}, clear=True), patch.object(main, "DATASET_OWNERS", ResourceOwners()):
            assert client.get(f"/dataset/{child}/summary", headers=b).status_code == 404
            assert client.get(f"/runs/{run_id}", headers=b).status_code == 404
            assert client.get("/runs", headers=b).json()["runs"] == []
            assert client.get(f"/runs/{run_id}", headers=a).json() == state
            assert main.owned_source_dataset(child, "user-a") == parent
            assert main.DATASETS[child].iloc[0]["x"] == 0
            assert main.PIPELINE_CONTEXT[child]["eda"]["summary"] == "Real analysis"


def test_store_refuses_owner_takeover():
    with tempfile.TemporaryDirectory() as directory:
        store = SQLiteStore(Path(directory) / "state.db")
        store.save("id", "a", "run", {"value": 1})
        with pytest.raises(PersistenceError):
            store.save("id", "b", "run", {"value": 2})
        assert store.get("id", "b", "run") is None


def test_cloud_backed_artifact_recovers_from_loss_of_local_files():
    import model_export
    with tempfile.TemporaryDirectory() as directory, patch.object(main, "resource_store", SQLiteStore(Path(directory) / "state.db")), patch.dict("os.environ", {"DAISY_MODEL_DIR": str(Path(directory) / "models")}), patch.object(main, "validate_access_token", AsyncMock(side_effect=lambda token: {"id": token})), TestClient(main.app) as client:
        identifier = str(uuid.uuid4())
        main.resource_store.save(identifier, "a", "artifact", {"artifact_id": identifier}, b"trusted-model-package")
        assert client.get(f"/models/{identifier}/download", headers={"Authorization": "Bearer b"}).status_code == 404
        response = client.get(f"/models/{identifier}/download", headers={"Authorization": "Bearer a"})
        assert response.content == b"trusted-model-package"
        assert model_export.artifact_owned_by(identifier, "a")


def test_supabase_lookup_filters_owner_before_reading_private_object():
    calls = []
    def handle(request):
        calls.append(request)
        if request.url.path.startswith("/rest"):
            assert request.url.params["owner_id"] == "eq.user-a"
            return httpx.Response(200, json=[{"metadata": {"steps": []}, "storage_bucket": "datasets", "storage_path": "user-a/id/object"}])
        return httpx.Response(200, content=b"private")
    store = SupabaseStore("https://example.supabase.co", "sb_secret_test", httpx.MockTransport(handle))
    assert store.get("id", "user-a", "dataset")["blob"] == b"private"
    assert calls[1].url.path == "/storage/v1/object/authenticated/datasets/user-a/id/object"
    assert "authorization" not in calls[0].headers


def test_supabase_refuses_metadata_pointing_to_another_owner():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=[{"metadata": {}, "storage_bucket": "datasets", "storage_path": "user-b/secret"}]))
    with pytest.raises(PersistenceError):
        SupabaseStore("https://example.supabase.co", "sb_secret_test", transport).get("id", "user-a", "dataset")

"""A resumed workflow must not mix datasets or private jobs from other runs."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import main
from job_queue import SQLiteQueue
from persistence import SQLiteStore


@pytest.fixture
def runtime(tmp_path):
    store, queue = SQLiteStore(tmp_path / "state.db"), SQLiteQueue(tmp_path / "state.db")
    with patch.object(main, "resource_store", store), patch.object(main, "job_queue", queue), patch.object(main, "validate_access_token", AsyncMock(side_effect=lambda token: {"id": token})), TestClient(main.app) as client:
        headers = {"Authorization": "Bearer a"}
        def upload(owner="a"):
            return client.post("/upload-dataset", headers={"Authorization": f"Bearer {owner}"}, files={"file": ("data.csv", "x,target\n1,0\n2,1", "text/csv")}).json()["dataset_id"]
        original = upload()
        child = main.create_derived_dataset(original, "a", main.DATASETS[original].copy(), [{"type": "normalize"}])
        run_id = str(uuid.uuid4())
        state = {"workflowId": run_id, "originalDatasetId": original, "currentDatasetId": child, "targetColumn": "target"}
        yield client, store, queue, headers, run_id, state, upload


def test_valid_derived_lineage_and_queued_job_roundtrip(runtime):
    client, store, queue, headers, run_id, state, _ = runtime
    job = queue.enqueue("a", "valid", {"dataset_id": state["currentDatasetId"], "workflow_id": run_id, "target_column": "target"})
    state["trainingJobId"] = job["id"]
    assert client.put(f"/runs/{run_id}", headers=headers, json={"state": state}).status_code == 200
    assert client.get(f"/runs/{run_id}", headers=headers).json() == state
    assert client.get(f"/runs/{run_id}", headers={"Authorization": "Bearer b"}).status_code == 404


def test_unrelated_owned_datasets_cannot_be_mixed_or_restored(runtime):
    client, store, _, headers, run_id, state, upload = runtime
    valid = dict(state)
    assert client.put(f"/runs/{run_id}", headers=headers, json={"state": valid}).status_code == 200
    state["currentDatasetId"] = upload()
    assert client.put(f"/runs/{run_id}", headers=headers, json={"state": state}).status_code == 409
    assert store.get(run_id, "a", "run")["metadata"] == valid
    # Also reject inconsistent snapshots written by older versions of the API.
    store.save(run_id, "a", "run", state)
    assert client.get(f"/runs/{run_id}", headers=headers).status_code == 409


@pytest.mark.parametrize("difference", ["dataset", "workflow", "target", "owner", "missing"])
def test_job_reference_must_match_owned_run(runtime, difference):
    client, store, queue, headers, run_id, state, upload = runtime
    payload = {"dataset_id": state["currentDatasetId"], "workflow_id": run_id, "target_column": "target"}
    if difference == "dataset":
        payload["dataset_id"] = upload()
    if difference == "workflow":
        payload["workflow_id"] = str(uuid.uuid4())
    if difference == "target":
        payload["target_column"] = "x"
    job = queue.enqueue("b" if difference == "owner" else "a", "job", payload)
    state["trainingJobId"] = str(uuid.uuid4()) if difference == "missing" else job["id"]
    expected = 404 if difference in {"owner", "missing"} else 409
    assert client.put(f"/runs/{run_id}", headers=headers, json={"state": state}).status_code == expected
    assert store.get(run_id, "a", "run") is None
    store.save(run_id, "a", "run", state)
    assert client.get(f"/runs/{run_id}", headers=headers).status_code == expected


@pytest.mark.parametrize("key,value", [("originalDatasetId", []), ("currentDatasetId", {}), ("trainingJobId", 123), ("workflowId", None)])
def test_malformed_references_produce_actionable_error(runtime, key, value):
    client, store, _, headers, run_id, state, _ = runtime
    state[key] = value
    assert client.put(f"/runs/{run_id}", headers=headers, json={"state": state}).status_code == 400
    store.save(run_id, "a", "run", state)
    assert client.get(f"/runs/{run_id}", headers=headers).status_code == 409

import json
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import main
from job_queue import QueueError, SQLiteQueue
from persistence import SQLiteStore
from worker import process_job


def test_idempotency_quotas_and_owner_access():
    with tempfile.TemporaryDirectory() as directory:
        queue = SQLiteQueue(Path(directory) / "jobs.db")
        first = queue.enqueue("a", "key", {"x": 1})
        assert queue.enqueue("a", "key", {"x": 1})["id"] == first["id"]
        with pytest.raises(QueueError) as exc:
            queue.enqueue("a", "key", {"x": 2})
        assert exc.value.status == 409
        assert queue.get(first["id"], "b") is None
        assert queue.cancel(first["id"], "b") is None
        queue.enqueue("a", "second", {"x": 2})
        with pytest.raises(QueueError):
            queue.enqueue("a", "third", {"x": 3})
        assert queue.cancel(first["id"], "a")["status"] == "cancelled"
        queue.enqueue("a", "third", {"x": 3})


def test_atomic_claim_and_expired_worker_lease():
    with tempfile.TemporaryDirectory() as directory:
        queue = SQLiteQueue(Path(directory) / "jobs.db")
        job = queue.enqueue("a", "key", {})
        with ThreadPoolExecutor(2) as executor:
            claims = list(executor.map(lambda _: queue.claim(), range(2)))
        assert sum(item is not None for item in claims) == 1
        with queue.db.connect() as db:
            db.execute("UPDATE training_jobs SET lease_until=? WHERE id=?", (time.time() - 1, job["id"]))
        assert queue.claim() is None
        assert queue.get(job["id"], "a")["status"] == "failed"


def test_worker_timeout_terminates_process_and_cancellation_cannot_be_overwritten():
    class FakeProcess:
        returncode = None
        terminated = False
        def poll(self): return self.returncode
        def terminate(self): self.terminated = True; self.returncode = -1
        def wait(self, timeout=None): return self.returncode
    with tempfile.TemporaryDirectory() as directory:
        queue = SQLiteQueue(Path(directory) / "jobs.db")
        job = queue.enqueue("a", "key", {})
        claimed = queue.claim()
        process = FakeProcess()
        process_job(queue, claimed, timeout=-1, runner=lambda *args, **kwargs: process)
        assert process.terminated
        assert queue.get(job["id"], "a")["status"] == "failed"
        another = queue.enqueue("a", "second", {})
        queue.claim()
        queue.cancel(another["id"], "a")
        queue.finish(another["id"], "a", "completed", result={"fake": True})
        assert queue.get(another["id"], "a")["status"] == "cancelled"


def test_api_enqueues_once_and_denies_other_users():
    with tempfile.TemporaryDirectory() as directory, patch.object(main, "resource_store", SQLiteStore(Path(directory) / "jobs.db")), patch.object(main, "job_queue", SQLiteQueue(Path(directory) / "jobs.db")), patch.object(main, "validate_access_token", AsyncMock(side_effect=lambda token: {"id": token})), TestClient(main.app) as client:
        a = {"Authorization": "Bearer a", "Idempotency-Key": "stable-request"}
        b = {"Authorization": "Bearer b"}
        dataset = client.post("/upload-dataset", headers=a, files={"file": ("data.csv", "x,target\n1,0\n2,1", "text/csv")}).json()["dataset_id"]
        payload = {"dataset_id": dataset, "target_column": "target", "candidate_models": ["logistic_regression"]}
        with patch.object(main.model_training, "train_and_evaluate") as train:
            first = client.post("/agents/model-training", headers=a, json=payload)
            assert first.status_code == 202
            assert client.post("/agents/model-training", headers=a, json=payload).json() == first.json()
            train.assert_not_called()
        job = first.json()["job_id"]
        assert client.get(f"/training-jobs/{job}", headers=b).status_code == 404
        assert client.post(f"/training-jobs/{job}/cancel", headers=b).status_code == 404
        assert client.post("/training-jobs", headers=b, json=payload).status_code == 404
        assert client.get(f"/training-jobs/{job}", headers=a).json()["status"] == "queued"
        assert client.post(f"/training-jobs/{job}/cancel", headers=a).json()["status"] == "cancelled"


def test_real_worker_process_trains_and_publishes_a_private_model():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "state.db"
        store, queue = SQLiteStore(path), SQLiteQueue(path)
        with patch.dict("os.environ", {"DAISY_PERSISTENCE": "sqlite", "DAISY_STATE_DB": str(path), "DAISY_MODEL_DIR": str(Path(directory) / "models")}), patch.object(main, "resource_store", store), patch.object(main, "job_queue", queue), patch.object(main, "validate_access_token", AsyncMock(return_value={"id": "a"})), TestClient(main.app) as client:
            headers = {"Authorization": "Bearer a"}
            csv = "x,target\n" + "\n".join(f"{i},{i % 2}" for i in range(60))
            dataset = client.post("/upload-dataset", headers=headers, files={"file": ("data.csv", csv, "text/csv")}).json()["dataset_id"]
            response = client.post("/training-jobs", headers=headers, json={"dataset_id": dataset, "target_column": "target", "candidate_models": ["logistic_regression"]})
            assert response.status_code == 202
            job = queue.claim()
            process_job(queue, job, timeout=90)
            completed = client.get(f"/training-jobs/{job['id']}", headers=headers).json()
            assert completed["status"] == "completed", completed
            artifact = completed["result"]["output_summary"]["model_artifact"]["artifact_id"]
            assert client.get(f"/models/{artifact}/download", headers=headers).status_code == 200

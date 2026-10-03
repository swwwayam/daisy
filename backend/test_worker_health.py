import time
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from job_queue import SQLiteQueue
from persistence import SQLiteStore, PersistenceError


def test_heartbeat_expires_and_readiness_checks_specific_worker(tmp_path):
    queue = SQLiteQueue(tmp_path / "state.db")
    assert not queue.worker_ready()
    queue.heartbeat("worker-a", "running")
    assert queue.worker_ready() and queue.worker_ready("worker-a")
    assert not queue.worker_ready("worker-b")
    with queue.db.connect() as db:
        db.execute("UPDATE worker_heartbeats SET seen_at=?", (time.time() - 91,))
    assert not queue.worker_ready()
    queue.heartbeat("worker-a", "idle")
    assert queue.worker_ready()
    queue.heartbeat("worker-a", "stopped")
    assert not queue.worker_ready()


def test_health_probe_reports_worker_loss_without_disclosing_jobs(tmp_path):
    path = tmp_path / "state.db"
    queue, store = SQLiteQueue(path), SQLiteStore(path)
    with patch.object(main, "job_queue", queue), patch.object(main, "resource_store", store), TestClient(main.app) as client:
        assert client.get("/health/worker").status_code == 503
        queue.heartbeat("worker-secret-host", "idle")
        response = client.get("/health/worker")
        assert response.status_code == 200
        assert "worker-secret-host" not in response.text
        assert response.headers["cache-control"] == "no-store"
        assert main.readiness_checks()["training_worker"]
        with patch.object(store, "probe", side_effect=PersistenceError("private message")):
            assert main.readiness_checks()["durable_storage"] is False
            assert client.get("/health/ready").status_code == 503

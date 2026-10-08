import time
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

import main
from account_usage import snapshot
from ai_privacy import MemoryBudget, SQLiteBudget
from job_queue import SQLiteQueue
from prediction_usage import PredictionUsage
from persistence import MemoryStore, SQLiteStore, SupabaseStore


def test_usage_is_private_read_only_and_recovers_after_restart(tmp_path):
    path = tmp_path / "state.db"
    store = SQLiteStore(path)
    ai, predictions, queue = SQLiteBudget(path), PredictionUsage(), SQLiteQueue(path)
    reservation = ai.reserve("a", 3000)
    ai.settle(reservation, "a", 1000)
    ai.reserve("b", 4000)
    predictions.reserve(store, "a", 280)
    queue.enqueue("a", "one", {"dataset_id": "a"})
    with store.connect() as db:
        db.execute("INSERT INTO prediction_usage VALUES(?,?,?)", ("a", time.time() - 86401, 10000))
        db.execute("INSERT INTO ai_usage VALUES(?,?,?,?)", ("expired", "a", time.time() - 86401, 100000))
    with patch.object(main, "resource_store", store), patch.object(main, "ai_budget", ai), patch.object(main, "prediction_usage", predictions), patch.object(main, "job_queue", queue), patch.object(main, "validate_access_token", AsyncMock(side_effect=lambda token: {"id": token})), TestClient(main.app) as client:
        result = client.get("/account/usage", headers={"Authorization": "Bearer a"}).json()
        assert result["ai"]["requests"] == 1 and result["ai"]["tokens"] == 1000
        assert result["inference"]["requests"] == 1 and result["inference"]["scored_rows"] == 280
        assert result["training"]["requests"] == result["training"]["active_jobs"] == 1
        assert result["ai"]["next_expiry"] and result["durable"]
        assert client.get("/account/usage", headers={"Authorization": "Bearer a"}).json() == result
        b = client.get("/account/usage", headers={"Authorization": "Bearer b"}).json()
        assert b["ai"]["tokens"] == 4000 and b["inference"]["scored_rows"] == 0 and b["training"]["requests"] == 0
        assert client.get("/account/usage").status_code == 401
    assert snapshot(SQLiteStore(path), "a", ai, PredictionUsage(), SQLiteQueue(path)) == result


def test_new_local_store_and_demo_report_empty_budgets(tmp_path):
    ai, predictions = MemoryBudget(), PredictionUsage()
    result = snapshot(SQLiteStore(tmp_path / "new.db"), "a", ai, predictions, None)
    assert result["inference"]["requests"] == result["ai"]["requests"] == 0
    ai.reserve("a", 10)
    predictions.reserve(MemoryStore(), "a", 2)
    result = snapshot(MemoryStore(), "a", ai, predictions, None)
    assert not result["durable"] and not result["training_metered"]
    assert result["ai"]["tokens"] == 10 and result["inference"]["scored_rows"] == 2


def test_cloud_usage_calls_owner_aggregate_rpc_only():
    def handler(request):
        assert request.url.path == "/rest/v1/rpc/daisy_account_usage"
        assert request.content == b'{"p_owner":"a"}'
        return httpx.Response(200, json={"ai": {"requests": 0}, "inference": {"requests": 0}, "training": {"requests": 0}})
    store = SupabaseStore("https://test.supabase.co", "sb_secret_test", httpx.MockTransport(handler))
    assert snapshot(store, "a", None, None, object())["durable"]


def test_account_export_is_owner_scoped_metadata_with_clear_exclusions(tmp_path):
    store = SQLiteStore(tmp_path / "state.db")
    store.save("run-a", "a", "run", {"chat": [{"text": "my private note"}]})
    store.save("dataset-a", "a", "dataset", {"filename": "mine.csv"}, b"private csv bytes")
    store.save("run-b", "b", "run", {"chat": [{"text": "another user's note"}]})
    with patch.object(main, "resource_store", store):
        export = main.account_export_document("a")
    assert export["format_version"] == 1 and export["scope"] == "account_metadata"
    assert export["resource_counts"] == {"dataset": 1, "run": 1}
    assert {row["id"] for row in export["resources"]} == {"run-a", "dataset-a"}
    assert "another user's note" not in str(export)
    assert "private csv bytes" not in str(export)
    assert any("CSV" in item for item in export["excluded"])

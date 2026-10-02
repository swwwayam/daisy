"""Compact history must paginate all owned runs without disclosing snapshots."""
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

import main
from persistence import SQLiteStore, SupabaseStore, run_summary


def test_paginated_history_is_compact_private_and_complete(tmp_path):
    store = SQLiteStore(tmp_path / "state.db")
    state = {"upload": {"filename": "homes.csv", "rows": 40, "columns": 3, "preview": [{"secret": "private"}]},
             "status": {"dataset": "done", "training": "error"}, "targetColumn": "price",
             "bestModel": "RandomForest", "chat": [{"text": "private chat"}], "eda": {"report": "private report"}}
    for index in range(45):
        store.save(f"run-{index:03}", "a", "run", state)
    store.save("other-run", "b", "run", state)
    store.save("dataset", "a", "dataset", state, b"private bytes")
    with store.connect() as db:
        db.execute("UPDATE resources SET updated_at='2026-10-03 00:00:00'")
    with patch.object(main, "resource_store", store), patch.object(main, "validate_access_token", AsyncMock(side_effect=lambda token: {"id": token})), TestClient(main.app) as client:
        ids, offset = [], 0
        while offset is not None:
            response = client.get(f"/runs?limit=20&offset={offset}", headers={"Authorization": "Bearer a"})
            assert response.status_code == 200
            body = response.json()
            assert body["durable"] is True
            assert len(body["runs"]) <= 20
            assert "private" not in response.text
            ids.extend(row["id"] for row in body["runs"])
            offset = body["next_offset"]
        assert len(ids) == len(set(ids)) == 45
        assert ids == sorted(ids, reverse=True)  # stable ID tiebreaker when saved in the same second
        assert store.get(ids[0], "a", "run")["metadata"] == state
        assert client.get("/runs", headers={"Authorization": "Bearer b"}).json()["runs"][0]["id"] == "other-run"
        assert client.get("/runs", headers={"Authorization": "Bearer c"}).json()["runs"] == []
        assert client.get("/runs").status_code == 401


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "offset=-1", "offset=100001", "limit=abc"])
def test_history_rejects_unbounded_queries(query):
    with patch.object(main, "validate_access_token", AsyncMock(return_value={"id": "a"})), TestClient(main.app) as client:
        assert client.get(f"/runs?{query}", headers={"Authorization": "Bearer a"}).status_code == 422


def test_cloud_history_projects_fields_and_paginates_before_transmission():
    calls = []
    def handle(request):
        calls.append(request)
        params = request.url.params
        assert params["owner_id"] == "eq.owner"
        assert params["kind"] == "eq.run"
        assert params["limit"] == "21" and params["offset"] == "40"
        assert params["order"] == "updated_at.desc,id.desc"
        assert "filename:metadata->upload->>filename" in params["select"]
        assert "metadata" not in params["select"].split(",")
        return httpx.Response(200, json=[{"id": "run", "updated_at": "2026-10-03T00:00:00Z", "filename": "homes.csv", "rows": 10, "columns": 2, "target": "price", "model": None, "status": {"dataset": "done"}}])
    rows = SupabaseStore("https://example.supabase.co", "sb_secret_test", httpx.MockTransport(handle)).list_runs("owner", 21, 40)
    assert rows[0]["metadata"]["upload"]["filename"] == "homes.csv"
    assert len(calls) == 1  # no Storage request for a history listing


def test_summary_bounds_untrusted_fields():
    row = {"id": "run", "updated_at": "now", "filename": "x" * 10000, "rows": -2,
           "columns": True, "target": {"secret": "value"}, "status": {"dataset": "done", "training": [], "chat": "private"}}
    summary = run_summary(row)["metadata"]
    assert len(summary["upload"]["filename"]) == 512
    assert summary["upload"]["rows"] is None and summary["upload"]["columns"] is None
    assert summary["targetColumn"] is None
    assert summary["status"] == {"dataset": "done"}
    assert run_summary({**row, "status": "not a status object"})["metadata"]["status"] == {}

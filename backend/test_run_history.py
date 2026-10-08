"""Compact history must paginate all owned runs without disclosing snapshots."""
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException, Request
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


def test_delete_run_is_private_and_preserves_pipeline_resources(tmp_path):
    store = SQLiteStore(tmp_path / "state.db")
    run_id = str(uuid.uuid4())
    store.save(run_id, "owner-a", "run", {"workflowId": run_id})
    store.save("dataset-a", "owner-a", "dataset", {"steps": []}, b"private dataset")
    def request_for(owner):
        request = Request({"type": "http", "method": "DELETE", "path": f"/runs/{run_id}", "headers": []})
        request.state.user = {"id": owner}
        return request
    with patch.object(main, "resource_store", store):
        with pytest.raises(HTTPException) as foreign:
            main.delete_saved_run(run_id, request_for("owner-b"))
        assert foreign.value.status_code == 404
        assert store.get(run_id, "owner-a", "run") is not None
        assert main.delete_saved_run(run_id, request_for("owner-a")) == {"deleted": True, "run_id": run_id}
        assert store.get(run_id, "owner-a", "run") is None
        assert store.get("dataset-a", "owner-a", "dataset")["blob"] == b"private dataset"
        with pytest.raises(HTTPException) as missing:
            main.delete_saved_run(run_id, request_for("owner-a"))
        assert missing.value.status_code == 404
        with pytest.raises(HTTPException) as invalid:
            main.delete_saved_run("not-a-uuid", request_for("owner-a"))
        assert invalid.value.status_code == 400


def test_clear_run_history_preserves_other_resources_and_owners(tmp_path):
    store = SQLiteStore(tmp_path / "state.db")
    store.save("run-a-1", "owner-a", "run", {})
    store.save("run-a-2", "owner-a", "run", {})
    store.save("dataset-a", "owner-a", "dataset", {}, b"dataset")
    store.save("run-b", "owner-b", "run", {})
    request = Request({"type": "http", "method": "DELETE", "path": "/runs", "headers": []})
    request.state.user = {"id": "owner-a"}
    with patch.object(main, "resource_store", store):
        assert main.clear_saved_runs(request) == {"deleted": 2}
    assert store.list_runs("owner-a", 20, 0) == []
    assert store.get("dataset-a", "owner-a", "dataset")["blob"] == b"dataset"
    assert store.get("run-b", "owner-b", "run") is not None

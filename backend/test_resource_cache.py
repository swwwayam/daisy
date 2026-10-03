from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import main
from persistence import SQLiteStore
from resource_cache import ResourceCache, CacheCapacityError


def test_capacity_lru_and_active_leases_do_not_discard_active_work():
    evicted = []
    cache = ResourceCache(5, 3, size=len, can_evict=lambda: True, on_evict=evicted.append)
    cache["a"], cache["b"] = b"aa", b"bb"
    with cache.lease():
        assert cache["b"] == b"bb"
        cache["c"] = b"cc"
        assert evicted == ["a"]
        with cache.lease():
            assert cache["c"] == b"cc"
            with pytest.raises(CacheCapacityError):
                cache["d"] = b"dd"
        assert set(cache) == {"b", "c"}
    cache["d"] = b"dd"
    assert cache.used_bytes == 4 and len(cache) == 2


def test_demo_preserves_data_and_rejects_capacity_overflow():
    cache = ResourceCache(3, 1, size=len, can_evict=lambda: False)
    cache["a"] = b"aa"
    with pytest.raises(CacheCapacityError):
        cache["b"] = b"bb"
    assert cache.copy() == {"a": b"aa"}
    cache.clear()
    assert cache.used_bytes == 0
    cache.update({"b": b"bb"})
    assert cache.pop("b") == b"bb" and cache.used_bytes == 0


def test_evicted_private_data_reloads_from_disk_and_is_not_reassigned(tmp_path):
    store = SQLiteStore(tmp_path / "state.db")
    cache = ResourceCache(10000, 2, size=lambda frame: frame.memory_usage(deep=True).sum(),
                          can_evict=lambda: True, on_evict=main.evict_dataset_cache)
    with patch.object(main, "resource_store", store), patch.object(main, "DATASETS", cache), patch.object(main, "validate_access_token", AsyncMock(side_effect=lambda token: {"id": token})), TestClient(main.app) as client:
        headers = {"Authorization": "Bearer cache-owner"}
        ids = [client.post("/upload-dataset", headers=headers, files={"file": ("source.csv", f"x,target\n{i},0\n{i+1},1", "text/csv")}).json()["dataset_id"] for i in range(5)]
        assert len(cache) == 2 and ids[0] not in cache
        assert main.DATASET_OWNERS.owner(ids[0]) is None
        assert client.get(f"/dataset/{ids[0]}/summary", headers={"Authorization": "Bearer stranger"}).status_code == 404
        recovered = client.get(f"/dataset/{ids[0]}/summary", headers=headers)
        assert recovered.status_code == 200 and recovered.json()["preview"][0]["x"] == 0
        assert len(cache) == 2
        assert main.DATASET_OWNERS.owner(ids[0]) == "cache-owner"

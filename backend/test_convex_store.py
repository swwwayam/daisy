"""Latency regressions: small metadata costs one RPC and no file transfer."""
import json
import httpx
import gzip
import pytest
from convex_store import ConvexStore


def test_small_metadata_save_update_and_read_do_not_transfer_files():
    requests = []

    def handle(request):
        requests.append(request)
        payload = json.loads(request.content)
        if payload["op"] == "get":
            return httpx.Response(200, json={"metadataJson": '{"enabled":false}', "blobUrl": None})
        return httpx.Response(200, content=b"null", headers={"Content-Type": "application/json"})

    store = ConvexStore("https://test.convex.site", "private", httpx.MockTransport(handle))
    store.save("settings", "a", "preferences", {"enabled": False})
    store.update_metadata("dataset", "a", "dataset", {"context": {"eda": "done"}})
    assert store.metadata("settings", "a", "preferences") == {"enabled": False}
    assert len(requests) == 3
    payloads = [json.loads(request.content) for request in requests]
    assert [p["op"] for p in payloads] == ["save", "updateMetadata", "get"]
    assert all("storageId" not in p and "metadataStorageId" not in p for p in payloads)
    store.client.close()


@pytest.mark.parametrize("kind,metadata,compressed", [("dataset", {}, True), ("dataset", {"source_csv": True}, False), ("artifact", {}, False)])
def test_snapshot_compression_is_lossless_and_leaves_csv_and_models_unchanged(kind, metadata, compressed):
    state = {}
    raw = b'{"values":[0,1,2],"literal":"NA"}' * 1000

    def handle(request):
        if request.url.path == "/upload":
            state["bytes"] = request.content
            state["uploads"] = state.get("uploads", 0) + 1
            return httpx.Response(200, json={"storageId": "file-id"})
        if request.url.path == "/file":
            return httpx.Response(200, content=state["bytes"])
        args = json.loads(request.content)
        if args["op"] == "upload":
            return httpx.Response(200, json="https://files.example/upload")
        if args["op"] == "save":
            state.update(args)
        if args["op"] == "updateMetadata":
            state["metadataJson"] = args["metadataJson"]
        if args["op"] == "get":
            return httpx.Response(200, json={"metadataJson": state["metadataJson"], "blobUrl": "https://files.example/file", "blobEncoding": state.get("blobEncoding")})
        return httpx.Response(200, content=b"null")

    store = ConvexStore("https://test.convex.site", "private", httpx.MockTransport(handle))
    store.save("id", "a", kind, metadata, raw)
    assert (state.get("blobEncoding") == "gzip") is compressed
    assert state["bytes"] == raw if not compressed else gzip.decompress(state["bytes"]) == raw
    store.update_metadata("id", "a", kind, {"stage": "complete"})
    assert store.get("id", "a", kind) == {"metadata": {"stage": "complete"}, "blob": raw}
    assert state["uploads"] == 1
    store.client.close()


def test_large_compressible_dataset_is_checked_after_compression():
    """A derived snapshot may exceed 50 MB before gzip but fit after it."""
    state = {}
    raw = b'{"values":[0,1,2],"literal":"NA"}\n' * 2_000_000
    assert len(raw) > 50 * 1024 * 1024

    def handle(request):
        if request.url.path == "/upload":
            state["bytes"] = request.content
            return httpx.Response(200, json={"storageId": "file-id"})
        args = json.loads(request.content)
        if args["op"] == "upload":
            return httpx.Response(200, json="https://files.example/upload")
        if args["op"] == "save":
            state.update(args)
        return httpx.Response(200, content=b"null")

    store = ConvexStore("https://test.convex.site", "private", httpx.MockTransport(handle))
    store.save("large", "a", "dataset", {}, raw)
    assert state["blobEncoding"] == "gzip"
    assert len(state["bytes"]) < 50 * 1024 * 1024
    assert gzip.decompress(state["bytes"]) == raw
    store.client.close()

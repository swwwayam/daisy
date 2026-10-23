"""Durable Convex resources and private file storage for the Python ML service."""
import json
import atexit
import gzip

import httpx

from persistence import PersistenceError, json_safe, run_summary


class ConvexRequestError(PersistenceError):
    def __init__(self, message, rejected=False):
        super().__init__(message)
        self.rejected = rejected


class ConvexStore:
    enabled = True
    parallel_uploads = True

    def __init__(self, url, secret, transport=None):
        if not url or not secret:
            raise PersistenceError("Convex persistence requires CONVEX_SITE_URL and DAISY_BACKEND_SECRET")
        self.url, self.secret, self.transport = url.rstrip("/"), secret, transport
        # httpx clients are thread-safe. Keep TLS connections alive across RPCs,
        # file transfers, requests and worker polls instead of reconnecting each time.
        self.client = httpx.Client(timeout=httpx.Timeout(120, connect=10), transport=transport,
                                   limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=60))
        atexit.register(self.client.close)

    def rpc(self, op, **args):
        try:
            response = self.client.post(self.url + "/api/daisy/backend", headers={"Authorization": "Bearer " + self.secret}, json={"op": op, **args}, timeout=30)
            if response.status_code >= 400:
                raise ConvexRequestError("Convex rejected the storage operation. Check the backend bridge configuration.", rejected=True)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ConvexRequestError("Convex storage unavailable. Check the deployment and backend bridge configuration.") from exc

    def probe(self):
        return self.rpc("probe")

    def upload(self, content, content_type="application/octet-stream"):
        if len(content) > 50 * 1024 * 1024:
            raise PersistenceError("Persisted object exceeds the 50 MB storage limit")
        url = self.rpc("upload")
        try:
            response = self.client.post(url, content=content, headers={"Content-Type": content_type})
            response.raise_for_status()
            return response.json()["storageId"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise PersistenceError("Convex file upload failed") from exc

    def download(self, url):
        try:
            response = self.client.get(url)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            raise PersistenceError("Convex file download failed") from exc

    @staticmethod
    def summary(kind, metadata):
        if kind == "run":
            upload = metadata.get("upload") or {}
            return {"upload": {key: upload.get(key) for key in ("filename", "rows", "columns")}, **{key: metadata.get(key) for key in ("targetColumn", "bestModel", "status")}}
        if kind == "experiment":
            training = metadata.get("training_result") or {}
            return {"created_at": metadata.get("created_at"), "dataset_id": metadata.get("dataset_id"), "target_column": metadata.get("target_column"), "training_result": {"best_model": training.get("best_model"), "primary_metric": training.get("primary_metric")}}
        return {}

    def save(self, identifier, owner, kind, metadata, blob=None):
        return self._save("save", identifier, owner, kind, metadata, blob)

    def update_metadata(self, identifier, owner, kind, metadata):
        """Update stage reports/settings without transferring unchanged dataset bytes."""
        return self._save("updateMetadata", identifier, owner, kind, metadata)

    def _save(self, operation, identifier, owner, kind, metadata, blob=None):
        files = []
        committing = False
        try:
            encoded = json.dumps(json_safe(metadata), allow_nan=False).encode()
            args = {"id": identifier, "owner": owner, "kind": kind, "summary": self.summary(kind, metadata)}
            if len(encoded) <= 32768:
                args["metadataJson"] = encoded.decode()
            else:
                args["metadataStorageId"] = self.upload(encoded, "application/json")
                files.append(args["metadataStorageId"])
            if blob is not None:
                if kind == "dataset" and not metadata.get("source_csv"):
                    blob = gzip.compress(blob, compresslevel=1)
                    args["blobEncoding"] = "gzip"
                # Check the bytes that will actually be uploaded. Derived
                # dataset snapshots are compressed above and can be much
                # smaller than their in-memory JSON representation.
                if len(blob) > 50 * 1024 * 1024:
                    raise PersistenceError("Persisted object exceeds the 50 MB storage limit")
                args["storageId"] = self.upload(blob, "application/zip" if kind == "artifact" else "application/octet-stream")
                files.append(args["storageId"])
            committing = True
            self.rpc(operation, **args)
        except Exception as exc:
            # A timeout can occur after the mutation commits. Do not delete files
            # that a successfully published resource may now reference.
            if committing and isinstance(exc, ConvexRequestError) and not exc.rejected:
                raise
            for storage_id in files:
                try:
                    self.rpc("discard", storageId=storage_id)
                except PersistenceError:
                    pass
            raise

    def insert_experiment(self, identifier, owner, metadata):
        self.save(identifier, owner, "experiment", metadata)

    def get(self, identifier, owner, kind):
        row = self.rpc("get", id=identifier, owner=owner, kind=kind)
        if not row:
            return None
        metadata = self._metadata(row)
        blob = self.download(row["blobUrl"]) if row.get("blobUrl") else None
        if blob is not None and row.get("blobEncoding") == "gzip":
            blob = gzip.decompress(blob)
        return {"metadata": metadata, "blob": blob}

    def metadata(self, identifier, owner, kind):
        row = self.rpc("get", id=identifier, owner=owner, kind=kind)
        if not row:
            return None
        return self._metadata(row)

    def _metadata(self, row):
        if row.get("metadataJson") is not None:
            return json.loads(row["metadataJson"])
        return json.loads(self.download(row["metadataUrl"])) if row.get("metadataUrl") else row["metadata"]

    def pages(self, owner, kind=None):
        cursor = None
        while True:
            args = {"owner": owner, "cursor": cursor, "limit": 50}
            if kind:
                args["kind"] = kind
            result = self.rpc("page", **args)
            yield from result["page"]
            if result["done"]:
                break
            cursor = result["cursor"]

    def page_slice(self, owner, kind, limit, offset):
        from itertools import islice
        return list(islice(self.pages(owner, kind), offset, offset + limit))

    def list(self, owner, kind):
        rows = self.page_slice(owner, kind, 30, 0)
        return [{"id": r["id"], "updated_at": r["updated_at"], "metadata": self.metadata(r["id"], owner, kind)} for r in rows]

    def list_runs(self, owner, limit, offset):
        result = []
        for row in self.page_slice(owner, "run", limit, offset):
            m = row["metadata"]
            upload = m.get("upload") or {}
            result.append(run_summary({"id": row["id"], "updated_at": row["updated_at"], "filename": upload.get("filename"), "rows": upload.get("rows"), "columns": upload.get("columns"), "target": m.get("targetColumn"), "model": m.get("bestModel"), "status": m.get("status")}))
        return result

    def list_experiments(self, owner, limit, offset):
        return [{"id": r["id"], "updated_at": r["updated_at"], "metadata": r["metadata"]} for r in self.page_slice(owner, "experiment", limit, offset)]

    def count(self, owner, kind):
        return self.rpc("count", owner=owner, kind=kind)

    def delete(self, identifier, owner, kind):
        return self.rpc("remove", id=identifier, owner=owner, kind=kind)

    def export_metadata(self, owner):
        return [{"id": r["id"], "kind": r["kind"], "updated_at": r["updated_at"], "metadata": self.metadata(r["id"], owner, r["kind"])} for r in self.pages(owner)]

    def delete_runs(self, owner):
        identifiers = [row["id"] for row in self.pages(owner, "run")]
        return sum(self.delete(identifier, owner, "run") for identifier in identifiers)

    def prune_runs(self, owner, before):
        from datetime import datetime
        cutoff = datetime.fromisoformat(before.replace("Z", "+00:00"))
        identifiers = [r["id"] for r in self.pages(owner, "run") if datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")) < cutoff]
        return sum(self.delete(identifier, owner, "run") for identifier in identifiers)

    def finalization(self, source, owner):
        return self._finalization("finalization", source, owner)

    def claim_finalization(self, source, owner, experiment):
        return self._finalization("claimFinalization", source, owner, experiment=experiment)

    def finish_finalization(self, source, owner, experiment, report):
        storage_id = self.upload(json.dumps(report, allow_nan=False).encode(), "application/json")
        return self._finalization("finishFinalization", source, owner, experiment=experiment, reportStorageId=storage_id)["report"]

    def _finalization(self, op, source, owner, **args):
        row = self.rpc(op, source=source, owner=owner, **args)
        if row and isinstance(row.get("report"), str):
            row["report"] = json.loads(row["report"])
        if row and row.get("reportUrl"):
            row["report"] = json.loads(self.download(row.pop("reportUrl")))
        return row


class ConvexQueue:
    def __init__(self, store): self.store = store
    def heartbeat(self, worker_id, status): self.store.rpc("heartbeat", worker=worker_id, status=status)
    def worker_ready(self, worker_id=None):
        return self.store.rpc("workerReady", **({"worker": worker_id} if worker_id else {}))
    def enqueue(self, owner, key, payload):
        from job_queue import QueueError, signature
        reply = self.store.rpc("enqueue", owner=owner, key=key, payload=payload, signature=signature(payload))
        if reply.get("error"): raise QueueError(reply["error"], reply.get("status", 429))
        return reply
    def get(self, identifier, owner):
        row = self.store.rpc("job", id=identifier, owner=owner)
        if row and row.get("resultUrl"):
            row["result"] = json.loads(self.store.download(row.pop("resultUrl")))
        return row
    def claim(self): return self.store.rpc("claimJob")
    def finish(self, identifier, owner, status, result=None, error=None):
        args = {"id": identifier, "owner": owner, "status": status, "error": error}
        if result is not None:
            args["resultStorageId"] = self.store.upload(json.dumps(json_safe(result), allow_nan=False).encode(), "application/json")
        self.store.rpc("finishJob", **args)
    def cancel(self, identifier, owner): return self.store.rpc("cancelJob", id=identifier, owner=owner)


class ConvexBudget:
    def __init__(self, store): self.store = store
    def reserve(self, owner, tokens):
        from fastapi import HTTPException
        result = self.store.rpc("reserveAi", owner=owner, amount=tokens)
        if result.get("error"): raise HTTPException(status_code=429, detail=result["error"], headers={"Retry-After": "60"})
        return result["id"]
    def settle(self, identifier, owner, tokens): self.store.rpc("settleAi", id=identifier, owner=owner, amount=tokens)

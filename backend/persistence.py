"""Owner-filtered durable resources; JSON metadata and private binary objects."""
import json
import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

import httpx


class PersistenceError(RuntimeError):
    pass


class MemoryStore:
    enabled = False

    def save(self, identifier, owner, kind, metadata, blob=None):
        pass

    def get(self, identifier, owner, kind):
        return None

    def list(self, owner, kind):
        return []


class SQLiteStore:
    """Development persistence with the same owner boundary as the cloud store."""
    enabled = True

    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS resources (id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL, metadata TEXT NOT NULL, blob BLOB, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, identifier, owner, kind, metadata, blob=None):
        with self.connect() as db:
            existing = db.execute("SELECT owner,kind FROM resources WHERE id=?", (identifier,)).fetchone()
            if existing and (existing["owner"] != owner or existing["kind"] != kind):
                raise PersistenceError("Resource identity cannot be reassigned")
            db.execute("INSERT INTO resources(id,owner,kind,metadata,blob) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET metadata=excluded.metadata,blob=excluded.blob,updated_at=CURRENT_TIMESTAMP", (identifier, owner, kind, json.dumps(metadata, allow_nan=False), blob))

    def get(self, identifier, owner, kind):
        with self.connect() as db:
            row = db.execute("SELECT metadata,blob FROM resources WHERE id=? AND owner=? AND kind=?", (identifier, owner, kind)).fetchone()
        return {"metadata": json.loads(row["metadata"]), "blob": row["blob"]} if row else None

    def list(self, owner, kind):
        with self.connect() as db:
            rows = db.execute("SELECT id,metadata,updated_at FROM resources WHERE owner=? AND kind=? ORDER BY updated_at DESC LIMIT 30", (owner, kind)).fetchall()
        return [{"id": r["id"], "metadata": json.loads(r["metadata"]), "updated_at": r["updated_at"]} for r in rows]


class SupabaseStore:
    enabled = True

    def __init__(self, url, key, transport=None):
        if not url or not key:
            raise PersistenceError("Supabase persistence requires URL and server secret key")
        self.url, self.key, self.transport = url.rstrip("/"), key, transport

    def request(self, method, path, **kwargs):
        headers = {"apikey": self.key}
        # Legacy service_role keys are JWTs; new sb_secret keys are not bearer tokens.
        if not self.key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.key}"
        headers.update(kwargs.pop("headers", {}))
        try:
            with httpx.Client(timeout=30, transport=self.transport) as client:
                response = client.request(method, self.url + path, headers=headers, **kwargs)
                response.raise_for_status()
                return response
        except httpx.HTTPError as exc:
            raise PersistenceError("Durable storage unavailable; retry after checking backend configuration") from exc

    def filters(self, identifier, owner, kind):
        return {"id": f"eq.{identifier}", "owner_id": f"eq.{owner}", "kind": f"eq.{kind}"}

    def save(self, identifier, owner, kind, metadata, blob=None):
        filters = self.filters(identifier, owner, kind)
        existing = self.request("GET", "/rest/v1/daisy_resources", params={**filters, "select": "id,storage_bucket,storage_path"}).json()
        body = {"metadata": metadata, "storage_bucket": None, "storage_path": None}
        if blob is not None:
            if len(blob) > 50 * 1024 * 1024:
                raise PersistenceError("Persisted object exceeds the 50 MB storage limit")
            bucket = "model-artifacts" if kind == "artifact" else "datasets"
            object_path = f"{quote(owner, safe='')}/{quote(identifier, safe='')}/{uuid.uuid4()}"
            self.request("POST", f"/storage/v1/object/{bucket}/{object_path}", content=blob, headers={"Content-Type": "application/octet-stream"})
            body.update(storage_bucket=bucket, storage_path=object_path)
        try:
            if existing:
                self.request("PATCH", "/rest/v1/daisy_resources", params=filters, json=body)
            else:
                self.request("POST", "/rest/v1/daisy_resources", json={"id": identifier, "owner_id": owner, "kind": kind, **body})
        except PersistenceError:
            if body["storage_path"]:
                self.request("DELETE", f"/storage/v1/object/{body['storage_bucket']}", json={"prefixes": [body["storage_path"]]})
            raise
        if existing and existing[0].get("storage_path"):
            try:
                self.request("DELETE", f"/storage/v1/object/{existing[0]['storage_bucket']}", json={"prefixes": [existing[0]["storage_path"]]})
            except PersistenceError:
                logging.getLogger("daisy.storage").warning("Old snapshot cleanup needs retry")

    def get(self, identifier, owner, kind):
        rows = self.request("GET", "/rest/v1/daisy_resources", params={**self.filters(identifier, owner, kind), "select": "metadata,storage_bucket,storage_path"}).json()
        if not rows:
            return None
        row = rows[0]
        blob = None
        if row["storage_path"]:
            if row["storage_bucket"] not in ("datasets", "model-artifacts") or not row["storage_path"].startswith(quote(owner, safe="") + "/"):
                raise PersistenceError("Invalid persisted object ownership")
            blob = self.request("GET", f"/storage/v1/object/authenticated/{row['storage_bucket']}/{row['storage_path']}").content
        return {"metadata": row["metadata"], "blob": blob}

    def list(self, owner, kind):
        return self.request("GET", "/rest/v1/daisy_resources", params={"owner_id": f"eq.{owner}", "kind": f"eq.{kind}", "select": "id,metadata,updated_at", "order": "updated_at.desc", "limit": "30"}).json()


def build_store():
    mode = os.getenv("DAISY_PERSISTENCE", "memory")
    if mode == "memory":
        return MemoryStore()
    if mode == "sqlite":
        return SQLiteStore(os.getenv("DAISY_STATE_DB", str(Path(__file__).with_name("state") / "daisy.sqlite")))
    if mode == "supabase":
        return SupabaseStore(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_SECRET_KEY", ""))
    raise PersistenceError("DAISY_PERSISTENCE must be memory, sqlite, or supabase")

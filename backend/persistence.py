"""Owner-filtered durable resources; JSON metadata and private binary objects."""
import json
import logging
import math
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

import httpx


class PersistenceError(RuntimeError):
    pass


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if hasattr(value, "item"):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


RUN_STAGES = ("dataset", "cleaning", "eda", "target", "feature", "selection", "training", "results")
RUN_STATUSES = {"idle", "available", "running", "done", "error", "waiting"}


def run_summary(row):
    """History never contains chat, previews, or full agent reports."""
    status = row.get("status") or {}
    if isinstance(status, str):
        try:
            status = json.loads(status)
        except ValueError:
            status = {}
    if not isinstance(status, dict):
        status = {}
    def text_field(key):
        value = row.get(key)
        return value[:512] if isinstance(value, str) else None
    def count_field(key):
        value = row.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
    return {"id": row["id"], "updated_at": row["updated_at"], "metadata": {
        "upload": {"filename": text_field("filename"), "rows": count_field("rows"), "columns": count_field("columns")},
        "targetColumn": text_field("target"), "bestModel": text_field("model"),
        "status": {key: status[key] for key in RUN_STAGES if isinstance(status.get(key), str) and status[key] in RUN_STATUSES},
    }}


class MemoryStore:
    enabled = False

    def probe(self):
        return True

    def save(self, identifier, owner, kind, metadata, blob=None):
        pass

    def get(self, identifier, owner, kind):
        return None

    def list(self, owner, kind):
        return []

    def metadata(self, identifier, owner, kind):
        return None

    def delete(self, identifier, owner, kind):
        return False

    def export_metadata(self, owner):
        return []

    def list_runs(self, owner, limit, offset):
        return []


class SQLiteStore:
    """Development persistence with the same owner boundary as the cloud store."""
    enabled = True

    def probe(self):
        with self.connect() as db:
            db.execute("SELECT 1 FROM resources LIMIT 1").fetchone()
        return True

    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS resources (id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL, metadata TEXT NOT NULL, blob BLOB, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            db.execute("CREATE INDEX IF NOT EXISTS resources_owner_kind_updated ON resources(owner,kind,updated_at DESC,id DESC)")
            db.execute("CREATE TABLE IF NOT EXISTS finalizations (source TEXT NOT NULL, owner TEXT NOT NULL, experiment_id TEXT NOT NULL, report TEXT, PRIMARY KEY(source,owner))")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        except sqlite3.Error as exc:
            raise PersistenceError("Durable local storage unavailable. Check the backend database.") from exc
        finally:
            db.close()

    def save(self, identifier, owner, kind, metadata, blob=None):
        with self.connect() as db:
            existing = db.execute("SELECT owner,kind FROM resources WHERE id=?", (identifier,)).fetchone()
            if existing and (existing["owner"] != owner or existing["kind"] != kind):
                raise PersistenceError("Resource identity cannot be reassigned")
            if existing and kind == "experiment":
                raise PersistenceError("Experiment records are immutable")
            db.execute("INSERT INTO resources(id,owner,kind,metadata,blob) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET metadata=excluded.metadata,blob=excluded.blob,updated_at=CURRENT_TIMESTAMP", (identifier, owner, kind, json.dumps(metadata, allow_nan=False), blob))

    def insert_experiment(self, identifier, owner, metadata):
        with self.connect() as db:
            db.execute("INSERT INTO resources(id,owner,kind,metadata) VALUES(?,?,?,?)", (identifier, owner, "experiment", json.dumps(metadata, allow_nan=False)))

    def list_experiments(self, owner, limit, offset):
        # Project compact fields in the database instead of loading fold IDs,
        # full candidate/per-class metrics, previews or pipeline context.
        with self.connect() as db:
            rows = db.execute("""SELECT id,updated_at,json_object(
                'created_at',json_extract(metadata,'$.created_at'),
                'dataset_id',json_extract(metadata,'$.dataset_id'),
                'target_column',json_extract(metadata,'$.target_column'),
                'training_result',json_object('best_model',json_extract(metadata,'$.training_result.best_model'),
                    'primary_metric',json_extract(metadata,'$.training_result.primary_metric'))
                ) AS summary FROM resources WHERE owner=? AND kind='experiment'
                ORDER BY updated_at DESC,id DESC LIMIT ? OFFSET ?""", (owner, limit, offset)).fetchall()
        return [{"id": row["id"], "updated_at": row["updated_at"], "metadata": json.loads(row["summary"])} for row in rows]

    def finalization(self, source, owner):
        with self.connect() as db:
            row = db.execute("SELECT experiment_id,report FROM finalizations WHERE source=? AND owner=?", (source, owner)).fetchone()
        return {"experiment_id": row["experiment_id"], "report": json.loads(row["report"]) if row["report"] else None} if row else None

    def claim_finalization(self, source, owner, experiment):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO finalizations(source,owner,experiment_id) VALUES(?,?,?)", (source, owner, experiment))
            row = db.execute("SELECT experiment_id,report FROM finalizations WHERE source=? AND owner=?", (source, owner)).fetchone()
            return {"experiment_id": row["experiment_id"], "report": json.loads(row["report"]) if row["report"] else None}

    def finish_finalization(self, source, owner, experiment, report):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT experiment_id,report FROM finalizations WHERE source=? AND owner=?", (source, owner)).fetchone()
            if not row or row["experiment_id"] != experiment:
                raise PersistenceError("Final evaluation does not match the claimed experiment")
            if row["report"]:
                return json.loads(row["report"])
            db.execute("UPDATE finalizations SET report=? WHERE source=? AND owner=?", (json.dumps(report, allow_nan=False), source, owner))
            return report

    def get(self, identifier, owner, kind):
        with self.connect() as db:
            row = db.execute("SELECT metadata,blob FROM resources WHERE id=? AND owner=? AND kind=?", (identifier, owner, kind)).fetchone()
        return {"metadata": json.loads(row["metadata"]), "blob": row["blob"]} if row else None

    def list(self, owner, kind):
        with self.connect() as db:
            rows = db.execute("SELECT id,metadata,updated_at FROM resources WHERE owner=? AND kind=? ORDER BY updated_at DESC LIMIT 30", (owner, kind)).fetchall()
        return [{"id": r["id"], "metadata": json.loads(r["metadata"]), "updated_at": r["updated_at"]} for r in rows]

    def metadata(self, identifier, owner, kind):
        with self.connect() as db:
            row = db.execute("SELECT metadata FROM resources WHERE id=? AND owner=? AND kind=?", (identifier, owner, kind)).fetchone()
        return json.loads(row["metadata"]) if row else None

    def delete(self, identifier, owner, kind):
        """Delete one resource without allowing its identifier to cross tenants."""
        with self.connect() as db:
            cursor = db.execute(
                "DELETE FROM resources WHERE id=? AND owner=? AND kind=?",
                (identifier, owner, kind),
            )
        return cursor.rowcount == 1

    def export_metadata(self, owner):
        """Return every owner-visible record without loading stored binary objects."""
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,kind,metadata,updated_at FROM resources WHERE owner=? ORDER BY updated_at,id",
                (owner,),
            ).fetchall()
        return [{"id": row["id"], "kind": row["kind"], "metadata": json.loads(row["metadata"]),
                 "updated_at": row["updated_at"]} for row in rows]

    def list_runs(self, owner, limit, offset):
        with self.connect() as db:
            rows = db.execute("""SELECT id,updated_at,
                json_extract(metadata,'$.upload.filename') AS filename,
                json_extract(metadata,'$.upload.rows') AS rows,
                json_extract(metadata,'$.upload.columns') AS columns,
                json_extract(metadata,'$.targetColumn') AS target,
                json_extract(metadata,'$.bestModel') AS model,
                json_extract(metadata,'$.status') AS status
                FROM resources WHERE owner=? AND kind='run'
                ORDER BY updated_at DESC,id DESC LIMIT ? OFFSET ?""", (owner, limit, offset)).fetchall()
        return [run_summary(dict(row)) for row in rows]


class SupabaseStore:
    enabled = True

    def probe(self):
        self.request("GET", "/rest/v1/daisy_resources", params={"select": "id", "limit": "0"})
        return True

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
        if existing and kind == "experiment":
            raise PersistenceError("Experiment records are immutable")
        body = {"metadata": metadata, "storage_bucket": None, "storage_path": None}
        if blob is not None:
            if len(blob) > 50 * 1024 * 1024:
                raise PersistenceError("Persisted object exceeds the 50 MB storage limit")
            bucket = "model-artifacts" if kind == "artifact" else "datasets"
            object_path = f"{quote(owner, safe='')}/{quote(identifier, safe='')}/{uuid.uuid4()}"
            content_type = "application/zip" if kind == "artifact" else ("text/csv" if metadata.get("source_csv") else "application/json")
            self.request("POST", f"/storage/v1/object/{bucket}/{object_path}", content=blob, headers={"Content-Type": content_type})
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

    def insert_experiment(self, identifier, owner, metadata):
        self.request("POST", "/rest/v1/daisy_resources", json={"id": identifier, "owner_id": owner, "kind": "experiment", "metadata": metadata})

    def list_experiments(self, owner, limit, offset):
        rows = self.request("GET", "/rest/v1/daisy_resources", params={
            "owner_id": f"eq.{owner}", "kind": "eq.experiment",
            "select": "id,updated_at,created_at:metadata->>created_at,dataset_id:metadata->>dataset_id,target_column:metadata->>target_column,best_model:metadata->training_result->>best_model,primary_metric:metadata->training_result->>primary_metric",
            "order": "updated_at.desc,id.desc", "limit": str(limit), "offset": str(offset),
        }).json()
        return [{"id": row["id"], "updated_at": row["updated_at"], "metadata": {"created_at": row["created_at"],
                 "dataset_id": row["dataset_id"], "target_column": row["target_column"],
                 "training_result": {"best_model": row["best_model"], "primary_metric": row["primary_metric"]}}} for row in rows]

    def finalization(self, source, owner):
        rows = self.request("GET", "/rest/v1/daisy_finalizations", params={"source_id": f"eq.{source}", "owner_id": f"eq.{owner}", "select": "experiment_id,report"}).json()
        return rows[0] if rows else None

    def claim_finalization(self, source, owner, experiment):
        return self.request("POST", "/rest/v1/rpc/daisy_claim_finalization", json={"p_source": source, "p_owner": owner, "p_experiment": experiment}).json()

    def finish_finalization(self, source, owner, experiment, report):
        return self.request("POST", "/rest/v1/rpc/daisy_finish_finalization", json={"p_source": source, "p_owner": owner, "p_experiment": experiment, "p_report": report}).json()

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

    def metadata(self, identifier, owner, kind):
        rows = self.request("GET", "/rest/v1/daisy_resources", params={**self.filters(identifier, owner, kind), "select": "metadata"}).json()
        return rows[0]["metadata"] if rows else None

    def delete(self, identifier, owner, kind):
        """Delete private object bytes first, then their owner-scoped metadata."""
        filters = self.filters(identifier, owner, kind)
        rows = self.request(
            "GET",
            "/rest/v1/daisy_resources",
            params={**filters, "select": "id,storage_bucket,storage_path"},
        ).json()
        if not rows:
            return False
        row = rows[0]
        path = row.get("storage_path")
        bucket = row.get("storage_bucket")
        if path:
            if bucket not in ("datasets", "model-artifacts") or not path.startswith(quote(owner, safe="") + "/"):
                raise PersistenceError("Invalid persisted object ownership")
            self.request("DELETE", f"/storage/v1/object/{bucket}", json={"prefixes": [path]})
        self.request("DELETE", "/rest/v1/daisy_resources", params=filters)
        return True

    def export_metadata(self, owner):
        """Page through metadata only; private Storage objects remain separate downloads."""
        records, offset, page_size = [], 0, 500
        while True:
            page = self.request("GET", "/rest/v1/daisy_resources", params={
                "owner_id": f"eq.{owner}", "select": "id,kind,metadata,updated_at",
                "order": "updated_at.asc,id.asc", "limit": str(page_size), "offset": str(offset),
            }).json()
            records.extend(page)
            if len(page) < page_size:
                return records
            offset += page_size

    def list_runs(self, owner, limit, offset):
        # Project JSON fields in Postgres: full snapshots never cross the history boundary.
        fields = "id,updated_at,filename:metadata->upload->>filename,rows:metadata->upload->rows,columns:metadata->upload->columns,target:metadata->>targetColumn,model:metadata->>bestModel,status:metadata->status"
        rows = self.request("GET", "/rest/v1/daisy_resources", params={
            "owner_id": f"eq.{owner}", "kind": "eq.run", "select": fields,
            "order": "updated_at.desc,id.desc", "limit": str(limit), "offset": str(offset),
        }).json()
        return [run_summary(row) for row in rows]


def build_store():
    mode = os.getenv("DAISY_PERSISTENCE", "memory")
    if mode == "memory":
        return MemoryStore()
    if mode == "sqlite":
        return SQLiteStore(os.getenv("DAISY_STATE_DB", str(Path(__file__).with_name("state") / "daisy.sqlite")))
    if mode == "supabase":
        return SupabaseStore(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_SECRET_KEY", ""))
    raise PersistenceError("DAISY_PERSISTENCE must be memory, sqlite, or supabase")

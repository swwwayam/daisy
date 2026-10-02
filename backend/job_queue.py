"""Durable training jobs with atomic claims and owner-scoped idempotency."""
import hashlib
import json
import os
import time
import uuid

from persistence import SQLiteStore, SupabaseStore


class QueueError(RuntimeError):
    def __init__(self, message, status=429):
        super().__init__(message)
        self.status = status


def signature(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class SQLiteQueue:
    def __init__(self, path):
        self.db = SQLiteStore(path)
        with self.db.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS training_jobs (id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, signature TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', created_at REAL NOT NULL, lease_until REAL, result TEXT, error TEXT, UNIQUE(owner_id,idempotency_key))")

    def enqueue(self, owner, key, payload):
        with self.db.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM training_jobs WHERE owner_id=? AND idempotency_key=?", (owner, key)).fetchone()
            if existing:
                if existing["signature"] != signature(payload):
                    raise QueueError("Idempotency key was used for a different request", 409)
                return self.decode(existing)
            active = db.execute("SELECT count(*) FROM training_jobs WHERE owner_id=? AND status IN ('queued','running')", (owner,)).fetchone()[0]
            daily = db.execute("SELECT count(*) FROM training_jobs WHERE owner_id=? AND created_at>?", (owner, time.time() - 86400)).fetchone()[0]
            total = db.execute("SELECT count(*) FROM training_jobs WHERE status IN ('queued','running')").fetchone()[0]
            if active >= 2 or daily >= 10 or total >= 100:
                raise QueueError("Training quota reached. Wait for active jobs or try again tomorrow.")
            identifier = str(uuid.uuid4())
            db.execute("INSERT INTO training_jobs(id,owner_id,idempotency_key,signature,payload,created_at) VALUES(?,?,?,?,?,?)", (identifier, owner, key, signature(payload), json.dumps(payload), time.time()))
            return self.decode(db.execute("SELECT * FROM training_jobs WHERE id=?", (identifier,)).fetchone())

    @staticmethod
    def decode(row):
        if not row:
            return None
        out = dict(row)
        out["payload"] = json.loads(out["payload"])
        out["result"] = json.loads(out["result"]) if out["result"] else None
        return out

    def get(self, identifier, owner):
        with self.db.connect() as db:
            return self.decode(db.execute("SELECT * FROM training_jobs WHERE id=? AND owner_id=?", (identifier, owner)).fetchone())

    def claim(self):
        with self.db.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE training_jobs SET status='failed',error='Worker lease expired. Submit a new job.' WHERE status='running' AND lease_until<?", (time.time(),))
            row = db.execute("SELECT * FROM training_jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE training_jobs SET status='running',lease_until=? WHERE id=?", (time.time() + 660, row["id"]))
            return self.decode(db.execute("SELECT * FROM training_jobs WHERE id=?", (row["id"],)).fetchone())

    def finish(self, identifier, owner, status, result=None, error=None):
        with self.db.connect() as db:
            db.execute("UPDATE training_jobs SET status=?,result=?,error=? WHERE id=? AND owner_id=? AND status='running'", (status, json.dumps(result) if result is not None else None, error, identifier, owner))

    def cancel(self, identifier, owner):
        with self.db.connect() as db:
            db.execute("UPDATE training_jobs SET status='cancelled' WHERE id=? AND owner_id=? AND status IN ('queued','running')", (identifier, owner))
        return self.get(identifier, owner)


class SupabaseQueue:
    def __init__(self, store):
        self.store = store

    def enqueue(self, owner, key, payload):
        data = self.store.request("POST", "/rest/v1/rpc/daisy_enqueue_training", json={"requested_owner": owner, "requested_key": key, "requested_signature": signature(payload), "requested_payload": payload}).json()
        if data.get("error"):
            raise QueueError(data["error"], data.get("status", 429))
        return data

    def get(self, identifier, owner):
        rows = self.store.request("GET", "/rest/v1/daisy_training_jobs", params={"id": f"eq.{identifier}", "owner_id": f"eq.{owner}", "select": "*"}).json()
        return rows[0] if rows else None

    def claim(self):
        return self.store.request("POST", "/rest/v1/rpc/daisy_claim_training", json={}).json()

    def finish(self, identifier, owner, status, result=None, error=None):
        self.store.request("PATCH", "/rest/v1/daisy_training_jobs", params={"id": f"eq.{identifier}", "owner_id": f"eq.{owner}", "status": "eq.running"}, json={"status": status, "result": result, "error": error})

    def cancel(self, identifier, owner):
        self.store.request("PATCH", "/rest/v1/daisy_training_jobs", params={"id": f"eq.{identifier}", "owner_id": f"eq.{owner}", "status": "in.(queued,running)"}, json={"status": "cancelled"})
        return self.get(identifier, owner)


def build_queue(store):
    if isinstance(store, SupabaseStore):
        return SupabaseQueue(store)
    if isinstance(store, SQLiteStore):
        return SQLiteQueue(store.path)
    return None

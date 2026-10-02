"""Minimize provider inputs and meter calls before spending an owner's budget."""
import re
import threading
import time
import uuid

from fastapi import HTTPException
from persistence import SQLiteStore, SupabaseStore

SENSITIVE_NAME = re.compile(r"email|phone|mobile|address|(?:^|_)name|ssn|aadhaar|passport|birth|patient|account|latitude|longitude", re.I)
VALUE_KEYS = {"top_values", "sample", "samples", "sample_values", "examples", "preview", "target_min", "target_max", "target_mean", "target_std"}
SAFE_FIELDS = {"name", "dtype", "is_numeric", "missing_count", "missing_ratio", "null_count", "zero_count", "unique_count", "unique_ratio"}


def redact_text(text):
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted email]", text)
    return re.sub(r"(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)", "[redacted identifier]", text)


def private_profile(profile, columns, sensitive_columns=(), strip_narratives=False):
    aliases = {str(column): f"field_{i+1}" for i, column in enumerate(columns)}
    sensitive = set(sensitive_columns) | {c for c in columns if SENSITIVE_NAME.search(str(c))}

    def visit(value):
        if isinstance(value, dict):
            if value.get("name") in sensitive:
                value = {k: v for k, v in value.items() if k in SAFE_FIELDS}
            out = {}
            for key, item in value.items():
                if key in VALUE_KEYS or (strip_narratives and key in {"summary", "reasoning", "message", "observations"}):
                    continue
                if key == "class_balance" and isinstance(item, dict):
                    out[key] = {f"class_{i+1}": amount for i, amount in enumerate(item.values())}
                elif key == "labels":
                    out[key] = [f"class_{i+1}" for i in range(len(item))]
                elif key in sensitive and isinstance(item, dict):
                    out[aliases.get(key, key)] = visit({k: v for k, v in item.items() if k in SAFE_FIELDS})
                else:
                    out[aliases.get(key, key)] = visit(item)
            return out
        if isinstance(value, list):
            return [visit(item) for item in value]
        if isinstance(value, str):
            return aliases.get(value, redact_text(value))
        return value

    return visit(profile), aliases


def restore_names(value, aliases):
    reverse = {alias: original for original, alias in aliases.items()}
    if isinstance(value, dict):
        return {reverse.get(k, k): restore_names(v, aliases) for k, v in value.items()}
    if isinstance(value, list):
        return [restore_names(v, aliases) for v in value]
    if isinstance(value, str) and reverse:
        pattern = r"\b(?:" + "|".join(re.escape(alias) for alias in sorted(reverse, key=len, reverse=True)) + r")\b"
        value = re.sub(pattern, lambda match: reverse[match.group()], value)
    return value


class MemoryBudget:
    """Demo-only budget. Durable deployments use SQLite or Postgres below."""
    def __init__(self):
        self.rows = {}
        self.lock = threading.Lock()

    def reserve(self, owner, tokens):
        with self.lock:
            recent = [r for r in self.rows.values() if r["owner"] == owner and r["time"] > time.time() - 86400]
            if len(recent) >= 100 or sum(r["tokens"] for r in recent) + tokens > 200000:
                raise HTTPException(status_code=429, detail="Daily AI budget reached. Try again tomorrow or disable AI reasoning.")
            identifier = str(uuid.uuid4())
            self.rows[identifier] = {"owner": owner, "time": time.time(), "tokens": tokens}
            return identifier

    def settle(self, identifier, owner, tokens):
        with self.lock:
            if self.rows[identifier]["owner"] == owner:
                self.rows[identifier]["tokens"] = tokens


class SQLiteBudget:
    def __init__(self, path):
        self.db = SQLiteStore(path)
        with self.db.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS ai_usage (id TEXT PRIMARY KEY, owner TEXT NOT NULL, created REAL NOT NULL, tokens INTEGER NOT NULL)")

    def reserve(self, owner, tokens):
        with self.db.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count, spent = db.execute("SELECT count(*),coalesce(sum(tokens),0) FROM ai_usage WHERE owner=? AND created>?", (owner, time.time() - 86400)).fetchone()
            if count >= 100 or spent + tokens > 200000:
                raise HTTPException(status_code=429, detail="Daily AI budget reached. Try again tomorrow or disable AI reasoning.")
            identifier = str(uuid.uuid4())
            db.execute("INSERT INTO ai_usage VALUES(?,?,?,?)", (identifier, owner, time.time(), tokens))
            return identifier

    def settle(self, identifier, owner, tokens):
        with self.db.connect() as db:
            db.execute("UPDATE ai_usage SET tokens=? WHERE id=? AND owner=?", (tokens, identifier, owner))


class SupabaseBudget:
    def __init__(self, store): self.store = store
    def reserve(self, owner, tokens):
        result = self.store.request("POST", "/rest/v1/rpc/daisy_reserve_ai", json={"requested_owner": owner, "requested_tokens": tokens}).json()
        if result.get("error"):
            raise HTTPException(status_code=429, detail="Daily AI budget reached. Try again tomorrow or disable AI reasoning.")
        return result["id"]
    def settle(self, identifier, owner, tokens):
        self.store.request("PATCH", "/rest/v1/daisy_ai_usage", params={"id": f"eq.{identifier}", "owner_id": f"eq.{owner}"}, json={"tokens": tokens})


def build_budget(store):
    if isinstance(store, SQLiteStore): return SQLiteBudget(store.path)
    if isinstance(store, SupabaseStore): return SupabaseBudget(store)
    return MemoryBudget()

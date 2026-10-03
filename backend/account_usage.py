"""Owner-only snapshots of enforced rolling-day budgets, without reserving usage."""
import time
from datetime import datetime, timezone

from persistence import SQLiteStore, SupabaseStore


def snapshot(store, owner, ai_budget, prediction_usage, queue):
    now = time.time()
    if isinstance(store, SupabaseStore):
        data = store.request("POST", "/rest/v1/rpc/daisy_account_usage", json={"p_owner": owner}).json()
    elif isinstance(store, SQLiteStore):
        with store.connect() as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            ai = db.execute("SELECT count(*),coalesce(sum(tokens),0),min(created) FROM ai_usage WHERE owner=? AND created>?", (owner, now - 86400)).fetchone() if "ai_usage" in tables else (0, 0, None)
            inference = db.execute("SELECT count(*),coalesce(sum(rows),0),min(created) FROM prediction_usage WHERE owner=? AND created>?", (owner, now - 86400)).fetchone() if "prediction_usage" in tables else (0, 0, None)
            training = db.execute("SELECT count(*),min(created_at) FROM training_jobs WHERE owner_id=? AND created_at>?", (owner, now - 86400)).fetchone() if "training_jobs" in tables else (0, None)
            active = db.execute("SELECT count(*) FROM training_jobs WHERE owner_id=? AND status IN ('queued','running')", (owner,)).fetchone()[0] if "training_jobs" in tables else 0
        def expiry(value):
            return datetime.fromtimestamp(value + 86400, timezone.utc).isoformat() if value is not None else None
        data = {"ai": {"requests": ai[0], "tokens": ai[1], "next_expiry": expiry(ai[2])},
                "inference": {"requests": inference[0], "scored_rows": inference[1], "next_expiry": expiry(inference[2])},
                "training": {"requests": training[0], "active_jobs": active, "next_expiry": expiry(training[1])}}
    else:
        with ai_budget.lock:
            ai = [row for row in ai_budget.rows.values() if row["owner"] == owner and row["time"] > now - 86400]
        with prediction_usage.lock:
            inference = [row for row in prediction_usage.rows if row[0] == owner and row[1] > now - 86400]
        data = {"ai": {"requests": len(ai), "tokens": sum(row["tokens"] for row in ai), "next_expiry": None},
                "inference": {"requests": len(inference), "scored_rows": sum(row[2] for row in inference), "next_expiry": None},
                "training": {"requests": None, "active_jobs": None, "next_expiry": None}}
    data.update(window_hours=24, durable=store.enabled, training_metered=queue is not None,
                limits={"ai_requests": 100, "ai_tokens": 200000, "inference_requests": 100,
                        "inference_scored_rows": 100000, "training_requests": 10, "active_training_jobs": 2})
    return data

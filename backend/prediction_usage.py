"""Atomic rolling-day inference budgets. Only counts are retained."""
import threading
import time

from fastapi import HTTPException
from persistence import SQLiteStore, SupabaseStore


class PredictionUsage:
    def __init__(self):
        self.rows = []
        self.lock = threading.Lock()

    def reserve(self, store, owner, rows):
        if isinstance(store, SupabaseStore):
            reply = store.request("POST", "/rest/v1/rpc/daisy_reserve_prediction", json={"p_owner": owner, "p_rows": rows}).json()
            accepted = reply["accepted"]
        elif isinstance(store, SQLiteStore):
            with store.connect() as db:
                db.execute("CREATE TABLE IF NOT EXISTS prediction_usage (owner TEXT NOT NULL, created REAL NOT NULL, rows INTEGER NOT NULL)")
                db.execute("BEGIN IMMEDIATE")
                db.execute("DELETE FROM prediction_usage WHERE created<?", (time.time() - 86400,))
                count, total = db.execute("SELECT count(*),coalesce(sum(rows),0) FROM prediction_usage WHERE owner=?", (owner,)).fetchone()
                accepted = count < 100 and total + rows <= 100000
                if accepted:
                    db.execute("INSERT INTO prediction_usage VALUES(?,?,?)", (owner, time.time(), rows))
        else:
            with self.lock:
                self.rows = [row for row in self.rows if row[1] > time.time() - 86400]
                mine = [row for row in self.rows if row[0] == owner]
                accepted = len(mine) < 100 and sum(row[2] for row in mine) + rows <= 100000
                if accepted:
                    self.rows.append((owner, time.time(), rows))
        if not accepted:
            raise HTTPException(status_code=429, detail="Prediction budget reached: 100 requests / 100,000 rows per rolling day. Retry tomorrow.")

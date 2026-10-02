"""Append-only experiments and a durable, one-winner holdout gate."""
import json
import threading
from datetime import datetime, timezone

from persistence import json_safe


class FinalizationConflict(ValueError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class ExperimentRegistry:
    """Demo records use memory; production records follow the configured store."""
    def __init__(self):
        self.records = {}
        self.finalizations = {}
        self.lock = threading.RLock()

    def create(self, store, identifier, owner, record):
        record = json_safe(record)
        if store.enabled:
            store.insert_experiment(identifier, owner, record)
        else:
            with self.lock:
                if identifier in self.records:
                    raise ValueError("Experiment already exists")
                self.records[identifier] = (owner, record)

    def get(self, store, identifier, owner):
        if store.enabled:
            return store.metadata(identifier, owner, "experiment")
        with self.lock:
            saved = self.records.get(identifier)
            return json.loads(json.dumps(saved[1])) if saved and saved[0] == owner else None

    def list(self, store, owner, limit=20, offset=0):
        if store.enabled:
            return store.list_experiments(owner, limit, offset)
        with self.lock:
            return [{"id": key, "metadata": value, "updated_at": value["created_at"]}
                    for key, (creator, value) in reversed(list(self.records.items())) if creator == owner][offset:offset + limit]

    def finalization(self, store, source, owner):
        if store.enabled:
            return store.finalization(source, owner)
        with self.lock:
            return self.finalizations.get((owner, source))

    def claim(self, store, source, owner, experiment):
        if store.enabled:
            state = store.claim_finalization(source, owner, experiment)
        else:
            with self.lock:
                state = self.finalizations.setdefault((owner, source), {"experiment_id": experiment, "report": None})
        if state["experiment_id"] != experiment:
            raise FinalizationConflict("This source dataset already has a final winner. Its holdout cannot evaluate another experiment. Use genuinely new unseen data for further evaluation.")
        return state

    def finish(self, store, source, owner, experiment, report):
        report = json_safe(report)
        if store.enabled:
            return store.finish_finalization(source, owner, experiment, report)
        with self.lock:
            state = self.claim(store, source, owner, experiment)
            if state["report"] is None:
                state["report"] = report
            return state["report"]


def public_record(record):
    # Fold row IDs stay server-side; compact history never includes diagnostics.
    return {key: value for key, value in record.items() if key != "evaluation_state"}

"""Read a server-owned export without extraction and evaluate its exact winner."""
import hashlib
import io
import json
import pickle
import zipfile

import joblib
import pandas as pd

from daisy_predict import transform
from model_training import TrainingDataError, _dataset_fingerprint, _hash_index, reserved_partitions, score_final_model


def load_server_package(path, artifact_id):
    # The API authorizes the artifact before calling this. User-uploaded pickles
    # are never accepted. Fixed members avoid filesystem extraction entirely.
    try:
        with zipfile.ZipFile(path) as archive:
            for name, limit in (("checksums.json", 65536), ("metadata.json", 8 * 1024 * 1024), ("model.joblib", 128 * 1024 * 1024)):
                if archive.namelist().count(name) != 1 or archive.getinfo(name).file_size > limit:
                    raise TrainingDataError("Saved package members are missing, duplicated, or exceed the read budget")
            checksums = json.loads(archive.read("checksums.json"))["files"]
            payload = archive.read("model.joblib")
            metadata_bytes = archive.read("metadata.json")
            for name, content in (("model.joblib", payload), ("metadata.json", metadata_bytes)):
                if hashlib.sha256(content).hexdigest() != checksums.get(name):
                    raise TrainingDataError("Saved model package failed integrity verification")
            metadata = json.loads(metadata_bytes)
            if metadata["artifact_id"] != artifact_id:
                raise TrainingDataError("Saved package does not match this experiment")
            return joblib.load(io.BytesIO(payload)), metadata
    except TrainingDataError:
        raise
    except (zipfile.BadZipFile, OSError, KeyError, ValueError, TypeError, EOFError, ImportError, AttributeError, pickle.UnpicklingError) as exc:
        raise TrainingDataError("Saved model package is damaged or incompatible with this runtime. Restore a valid package or retrain.") from exc


def load_owned_package(path, experiment):
    bundle, metadata = load_server_package(path, experiment["model_artifact"]["artifact_id"])
    if metadata.get("experiment_id") != experiment["experiment_id"]:
        raise TrainingDataError("Saved package does not match this experiment")
    return bundle, metadata


def evaluate_saved_winner(bundle, metadata, experiment, raw):
    source, _, _, test_ids = reserved_partitions(raw, metadata["test_size"], metadata["random_state"], metadata.get("training_config"))
    if _dataset_fingerprint(source) != metadata["dataset_fingerprint"]:
        raise TrainingDataError("Source data no longer matches the experiment fingerprint")
    state = experiment["evaluation_state"]
    train_ids = pd.Index(state["train_row_ids"])
    recorded_test = pd.Index(state["test_row_ids"])
    if _hash_index(train_ids) != metadata["train_index_hash"] or _hash_index(recorded_test) != metadata["test_index_hash"]:
        raise TrainingDataError("Recorded evaluation folds do not match the trained model")
    target = metadata["target_column"]
    expected_test = source.loc[test_ids].dropna(subset=[target]).index
    if not recorded_test.equals(expected_test):
        raise TrainingDataError("Held-out rows do not match the frozen split")
    train_raw, test_raw = source.loc[train_ids], source.loc[recorded_test]
    X_train, X_test = transform(bundle, train_raw), transform(bundle, test_raw)
    result = score_final_model(bundle["estimator"], metadata["model"], metadata["problem_type"], X_train, X_test,
                               train_raw[target], test_raw[target], experiment["training_result"]["warnings"], metadata["primary_metric"])
    result.update(experiment_id=experiment["experiment_id"], artifact_id=metadata["artifact_id"],
                  selection_metric=metadata["primary_metric"], split_strategy=metadata["split_strategy"])
    return result

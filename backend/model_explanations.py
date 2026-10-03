"""Bounded permutation sensitivity on the frozen validation fold, never the test."""
import numpy as np
from sklearn.metrics import get_scorer

from daisy_predict import transform
from model_training import TrainingDataError, _dataset_fingerprint, _hash_index, reserved_partitions


SCORERS = {"mae": "neg_mean_absolute_error", "rmse": "neg_root_mean_squared_error",
           "r2": "r2", "accuracy": "accuracy", "balanced_accuracy": "balanced_accuracy",
           "f1_weighted": "f1_weighted", "f1_macro": "f1_macro"}


def prepare_validation(bundle, metadata, raw, features):
    if not features or len(features) > 15 or len(set(features)) != len(features):
        raise TrainingDataError("Choose 1 to 15 distinct encoded features")
    if set(features) - set(bundle["feature_columns"]):
        raise TrainingDataError("Choose only features from this saved model")
    source, _, validation_ids, _ = reserved_partitions(raw, metadata["test_size"], metadata["random_state"], metadata.get("training_config"))
    if _dataset_fingerprint(source) != metadata["dataset_fingerprint"]:
        raise TrainingDataError("Source data no longer matches the experiment fingerprint")
    target = metadata["target_column"]
    validation = source.loc[validation_ids].dropna(subset=[target])
    if _hash_index(validation.index) != metadata["validation_index_hash"]:
        raise TrainingDataError("Validation rows do not match the frozen split")
    if metadata["primary_metric"] not in SCORERS:
        raise TrainingDataError("This model has no supported recorded selection metric")
    # Sample before expanding encodings. No estimator fitting occurs here.
    sample = validation.sample(n=min(200, len(validation)), random_state=42)
    if len(sample) * len(bundle["feature_columns"]) > 1000000:
        raise TrainingDataError("This model exceeds the explanation feature-cell budget")
    X = transform(bundle, sample)
    return X, sample[target], len(validation)


def explain_validation(bundle, metadata, X, y, features, total_validation):
    metric = metadata["primary_metric"]
    scorer = get_scorer(SCORERS[metric])
    estimator = bundle["estimator"]
    baseline = float(scorer(estimator, X, y))
    rng = np.random.default_rng(42)
    # Reuse the same permutations for each feature for a fair, reproducible comparison.
    permutations = [rng.permutation(len(X)) for _ in range(3)]
    results = []
    for name in features:
        changes = []
        for order in permutations:
            shuffled = X.copy()
            shuffled[name] = X[name].to_numpy()[order]
            changes.append(baseline - float(scorer(estimator, shuffled, y)))
        results.append({"feature": name, "score_decrease": float(np.mean(changes)), "repeat_std": float(np.std(changes))})
    if not np.isfinite([baseline, *[value for row in results for key, value in row.items() if key != "feature"]]).all():
        raise TrainingDataError("Validation scores are undefined; an explanation cannot be reported")
    return {"method": "validation_permutation", "artifact_id": metadata["artifact_id"],
            "metric": metric, "baseline_metric_value": -baseline if metric in {"mae", "rmse"} else baseline,
            "change_label": "Error increase" if metric in {"mae", "rmse"} else "Score decrease",
            "rows_evaluated": len(X), "validation_rows": total_validation, "repeats": 3, "random_state": 42,
            "features": sorted(results, key=lambda row: row["score_decrease"], reverse=True),
            "scope": "Selected encoded features; validation only. Final-test rows are never scored.",
            "limitations": ["Positive changes mean shuffling hurt this saved model; negative changes mean it helped.",
                            "Repeat standard deviation measures shuffle variation, not a confidence interval.",
                            "Correlated features can hide importance; shuffling encoded categories can create unrealistic combinations.",
                            "This explains model sensitivity, not causation, feature quality, or future prediction accuracy.",
                            "Validation was used for model selection; these are exploratory diagnostics, not independent final evidence."]}

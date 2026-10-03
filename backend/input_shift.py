"""Training-serving input checks; heuristics, not a test of model accuracy."""
import numpy as np


def training_reference(features):
    # Avoid unbounded report/ZIP metadata for very wide encodings.
    if len(features.columns) > 1000:
        return {"available": False, "reason": "More than 1000 encoded features"}
    return {"available": True, "scope": "transformed_training_only", "rows": len(features),
            "features": {str(name): {"mean": float(features[name].mean()), "std": float(features[name].std(ddof=0)),
                                     "min": float(features[name].min()), "max": float(features[name].max())}
                         for name in features.columns}}


def compare_inputs(reference, features):
    if not reference or not reference.get("available"):
        return {"status": "unavailable", "reason": "This package has no bounded training-only reference. Train a new model to enable comparisons."}
    if len(features) < 30:
        return {"status": "insufficient_rows", "reason": "Supply at least 30 rows for batch input comparisons; small batches are unreliable."}
    flagged = []
    for name, stats in reference["features"].items():
        values = features[name].to_numpy(dtype=float)
        tolerance = max(abs(stats["min"]), abs(stats["max"]), 1) * 1e-12
        outside = float(np.mean((values < stats["min"] - tolerance) | (values > stats["max"] + tolerance)))
        shift = abs(float(np.mean(values)) - stats["mean"]) / stats["std"] if stats["std"] > tolerance else None
        if (shift is not None and shift > 1) or outside > .1:
            flagged.append({"feature": name, "mean_shift_in_training_std": shift, "outside_training_range_fraction": outside})
    flagged.sort(key=lambda row: (row["outside_training_range_fraction"], row["mean_shift_in_training_std"] or 0), reverse=True)
    return {"status": "review_inputs" if flagged else "no_flags", "reference_scope": reference["scope"],
            "training_rows": reference["rows"], "batch_rows": len(features), "features_checked": len(reference["features"]),
            "flagged_feature_count": len(flagged), "flagged_features": flagged[:20],
            "thresholds": {"mean_shift_training_std": 1, "outside_training_range_fraction": .1},
            "limitations": "Exploratory thresholds, not statistical significance. No flags does not prove stable distributions or accurate predictions. Compare labelled outcomes before retraining. Only transformed features are checked; preprocessing can hide raw shifts."}

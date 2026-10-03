"""Training-serving input checks; heuristics, not a test of model accuracy."""
import numpy as np


def stable_moments(values):
    """Compute finite moments without summing or squaring large raw values."""
    values = np.asarray(values, dtype=float)
    if not values.size or not np.isfinite(values).all():
        raise ValueError("Input comparisons require finite, nonempty features")
    scale = float(np.max(np.abs(values)))
    if scale == 0:
        return 0.0, 0.0
    normalized = values / scale
    # Normalized values lie in [-1, 1]; the population std cannot exceed 1.
    mean = float(np.clip(np.mean(normalized), -1, 1)) * scale
    std = min(float(np.std(normalized, ddof=0)), 1.0) * scale
    return mean, std


def training_reference(features):
    # Avoid unbounded report/ZIP metadata for very wide encodings.
    if len(features.columns) > 1000:
        return {"available": False, "reason": "More than 1000 encoded features"}
    summaries = {}
    for name in features.columns:
        values = features[name].to_numpy(dtype=float)
        mean, std = stable_moments(values)
        summaries[str(name)] = {"mean": mean, "std": std, "min": float(values.min()), "max": float(values.max())}
    return {"available": True, "scope": "transformed_training_only", "rows": len(features), "features": summaries}


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
        mean, _ = stable_moments(values)
        shift, overflow = None, False
        if stats["std"] > tolerance:
            scale = max(abs(mean), abs(stats["mean"]), stats["std"], 1)
            shift = abs(mean / scale - stats["mean"] / scale) / (stats["std"] / scale)
            if not np.isfinite(shift):
                shift, overflow = None, True
        if overflow or (shift is not None and shift > 1) or outside > .1:
            flagged.append({"feature": name, "mean_shift_in_training_std": shift,
                            "mean_shift_exceeds_numeric_range": overflow, "outside_training_range_fraction": outside})
    flagged.sort(key=lambda row: (row["outside_training_range_fraction"], row["mean_shift_in_training_std"] or 0), reverse=True)
    return {"status": "review_inputs" if flagged else "no_flags", "reference_scope": reference["scope"],
            "training_rows": reference["rows"], "batch_rows": len(features), "features_checked": len(reference["features"]),
            "flagged_feature_count": len(flagged), "flagged_features": flagged[:20],
            "thresholds": {"mean_shift_training_std": 1, "outside_training_range_fraction": .1},
            "limitations": "Exploratory thresholds, not statistical significance. No flags does not prove stable distributions or accurate predictions. Compare labelled outcomes before retraining. Only transformed features are checked; preprocessing can hide raw shifts."}

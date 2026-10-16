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


def validate_shap_model(estimator, X):
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, ExtraTreesClassifier, ExtraTreesRegressor
    if not isinstance(estimator, (DecisionTreeClassifier, DecisionTreeRegressor, RandomForestClassifier, RandomForestRegressor, ExtraTreesClassifier, ExtraTreesRegressor)):
        raise TrainingDataError("Tree SHAP supports decision trees, random forests and Extra Trees. Use permutation importance for this model.")
    trees = list(getattr(estimator, "estimators_", [estimator]))
    if len(trees) > 500 or sum(tree.tree_.node_count for tree in trees) > 100000 or max(tree.tree_.max_depth for tree in trees) > 32 or X.shape[1] > 256:
        raise TrainingDataError("This model exceeds the bounded SHAP budget. Use permutation importance instead.")
    classes = getattr(estimator, "classes_", [])
    if len(classes) > 20 or getattr(estimator, "n_outputs_", 1) != 1:
        raise TrainingDataError("SHAP supports single-output models with up to 20 classes.")


def explain_tree_shap(bundle, metadata, X, features, total_validation):
    """Exact Tree SHAP on at most 64 frozen validation rows; no refit or raw rows returned."""
    estimator = bundle["estimator"]
    validate_shap_model(estimator, X)
    try:
        import shap
    except ImportError as exc:
        raise TrainingDataError("SHAP is not installed. Install backend requirements or use permutation importance.") from exc
    X = X.iloc[:64]
    try:
        explainer = shap.TreeExplainer(estimator, feature_perturbation="tree_path_dependent", model_output="raw")
        values = np.asarray(explainer.shap_values(X, check_additivity=True))
    except Exception as exc:
        raise TrainingDataError("Tree SHAP could not explain this estimator. Try permutation importance.") from exc
    classes = getattr(estimator, "classes_", None)
    output_index = 1 if classes is not None and len(classes) == 2 else 0
    contributions = values[:, :, output_index] if values.ndim == 3 else values
    expected = np.asarray(explainer.expected_value).reshape(-1)
    base = float(expected[output_index if len(expected) > 1 else 0])
    output = float(estimator.predict_proba(X.iloc[:1])[0, output_index]) if classes is not None else float(estimator.predict(X.iloc[:1])[0])
    if contributions.shape != X.shape or not np.isfinite(contributions).all() or not np.isfinite([base, output]).all():
        raise TrainingDataError("SHAP returned invalid contribution values")
    if not np.isclose(base + contributions[0].sum(), output, rtol=1e-4, atol=1e-5):
        raise TrainingDataError("SHAP contributions did not reconstruct the saved model output")
    indices = [X.columns.get_loc(name) for name in features]
    selected = [{"feature": name, "mean_abs_shap": float(np.abs(contributions[:, index]).mean()), "mean_signed_shap": float(contributions[:, index].mean())} for name, index in zip(features, indices)]
    local = [{"feature": name, "contribution": float(contributions[0, index])} for name, index in zip(features, indices)]
    return {"method": "tree_shap", "artifact_id": metadata["artifact_id"], "rows_evaluated": len(X), "validation_rows": total_validation,
            "output_label": f"Probability of {classes[output_index]}" if classes is not None else "Predicted target value",
            "features": sorted(selected, key=lambda row: row["mean_abs_shap"], reverse=True),
            "local": {"validation_sample_position": 0, "base_value": base, "model_output": output, "features": local,
                      "other_features_contribution": float(contributions[0].sum() - sum(row["contribution"] for row in local))},
            "scope": "Frozen validation rows only; tree-path-dependent background uses training path counts.",
            "limitations": ["SHAP explains the saved model's output, not causation or future accuracy.",
                            "Correlated features can share contributions differently under other background assumptions.",
                            "Features are encoded model inputs. Only selected features are displayed; other contributions are grouped.",
                            "The local chart explains the first sampled validation row. Feature values and source rows are not returned.",
                            "For multiclass models the first class is explained; binary models explain the second class."]}

"""
D.A.I.S.Y — Model Training Agent (Phase A, item 3)
-------------------------------------------------------
Different shape from every prior agent: NO Gemini call. Reasoning steps
exist in other agents because there's a genuinely subjective judgment to
make (which cleaning action fits, which model is "suitable" for a
profile). Choosing the best-PERFORMING model among ones already trained
is not subjective — it's an objective comparison against a measured
metric. Dressing that up as an "AI decision" would be worse engineering,
not better: slower, more expensive, and no more correct than sorting a
list. See Decisions.md for the explicit reasoning behind this choice.

  sense : prepare_training_data()  -> validates the dataset is ready to
                                       train on (all-numeric features,
                                       drops any stray NaN rows, reuses
                                       model_selection.detect_problem_type
                                       for classification/regression)
  act   : train_and_evaluate()     -> REAL sklearn .fit()/.predict() calls
                                       for each requested candidate model,
                                       real train/test split, real metrics.
                                       Each model's failure is caught and
                                       reported independently — one bad
                                       model doesn't sink the whole run.
  select: deterministic winner     -> highest f1_weighted (classification)
                                       or lowest RMSE (regression). No LLM
                                       involved — this is just sorting.
"""

import hashlib
import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    confusion_matrix,
    balanced_accuracy_score,
    classification_report,
)
from sklearn.model_selection import train_test_split
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC, SVR

from model_selection import detect_problem_type

# Same fixed vocabulary as model_selection.py, mapped to real estimators.
# Kept here rather than imported to avoid this module depending on
# sklearn-object construction happening inside model_selection.py, which
# only ever deals with model NAMES, never instances.
from model_catalog import MODEL_FACTORY


# Which metric decides the winner, and whether higher or lower is better.
PRIMARY_METRIC = {"classification": "f1_weighted", "regression": "rmse"}
HIGHER_IS_BETTER = {"classification": True, "regression": False}


class TrainingDataError(ValueError):
    """Raised for problems that mean training genuinely cannot proceed —
    surfaced to the caller as a clear 400, not a generic crash."""


def _hash_index(index: pd.Index) -> str:
    return hashlib.sha256(repr(index.tolist()).encode("utf-8")).hexdigest()


def _dataset_fingerprint(df: pd.DataFrame) -> str:
    values = pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes()
    return hashlib.sha256(values).hexdigest()


def _fit_recorded_preprocessing(
    train_df: pd.DataFrame,
    steps: list[dict],
    target_column: str,
) -> tuple[pd.DataFrame, list[dict], list[str]]:
    """Refit every learned preprocessing value using training rows only."""
    import agents
    import feature_engineering

    current = train_df.copy()
    fitted: list[dict] = []
    ignored_target_steps: list[str] = []
    for saved in steps:
        kind = saved.get("type")
        column = saved.get("column")
        if kind == "normalize":
            from daisy_predict import normalize_input
            current = normalize_input(current, saved)
            fitted.append(dict(saved))
            continue
        if (target_column is not None and column == target_column) or kind == "drop_rows_missing_target":
            ignored_target_steps.append(kind)
            continue

        action = {
            key: saved[key]
            for key in ("type", "column", "strategy", "column_b", "value")
            if key in saved
        }
        if kind == "impute" and action.get("strategy") not in {"mean", "median", "mode"}:
            action["value"] = saved.get("fill")

        if kind in agents.ACTION_HANDLERS:
            current, report = agents.apply_cleaning_plan(current, [action], fitted_steps=fitted)
        elif kind in feature_engineering.ACTION_HANDLERS:
            current, report = feature_engineering.apply_feature_engineering_plan(
                current, [action], target_column=target_column, fitted_steps=fitted
            )
        else:
            raise TrainingDataError(f"Cannot reproduce preprocessing step '{kind}' during training")
        if not report or report[0]["status"] != "success":
            message = report[0].get("message", "unknown preprocessing failure") if report else "no result"
            raise TrainingDataError(f"Could not fit preprocessing step '{kind}' on training data: {message}")
    return current, fitted, ignored_target_steps


def prepare_split_data(
    df: pd.DataFrame,
    target_column: str,
    problem_type: str,
    test_size: float,
    random_state: int,
    raw_df: pd.DataFrame | None = None,
    preprocessing_steps: list[dict] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, dict, list[dict], dict]:
    """Create a deterministic split and fit preprocessing on its train fold only."""
    if raw_df is None:
        X, y, warnings = prepare_training_data(df, target_column)
        stratify = y if problem_type == "classification" and y.value_counts().min() >= 2 else None
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state, stratify=stratify
            )
        except ValueError as exc:
            raise TrainingDataError(f"Could not create train/test split: {exc}") from exc
        schema = {
            "feature_columns": X.columns.tolist(),
            "input_columns": X.columns.tolist(),
            "dataset_fingerprint": _dataset_fingerprint(df),
            "train_index_hash": _hash_index(X_train.index),
            "test_index_hash": _hash_index(X_test.index),
            "leakage_free_preprocessing": False,
        }
        return X_train, X_test, y_train, y_test, warnings, list(preprocessing_steps or []), schema

    if target_column not in raw_df.columns:
        raise TrainingDataError(f"Target column '{target_column}' not found in original dataset")
    source = raw_df.copy()
    if any(step.get("type") == "normalize" for step in preprocessing_steps or []):
        source = source.replace(r"^\s*$", np.nan, regex=True)
        missing_tokens = ["NA", "N/A", "na", "n/a", "NULL", "null", "None", "none", "?", "-"]
        for column in source.select_dtypes(include=["object", "string"]).columns:
            source[column] = source[column].replace(missing_tokens, np.nan)
    missing_target_count = int(source[target_column].isna().sum())
    source = source.dropna(subset=[target_column])
    remove_duplicates = any(step.get("type") == "drop_duplicates" for step in preprocessing_steps or [])
    duplicate_count = int(source.duplicated().sum()) if remove_duplicates else 0
    if remove_duplicates:
        # Exact duplicates must not be allowed to land on opposite sides of the
        # split. Removing them uses no learned statistics and is deterministic.
        source = source.drop_duplicates()
    if len(source) < 10:
        raise TrainingDataError("Not enough rows with a target value to create a meaningful train/test split")

    y_for_split = source[target_column]
    stratify = y_for_split if problem_type == "classification" and y_for_split.value_counts().min() >= 2 else None
    try:
        train_index, test_index = train_test_split(
            source.index, test_size=test_size, random_state=random_state, stratify=stratify
        )
    except ValueError as exc:
        raise TrainingDataError(f"Could not create train/test split: {exc}") from exc

    transformed_train, fitted_steps, ignored = _fit_recorded_preprocessing(
        source.loc[train_index], list(preprocessing_steps or []), target_column
    )
    X_train, y_train, train_warnings = prepare_training_data(transformed_train, target_column)

    from daisy_predict import transform
    from model_export import required_columns

    feature_columns = X_train.columns.tolist()
    input_columns = required_columns(feature_columns, fitted_steps)
    bundle = {
        "input_columns": input_columns,
        "feature_columns": feature_columns,
        "target_column": target_column,
        "preprocessing": fitted_steps,
    }
    try:
        X_test = transform(bundle, source.loc[test_index])
    except (ValueError, TypeError) as exc:
        raise TrainingDataError(f"Could not transform the held-out test data: {exc}") from exc
    y_test = source.loc[test_index, target_column]

    warnings = {
        "rows_dropped_for_missing_values": train_warnings["rows_dropped_for_missing_values"],
        "rows_missing_target_excluded_before_split": missing_target_count,
        "duplicate_rows_excluded_before_split": duplicate_count,
        "rows_used": len(X_train) + len(X_test),
        "target_preprocessing_ignored": sorted(set(ignored)),
    }
    schema = {
        "feature_columns": feature_columns,
        "input_columns": input_columns,
        "feature_dtypes": {column: str(X_train[column].dtype) for column in feature_columns},
        "dataset_fingerprint": _dataset_fingerprint(raw_df),
        "train_index_hash": _hash_index(X_train.index),
        "test_index_hash": _hash_index(X_test.index),
        "leakage_free_preprocessing": True,
    }
    return X_train, X_test, y_train, y_test, warnings, fitted_steps, schema


def prepare_training_data(
    df: pd.DataFrame, target_column: str
) -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    """The 'sense' step. Validates readiness, does NOT silently fix
    everything — non-numeric feature columns are a hard error, since
    that means Feature Engineering wasn't run (or didn't finish), and
    guessing an encoding here would hide that upstream problem rather
    than surface it."""
    if target_column not in df.columns:
        raise TrainingDataError(f"Target column '{target_column}' not found in dataset")

    feature_columns = [c for c in df.columns if c != target_column]
    if not feature_columns:
        raise TrainingDataError("Dataset has no feature columns other than the target")

    non_numeric = [c for c in feature_columns if not pd.api.types.is_numeric_dtype(df[c])]
    if non_numeric:
        raise TrainingDataError(
            "These feature columns are not numeric, so the model can't train on them "
            f"directly: {non_numeric}. Run the Feature Engineering Agent first to encode "
            "them (e.g. encode_categorical)."
        )

    working = df[feature_columns + [target_column]].copy()
    n_before = len(working)
    working = working.dropna()
    n_dropped = n_before - len(working)

    if len(working) < 10:
        raise TrainingDataError(
            f"Only {len(working)} complete rows remain after dropping missing values — "
            "not enough to train/test split meaningfully. Need at least 10."
        )

    X = working[feature_columns]
    y = working[target_column]

    warnings: dict[str, Any] = {"rows_dropped_for_missing_values": n_dropped, "rows_used": len(working)}
    return X, y, warnings


def _classification_metrics(y_true, y_pred, y_proba) -> dict:
    metrics = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision_weighted": round(float(precision_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "recall_weighted": round(float(recall_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "f1_weighted": round(float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "f1_macro": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 4),
        "per_class": {key: value for key, value in classification_report(y_true, y_pred, output_dict=True, zero_division=0).items() if key not in {"accuracy", "macro avg", "weighted avg"}},
    }
    # ROC-AUC only well-defined for binary classification with predicted probabilities
    if y_proba is not None and y_proba.shape[1] == 2 and len(set(y_true)) == 2:
        try:
            metrics["roc_auc"] = round(float(roc_auc_score(y_true, y_proba[:, 1])), 4)
        except Exception:
            pass  # not fatal — some edge cases (e.g. single-class test fold) can't compute this
    return metrics


def _regression_metrics(y_true, y_pred) -> dict:
    mse = mean_squared_error(y_true, y_pred)
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse": round(float(np.sqrt(mse)), 4),
        "r2": round(float(r2_score(y_true, y_pred)), 4),
    }


def score_final_model(winner, model_name, problem_type, X_train, X_test, y_train, y_test, warnings):
    """Score an already fitted estimator; never refit the chosen winner."""
    predictions = winner.predict(X_test)
    if problem_type == "classification":
        probabilities = winner.predict_proba(X_test) if hasattr(winner, "predict_proba") else None
        test_metrics = _classification_metrics(y_test, predictions, probabilities)
        baseline = DummyClassifier(strategy="most_frequent").fit(X_train, y_train)
        baseline_metrics = _classification_metrics(y_test, baseline.predict(X_test), None)
    else:
        test_metrics = _regression_metrics(y_test, predictions)
        baseline = DummyRegressor(strategy="mean").fit(X_train, y_train)
        baseline_metrics = _regression_metrics(y_test, baseline.predict(X_test))
    train_predictions = winner.predict(X_train)
    train_metrics = _classification_metrics(y_train, train_predictions, None) if problem_type == "classification" else _regression_metrics(y_train, train_predictions)
    metric = "f1_weighted" if problem_type == "classification" else "r2"
    report = {"model": model_name, "problem_type": problem_type, "n_train": len(X_train), "n_test": len(X_test),
              "warnings": warnings, "train_metrics": train_metrics, "test_metrics": test_metrics,
              "baseline_test_metrics": baseline_metrics, "primary_metric": metric,
              "train_test_gap": round(train_metrics[metric] - test_metrics[metric], 4)}
    if problem_type == "classification":
        labels = sorted(pd.concat([y_train, y_test]).unique().tolist())
        report["confusion_matrix"] = {"labels": [str(label) for label in labels], "matrix": confusion_matrix(y_test, predictions, labels=labels).tolist()}
    else:
        residuals = np.asarray(y_test) - np.asarray(predictions)
        report["residuals"] = {"mean": round(float(residuals.mean()), 4), "std": round(float(residuals.std()), 4), "min": round(float(residuals.min()), 4), "max": round(float(residuals.max()), 4)}
    return report


def reserved_partitions(source, test_size=0.2, random_state=42, configuration=None):
    """Reserve folds before target-dependent decisions, including AI planning."""
    if configuration:
        from training_config import configured_partitions
        try:
            return configured_partitions(source, configuration, random_state)
        except (ValueError, TypeError) as exc:
            raise TrainingDataError(f"Study split is invalid: {exc}") from exc
    source = source.drop_duplicates()
    if not source.index.is_unique or len(source) < 15:
        raise TrainingDataError("At least 15 uniquely indexed rows are needed for train/validation/test evaluation")
    try:
        development, test = train_test_split(source.index, test_size=test_size, random_state=random_state)
        train, validation = train_test_split(development, test_size=0.25, random_state=random_state)
    except ValueError as exc:
        raise TrainingDataError(f"Could not reserve evaluation folds: {exc}") from exc
    return source, train, validation, test


def planning_frame(source, test_size=0.2, random_state=42, configuration=None):
    source, train, _, _ = reserved_partitions(source, test_size, random_state, configuration)
    return source.loc[train].copy()


def prepare_three_way_data(df, target_column, problem_type, test_size, random_state, raw_df=None, preprocessing_steps=None, configuration=None):
    source, train_ids, validation_ids, test_ids = reserved_partitions(raw_df if raw_df is not None else df, test_size, random_state, configuration)
    if target_column not in source:
        raise TrainingDataError(f"Target column '{target_column}' not found in dataset")
    # Exclude missing targets after partitioning so planning cannot see test rows.
    train_raw = source.loc[train_ids].dropna(subset=[target_column])
    validation_raw = source.loc[validation_ids].dropna(subset=[target_column])
    test_raw = source.loc[test_ids].dropna(subset=[target_column])
    if min(len(validation_raw), len(test_raw)) < 2:
        raise TrainingDataError("Validation and test folds need at least two labeled rows each")
    steps = list(preprocessing_steps or [])
    if raw_df is not None:
        transformed, fitted, ignored = _fit_recorded_preprocessing(train_raw, steps, target_column)
    else:
        transformed, fitted, ignored = train_raw, steps, []
    X_train, y_train, warnings = prepare_training_data(transformed, target_column)
    from daisy_predict import transform
    from model_export import required_columns
    features = X_train.columns.tolist()
    inputs = required_columns(features, fitted) if raw_df is not None else features
    bundle = {"input_columns": inputs, "feature_columns": features, "target_column": target_column, "preprocessing": fitted}
    try:
        X_validation = transform(bundle, validation_raw) if raw_df is not None else validation_raw[features].astype(float)
        X_test = transform(bundle, test_raw) if raw_df is not None else test_raw[features].astype(float)
        if not np.isfinite(X_validation.to_numpy()).all() or not np.isfinite(X_test.to_numpy()).all():
            raise ValueError("Missing or infinite held-out feature values")
    except (TypeError, ValueError) as exc:
        raise TrainingDataError(f"Could not transform held-out data: {exc}") from exc
    warnings.update(target_preprocessing_ignored=sorted(set(ignored)),
                    duplicate_rows_excluded_before_split=int(len(raw_df if raw_df is not None else df) - len(source)),
                    rows_missing_target_excluded_before_split=int(source[target_column].isna().sum()),
                    class_imbalance=bool(problem_type == "classification" and y_train.value_counts(normalize=True).max() >= 0.8),
                    small_test_fold=len(X_test) < 30)
    schema = {"feature_columns": features, "input_columns": inputs,
              "feature_dtypes": {c: str(X_train[c].dtype) for c in features},
              "dataset_fingerprint": _dataset_fingerprint(source),
              "train_index_hash": _hash_index(X_train.index),
              "validation_index_hash": _hash_index(X_validation.index),
              "test_index_hash": _hash_index(X_test.index),
              "split_strategy": configuration["split_strategy"] if configuration else "random_train_validation_test", "leakage_free_preprocessing": raw_df is not None}
    return X_train, X_validation, X_test, y_train, validation_raw[target_column], test_raw[target_column], warnings, fitted, schema


def train_and_evaluate(
    df: pd.DataFrame,
    target_column: str,
    candidate_models: list[str],
    test_size: float = 0.2,
    random_state: int = 42,
    fitted_models: dict | None = None,
    raw_df: pd.DataFrame | None = None,
    preprocessing_steps: list[dict] | None = None,
    fitted_preprocessing: list | None = None,
    configuration: dict | None = None,
    finalize_test: bool = True,
    evaluation_state: dict | None = None,
) -> dict:
    """The 'act' step. Real fit/predict for every candidate. Each model's
    failure is isolated — reported, not fatal to the whole run."""
    problem_info = detect_problem_type(planning_frame(raw_df if raw_df is not None else df, test_size, random_state, configuration), target_column, configuration.get("problem_type") if configuration else None)
    problem_type = problem_info["problem_type"]

    if not candidate_models:
        raise TrainingDataError("Select at least one candidate model")
    if not 0 < test_size < 1:
        raise TrainingDataError("test_size must be between 0 and 1")

    unknown = [m for m in candidate_models if m not in MODEL_FACTORY]
    if unknown:
        raise TrainingDataError(f"Unknown model name(s): {unknown}")

    wrong_bucket = [
        m
        for m in candidate_models
        if (problem_type == "classification" and m not in _classification_names())
        or (problem_type == "regression" and m not in _regression_names())
    ]
    if wrong_bucket:
        raise TrainingDataError(
            f"These models don't match the detected problem type ({problem_type}): {wrong_bucket}"
        )

    X_train, X_validation, X_test, y_train, y_validation, y_test, warnings, fitted_steps, schema = prepare_three_way_data(
        df,
        target_column,
        problem_type,
        test_size,
        random_state,
        raw_df=raw_df,
        preprocessing_steps=preprocessing_steps,
        configuration=configuration,
    )
    if fitted_preprocessing is not None:
        fitted_preprocessing.extend(fitted_steps)

    primary_metric = configuration.get("primary_metric", "auto") if configuration else "auto"
    if primary_metric == "auto": primary_metric = PRIMARY_METRIC[problem_type]
    allowed_metrics = {"f1_weighted", "f1_macro", "accuracy", "balanced_accuracy"} if problem_type == "classification" else {"rmse", "mae", "r2"}
    if primary_metric not in allowed_metrics:
        raise TrainingDataError("Selected metric does not match the detected task type. Choose the task explicitly during review.")
    if evaluation_state is not None:
        evaluation_state.update(train_row_ids=X_train.index.tolist(), test_row_ids=X_test.index.tolist())

    results = []
    estimators = {}
    for model_name in candidate_models:
        entry: dict[str, Any] = {"model": model_name}
        start = time.time()
        try:
            estimator = MODEL_FACTORY[model_name]()
            estimator.fit(X_train, y_train)
            y_pred = estimator.predict(X_validation)

            if problem_type == "classification":
                y_proba = estimator.predict_proba(X_validation) if hasattr(estimator, "predict_proba") else None
                entry["metrics"] = _classification_metrics(y_validation, y_pred, y_proba)
            else:
                entry["metrics"] = _regression_metrics(y_validation, y_pred)

            entry["status"] = "success"
            entry["metric_scope"] = "validation"
            estimators[model_name] = estimator
            if fitted_models is not None:
                fitted_models[model_name] = estimator
        except Exception as e:  # noqa: BLE001 — isolate failure to this model only
            entry["status"] = "failed"
            entry["message"] = str(e)
            entry["metrics"] = {}
        entry["training_time_seconds"] = round(time.time() - start, 4)
        results.append(entry)

    higher_is_better = primary_metric not in {"rmse", "mae"}
    successful = [r for r in results if r["status"] == "success" and primary_metric in r["metrics"]]

    best_model = None
    if successful:
        best_model = max(
            successful,
            key=lambda r: r["metrics"][primary_metric] if higher_is_better else -r["metrics"][primary_metric],
        )["model"]

    final_test_metrics = None
    baseline_metrics = None
    evaluation_data = None
    if best_model and finalize_test:
        evaluation_data = score_final_model(estimators[best_model], best_model, problem_type, X_train, X_test, y_train, y_test, warnings)
        final_test_metrics = evaluation_data["test_metrics"]
        baseline_metrics = evaluation_data["baseline_test_metrics"]

    return {
        "problem_type": problem_type,
        "primary_metric": primary_metric,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "n_validation": len(X_validation),
        "selection_scope": "validation",
        "split_strategy": schema["split_strategy"],
        "training_config": configuration,
        "final_test_metrics": final_test_metrics,
        "baseline_test_metrics": baseline_metrics,
        "evaluation_data": evaluation_data,
        "test_size": test_size,
        "random_state": random_state,
        "feature_columns": schema["feature_columns"],
        "input_columns": schema["input_columns"],
        "feature_dtypes": schema.get("feature_dtypes", {}),
        "dataset_fingerprint": schema["dataset_fingerprint"],
        "train_index_hash": schema["train_index_hash"],
        "test_index_hash": schema["test_index_hash"],
        "validation_index_hash": schema["validation_index_hash"],
        "leakage_free_preprocessing": schema["leakage_free_preprocessing"],
        "warnings": warnings,
        "results": results,
        "best_model": best_model,
    }


def _classification_names() -> set[str]:
    from model_selection import CLASSIFICATION_MODELS

    return set(CLASSIFICATION_MODELS)


def _regression_names() -> set[str]:
    from model_selection import REGRESSION_MODELS

    return set(REGRESSION_MODELS)

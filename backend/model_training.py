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
)
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC, SVR

from model_selection import detect_problem_type

# Same fixed vocabulary as model_selection.py, mapped to real estimators.
# Kept here rather than imported to avoid this module depending on
# sklearn-object construction happening inside model_selection.py, which
# only ever deals with model NAMES, never instances.
MODEL_FACTORY = {
    "logistic_regression": lambda: LogisticRegression(max_iter=1000, random_state=42),
    "random_forest_classifier": lambda: RandomForestClassifier(random_state=42),
    "gradient_boosting_classifier": lambda: GradientBoostingClassifier(random_state=42),
    "knn_classifier": lambda: KNeighborsClassifier(),
    "svm_classifier": lambda: SVC(probability=True, random_state=42),
    "linear_regression": lambda: LinearRegression(),
    "random_forest_regressor": lambda: RandomForestRegressor(random_state=42),
    "gradient_boosting_regressor": lambda: GradientBoostingRegressor(random_state=42),
    "ridge_regression": lambda: Ridge(),
    "svm_regressor": lambda: SVR(),
}

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
            fitted.append({"type": "normalize"})
            continue
        if column == target_column or kind == "drop_rows_missing_target":
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
    }
    # ROC-AUC only well-defined for binary classification with predicted probabilities
    if y_proba is not None and len(set(y_true)) == 2:
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
) -> dict:
    """The 'act' step. Real fit/predict for every candidate. Each model's
    failure is isolated — reported, not fatal to the whole run."""
    problem_info = detect_problem_type(df, target_column)
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

    X_train, X_test, y_train, y_test, warnings, fitted_steps, schema = prepare_split_data(
        df,
        target_column,
        problem_type,
        test_size,
        random_state,
        raw_df=raw_df,
        preprocessing_steps=preprocessing_steps,
    )
    if fitted_preprocessing is not None:
        fitted_preprocessing.extend(fitted_steps)

    results = []
    for model_name in candidate_models:
        entry: dict[str, Any] = {"model": model_name}
        start = time.time()
        try:
            estimator = MODEL_FACTORY[model_name]()
            estimator.fit(X_train, y_train)
            y_pred = estimator.predict(X_test)

            if problem_type == "classification":
                y_proba = estimator.predict_proba(X_test) if hasattr(estimator, "predict_proba") else None
                entry["metrics"] = _classification_metrics(y_test, y_pred, y_proba)
            else:
                entry["metrics"] = _regression_metrics(y_test, y_pred)

            entry["status"] = "success"
            if fitted_models is not None:
                fitted_models[model_name] = estimator
        except Exception as e:  # noqa: BLE001 — isolate failure to this model only
            entry["status"] = "failed"
            entry["message"] = str(e)
            entry["metrics"] = {}
        entry["training_time_seconds"] = round(time.time() - start, 4)
        results.append(entry)

    primary_metric = PRIMARY_METRIC[problem_type]
    higher_is_better = HIGHER_IS_BETTER[problem_type]
    successful = [r for r in results if r["status"] == "success" and primary_metric in r["metrics"]]

    best_model = None
    if successful:
        best_model = max(
            successful,
            key=lambda r: r["metrics"][primary_metric] if higher_is_better else -r["metrics"][primary_metric],
        )["model"]

    return {
        "problem_type": problem_type,
        "primary_metric": primary_metric,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "test_size": test_size,
        "random_state": random_state,
        "feature_columns": schema["feature_columns"],
        "input_columns": schema["input_columns"],
        "feature_dtypes": schema.get("feature_dtypes", {}),
        "dataset_fingerprint": schema["dataset_fingerprint"],
        "train_index_hash": schema["train_index_hash"],
        "test_index_hash": schema["test_index_hash"],
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

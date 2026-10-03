"""Capture fitted preprocessing and persist portable model ZIPs, without raw rows."""
import io
import hashlib
import json
import os
import platform
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import scipy
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler


def capture_operation(df, action):
    """Snapshot learned values from the same input used by the stage handler."""
    kind, col = action.get("type"), action.get("column")
    step = {"type": kind, "column": col, "strategy": action.get("strategy")}
    for key in ("column_b", "value"):
        if key in action:
            step[key] = action[key]
    if kind == "impute":
        series = df[col]
        strategy = step["strategy"]
        if strategy == "mean":
            fill = series.mean()
        elif strategy == "median":
            fill = series.median()
        elif strategy == "mode":
            modes = series.mode(dropna=True)
            fill = modes.iloc[0] if not modes.empty else None
        else:
            fill = action.get("value")
        step["fill"] = fill
    elif kind == "handle_outliers":
        q1, q3 = df[col].quantile(.25), df[col].quantile(.75)
        step.update(lower=q1 - 1.5 * (q3 - q1), upper=q3 + 1.5 * (q3 - q1), preserve_zero=True)
    elif kind == "strip_whitespace":
        step["columns"] = [col] if col else df.select_dtypes(include=["object", "string"]).columns.tolist()
    elif kind == "scale_numeric":
        scaler = {"standard": StandardScaler, "minmax": MinMaxScaler, "robust": RobustScaler}[step["strategy"]]()
        step["scaler"] = scaler.fit(df[[col]].astype(float))
    elif kind == "encode_categorical":
        if step["strategy"] == "onehot":
            step["categories"] = pd.Categorical(df[col]).categories.tolist()
            step["output_columns"] = pd.get_dummies(df[col], prefix=col, dummy_na=False).columns.tolist()
        elif step["strategy"] == "label":
            values = sorted(df[col].dropna().astype(str).unique())
            step["mapping"] = {value: index for index, value in enumerate(values)}
        else:
            step["mapping"] = df[col].value_counts(normalize=True).to_dict()
    return step


def required_columns(features, steps):
    required = set(features)
    for step in reversed(steps):
        col = step.get("column")
        outputs = step.get("output_columns", [])
        if step["type"] == "extract_datetime_features":
            outputs = [f"{col}_{part}" for part in ("year", "month", "day", "dayofweek")]
        if required.intersection(outputs):
            required.difference_update(outputs)
            required.add(col)
    return sorted(required)


def artifact_directory():
    directory = Path(os.environ.get("DAISY_MODEL_DIR", Path(__file__).with_name("artifacts")))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def artifact_path(artifact_id):
    try:
        identifier = str(uuid.UUID(artifact_id))
    except (ValueError, AttributeError):
        raise ValueError("Invalid model artifact ID")
    return artifact_directory() / f"{identifier}.zip"


def artifact_owned_by(artifact_id: str, owner_id: str) -> bool:
    """Read trusted server metadata, never a user-provided ZIP or joblib file."""
    if not isinstance(owner_id, str) or not owner_id:
        return False
    try:
        path = artifact_path(artifact_id)
        manifest = json.loads(path.with_suffix(".owner.json").read_text(encoding="utf-8"))
        return (
            isinstance(manifest, dict)
            and manifest.get("format_version") == 1
            and manifest.get("artifact_id") == path.stem
            and manifest.get("owner_id") == owner_id
        )
    except (OSError, ValueError, TypeError):
        return False


def export_model(estimator, df, target_column, steps, training_result, dataset_id, workflow_id, source_df=None, *, owner_id=None):
    from daisy_predict import transform

    if owner_id is not None and (not isinstance(owner_id, str) or not owner_id):
        raise ValueError("An authenticated artifact owner is required")
    features = training_result.get("feature_columns") or [col for col in df.columns if col != target_column]
    input_columns = (
        training_result.get("input_columns")
        if training_result.get("leakage_free_preprocessing")
        else required_columns(features, steps)
    )
    bundle = {"format_version": 1, "estimator": estimator, "preprocessing": steps,
              "feature_columns": features, "input_columns": input_columns, "target_column": target_column}
    # Fail closed if a future stage handler changes without updating its export replay.
    if source_df is not None and training_result.get("leakage_free_preprocessing"):
        replayed = transform(bundle, source_df.dropna(subset=[target_column]))
        if replayed.columns.tolist() != features or replayed.empty:
            raise AssertionError("Saved preprocessing did not reproduce the trained feature schema")
    elif source_df is not None:
        complete = df.dropna()
        replayed = transform(bundle, source_df.loc[complete.index])
        np.testing.assert_allclose(replayed.to_numpy(dtype=float), complete[features].to_numpy(dtype=float), rtol=1e-9, atol=1e-9)
    versions = {"scikit-learn": sklearn.__version__, "pandas": pd.__version__,
                "numpy": np.__version__, "scipy": scipy.__version__, "joblib": joblib.__version__}
    model_parameters = {
        key: value if value is None or isinstance(value, (str, int, float, bool)) else str(value)
        for key, value in estimator.get_params(deep=True).items()
    }
    identifier = str(uuid.uuid4())
    metadata = {"format_version": 1, "artifact_id": identifier,
                "experiment_id": training_result.get("experiment_id"),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model": training_result["best_model"], "target_column": target_column,
                "problem_type": training_result["problem_type"], "primary_metric": training_result["primary_metric"],
                "training_results": training_result["results"], "n_train": training_result["n_train"],
                "n_test": training_result["n_test"], "dataset_id": dataset_id, "workflow_id": workflow_id,
                "test_size": training_result["test_size"], "random_state": training_result["random_state"],
                "dataset_fingerprint": training_result.get("dataset_fingerprint"),
                "train_index_hash": training_result.get("train_index_hash"),
                "test_index_hash": training_result.get("test_index_hash"),
                "validation_index_hash": training_result.get("validation_index_hash"),
                "n_validation": training_result.get("n_validation"),
                "selection_scope": training_result.get("selection_scope", "test"),
                "training_config": training_result.get("training_config"),
                "training_reference": training_result.get("training_reference"),
                "split_strategy": training_result.get("split_strategy"),
                "final_test_metrics": training_result.get("final_test_metrics"),
                "baseline_test_metrics": training_result.get("baseline_test_metrics"),
                "leakage_free_preprocessing": training_result.get("leakage_free_preprocessing", False),
                "python_version": platform.python_version(), "dependencies": versions,
                "model_parameters": model_parameters,
                "input_columns": input_columns, "feature_columns": features,
                "preprocessing_steps": [{k: s[k] for k in ("type", "column", "strategy") if k in s} for s in steps],
                "limitations": ["Candidates are compared on validation scores. Null final-test metrics mean this package has not been finalized.",
                    "The split strategy must match the deployment setting; random splits assume independent rows.",
                    "Estimator is the exact train-split model scored in training, not a refit on all rows.",
                    "Inference preserves row count. Training-only row removal and target transforms are not replayed.",
                    "Unseen categories: one-hot -> all zeros; label -> -1; frequency -> 0.",
                    "Use only trusted joblib files; loading a pickle-based model can execute code."]}
    payload = io.BytesIO()
    joblib.dump(bundle, payload, compress=3)
    schema = {"required_columns": input_columns, "feature_columns_after_preprocessing": features,
              "target_column_not_required": target_column,
              "input_dtypes": {col: str(source_df[col].dtype) for col in input_columns} if source_df is not None else {},
              "feature_dtypes": training_result.get("feature_dtypes") or {col: str(df[col].dtype) for col in features}}
    readme = f"""# DAISY trained model: {training_result['best_model']}

This package contains the fitted winning estimator and saved preprocessing values.
It works independently of DAISY, Groq, or NVIDIA. No raw training rows are included.

## Predict on new data

Use Python {platform.python_version()} (the training version) in a fresh environment:

    python -m pip install -r requirements.txt
    python daisy_predict.py new_data.csv predictions.csv

Provide the original feature values in the required columns listed in input_schema.json.
Do not pre-encode or pre-scale them. The target column is not required. Extra columns
are ignored after preprocessing. The helper preserves input row order and outputs one
prediction per row; unresolved missing/infinite values produce a clear error.

Python usage:

    import pandas as pd
    from daisy_predict import load_model, predict
    predictions = predict(load_model(), pd.read_csv("new_data.csv", dtype=str, keep_default_na=False))

model.joblib is a dictionary with estimator, preprocessing, feature_columns,
input_columns, and target_column. Use the helper to apply saved preprocessing;
calling the estimator directly requires already-transformed features in saved order.

## Interpretation and trust

This is the exact estimator scored during training, not a newly refitted model.
DAISY reserved train/validation/test folds before fitting imputation, scaling, and encoding;
the held-out rows did not influence those learned preprocessing values.
Candidate scores in metadata are validation scores. Null final-test metrics mean
final evaluation has not run. DAISY finalization produces a separate report with
the winner's test scores and a simple baseline; this package remains immutable.
The split strategy is recorded in metadata. Random splits assume independent rows.
Training-only duplicate/outlier/target-missing row removal is not applied at inference.
Target values reflect any cleaning performed on the target during the training run.
Unseen categories map to zero one-hot columns, -1 labels, or zero frequency.
Only load model.joblib from a trusted source: joblib/pickle loading can execute code.
Keep the pinned dependency versions for reliable compatibility.
New packages include checksums.json. The helper verifies package files before
loading the estimator and rejects changed or missing files. Extract the complete
ZIP together. Checksums detect accidental corruption; they are not a signature
and do not make an untrusted pickle safe. Older packages without a manifest still load.
"""
    destination = artifact_path(identifier)
    temporary = destination.with_suffix(".tmp")
    owner_path = destination.with_suffix(".owner.json")
    owner_temporary = destination.with_suffix(".owner.tmp")
    try:
        files = {
            "model.joblib": payload.getvalue(),
            "metadata.json": json.dumps(metadata, indent=2, allow_nan=False).encode("utf-8"),
            "input_schema.json": json.dumps(schema, indent=2).encode("utf-8"),
            "requirements.txt": ("\n".join(f"{name}=={version}" for name, version in versions.items()) + "\n").encode("utf-8"),
            "README.md": readme.encode("utf-8"),
            "daisy_predict.py": Path(__file__).with_name("daisy_predict.py").read_bytes(),
        }
        checksums = {"format_version": 1, "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
            archive.writestr("checksums.json", json.dumps(checksums, indent=2))
        if owner_id is not None:
            # Ownership stays on the server, outside the downloadable package.
            # Publish it before the ZIP so a visible package never lacks its owner.
            owner_temporary.write_text(json.dumps({
                "format_version": 1, "artifact_id": identifier, "owner_id": owner_id,
            }), encoding="utf-8")
            owner_temporary.replace(owner_path)
        temporary.replace(destination)
    except Exception:
        owner_path.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)
        owner_temporary.unlink(missing_ok=True)
    return {"artifact_id": identifier, "filename": f"daisy-{training_result['best_model']}-{identifier}.zip",
            "model": training_result["best_model"], "input_columns": input_columns}

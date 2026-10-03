"""Portable inference helper included in DAISY model downloads.

    python daisy_predict.py new_data.csv predictions.csv
    from daisy_predict import load_model, predict
    predictions = predict(load_model(), dataframe)
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

import joblib
import numpy as np
import pandas as pd


def verify_package(path):
    """Detect incomplete/changed packages, not source authenticity or pickle safety."""
    path = Path(path)
    manifest_path = path.with_name("checksums.json")
    if not manifest_path.exists():
        return False  # Older DAISY packages remain supported.
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest["files"]
        if manifest["format_version"] != 1 or not isinstance(files, dict) or path.name not in files:
            raise ValueError("Invalid checksum manifest")
        for name, expected in files.items():
            if not isinstance(name, str) or name in {".", ".."} or "/" in name or "\\" in name or ":" in name:
                raise ValueError("Invalid package filename")
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise ValueError("Invalid package checksum")
            member = path.with_name(name)
            digest = hashlib.sha256()
            with member.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise ValueError(f"Checksum mismatch: {name}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"Model package integrity check failed: {exc}. Extract a fresh trusted download.") from exc
    return True


def load_model(path=None):
    # joblib uses pickle: load only a model package you trust.
    path = Path(path or Path(__file__).with_name("model.joblib"))
    verify_package(path)
    return joblib.load(path)


def normalize_input(data, policy):
    df = data.copy()
    if policy.get("blank_is_missing", True):
        df = df.replace(r"^\s*$", np.nan, regex=True)
    defaults = ["NA", "N/A", "na", "n/a", "NULL", "null", "None", "none", "?", "-"]
    tokens = policy.get("missing_tokens", defaults)
    for name in df.columns:
        if pd.api.types.is_object_dtype(df[name]) or pd.api.types.is_string_dtype(df[name]):
            df[name] = df[name].replace([*tokens, *policy.get("column_tokens", {}).get(name, [])], np.nan)
        kind = policy.get("column_types", {}).get(name, "auto")
        if kind == "numeric":
            df[name] = pd.to_numeric(df[name], errors="raise")
        elif kind == "text":
            df[name] = df[name].astype("string")
        elif kind == "datetime":
            df[name] = pd.to_datetime(df[name], errors="raise", utc=True)
        elif kind == "auto" and not pd.api.types.is_numeric_dtype(df[name]):
            # Infer a numeric type only when every nonmissing value is numeric.
            converted = pd.to_numeric(df[name], errors="coerce")
            leading_zeros = df[name].dropna().astype(str).str.match(r"^[+-]?0\d+").any()
            if not leading_zeros and df[name].notna().any() and converted.notna().sum() == df[name].notna().sum():
                df[name] = converted
    return df


def transform(bundle, data):
    if not isinstance(data, pd.DataFrame):
        raise ValueError("Prediction input must be a pandas DataFrame.")
    if data.columns.duplicated().any():
        raise ValueError("Input contains duplicate column names.")
    missing = set(bundle["input_columns"]) - set(data.columns)
    if missing:
        raise ValueError(f"Missing required input columns: {sorted(missing)}")
    df = data.drop(columns=[bundle["target_column"]], errors="ignore").copy()
    for step in bundle["preprocessing"]:
        kind, col = step["type"], step.get("column")
        if kind == "normalize":
            df = normalize_input(df, step)
        elif kind == "strip_whitespace":
            for name in step["columns"]:
                if name in df and pd.api.types.is_string_dtype(df[name]):
                    df[name] = df[name].map(lambda value: value.strip() if isinstance(value, str) else value)
        elif kind in {"drop_column", "drop_low_variance_column", "drop_high_correlation_column"}:
            df = df.drop(columns=[col], errors="ignore")
        elif col not in df:
            continue  # Target-only and unused-column operations are not needed at inference.
        elif kind == "zero_to_missing":
            df[col] = df[col].mask(df[col].eq(0))
        elif kind == "impute":
            df[col] = df[col].fillna(step["fill"])
        elif kind == "fix_dtype":
            strategy = step["strategy"]
            if strategy == "to_numeric":
                df[col] = pd.to_numeric(df[col], errors="coerce")
            elif strategy == "to_datetime":
                df[col] = pd.to_datetime(df[col], errors="coerce")
            elif strategy == "to_category":
                df[col] = df[col].astype("category")
        elif kind == "handle_outliers":
            if step["strategy"] == "iqr_clip":
                zero_mask = df[col].eq(0) if step.get("preserve_zero") else None
                df[col] = df[col].clip(lower=step["lower"], upper=step["upper"])
                if zero_mask is not None:
                    df[col] = df[col].mask(zero_mask, 0)
            # Training-only row removal is never applied to inference batches.
        elif kind == "scale_numeric":
            df[col] = step["scaler"].transform(df[[col]].astype(float)).ravel()
        elif kind == "extract_datetime_features":
            dates = pd.to_datetime(df[col], errors="coerce")
            for part in ("year", "month", "day", "dayofweek"):
                df[f"{col}_{part}"] = getattr(dates.dt, part)
            df = df.drop(columns=[col])
        elif kind == "encode_categorical":
            strategy = step["strategy"]
            if strategy == "onehot":
                # Frozen training vocabulary: unseen categories produce all zeros.
                known = df[col].where(df[col].isin(step["categories"]))
                values = pd.Categorical(known, categories=step["categories"])
                encoded = pd.get_dummies(values, prefix=col, dummy_na=False)
                df = df.drop(columns=[col])
                for name in step["output_columns"]:
                    df[name] = encoded[name].to_numpy(dtype=int)
            elif strategy == "label":
                df[col] = df[col].astype(str).map(step["mapping"]).fillna(-1)
            else:
                df[col] = df[col].astype(object).map(step["mapping"]).fillna(0.0)
    missing = set(bundle["feature_columns"]) - set(df.columns)
    if missing:
        raise ValueError(f"Preprocessing did not produce features: {sorted(missing)}")
    features = df[bundle["feature_columns"]].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(features.to_numpy(dtype=float)).all():
        raise ValueError("Input has missing or infinite values after saved preprocessing. Supply valid values; rows have not been dropped.")
    return features


def predict(bundle, data):
    features = transform(bundle, data)
    if features.empty:
        return pd.Series([], index=data.index, name="prediction", dtype=object)
    return pd.Series(bundle["estimator"].predict(features), index=data.index, name="prediction")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict using a downloaded DAISY model.")
    parser.add_argument("input_csv")
    parser.add_argument("output_csv", nargs="?", default="predictions.csv")
    parser.add_argument("--model", default=str(Path(__file__).with_name("model.joblib")))
    args = parser.parse_args()
    bundle = load_model(args.model)
    # New packages interpret tokens themselves; historic packages without a
    # normalization step retain their original pandas parsing semantics.
    options = {"dtype": str, "keep_default_na": False} if any(step["type"] == "normalize" for step in bundle["preprocessing"]) else {}
    predict(bundle, pd.read_csv(args.input_csv, **options)).to_csv(args.output_csv, index=False)

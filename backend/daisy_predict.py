"""Portable inference helper included in DAISY model downloads.

    python daisy_predict.py new_data.csv predictions.csv
    from daisy_predict import load_model, predict
    predictions = predict(load_model(), dataframe)
"""
from pathlib import Path
import argparse

import joblib
import numpy as np
import pandas as pd


def load_model(path=None):
    # joblib uses pickle: load only a model package you trust.
    return joblib.load(path or Path(__file__).with_name("model.joblib"))


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
            df = df.replace(r"^\s*$", np.nan, regex=True)
            for name in df.select_dtypes(include=["object", "string"]).columns:
                df[name] = df[name].replace(["NA", "N/A", "na", "n/a", "NULL", "null", "None", "none", "?", "-"], np.nan)
        elif kind == "strip_whitespace":
            for name in step["columns"]:
                if name in df and pd.api.types.is_string_dtype(df[name]):
                    df[name] = df[name].astype(str).str.strip()
        elif kind in {"drop_column", "drop_low_variance_column", "drop_high_correlation_column"}:
            df = df.drop(columns=[col], errors="ignore")
        elif col not in df:
            continue  # Target-only and unused-column operations are not needed at inference.
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
                df[col] = df[col].clip(lower=step["lower"], upper=step["upper"])
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
    predict(load_model(args.model), pd.read_csv(args.input_csv)).to_csv(args.output_csv, index=False)

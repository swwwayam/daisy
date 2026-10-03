"""Bounded, ephemeral CSV inference using saved training-only preprocessing."""
import csv
import io

import numpy as np
import pandas as pd

from daisy_predict import normalize_input, predict


def read_csv(content, bundle):
    header = next(csv.reader(io.StringIO(content.decode("utf-8-sig"))), [])
    if not header or len(header) != len(set(header)):
        raise ValueError("CSV column names must be present and unique")
    if len(header) > 1000:
        raise ValueError("Prediction CSV is limited to 1000 columns")
    options = {"dtype": str, "keep_default_na": False} if any(s["type"] == "normalize" for s in bundle["preprocessing"]) else {}
    frame = pd.read_csv(io.BytesIO(content), nrows=10001, **options)
    if frame.empty or len(frame) > 10000:
        raise ValueError("Supply 1 to 10,000 prediction rows per CSV")
    if frame.size > 1000000 or frame.memory_usage(deep=True).sum() > 64 * 1024 * 1024:
        raise ValueError("Prediction CSV exceeds the 1 million cell / 64 MiB parsed-data limit")
    if len(frame) * len(bundle["feature_columns"]) > 1000000:
        raise ValueError("Saved encoding would exceed one million prediction feature cells. Supply fewer rows.")
    return frame


def diagnostics(bundle, frame):
    current = frame.copy()
    for step in bundle["preprocessing"]:
        if step["type"] == "normalize":
            current = normalize_input(current, step)
    missing = {str(column): int(current[column].isna().sum()) for column in bundle["input_columns"] if column in current}
    unknown = {}
    for step in bundle["preprocessing"]:
        column = step.get("column")
        if step["type"] == "strip_whitespace":
            for name in step["columns"]:
                if name in current:
                    current[name] = current[name].map(lambda value: value.strip() if isinstance(value, str) else value)
        if column not in current:
            continue
        if step["type"] == "zero_to_missing":
            current[column] = current[column].mask(current[column].eq(0))
            missing[column] = int(current[column].isna().sum())
        if step["type"] == "fix_dtype" and step["strategy"] in {"to_numeric", "to_datetime"}:
            current[column] = (pd.to_numeric if step["strategy"] == "to_numeric" else pd.to_datetime)(current[column], errors="coerce")
            missing[column] = int(current[column].isna().sum())
        if step["type"] == "impute":
            current[column] = current[column].fillna(step["fill"])
        if step["type"] == "encode_categorical":
            known = step["categories"] if step["strategy"] == "onehot" else step["mapping"].keys()
            values = current[column].astype(str) if step["strategy"] == "label" else current[column]
            unknown[column] = int((values.notna() & ~values.isin(known)).sum())
    return {"missing_values_before_imputation": missing, "unseen_category_counts": unknown,
            "extra_columns_ignored": sorted(set(frame.columns) - set(bundle["input_columns"]) - {bundle["target_column"]}),
            "input_rows_persisted": False}


def predict_csv(bundle, frame):
    predictions = predict(bundle, frame)
    values = predictions.to_frame()
    # Stable positional IDs let users join results to their original CSV without
    # sending arbitrary input columns back or overwriting a feature named prediction.
    values.insert(0, "input_row", np.arange(len(frame)))
    return values

"""
D.A.I.S.Y — Feature Engineering Agent (Phase A, item 1)
----------------------------------------------------------
Same Sense -> Reason -> Act pattern as the Data Cleaning Agent (agents.py).
Gemini never touches data directly; it only picks from a fixed menu of
actions, executed here deterministically with pandas/scikit-learn.

  sense  : profile_for_feature_engineering()  -> stats relevant to feature
                                                  decisions (cardinality,
                                                  skew, correlation, date-
                                                  like column detection)
  reason : build_feature_engineering_prompt()  -> Gemini returns strict
                                                   JSON actions
  act    : apply_feature_engineering_plan()    -> pandas/sklearn executes,
                                                   reports success/failed/
                                                   skipped + a message

Action menu (fixed, matches project plan agreed 2026-08-16):
  - encode_categorical      (onehot | label | frequency)
  - scale_numeric           (standard | minmax | robust)
  - extract_datetime_features
  - drop_low_variance_column
  - drop_high_correlation_column
"""

import json
import math
from typing import Any

import pandas as pd
from sklearn.preprocessing import (
    LabelEncoder,
    MinMaxScaler,
    RobustScaler,
    StandardScaler,
)


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value


def _looks_like_datetime(series: pd.Series) -> bool:
    """Cheap heuristic sense-check: try parsing a sample, don't force the
    whole column through pd.to_datetime (expensive + noisy on false
    positives like plain integers)."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if not pd.api.types.is_object_dtype(series) and not pd.api.types.is_string_dtype(series):
        return False
    sample = series.dropna().astype(str).head(20)
    if sample.empty:
        return False
    try:
        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        return bool(parsed.notna().mean() >= 0.8)  # 80%+ of sample parses cleanly
    except Exception:
        return False


def profile_for_feature_engineering(df: pd.DataFrame) -> dict:
    """The agent's 'sense' step. Stats only — same discipline as the
    cleaning agent's profile_dataframe(); no raw rows sent to the LLM."""
    columns_profile = []
    numeric_df = df.select_dtypes(include="number")

    for col in df.columns:
        series = df[col]
        info: dict[str, Any] = {
            "name": col,
            "dtype": str(series.dtype),
            "unique_count": int(series.nunique(dropna=True)),
            "unique_ratio": round(series.nunique(dropna=True) / max(len(series), 1), 4),
        }

        if pd.api.types.is_numeric_dtype(series):
            info["is_numeric"] = True
            info["variance"] = _json_safe(round(float(series.var()), 6)) if series.notna().any() else 0.0
            info["skew"] = _json_safe(round(float(series.skew()), 4)) if series.notna().sum() > 2 else None
        else:
            info["is_numeric"] = False
            info["is_datetime_like"] = bool(_looks_like_datetime(series))
            info["cardinality"] = int(series.nunique(dropna=True))

        columns_profile.append(info)

    # High-correlation pairs among numeric columns — candidates for
    # drop_high_correlation_column. Only report pairs, never auto-decide.
    high_corr_pairs = []
    if numeric_df.shape[1] >= 2:
        corr = numeric_df.corr(numeric_only=True).abs()
        for i, col_a in enumerate(corr.columns):
            for col_b in corr.columns[i + 1:]:
                value = corr.loc[col_a, col_b]
                if pd.notna(value) and value >= 0.9:
                    high_corr_pairs.append(
                        {"column_a": col_a, "column_b": col_b, "correlation": round(float(value), 4)}
                    )

    return {
        "n_rows": int(len(df)),
        "n_columns": int(len(df.columns)),
        "columns": columns_profile,
        "high_correlation_pairs": high_corr_pairs,
    }


FEATURE_ENGINEERING_PROMPT_TEMPLATE = """You are DAISY's Feature Engineering Agent, part of a student's ML pipeline project.

You are given a statistical profile of a dataset that has already been cleaned. \
Decide the best sequence of feature engineering actions to prepare it for machine \
learning. Be conservative — only act where the profile clearly justifies it. Every \
action needs a one-sentence, plain-language reason.

DATASET PROFILE:
{profile_json}

Respond with STRICT JSON ONLY — no markdown, no code fences, no commentary. Match exactly:

{{
  "summary": "one short paragraph on the overall feature engineering approach, plain language",
  "actions": [
    {{
      "type": "encode_categorical" | "scale_numeric" | "extract_datetime_features" | "drop_low_variance_column" | "drop_high_correlation_column",
      "column": "exact column name from the profile, or null if the action targets a pair (see column_b)",
      "column_b": "only set for drop_high_correlation_column, the second column in the pair",
      "strategy": "onehot" | "label" | "frequency" | "standard" | "minmax" | "robust" | null,
      "reasoning": "one sentence explaining why"
    }}
  ]
}}

Rules:
- Only use encode_categorical on non-numeric columns.
- Only use scale_numeric on numeric columns with is_numeric true.
- Only use extract_datetime_features on columns where is_datetime_like is true.
- Only use drop_low_variance_column when variance is at or near zero, or unique_count is 1.
- Only use drop_high_correlation_column on pairs already listed in high_correlation_pairs — pick which of the two to drop and put it in "column", with the kept one in "column_b".
- Use exact column names as they appear in the profile — never invent columns.
- Keep actions under 15 items. If no changes are justified, return an empty actions array.
- Every action must include a non-empty reasoning string.
"""


def build_feature_engineering_prompt(profile: dict) -> str:
    return FEATURE_ENGINEERING_PROMPT_TEMPLATE.format(profile_json=json.dumps(profile, indent=2))


def parse_plan(raw_text: str) -> dict:
    """Same defensive parsing as agents.py — Gemini is asked for strict
    JSON but sometimes still wraps it in a code fence."""
    try:
        plan = json.loads(raw_text)
    except json.JSONDecodeError:
        stripped = raw_text.replace("```json", "").replace("```", "").strip()
        plan = json.loads(stripped)

    if not isinstance(plan, dict) or not isinstance(plan.get("actions"), list):
        raise ValueError("Feature engineering plan came back in an unexpected shape")
    return plan


# ---------------------------------------------------------------------------
# Action execution — the 'act' step.
# ---------------------------------------------------------------------------

def _apply_encode_categorical(df, column, strategy, **_):
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    if strategy == "onehot":
        dummies = pd.get_dummies(df[column], prefix=column, dummy_na=False)
        df.drop(columns=[column], inplace=True)
        for dummy_col in dummies.columns:
            df[dummy_col] = dummies[dummy_col].astype(int)
        return f"One-hot encoded '{column}' into {len(dummies.columns)} column(s)"
    elif strategy == "label":
        # pandas >= 3.0's native string dtype rejects assigning ints
        # directly into a string-typed column — cast to object first so
        # the encoded integers can actually be stored.
        encoder = LabelEncoder()
        non_null_mask = df[column].notna()
        encoded_column = df[column].astype(object)
        encoded_column.loc[non_null_mask] = encoder.fit_transform(df.loc[non_null_mask, column].astype(str))
        df[column] = encoded_column
        return f"Label-encoded '{column}' ({len(encoder.classes_)} classes)"
    elif strategy == "frequency":
        freq_map = df[column].value_counts(normalize=True)
        df[column] = df[column].astype(object).map(freq_map)
        return f"Frequency-encoded '{column}'"
    raise ValueError(f"Unknown encoding strategy '{strategy}'")


def _apply_scale_numeric(df, column, strategy, **_):
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise ValueError(f"Column '{column}' is not numeric, cannot scale")
    scaler_map = {"standard": StandardScaler, "minmax": MinMaxScaler, "robust": RobustScaler}
    if strategy not in scaler_map:
        raise ValueError(f"Unknown scaling strategy '{strategy}'")
    scaler = scaler_map[strategy]()
    values = df[[column]].astype(float)
    df[column] = scaler.fit_transform(values)
    return f"Scaled '{column}' using {strategy} scaling"


def _apply_extract_datetime_features(df, column, **_):
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    parsed = pd.to_datetime(df[column], errors="coerce")
    df[f"{column}_year"] = parsed.dt.year
    df[f"{column}_month"] = parsed.dt.month
    df[f"{column}_day"] = parsed.dt.day
    df[f"{column}_dayofweek"] = parsed.dt.dayofweek
    df.drop(columns=[column], inplace=True)
    return f"Extracted year/month/day/dayofweek from '{column}' and dropped the original column"


def _apply_drop_low_variance_column(df, column, **_):
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    df.drop(columns=[column], inplace=True)
    return f"Dropped low-variance column '{column}'"


def _apply_drop_high_correlation_column(df, column, column_b, **_):
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    df.drop(columns=[column], inplace=True)
    kept = f", kept '{column_b}'" if column_b else ""
    return f"Dropped '{column}' due to high correlation with another column{kept}"


ACTION_HANDLERS = {
    "encode_categorical": lambda df, a: _apply_encode_categorical(df, a.get("column"), a.get("strategy")),
    "scale_numeric": lambda df, a: _apply_scale_numeric(df, a.get("column"), a.get("strategy")),
    "extract_datetime_features": lambda df, a: _apply_extract_datetime_features(df, a.get("column")),
    "drop_low_variance_column": lambda df, a: _apply_drop_low_variance_column(df, a.get("column")),
    "drop_high_correlation_column": lambda df, a: _apply_drop_high_correlation_column(
        df, a.get("column"), a.get("column_b")
    ),
}


def apply_feature_engineering_plan(df: pd.DataFrame, actions: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    """Runs on a COPY of df — caller decides whether/how to persist the result."""
    df = df.copy()
    steps = []
    for action in actions:
        action_type = action.get("type")
        handler = ACTION_HANDLERS.get(action_type)
        step = {
            "type": action_type,
            "column": action.get("column"),
            "reasoning": action.get("reasoning"),
        }
        if handler is None:
            step["status"] = "skipped"
            step["message"] = f"Unknown action type '{action_type}'"
        else:
            try:
                step["message"] = handler(df, action)
                step["status"] = "success"
            except Exception as e:  # noqa: BLE001 — surfaced, not swallowed
                step["status"] = "failed"
                step["message"] = str(e)
        steps.append(step)
    return df, steps

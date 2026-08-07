"""
D.A.I.S.Y — Data Cleaning Agent (Phase 3)
--------------------------------------------
Same sense -> reason -> act pattern as the rest of the pipeline, kept in
ONE backend on purpose (see main.py's docstring — no separate Node service,
no separate ml-service; Python already talks to Gemini directly).

  sense  : profile_dataframe()      -> stats only, never raw data to the LLM
  reason : request_cleaning_plan()  -> Gemini returns strict JSON actions
  act    : apply_cleaning_plan()    -> pandas executes each action, reports
                                        success/failed/skipped + a message

This keeps "decide" (Gemini) and "do" (pandas) in separate, auditable
layers — the LLM never runs arbitrary code, it only ever picks from a
fixed menu of actions.
"""

import json
import math
from typing import Any

import pandas as pd


def _json_safe(value: Any) -> Any:
    """Convert numpy/pandas scalars into plain JSON-serializable values."""
    if value is None:
        return None
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):  # numpy scalar
        return _json_safe(value.item())
    return value


def profile_dataframe(df: pd.DataFrame) -> dict:
    """The agent's 'sense' step — richer than the schema report (includes
    per-column min/max/mean/std and top categorical values), still no raw
    rows beyond what the frontend already showed the user."""
    columns_profile = []
    for col in df.columns:
        series = df[col]
        n_rows = len(series) or 1
        null_count = int(series.isna().sum())

        info = {
            "name": col,
            "dtype": str(series.dtype),
            "null_count": null_count,
            "null_pct": round((null_count / n_rows) * 100, 2),
            "unique_count": int(series.nunique(dropna=True)),
        }

        if pd.api.types.is_numeric_dtype(series):
            desc = series.describe()
            info.update(
                {
                    "min": _json_safe(desc.get("min")),
                    "max": _json_safe(desc.get("max")),
                    "mean": _json_safe(round(desc.get("mean"), 4)) if pd.notna(desc.get("mean")) else None,
                    "std": _json_safe(round(desc.get("std"), 4)) if pd.notna(desc.get("std")) else None,
                }
            )
        else:
            top = series.value_counts(dropna=True).head(5)
            info["top_values"] = {str(k): int(v) for k, v in top.items()}

        columns_profile.append(info)

    return {
        "n_rows": int(len(df)),
        "n_columns": int(len(df.columns)),
        "duplicate_rows": int(df.duplicated().sum()),
        "total_nulls": int(df.isna().sum().sum()),
        "columns": columns_profile,
    }


CLEANING_PROMPT_TEMPLATE = """You are DAISY's Data Cleaning Agent, part of a student's ML pipeline project.

You are given a statistical profile of an uploaded dataset (stats only, no raw data). \
Decide the best sequence of cleaning actions to prepare it for machine learning. Be \
conservative — only act where the profile clearly justifies it. Every action needs a \
one-sentence, plain-language reason.

DATASET PROFILE:
{profile_json}

Respond with STRICT JSON ONLY — no markdown, no code fences, no commentary. Match exactly:

{{
  "summary": "one short paragraph on overall data quality, plain language",
  "actions": [
    {{
      "type": "drop_duplicates" | "impute" | "drop_column" | "fix_dtype" | "handle_outliers" | "strip_whitespace" | "drop_rows_missing_target",
      "column": "exact column name from the profile, or null if it applies to the whole dataset",
      "strategy": "mean" | "median" | "mode" | "constant" | "iqr_clip" | "iqr_remove" | "to_numeric" | "to_datetime" | "to_category" | null,
      "value": "only set when strategy is constant, otherwise null",
      "reasoning": "one sentence explaining why"
    }}
  ]
}}

Rules:
- Only use drop_column if a column is over 90% null, or is an obvious raw ID/index with no predictive value.
- Only use handle_outliers on numeric columns where min/max/mean/std clearly show extreme values.
- Use exact column names as they appear in the profile — never invent columns.
- Keep actions under 12 items. If the data already looks clean, return an empty actions array.
- Every action must include a non-empty reasoning string.
"""


def build_cleaning_prompt(profile: dict) -> str:
    return CLEANING_PROMPT_TEMPLATE.format(profile_json=json.dumps(profile, indent=2))


def parse_plan(raw_text: str) -> dict:
    """Gemini is asked for strict JSON but models sometimes still wrap it
    in a code fence — strip that defensively before parsing."""
    try:
        plan = json.loads(raw_text)
    except json.JSONDecodeError:
        stripped = raw_text.replace("```json", "").replace("```", "").strip()
        plan = json.loads(stripped)

    if not isinstance(plan, dict) or not isinstance(plan.get("actions"), list):
        raise ValueError("Cleaning plan came back in an unexpected shape")
    return plan


# ---------------------------------------------------------------------------
# Action execution — the 'act' step. Each handler mutates df in place and
# returns a human-readable message; unknown actions or bad columns are
# reported, never silently ignored or allowed to crash the whole run.
# ---------------------------------------------------------------------------

def _apply_impute(df, column, strategy, value):
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    series = df[column]
    if strategy == "mean":
        fill = series.mean()
    elif strategy == "median":
        fill = series.median()
    elif strategy == "mode":
        modes = series.mode(dropna=True)
        fill = modes.iloc[0] if not modes.empty else None
    elif strategy == "constant":
        fill = value
    else:
        raise ValueError(f"Unknown impute strategy '{strategy}'")
    before = int(series.isna().sum())
    df[column] = series.fillna(fill)
    return f"Filled {before} missing value(s) in '{column}' using {strategy} ({_json_safe(fill)})"


def _apply_drop_column(df, column, **_):
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    df.drop(columns=[column], inplace=True)
    return f"Dropped column '{column}'"


def _apply_fix_dtype(df, column, strategy, **_):
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    if strategy == "to_numeric":
        df[column] = pd.to_numeric(df[column], errors="coerce")
    elif strategy == "to_datetime":
        df[column] = pd.to_datetime(df[column], errors="coerce")
    elif strategy == "to_category":
        df[column] = df[column].astype("category")
    else:
        raise ValueError(f"Unknown dtype strategy '{strategy}'")
    return f"Converted '{column}' to {strategy}"


def _apply_handle_outliers(df, column, strategy, **_):
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise ValueError(f"Column '{column}' is not numeric, cannot handle outliers")
    q1, q3 = df[column].quantile(0.25), df[column].quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    if strategy == "iqr_clip":
        df[column] = df[column].clip(lower=lower, upper=upper)
        return f"Clipped outliers in '{column}' to [{round(lower, 2)}, {round(upper, 2)}]"
    elif strategy == "iqr_remove":
        before = len(df)
        df.drop(df[(df[column] < lower) | (df[column] > upper)].index, inplace=True)
        return f"Removed {before - len(df)} outlier row(s) based on '{column}'"
    raise ValueError(f"Unknown outlier strategy '{strategy}'")


def _apply_strip_whitespace(df, column, **_):
    targets = [column] if column else df.select_dtypes(include=["object", "string"]).columns.tolist()
    for col in targets:
        if col in df.columns and pd.api.types.is_string_dtype(df[col]):
            df[col] = df[col].astype(str).str.strip()
    return f"Trimmed whitespace on: {', '.join(targets) if targets else 'no columns'}"


def _apply_drop_duplicates(df, **_):
    before = len(df)
    df.drop_duplicates(inplace=True)
    return f"Removed {before - len(df)} duplicate row(s)"


def _apply_drop_rows_missing_target(df, column, **_):
    if column not in df.columns:
        raise ValueError(f"Target column '{column}' not found")
    before = len(df)
    df.dropna(subset=[column], inplace=True)
    return f"Dropped {before - len(df)} row(s) missing the target column '{column}'"


ACTION_HANDLERS = {
    "drop_duplicates": lambda df, a: _apply_drop_duplicates(df),
    "impute": lambda df, a: _apply_impute(df, a.get("column"), a.get("strategy"), a.get("value")),
    "drop_column": lambda df, a: _apply_drop_column(df, a.get("column")),
    "fix_dtype": lambda df, a: _apply_fix_dtype(df, a.get("column"), a.get("strategy")),
    "handle_outliers": lambda df, a: _apply_handle_outliers(df, a.get("column"), a.get("strategy")),
    "strip_whitespace": lambda df, a: _apply_strip_whitespace(df, a.get("column")),
    "drop_rows_missing_target": lambda df, a: _apply_drop_rows_missing_target(df, a.get("column")),
}


def apply_cleaning_plan(df: pd.DataFrame, actions: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    """Runs on a COPY of df — caller decides whether/how to persist the result."""
    df = df.copy()
    steps = []
    for action in actions:
        action_type = action.get("type")
        handler = ACTION_HANDLERS.get(action_type)
        step = {"type": action_type, "column": action.get("column"), "reasoning": action.get("reasoning")}
        if handler is None:
            step["status"] = "skipped"
            step["message"] = f"Unknown action type '{action_type}'"
        else:
            try:
                step["message"] = handler(df, action)
                step["status"] = "success"
            except Exception as e:  # noqa: BLE001 — surfaced to the user, not swallowed
                step["status"] = "failed"
                step["message"] = str(e)
        steps.append(step)
    return df, steps


def profile_for_eda(df: pd.DataFrame) -> dict:
    """
    Builds a complete EDA profile using pandas.
    This is the EDA Agent's 'sense' phase.
    """

    numeric_df = df.select_dtypes(include="number")
    categorical_df = df.select_dtypes(exclude="number")

    # Overview
    overview = {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "duplicates": int(df.duplicated().sum()),
        "missing_values": int(df.isna().sum().sum()),
        "memory_usage_kb": round(df.memory_usage(deep=True).sum() / 1024, 2),
    }

    # Numeric statistics
    statistics = {}
    for col in numeric_df.columns:
        statistics[col] = {
            "mean": round(float(df[col].mean()), 2),
            "median": round(float(df[col].median()), 2),
            "std": round(float(df[col].std()), 2),
            "min": round(float(df[col].min()), 2),
            "max": round(float(df[col].max()), 2),
        }

    # Correlation
    correlation = (
        numeric_df.corr(numeric_only=True)
        .round(2)
        .fillna(0)
        .to_dict()
    )

    # Outlier detection (IQR)
    outliers = {}

    for col in numeric_df.columns:

        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)

        iqr = q3 - q1

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        count = int(((df[col] < lower) | (df[col] > upper)).sum())

        outliers[col] = count

    return {
        "overview": overview,
        "numeric_columns": numeric_df.columns.tolist(),
        "categorical_columns": categorical_df.columns.tolist(),
        "statistics": statistics,
        "correlation": correlation,
        "outliers": outliers,
    }

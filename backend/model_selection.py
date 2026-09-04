"""
D.A.I.S.Y — Model Selection Agent (Phase A, item 2)
-------------------------------------------------------
Unlike Cleaning/EDA/Feature Engineering, this agent does not transform the
dataset — it recommends which ML algorithms to try next. Same discipline
carries over in a different shape:

  sense      : detect_problem_type()       -> DETERMINISTIC, not left to
                                               Gemini. Classification vs.
                                               regression is decided by
                                               looking at the target
                                               column's dtype/cardinality,
                                               not by asking the LLM.
  reason     : build_model_selection_prompt() -> Gemini ranks candidates
                                               FROM A FIXED VOCABULARY
                                               (never invents model names)
  guardrail  : validate_recommendations()   -> strips out anything Gemini
                                               returned that isn't in the
                                               allowed vocabulary for the
                                               detected problem type. This
                                               plays the role the 'Act'
                                               step plays in other agents:
                                               the deterministic safety net
                                               that keeps the LLM from
                                               steering the pipeline
                                               somewhere invalid.

Fixed vocabulary (matches what the future Model Training Agent will know
how to build with scikit-learn — no XGBoost/LightGBM dependency added
here to keep this agent's requirements minimal):
  classification: logistic_regression, random_forest_classifier,
                  gradient_boosting_classifier, knn_classifier, svm_classifier
  regression:     linear_regression, random_forest_regressor,
                  gradient_boosting_regressor, ridge_regression, svm_regressor
"""

import json
from typing import Any

import pandas as pd

CLASSIFICATION_MODELS = [
    "logistic_regression",
    "random_forest_classifier",
    "gradient_boosting_classifier",
    "knn_classifier",
    "svm_classifier",
]

REGRESSION_MODELS = [
    "linear_regression",
    "random_forest_regressor",
    "gradient_boosting_regressor",
    "ridge_regression",
    "svm_regressor",
]

# Heuristic: if a numeric target's number of unique values is small relative
# to the row count (and under an absolute cap), treat it as classification
# (e.g. 0/1 labels, or a handful of categories encoded as numbers) rather
# than regression.
MAX_CLASSIFICATION_UNIQUE_ABS = 20
MAX_CLASSIFICATION_UNIQUE_RATIO = 0.05


def detect_problem_type(df: pd.DataFrame, target_column: str) -> dict:
    """The 'sense' step. Deterministic — Gemini never decides this."""
    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' not found in dataset")

    target = df[target_column].dropna()
    n_rows = len(df)
    unique_count = int(target.nunique())

    if pd.api.types.is_numeric_dtype(target):
        uniqueness_ratio = unique_count / max(n_rows, 1)
        # A real categorical target has REPEATED values (e.g. many rows
        # share the same 0/1 label). If almost every row has a distinct
        # value, that's a strong signal of a continuous target, even on a
        # tiny dataset where the absolute unique count also happens to be
        # small. Checked first so it overrides the absolute-count check
        # below.
        if uniqueness_ratio >= 0.9:
            looks_categorical = False
        else:
            looks_categorical = unique_count <= 10 or (
                unique_count <= MAX_CLASSIFICATION_UNIQUE_ABS
                and uniqueness_ratio <= MAX_CLASSIFICATION_UNIQUE_RATIO
            )
        problem_type = "classification" if looks_categorical else "regression"
    else:
        problem_type = "classification"

    result: dict[str, Any] = {
        "target_column": target_column,
        "problem_type": problem_type,
        "target_unique_count": unique_count,
        "target_dtype": str(df[target_column].dtype),
        "n_rows": n_rows,
    }

    if problem_type == "classification":
        counts = target.value_counts()
        total = int(counts.sum())
        proportions = (counts / total).round(4).to_dict()
        result["class_balance"] = {str(k): float(v) for k, v in proportions.items()}
        result["is_imbalanced"] = bool(max(proportions.values()) >= 0.8) if proportions else False
    else:
        result["target_min"] = float(target.min()) if not target.empty else None
        result["target_max"] = float(target.max()) if not target.empty else None
        result["target_mean"] = float(target.mean()) if not target.empty else None

    return result


def profile_for_model_selection(df: pd.DataFrame, target_column: str) -> dict:
    """Combines the deterministic target analysis with basic feature-space
    stats Gemini needs to reason about candidate suitability (e.g. dataset
    size affects whether KNN/SVM are practical)."""
    problem_info = detect_problem_type(df, target_column)
    feature_columns = [c for c in df.columns if c != target_column]
    numeric_features = [c for c in feature_columns if pd.api.types.is_numeric_dtype(df[c])]

    return {
        **problem_info,
        "n_features": len(feature_columns),
        "n_numeric_features": len(numeric_features),
        "n_non_numeric_features": len(feature_columns) - len(numeric_features),
    }


MODEL_SELECTION_PROMPT_TEMPLATE = """You are DAISY's Model Selection Agent, part of a student's ML pipeline project.

The problem type has ALREADY been determined deterministically — do not question or \
override it. Your job is only to rank which candidate algorithms are most suitable \
given the profile below, and explain why.

PROBLEM PROFILE:
{profile_json}

ALLOWED CANDIDATES (you may ONLY choose from this exact list, matching the problem type above):
{allowed_models}

Respond with STRICT JSON ONLY — no markdown, no code fences, no commentary. Match exactly:

{{
  "summary": "one short paragraph explaining the overall reasoning, plain language",
  "recommendations": [
    {{
      "model": "exact name from the allowed candidates list",
      "rank": 1,
      "reasoning": "one to two sentences explaining why this model suits this specific profile"
    }}
  ]
}}

Rules:
- Rank between 2 and 4 candidates, best first (rank 1 = most suitable).
- Only use model names exactly as they appear in the allowed candidates list — never invent or rename one.
- Consider dataset size, class balance/imbalance, and feature count when ranking (e.g. KNN and SVM scale poorly to large datasets; tree-based models handle imbalance and mixed feature types better).
- Every recommendation must include a specific, profile-grounded reasoning string — not a generic statement that could apply to any dataset.
"""


def build_model_selection_prompt(profile: dict) -> str:
    allowed = CLASSIFICATION_MODELS if profile["problem_type"] == "classification" else REGRESSION_MODELS
    return MODEL_SELECTION_PROMPT_TEMPLATE.format(
        profile_json=json.dumps(profile, indent=2),
        allowed_models=json.dumps(allowed, indent=2),
    )


def parse_plan(raw_text: str) -> dict:
    """Same defensive parsing pattern as the other agents."""
    try:
        plan = json.loads(raw_text)
    except json.JSONDecodeError:
        stripped = raw_text.replace("```json", "").replace("```", "").strip()
        plan = json.loads(stripped)

    if not isinstance(plan, dict) or not isinstance(plan.get("recommendations"), list):
        raise ValueError("Model selection plan came back in an unexpected shape")
    return plan


def validate_recommendations(recommendations: list[dict], problem_type: str) -> tuple[list[dict], list[dict]]:
    """The guardrail step — this agent's equivalent of 'Act'. Filters out
    any model name Gemini returned that isn't in the allowed vocabulary
    for the detected problem type. Never trusts the LLM's output blindly,
    same philosophy as every other agent in this project.

    Returns (valid, rejected) — both reported to the caller so nothing is
    silently dropped without a trace."""
    allowed = set(CLASSIFICATION_MODELS if problem_type == "classification" else REGRESSION_MODELS)
    valid, rejected = [], []
    for rec in recommendations:
        model_name = rec.get("model")
        entry = {
            "model": model_name,
            "rank": rec.get("rank"),
            "reasoning": rec.get("reasoning"),
        }
        if model_name in allowed:
            entry["status"] = "accepted"
            valid.append(entry)
        else:
            entry["status"] = "rejected"
            entry["message"] = f"'{model_name}' is not in the allowed {problem_type} vocabulary"
            rejected.append(entry)
    return valid, rejected

"""
D.A.I.S.Y — Evaluation Agent (Phase B, item 1)
-------------------------------------------------------
Takes the winning model from Model Training and produces an actual
assessment, not just a table of numbers.

  sense  : evaluate_model()            -> DETERMINISTIC. Re-trains ONLY
                                           the winning model, using the
                                           SAME test_size/random_state as
                                           Model Training, so this
                                           evaluates the exact same test
                                           split — not a different one.
                                           Computes train-vs-test metrics
                                           (overfitting signal) and a real
                                           confusion matrix / residual
                                           analysis from real predictions,
                                           which aggregate metrics alone
                                           can't give you.
  reason : build_evaluation_prompt()    -> Gemini interprets the real
                                           numbers into a plain-language
                                           verdict. This DOES need an LLM
                                           call, unlike Model Training —
                                           "is this model trustworthy" is
                                           a genuine judgment call, not an
                                           objective comparison.
  guardrail : validate_verdict()        -> Gemini's verdict must be one of
                                           a fixed set (good/moderate/poor).
                                           If not, a deterministic fallback
                                           based on the actual test metric
                                           takes over — same "never blindly
                                           trust LLM output" philosophy as
                                           every other agent.

Why re-train instead of reusing Model Training's numbers directly: Model
Training doesn't persist trained models or raw predictions anywhere (each
request trains fresh and discards them) — there's nothing to evaluate
further without either persisting a lot of state, or cheaply re-deriving
it. Since the split is deterministic (fixed random_state), re-training
the ONE winning model is fast and reproduces the exact same test fold.
"""

import json
from typing import Any

import numpy as np
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split

from model_selection import detect_problem_type
from model_training import (
    MODEL_FACTORY,
    TrainingDataError,
    _classification_metrics,
    _regression_metrics,
    prepare_training_data,
)

VALID_VERDICTS = {"good", "moderate", "poor"}

# Deterministic fallback thresholds if Gemini's verdict needs correcting —
# same primary-metric convention as model_training.py.
FALLBACK_THRESHOLDS = {
    "classification": {"good": 0.80, "moderate": 0.60},  # by f1_weighted
    "regression": {"good": 0.75, "moderate": 0.40},  # by R^2
}


def evaluate_model(
    df,
    target_column: str,
    model_name: str,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """The 'sense' step. Fully deterministic — re-trains just the one
    requested model to get real predictions for real diagnostics."""
    if model_name not in MODEL_FACTORY:
        raise TrainingDataError(f"Unknown model name: {model_name}")

    problem_info = detect_problem_type(df, target_column)
    problem_type = problem_info["problem_type"]

    X, y, warnings = prepare_training_data(df, target_column)

    stratify = y if problem_type == "classification" and y.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=stratify
    )

    estimator = MODEL_FACTORY[model_name]()
    estimator.fit(X_train, y_train)
    y_pred_train = estimator.predict(X_train)
    y_pred_test = estimator.predict(X_test)

    result: dict[str, Any] = {
        "model": model_name,
        "problem_type": problem_type,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "warnings": warnings,
    }

    if problem_type == "classification":
        y_proba_test = estimator.predict_proba(X_test) if hasattr(estimator, "predict_proba") else None
        result["train_metrics"] = _classification_metrics(y_train, y_pred_train, None)
        result["test_metrics"] = _classification_metrics(y_test, y_pred_test, y_proba_test)

        labels = sorted(y.unique().tolist())
        cm = confusion_matrix(y_test, y_pred_test, labels=labels)
        result["confusion_matrix"] = {
            "labels": [str(l) for l in labels],
            "matrix": cm.tolist(),
        }
        result["primary_metric"] = "f1_weighted"
    else:
        result["train_metrics"] = _regression_metrics(y_train, y_pred_train)
        result["test_metrics"] = _regression_metrics(y_test, y_pred_test)

        residuals = np.asarray(y_test) - np.asarray(y_pred_test)
        result["residuals"] = {
            "mean": round(float(np.mean(residuals)), 4),
            "std": round(float(np.std(residuals)), 4),
            "min": round(float(np.min(residuals)), 4),
            "max": round(float(np.max(residuals)), 4),
        }
        result["primary_metric"] = "r2"

    # Overfitting signal: gap between train and test performance on the
    # primary metric. Positive gap (train notably better than test) is
    # the classic overfitting pattern.
    pm = result["primary_metric"]
    result["train_test_gap"] = round(result["train_metrics"][pm] - result["test_metrics"][pm], 4)

    return result


EVALUATION_PROMPT_TEMPLATE = """You are DAISY's Evaluation Agent, part of a student's ML pipeline project.

You are given the REAL, measured training and test performance of a model that has \
already been trained. Do not invent or assume any numbers beyond what's given. Your \
job is to interpret what these numbers actually mean in plain language, and give an \
honest, evidence-based verdict.

EVALUATION DATA:
{eval_json}

Respond with STRICT JSON ONLY — no markdown, no code fences, no commentary. Match exactly:

{{
  "verdict": "good" | "moderate" | "poor",
  "summary": "2-4 sentences giving an honest, evidence-based assessment. Reference the actual numbers given.",
  "observations": [
    "one specific observation grounded in the data, e.g. about the train/test gap, class imbalance in the confusion matrix, or residual pattern"
  ]
}}

Rules:
- "verdict" must be exactly one of: good, moderate, poor. Base it on the primary test metric AND the train/test gap — a model with strong test performance but a large train/test gap should not be called "good" without noting the overfitting risk.
- Every observation must reference a specific real number from the data given — no generic statements that could apply to any model.
- Keep observations to 2-4 items, each one sentence.
- Do not recommend specific next steps beyond what the data supports — stay descriptive and evidence-based, not prescriptive.
"""


def build_evaluation_prompt(eval_result: dict) -> str:
    # Exclude n_train/n_test/warnings from what Gemini sees — keep the
    # prompt focused on the actual performance data it needs to interpret.
    relevant = {
        k: v
        for k, v in eval_result.items()
        if k in ("model", "problem_type", "train_metrics", "test_metrics", "train_test_gap",
                  "confusion_matrix", "residuals", "primary_metric")
    }
    return EVALUATION_PROMPT_TEMPLATE.format(eval_json=json.dumps(relevant, indent=2))


def parse_plan(raw_text: str) -> dict:
    try:
        plan = json.loads(raw_text)
    except json.JSONDecodeError:
        stripped = raw_text.replace("```json", "").replace("```", "").strip()
        plan = json.loads(stripped)

    if not isinstance(plan, dict) or "verdict" not in plan or "summary" not in plan:
        raise ValueError("Evaluation plan came back in an unexpected shape")
    return plan


def _fallback_verdict(eval_result: dict) -> str:
    """Deterministic fallback if Gemini's verdict needs correcting —
    based on the actual primary test metric against fixed thresholds."""
    problem_type = eval_result["problem_type"]
    pm = eval_result["primary_metric"]
    score = eval_result["test_metrics"][pm]
    thresholds = FALLBACK_THRESHOLDS[problem_type]
    if score >= thresholds["good"]:
        return "good"
    elif score >= thresholds["moderate"]:
        return "moderate"
    return "poor"


def validate_verdict(plan: dict, eval_result: dict) -> tuple[str, bool]:
    """The guardrail. Returns (final_verdict, was_corrected)."""
    verdict = plan.get("verdict")
    if verdict in VALID_VERDICTS:
        return verdict, False
    return _fallback_verdict(eval_result), True

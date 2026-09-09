"""
D.A.I.S.Y — Standardized Agent Output Schema (resolves Decisions.md OD-4)
--------------------------------------------------------------------------
Every NEW agent (starting with Feature Engineering) wraps its response in
this envelope so the future Experience Memory layer can store/compare
workflow records without every agent inventing its own shape.

Deliberately NOT retrofitted onto the existing Cleaning/EDA endpoints yet —
that was an explicit, documented choice (see Decisions.md OD-4), not an
oversight. Retrofitting them is a separate, later task if it turns out to
be worth the churn.
"""

import time
import uuid
from typing import Any, Literal

Status = Literal["success", "partial", "failed"]


def new_workflow_id() -> str:
    """One workflow_id per pipeline run, shared across the agents that
    were actually invoked. Callers create this once per /upload-dataset
    (or reuse an existing one on subsequent stage calls) — main.py owns
    the actual reuse policy."""
    return str(uuid.uuid4())


def build_agent_record(
    *,
    workflow_id: str,
    dataset_id: str,
    agent: str,
    status: Status,
    input_summary: dict[str, Any],
    reasoning: str,
    actions: list[dict[str, Any]],
    output_summary: dict[str, Any],
    metrics: dict[str, Any] | None,
    execution_time_seconds: float,
) -> dict[str, Any]:
    """The generic envelope. Fields match Decisions.md OD-4 / project report
    Section 33: workflow_id, dataset_id, agent, status, input_summary,
    reasoning, actions, output_summary, metrics, execution_time."""
    return {
        "workflow_id": workflow_id,
        "dataset_id": dataset_id,
        "agent": agent,
        "status": status,
        "input_summary": input_summary,
        "reasoning": reasoning,
        "actions": actions,
        "output_summary": output_summary,
        "metrics": metrics or {},
        "execution_time_seconds": round(execution_time_seconds, 4),
    }


class Timer:
    """Small helper so agent endpoints can measure execution_time_seconds
    without every endpoint hand-rolling time.time() bookkeeping."""

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, *exc):
        self.elapsed = time.time() - self._start

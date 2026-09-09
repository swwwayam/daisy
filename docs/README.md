# DAISY — Documentation System

**What DAISY is:** An AI-powered agentic data-science assistant. Upload a
CSV, and it progressively handles cleaning → EDA → feature engineering →
model selection → model training → (planned: evaluation → SHAP
explainability → final insights), with a persistent "Experience Memory"
planned for later.

**Current stack:** React (+ Three.js/R3F 3D interface) frontend, FastAPI +
pandas + scikit-learn + Gemini backend, in-memory dataset storage.

**Current status (as of 2026-09-04):** **Phase A is functionally
complete.** All 5 core pipeline stages implemented AND independently
verified end-to-end with real evidence, live Gemini calls, on a real
4,894-row dataset, through the actual React UI (not just Swagger):
Data Cleaning, EDA, Feature Engineering, Model Selection, Model Training.
150+ pytest tests passing on the real dev machine. Everything is
committed and pushed to `swwwayam/daisy` at commit `78eb529` — confirmed
via independent fresh clone.

**Team:** Jatin (backend/ML/agents/memory), Swayam (frontend/visualization/UX).

## This folder

Local only — not committed to `swwwayam/daisy` (see Decisions.md D-005).

| File | Purpose |
|---|---|
| `Handover.md` | Living current-state snapshot. Read this first. |
| `Decisions.md` | Why each real decision was made; open/unresolved decisions. |
| `Architecture.md` | System design, data flow, repo structure. |
| `Constraints.md` | Boundaries, rules for how Claude works on this project. |
| `Test-Checklist.md` | Real test cases, honest Pass/Not Run status. |
| `Flow.md` | End-to-end user/request/error flow. |
| `Rollback.md` | How to undo changes at every scale. |
| `Feature.md` | One entry per feature, built or planned. |
| `Bug.md` | One entry per real bug hit, root cause, fix. |

## Working discipline (short version)

Ask before assuming. Never claim something works without real evidence.
One logical change at a time. Explain before implementing. Hand off real
code files as soon as they're built and verified — not at a deferred
"natural stopping point" (this was learned the hard way once, see
Decisions.md D-010). Update these docs after real work. Log mistakes
honestly.

## What actually happened this cycle (short version)

Built Model Selection Agent (deterministic problem-type detection +
Gemini ranking from a fixed vocabulary + a validation guardrail that
rejects hallucinated model names) and Model Training Agent (the first
agent with NO Gemini call — real sklearn training, objective metric-based
winner selection). Built the full frontend for all three new agents.
Along the way, a real live-testing session surfaced a genuine bug — Model
Training would hard-fail if Feature Engineering's Gemini-generated plan
left some categorical columns unencoded — which was fixed with a
deterministic fallback-encoding step, and the fix was verified by
reproducing the exact original failure, then confirming it was resolved.
Everything was then run live, end-to-end, through the real UI, on a real
4,894-row dataset, successfully.

## Why this matters for this specific project

This log doubles as raw material for the final project report ("black
book," ~400-500 pages) — a true chronological record (decisions, bugs
found/fixed, verified vs. claimed status) is far more useful to write
from later than reconstructing the project's history from memory.

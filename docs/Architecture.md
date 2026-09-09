# Architecture.md — DAISY System Design

> Reflects state as of 2026-09-04, verified against commit `78eb529`.

## High-Level Flow

```text
React Frontend (CRA, port 3000)
        │  REST (fetch), CORS allowed for localhost:3000
        ▼
FastAPI Backend (backend/main.py, port 8000)
        │
        ├── In-memory DATASETS: dict[str, pd.DataFrame]
        │
        ├── /agents/dataset-discovery ──► [PLANNED, Phase C]
        ├── /upload-dataset ──► pandas parse ──► schema report
        ├── /chat ──► Gemini, grounded in schema if dataset_id given
        ├── /agents/data-cleaning ──► agents.py: profile → Gemini plan → pandas execute
        ├── /agents/eda ──► agents.py: profile_for_eda → Gemini narrative summary
        ├── /agents/feature-engineering ──► profile → Gemini plan → pandas/sklearn execute
        │       → NEW: deterministic fallback auto-encodes any leftover non-numeric column
        ├── /agents/model-selection ──► deterministic problem-type detection → Gemini
        │       ranks from fixed vocabulary → validation guardrail rejects hallucinations
        ├── /agents/model-training ──► NO Gemini call — real sklearn .fit()/.predict(),
        │       objective metric-based winner selection
        ├── /agents/report-export ──► [PLANNED, Phase C]
        └── /dataset/{id}/download ──► streamed CSV
```

## Full Pipeline Status (as of 2026-09-04)

```text
0. Dataset Discovery Agent   [PLANNED, Phase C]
1. Data Cleaning Agent       [BUILT + VERIFIED — including live, 2026-09-04]
2. EDA Agent                 [BUILT + VERIFIED — including live, 2026-09-04]
3. Feature Engineering Agent [BUILT + VERIFIED — extended with fallback fix, 2026-09-04]
4. Model Selection Agent     [BUILT + VERIFIED live, 2026-09-02/04]
5. Model Training Agent      [BUILT + VERIFIED live, 2026-09-02/04]
6. Evaluation Agent          [PLANNED — Phase B, next up]
7. SHAP Explainability Agent [PLANNED — Phase B]
8. Report/Export Agent       [PLANNED — Phase C]
```

**Phase A (stages 1-5, plus item 4 test coverage) is functionally
complete and verified end-to-end live, through the real UI, on a real
4,894-row dataset — see Handover.md Section 4 for the full run.**

## Repository Structure (backend, as of commit `78eb529`)

```text
backend/
├── .env                       (local only, gitignored)
├── .env.example
├── main.py                     — all endpoints, including the fallback wiring
├── agents.py                   — Cleaning + EDA agent logic (unchanged)
├── agent_schema.py             — standardized output envelope (resolves OD-4)
├── feature_engineering.py      — Feature Engineering Agent + NEW fallback encoding
├── model_selection.py          — NEW: deterministic detection + Gemini ranking + guardrail
├── model_training.py           — NEW: real sklearn training, no Gemini call
├── test_agents.py              — 21 tests
├── test_feature_engineering.py — 24 tests (17 original + 7 for fallback)
├── test_model_selection.py     — 17 tests
├── test_model_training.py      — 14 tests
└── requirements.txt            — includes scikit-learn
```

Total: 76 backend tests across all agents, all passing on the real dev
machine as of this update.

## Repository Structure (frontend, relevant files)

```text
src/components/
├── Scene.js                — main orchestrator; NEW: 5th "Feature" node,
│                              handlers for all 3 new agents, fixed a
│                              pre-existing stray node-activation bug
├── ControlPanel.js         — NEW: "Run Feature Engineering Agent" button
├── AgentLogPanel.js        — NEW: FeatureEngineeringSection,
│                              ModelSelectionSection (shows accepted AND
│                              rejected recommendations), ModelTrainingSection
│                              (comparison table + objective winner marker)
└── TargetColumnSelector.js — NEW: standalone panel, appears after Feature
                               Engineering completes, feeds target_column
                               into Model Selection
```

## Data Flow — Feature Engineering Agent (updated with fallback)

```text
DataFrame
   │
   ▼ SENSE
profile_for_feature_engineering(df) — stats only, no raw rows to the LLM
   │
   ▼ REASON
Gemini plan (strict JSON, fixed 5-action menu)
   │
   ▼ ACT
apply_feature_engineering_plan() — executes Gemini's plan
   │
   ▼ FALLBACK (NEW, 2026-09-04)
apply_fallback_encoding() — any column STILL non-numeric after Gemini's
plan gets auto-encoded (onehot if ≤10 unique values, frequency otherwise),
logged as a distinct "auto_encode_remaining" action — never merged into
Gemini's own action list, keeping the audit trail honest about what the
AI decided vs. what this deterministic safety net caught
   │
   ▼
engineered_df stored as DATASETS[f"{dataset_id}-engineered"]
```

**Why this fallback exists:** Model Training's own guardrail correctly
(and intentionally) refuses non-numeric data rather than guessing — see
`model_training.py`'s docstring. That's the right behavior for that
agent, but it means the pipeline needs a guarantee upstream that it never
reaches that dead end because Gemini's reasoning simply didn't cover
every column. Real bug, real fix — see Bug.md B-008.

## Data Flow — Model Selection Agent

```text
DataFrame + target_column
   │
   ▼ SENSE (fully deterministic, never left to Gemini)
detect_problem_type() — classification vs. regression via value
repetition + cardinality, not just a unique/row ratio (see Decisions.md
D-014 and Bug.md B-007 for why this needed a real fix)
   │
   ▼ REASON
Gemini ranks 2-4 candidates FROM A FIXED VOCABULARY — 5 classification
models, 5 regression models — never invents a model name
   │
   ▼ GUARDRAIL (this agent's equivalent of "Act")
validate_recommendations() — strips anything not in the allowed
vocabulary for the detected problem type; rejected AND accepted
recommendations are both reported, nothing silently dropped
   │
   ▼
Response includes ranked accepted candidates + any rejected ones with
the reason they were rejected
```

**Verified live (2026-09-04):** on the real 4,894-row salary dataset, all
4 recommendations were accepted (0 rejected) — `gradient_boosting_regressor`,
`random_forest_regressor`, `ridge_regression`, `svm_regressor`, reasoning
grounded in real profile numbers ("31 numeric features," "nearly 5,000 rows").

## Data Flow — Model Training Agent (no Gemini call — see Decisions.md D-013)

```text
DataFrame (post-Feature-Engineering, all-numeric) + target_column +
candidate_models (a list of model names, typically from Model Selection's
accepted recommendations)
   │
   ▼ SENSE
prepare_training_data() — validates all feature columns are numeric
(hard error with a clear message if not — this is intentional strictness,
not a bug, see the fallback discussion above), drops any stray NaN rows,
reuses model_selection.detect_problem_type() for consistency
   │
   ▼ ACT (real, not simulated)
train_and_evaluate() — real train/test split, real .fit()/.predict() for
EVERY candidate, real metrics (accuracy/precision/recall/F1/ROC-AUC for
classification; MAE/RMSE/R² for regression). Each model's failure is
isolated — one bad model doesn't sink the others.
   │
   ▼ SELECT (deterministic, objective — no LLM)
Winner picked by highest f1_weighted (classification) or lowest RMSE
(regression) — a metric comparison, not a judgment call
```

**Verified live (2026-09-04):** trained 4 real models on the salary
dataset, correctly selected Gradient Boosting Regressor by RMSE — visible
in the actual UI's comparison table with the winner clearly marked.

## Standardized Agent Output Schema (unchanged, `agent_schema.py`)

Every agent from Feature Engineering onward uses the same envelope:
`workflow_id, dataset_id, agent, status, input_summary, reasoning,
actions, output_summary, metrics, execution_time_seconds`. Still not
retrofitted onto Cleaning/EDA (deliberate, OD-4 resolution note).

## Known Architectural Gaps (DECISION REQUIRED before building on top)

- **Feature Engineering has no target-column awareness** (Decisions.md
  OD-12, new this cycle) — it's possible for it (via Gemini's plan or the
  new fallback) to transform the column the user will later choose as
  target. Didn't cause a problem in the verified live run, but is a real
  latent inconsistency worth fixing before it does.
- **No API-contract doc for Phase B agents** (Evaluation, SHAP).
- **Persistence layer** still not designed — no schema, no ORM choice.
- **CI would currently fail** on `npm run build` due to 3 pre-existing
  ESLint warnings, confirmed present before this cycle's work — needs
  addressing as part of Phase B's CI/CD item.

## Frontend State Ownership

`Scene.js` remains the single source of truth, now extended with
`featureResult`, `modelSelectionResult`, `modelTrainingResult` state and
their corresponding handlers. All three new agents are now reachable
through the real UI, not just Swagger — confirmed via the full live
pipeline run (Handover.md Section 4).

## Deployment

Unchanged — local dev only. No deployment target confirmed yet.

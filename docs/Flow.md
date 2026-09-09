# Flow.md — End-to-End Application Flow

## User Flow (current, fully verified live 2026-09-04)

```text
1. User opens app (localhost:3000) → 3D Scene renders (5 nodes: Data,
   Model, Training, Evaluation [dormant], Feature)
2. User uploads a CSV via ControlPanel
3. Frontend POSTs file to /upload-dataset → schema report + dataset_id
4. User clicks "Run Cleaning Agent" → real Gemini call → cleaning
   actions displayed in Pipeline Results panel
5. User clicks "Run EDA Agent" → real Gemini call → narrative summary
6. User clicks "Run Feature Engineering Agent" (NEW) → real Gemini call
   → Gemini's plan executes → fallback auto-encodes any leftover
   non-numeric columns → results shown, columns before→after displayed
7. TargetColumnSelector panel appears (NEW) → user picks the column to
   predict from a dropdown of the engineered dataset's real columns
8. Model Selection runs automatically on confirm (NEW) → real Gemini
   call → ranked candidates shown, accepted AND rejected both visible
9. User clicks "Train These Models" (NEW) → Model Training runs — NO
   Gemini call, real sklearn training → comparison table shown with the
   objective winner marked
10. User clicks download → GET /dataset/{id}/download → CSV file
11. (Optional, any point) User chats via ChatPanel
```

**This entire flow was run live, successfully, on a real 4,894-row
dataset on 2026-09-04** — see Handover.md Section 4 for the full result.

## Request/Response Flow — Feature Engineering Agent (updated with fallback)

```text
Frontend                    Backend (main.py)              feature_engineering.py
   │  POST /agents/feature-engineering { dataset_id }
   ├────────────────────────►│
   │                         │  lookup dataset, check API key
   │                         │  profile_for_feature_engineering(df) ─►│ SENSE
   │                         │◄────────────────────────────────────────┤
   │                         │  Gemini call (real, live) ─────────────►│ REASON
   │                         │◄────────────────────────────────────────┤ plan dict
   │                         │  apply_feature_engineering_plan() ─────►│ ACT
   │                         │◄────────────────────────────────────────┤ (df, steps)
   │                         │  apply_fallback_encoding(df) ──────────►│ FALLBACK (NEW)
   │                         │◄────────────────────────────────────────┤ (df, fallback_steps)
   │                         │  steps = steps + fallback_steps
   │◄────────────────────────┤  JSON response, includes both Gemini's
   │                         │  actions AND fallback actions, clearly
   │                         │  distinguishable by action "type"
```

## Request/Response Flow — Model Selection → Model Training handoff

```text
Frontend (TargetColumnSelector)     Backend
   │  POST /agents/model-selection
   │  { dataset_id: engineered_dataset_id, target_column }
   ├──────────────────────────────►│
   │                                │  detect_problem_type() — DETERMINISTIC
   │                                │  Gemini ranks from fixed vocabulary
   │                                │  guardrail validates/filters
   │◄───────────────────────────────┤  { actions: [accepted + rejected] }
   │
   │  (user clicks "Train These Models" with the accepted model names)
   │
   │  POST /agents/model-training
   │  { dataset_id: engineered_dataset_id, target_column,
   │    candidate_models: [accepted model names] }
   ├──────────────────────────────►│
   │                                │  prepare_training_data() — validates
   │                                │  numeric, drops NaN rows
   │                                │  REAL sklearn .fit()/.predict() per
   │                                │  candidate — NO Gemini call
   │                                │  objective winner selection
   │◄───────────────────────────────┤  { actions: [per-model results],
   │                                │    output_summary.best_model }
```

## Error Flow — the real bug this cycle found and fixed

```text
BEFORE the fallback fix:
  Feature Engineering plan (Gemini) leaves some columns unencoded
       ↓
  Model Training's guardrail correctly refuses:
  "These feature columns are not numeric... Run the Feature Engineering
  Agent first to encode them" — but Feature Engineering ALREADY ran.
       ↓
  DEAD END — no way to progress without direct backend intervention.

AFTER the fallback fix (2026-09-04):
  Feature Engineering plan (Gemini) leaves some columns unencoded
       ↓
  apply_fallback_encoding() catches it deterministically, encodes the
  remaining columns, logs it as a distinct visible action
       ↓
  Model Training receives a fully numeric dataset — proceeds normally.
```

This was reproduced exactly (same 3 column names) in a controlled test
before the fix was trusted, then confirmed resolved in the same live
scenario on the real dataset. See Bug.md B-008.

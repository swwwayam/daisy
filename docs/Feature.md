# Feature.md — Feature Log

> One entry per feature, filled in only as actually built.

---

## Template

```
## F-XXX — <Feature Name>
- **Objective:**
- **Approach:**
- **Files changed:**
- **Testing done:**
- **Problems encountered:**
- **Final result:**
```

---

## F-001 to F-005 (condensed — see prior regeneration for full detail)
CSV Upload, Gemini Chat, Data Cleaning Agent, EDA Agent, Documentation
System Setup. All previously logged in detail; unchanged this cycle
except where noted below.

## F-006 — Dataset Discovery Agent (still planned, not yet built)
No change since scoping — Phase C.

## F-007 — Report/Export Agent (still planned, not yet built)
No change since scoping — Phase C.

## F-008 — Feature Engineering Agent (built + verified, extended this cycle)
Original build unchanged from prior entry. **Extension this cycle:**
`apply_fallback_encoding()` added — see F-011 below for the dedicated
entry on this specific fix, since it was substantial enough (a real bug
found via live testing) to warrant its own record.

## F-009 — Model Selection Agent (NEW, built + verified)
- **Objective:** Recommend which ML algorithms to try, without
  transforming any data — deterministic problem-type detection + Gemini
  ranking from a fixed, safe vocabulary + a validation guardrail.
- **Approach:** See Architecture.md's full data-flow section. Key design
  choice (Decisions.md D-014): classification-vs-regression detection is
  fully deterministic, never left to Gemini's judgment.
- **Files changed:** `backend/model_selection.py` (new), `backend/
  test_model_selection.py` (new, 17 tests), `backend/main.py` (new
  endpoint).
- **Testing done:** Sandbox-verified (17 tests, mocked Gemini) →
  real-machine-verified (55 tests total, screenshot 2026-09-02) →
  UI-verified live on the real 4,894-row dataset (screenshot 2026-09-04)
  — correctly detected regression, all 4 recommendations accepted.
- **Problems encountered:** A real bug in the problem-type heuristic
  (ratio-based detection misjudged small binary-target datasets) —
  caught by tests before reaching the user, fixed by checking value
  repetition first. See Bug.md B-007.
- **Final result:** Fully built and verified at all three tiers.

## F-010 — Model Training Agent (NEW, built + verified)
- **Objective:** Actually train and compare real ML models — the one
  agent in this whole project that does genuine machine learning, not
  API-orchestration.
- **Approach:** No Gemini call at all (Decisions.md D-013) — real sklearn
  `.fit()`/`.predict()` for every candidate, real train/test split, real
  metrics, objective winner selection by a primary metric.
- **Files changed:** `backend/model_training.py` (new), `backend/
  test_model_training.py` (new, 14 tests), `backend/main.py` (new
  endpoint).
- **Testing done:** Sandbox-verified (14 tests, including a genuine
  sanity check — linear regression achieving R²>0.8 on near-linear
  synthetic data, confirming real learning) → real-machine-verified (69
  tests total) → UI-verified live on the real dataset (Gradient Boosting
  Regressor correctly selected by RMSE, visible in the comparison table).
- **Problems encountered:** None specific to this agent's own logic —
  the real problem it hit (non-numeric leftover columns) was actually a
  Feature Engineering gap, correctly diagnosed as belonging upstream —
  see F-011.
- **Final result:** Fully built and verified at all three tiers. This is
  the milestone that most directly addresses the recruiter-rating
  discussion's biggest identified gap (Handover.md Section 7).

## F-011 — Feature Engineering fallback auto-encoding (NEW, bug fix)
- **Objective:** Guarantee Feature Engineering always produces a fully
  numeric dataset, even when Gemini's plan doesn't address every
  categorical column.
- **Approach:** Deterministic fallback step, run after Gemini's plan
  executes: any column still non-numeric gets auto-encoded (onehot for
  ≤10 unique values, frequency encoding otherwise), logged as a distinct
  `auto_encode_remaining` action — never merged into Gemini's own action
  list, preserving an honest audit trail. See Decisions.md D-015 for why
  this fix belongs here and not in Model Training.
- **Files changed:** `backend/feature_engineering.py` (new function),
  `backend/main.py` (wired into the endpoint), `backend/
  test_feature_engineering.py` (7 new tests).
- **Testing done:** This is the one fix in the project verified through
  a full bug-reproduction cycle: (1) the real live error was observed
  through the actual UI on the real dataset, listing 3 specific column
  names; (2) that exact scenario was reproduced in a controlled sandbox
  test, confirming the same failure; (3) the fix was applied; (4) the
  same reproduction was re-run and confirmed successful; (5) the full
  live pipeline was re-run through the real UI on the real dataset and
  completed successfully, with the same 3 column names now correctly
  auto-encoded and visibly logged.
- **Problems encountered:** Discovered a related, NOT-yet-fixed gap while
  building this: Feature Engineering doesn't know which column will
  become the target, so it's theoretically possible for it to
  encode/transform the target column itself. Didn't cause a problem in
  the verified run (target was numeric, untouched) but flagged as
  Decisions.md OD-12 for a future fix.
- **Final result:** Fixed and verified at the strongest evidence tier in
  the project (UI-verified, real bug reproduction, real dataset).

## F-012 — Frontend for Feature Engineering, Model Selection, Model Training (NEW)
- **Objective:** Make all three new agents usable through the actual
  product, not just Swagger — directly addresses the "recruiter watching
  you use Swagger instead of your real app" risk raised earlier in the
  project.
- **Approach:** One new component (`TargetColumnSelector.js`), three
  modified components (`Scene.js`, `ControlPanel.js`, `AgentLogPanel.js`).
  Matched the existing visual language exactly (same fonts, same cyan/
  dark palette, same panel patterns) rather than introducing a new style.
- **Files changed:** See Architecture.md's frontend repository structure
  section.
- **Testing done:** Real `npm install` + real production build (succeeded,
  real bundle produced). Real ESLint run on every changed file (zero new
  warnings; confirmed the 3 that do appear are pre-existing in the
  untouched original repo). Then **UI-verified live** — the user ran the
  complete real pipeline through the real browser on the real dataset.
- **Problems encountered:** Found and fixed a pre-existing bug while
  extending the node graph — the cleaning handler was lighting up an
  "Evaluation" node that didn't correspond to any real running stage.
  Fixed the node-activation mapping across all 5 real agents. See Bug.md
  B-009.
- **Final result:** Fully built and verified at the strongest evidence
  tier — this is what made the full end-to-end live pipeline run
  (Handover.md Section 4) possible at all.

## F-013 — Figma design brief for extending the 3D UI (NEW, planning deliverable)
- **Objective:** Give Swayam (or Figma's AI tools) a detailed, grounded
  brief for designing the remaining UI work (loading states, error
  states, extended 8-node graph) without needing to hand over source code.
- **Approach:** Text-based design brief referencing real field names,
  real agent output shapes, and real observed states (the 503 overload
  error, the "AI summary could not be generated" partial-success state)
  rather than generic placeholder content.
- **Files changed:** N/A — standalone document, not application code.
- **Testing done:** N/A — planning artifact.
- **Problems encountered:** None.
- **Final result:** Delivered as a downloadable markdown file. Not yet
  acted upon (design/frontend work for loading/error states remains
  open).

# Handover.md — DAISY Project Status

> Living document. Updated after every real chunk of work. Anything not
> personally verified is marked as such.

**Last updated:** 2026-09-04
**Third regeneration of this docs folder.** See Decisions.md D-010/D-011
for why continuity matters here — this file bundle, not chat history, is
the durable record.

---

## 1. Current Phase

**Phase A is functionally complete.** All 5 stages of the core pipeline
(Cleaning, EDA, Feature Engineering, Model Selection, Model Training) are
built and independently verified end-to-end, live, through the real React
UI, on a real dataset. Next up: Phase B (Evaluation Agent, SHAP, CI/CD).

## 2. Repo / Environment State (independently verified 2026-09-04)

Local and GitHub (`swwwayam/daisy`, branch `main`) confirmed in sync at
commit `78eb529` ("Add Model Selection, Model Training agents, frontend
UI, and FE fallback fix") — verified via a fresh clone from this session,
not assumed. `backend/` contains all 6 agent-related Python modules
(`agents.py`, `feature_engineering.py`, `model_selection.py`,
`model_training.py`, `agent_schema.py`) plus 5 test files. `src/
components/` contains the new `TargetColumnSelector.js` plus the modified
`Scene.js`, `ControlPanel.js`, `AgentLogPanel.js`. `package-lock.json`
was also updated and committed.

## 3. What's Actually Implemented (verified)

### Data Cleaning, EDA (verified 2026-08-16, unchanged since)

### Feature Engineering Agent (verified 2026-09-01, extended 2026-09-04)

Original build unchanged. **New this cycle:** a deterministic fallback-
encoding step (`apply_fallback_encoding()`) runs after Gemini's plan
executes — see Section 5 below for the bug this closes. Logged as its own
distinct `auto_encode_remaining` action type, never merged into Gemini's
own action list.

### Model Selection Agent (NEW, built + verified 2026-09-02/04)

- **Files:** `backend/model_selection.py`, `backend/test_model_selection.py`
  (17 tests).
- **Structurally different from every prior agent:** the "sense" step
  (classification vs. regression detection) is fully deterministic, never
  left to Gemini. Gemini only ranks 2-4 candidates from a fixed
  vocabulary (5 classification models, 5 regression models). A validation
  guardrail strips out anything Gemini returns that isn't in that
  vocabulary — this plays the role the "Act" step plays in data-
  transforming agents, except here the safety net is validation, not
  execution.
- **Real bug found and fixed during build:** the original problem-type
  heuristic (ratio of unique values to row count) misclassified a small
  binary-target dataset as regression. Fixed by checking for value
  *repetition* first (a real categorical target has repeats) before
  falling back to the ratio check. Caught by the test suite before ever
  reaching the user.
- **Verification, both tiers:**
  - Sandbox-verified: all 17 tests pass against deterministic logic;
    guardrail specifically tested against a deliberately hallucinated
    model name (correctly rejected, mocked Gemini).
  - Real-machine-verified: 55 tests total passed on the real dev machine
    (2026-09-02). Live Gemini call confirmed twice: once on a toy 4-row
    dataset, once on the real 4,894-row salary dataset — correctly
    identified regression, correctly reasoned about "31 numeric features"
    and "nearly 5,000 rows" (real profile numbers, not generic text), all
    4 recommendations accepted (0 rejected) on the real run.

### Model Training Agent (NEW, built + verified 2026-09-02/04)

- **Files:** `backend/model_training.py`, `backend/test_model_training.py`
  (14 tests).
- **The one agent with NO Gemini call at all** — deliberate design
  choice (Decisions.md D-013): picking the best-performing model among
  already-trained candidates is an objective metric comparison, not a
  subjective judgment call, so dressing it up as an "AI decision" would
  be worse engineering, not better.
- **Real sklearn training:** actual `.fit()`/`.predict()` for every
  requested candidate, real train/test split, real classification
  metrics (accuracy/precision/recall/F1/ROC-AUC) or regression metrics
  (MAE/RMSE/R²) depending on detected problem type. Each candidate's
  failure is isolated — one bad model doesn't sink the run.
- **Verification, both tiers:**
  - Sandbox-verified: 14/14 tests, including a genuine sanity check
    (linear regression achieving R² > 0.8 on near-linear synthetic data
    — confirms real learning is happening, not just code that runs).
  - Real-machine-verified: 69 tests total passed on the real dev machine.
    Live run on a real, all-numeric-post-FE dataset trained 3 models,
    correctly picked the highest-F1 model as winner. On the real
    4,894-row salary dataset, trained 4 real models and correctly picked
    Gradient Boosting Regressor by RMSE — visible, confirmed in the
    actual UI's comparison table.

### Frontend for the three new agents (NEW, built + verified 2026-09-04)

- **New file:** `TargetColumnSelector.js` — appears after Feature
  Engineering completes, lets the user pick a prediction target before
  Model Selection runs.
- **Modified:** `Scene.js` (new "Feature" node in the 3D graph, new state
  and handlers for all 3 agents, fixed a pre-existing bug — see Section 5),
  `AgentLogPanel.js` (three new result sections: Feature Engineering,
  Model Selection with visible accepted/rejected recommendations, Model
  Training with a comparison table and an objective winner marker),
  `ControlPanel.js` (new "Run Feature Engineering Agent" button).
- **Verification:** actually ran `npm install` + a full production build
  (`npx react-scripts build`) — succeeded, produced a real deployable
  bundle. Ran ESLint on every changed file — zero new warnings (confirmed
  the 3 pre-existing warnings already existed in the untouched original
  repo, not introduced by this work). **Then verified live in the actual
  browser** — the user ran the full real pipeline through the real UI on
  the real 4,894-row dataset and it worked end to end (screenshots
  captured, 2026-09-04).

## 4. Confirmed Working — Full Live Pipeline Run (2026-09-04, strongest evidence in the project to date)

A real, messy, real-world dataset (student/event attendance data, 4,894
rows, mixed types, target = "Expected salary (Lac)") went through the
**entire pipeline live, through the real UI, with zero manual
intervention and zero dead ends**:

1. Upload → schema report
2. Cleaning → 8 real actions (dropped 3 identifier/zero-variance/mostly-
   null columns, stripped whitespace, imputed missing values) — nulls
   7036 → 0
3. EDA → real AI-generated narrative referencing actual dataset facts
4. Feature Engineering → 12 → 32 columns; Gemini's plan encoded 8 columns
   correctly; the new fallback caught and encoded 3 more it missed
   (`Attendee Status`, `Family Income`, `Leadership- skills`) — visibly
   logged as `auto_encode_remaining`, distinct from Gemini's own actions
5. Model Selection → correctly detected regression; 4 candidates
   recommended and **all 4 accepted** (0 rejected)
6. Model Training → all 4 models actually trained; **Gradient Boosting
   Regressor** correctly selected as winner by RMSE

This is qualitatively the strongest evidence gathered in this project —
not a toy example, not mocked, not Swagger-only — a real dataset, the
real UI, the real AI provider, start to finish.

## 5. Known Issues / Bugs Found and Fixed This Cycle

| Item | Status |
|---|---|
| Model Selection problem-type heuristic misjudged small binary datasets | Found + fixed 2026-09-02, see Bug.md B-007 |
| Model Training hard-failed when Feature Engineering left columns unencoded | Found via live testing 2026-09-04, fixed same day, see Bug.md B-008 |
| Pre-existing stray `setActiveNode("Evaluation")` bug in `Scene.js` | Found + fixed 2026-09-04 while wiring new nodes, see Bug.md B-009 |
| `MetricsPanel.js` still unused | Unchanged, still open — Decisions.md OD-1 |
| 3 pre-existing ESLint warnings (unused vars) block `CI=true npm run build` | Confirmed pre-existing (present in untouched original repo too), not caused by this work. Relevant for Phase B's CI/CD — a strict CI build would fail on this today |
| Feature Engineering doesn't know the target column | **New, real gap found during fallback-fix testing** — Feature Engineering (and now its fallback) can transform/encode the actual target column before the user has even picked it, since `target_column` isn't passed to this agent at all. Did not cause a problem in the verified live run, but is a real latent inconsistency. Not yet fixed — flagged as OD-12 |

## 6. Known Risks

- No persistence: server restart loses all uploaded/cleaned/engineered
  datasets (unchanged, still accepted for current stage).
- No API-contract doc yet for Phase B agents (Evaluation, SHAP) —
  increasingly worth doing given the project's growing complexity.
- CI would currently fail on the frontend build due to pre-existing lint
  warnings — needs cleanup before or during Phase B's CI/CD work.
- Feature Engineering's lack of target-column awareness (Section 5) could
  cause a real problem on a future dataset where the intended target has
  low cardinality and gets encoded away before selection.

## 7. Recruiter-Rating Discussion — Progress Update

Original rating (2026-08-16): 4/10, biggest gap identified as "zero real
model training/evaluation exists anywhere." **That gap is now
substantially closed** — real models are now actually trained with real
measured metrics, verified live on a real dataset. Evaluation Agent and
SHAP (Phase B) remain to fully round this out. Still true: the "Adaptive
Experience Memory" differentiator remains 0% built — see Decisions.md D-008.

## 8. Phase Plan — Status Update

### Phase A — COMPLETE
1. ~~Feature Engineering Agent~~ — done, verified, extended with fallback fix
2. ~~Model Selection Agent~~ — done, verified live
3. ~~Model Training Agent~~ — done, verified live
4. ~~pytest suite for `agents.py`~~ — done

**Exit condition met:** DAISY takes a raw CSV to real, compared, measured
models — confirmed live, through the real UI, on a real dataset.

### Phase B — Evaluation, Explainability, CI/CD (NOT STARTED)
1. Evaluation Agent
2. SHAP Explainability Agent
3. CI/CD pipeline — note the pre-existing lint-warning blocker (Section 5)
   will need addressing as part of this, not a separate surprise later

### Phase C — Persistence + Dataset Discovery + Report/Export (NOT STARTED)

Unchanged from prior plan.

## 9. Immediate Next Step

Phase B, item 1 (Evaluation Agent) is the logical next step — Phase A's
exit condition is genuinely met. Two smaller open items worth considering
alongside it: OD-12 (Feature Engineering's target-column blindness) and
the pre-existing ESLint warnings, since Phase B explicitly includes CI/CD
work that will hit that blocker. Not deciding unilaterally — present as
options when work resumes.

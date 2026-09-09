# Test-Checklist.md

> Three tiers now apply: Sandbox-verified (Gemini mocked), Real-machine-
> verified (real machine, real Gemini, via Swagger/direct API), and
> **UI-verified** (real machine, real Gemini, through the actual React
> app — the strongest standard, established 2026-09-04).

## Data Cleaning + EDA Agents

| # | Test Case | Status | Evidence |
|---|---|---|---|
| 1 | Backend starts | Real-machine-verified PASS | Screenshot 2026-09-01 |
| 3 | Upload dataset | UI-verified PASS | Screenshot 2026-09-04, full pipeline run |
| 10 | Data Cleaning live | **UI-verified PASS** | Screenshot 2026-09-04 — 8 real actions on the salary dataset |
| 12 | EDA live | **UI-verified PASS** | Screenshot 2026-09-04 — real narrative summary referencing actual dataset facts |

## Feature Engineering Agent

| # | Test Case | Status | Evidence |
|---|---|---|---|
| 16-27 | Deterministic logic (profiling, actions, edge cases) | Sandbox + Real-machine-verified PASS | 24 tests, `test_feature_engineering.py`, all passing |
| 28 | Live Gemini call, toy dataset | Real-machine-verified PASS | Screenshot 2026-09-01 |
| 30 (NEW) | Live Gemini call, real 4,894-row dataset | **UI-verified PASS** | Screenshot 2026-09-04 — 12→32 columns, Gemini's 8 real actions correctly reasoned |
| 31 (NEW) | Fallback auto-encoding, real bug reproduction | **Sandbox-verified PASS** | Reproduced exact original failure (3 same column names), confirmed fix resolves it — see session transcript 2026-09-04 |
| 32 (NEW) | Fallback auto-encoding, live on real dataset | **UI-verified PASS** | Screenshot 2026-09-04 — `auto_encode_remaining` fired correctly on `Attendee Status`, `Family Income`, `Leadership- skills`, exact same 3 columns that broke training before the fix |

## Model Selection Agent (NEW)

| # | Test Case | Status | Evidence |
|---|---|---|---|
| 33 | Deterministic problem-type detection (binary, continuous, missing column) | Sandbox-verified PASS | `test_model_selection.py`, 17 tests |
| 34 | Problem-type heuristic bug found + fixed | Sandbox-verified PASS (after fix) | Real bug caught by tests before reaching user — see Bug.md B-007 |
| 35 | Class balance / imbalance detection | Sandbox-verified PASS | Same suite |
| 36 | Validation guardrail — accepts real models | Sandbox-verified PASS | Same suite |
| 37 | Validation guardrail — rejects hallucinated model name | **Sandbox-verified PASS**, mocked test deliberately fed a fake model name | Same suite + endpoint-level mocked test |
| 38 | Full suite on real machine | **Real-machine-verified PASS** | 55 tests total, screenshot 2026-09-02 |
| 39 | Live Gemini call, toy dataset | Real-machine-verified PASS | Screenshot 2026-09-02 |
| 40 (NEW) | Live Gemini call, real 4,894-row dataset | **UI-verified PASS** | Screenshot 2026-09-04 — correctly detected regression, 4/4 candidates accepted, reasoning grounded in real profile numbers |

## Model Training Agent (NEW)

| # | Test Case | Status | Evidence |
|---|---|---|---|
| 41 | Real sklearn training, classification | Sandbox-verified PASS | `test_model_training.py`, 14 tests, real `.fit()` calls, no mocking needed (no Gemini call in this agent) |
| 42 | Real sklearn training, regression | Sandbox-verified PASS | Same suite |
| 43 | Sanity check: linear regression achieves R²>0.8 on near-linear data | **Sandbox-verified PASS** | Confirms real learning, not just code that runs without error |
| 44 | Objective winner selection (highest F1 / lowest RMSE) | Sandbox-verified PASS | Same suite |
| 45 | Failure isolation (one bad model doesn't sink the run) | Sandbox-verified PASS | Same suite |
| 46 | Full suite on real machine | **Real-machine-verified PASS** | 69 tests total, screenshot 2026-09-02 |
| 47 (NEW) | Live training on real 4,894-row dataset | **UI-verified PASS** | Screenshot 2026-09-04 — 4 real models trained, Gradient Boosting Regressor correctly selected by RMSE, visible in the comparison table |

## Frontend (NEW)

| # | Test Case | Status | Evidence |
|---|---|---|---|
| 48 | `npm install` + production build | **Real-machine-verified PASS** (Claude's sandbox) | Real build succeeded, real JS bundle produced (369.29 kB) |
| 49 | ESLint on all changed/new files | PASS, zero new warnings | Confirmed 3 pre-existing warnings already existed in untouched original repo |
| 50 | Full live pipeline through real UI | **UI-verified PASS — strongest evidence in the project** | Screenshots 2026-09-04: Upload → Clean → EDA → Feature Engineering → target selection → Model Selection → Model Training, all live, all correct, zero dead ends |
| 51 | Node graph renders all 5 real agent nodes | UI-verified PASS | Screenshot 2026-09-04 |
| 52 | Pre-existing stray node-activation bug | Found + fixed | See Bug.md B-009 |

## Notes

- Item 50 is the single strongest piece of evidence gathered in this
  project — a real, messy, real-world dataset, the real UI, the real AI
  provider, zero manual workarounds, start to finish.
- Original Cleaning/EDA agents' live behavior is now also UI-verified
  (items 10, 12) — closes out the previously-open item OD-5, at least for
  the version of the pipeline exercised in the 2026-09-04 run.
- CI (`CI=true npm run build`) still fails on 3 pre-existing lint warnings
  — this is a known, tracked item (OD-7), not a new regression.

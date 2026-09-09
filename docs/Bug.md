# Bug.md — Bug Log

> Only added when a real bug is hit. Logged honestly rather than hidden.

---

## Template

```
## B-XXX — <Short Title>
- **Symptom:**
- **Root cause:**
- **Fix:**
- **Files touched:**
- **Verified fixed?**
```

---

## B-001 to B-006 (condensed — see prior regeneration for full detail)
Python environment mismatch (B-001), missing frontend components after
git migration (B-002), Gemini API key missing after migration (B-003),
`MetricsPanel.js` unused/unresolved (B-004), pandas 3.0 string dtype
breaking categorical encoding (B-005), Feature Engineering Agent work
lost between sessions — a process bug, not a code bug (B-006). All
previously logged in full detail; unchanged this cycle.

---

## B-007 — Model Selection problem-type heuristic misjudged small binary datasets
- **Symptom:** A tiny (8-row) dataset with a binary target (`purchased`:
  0/1) was incorrectly classified as a regression problem.
- **Root cause:** The original heuristic checked `unique_count / n_rows`
  against a fixed ratio threshold. On small datasets, even a genuinely
  binary target (2 unique values / 8 rows = 25%) can exceed a strict
  ratio threshold designed for larger datasets, causing a false
  regression classification.
- **Fix:** Check for value *repetition* first — if almost every row has
  a distinct value (`uniqueness_ratio >= 0.9`), that's a strong signal of
  a genuinely continuous target regardless of dataset size; otherwise,
  fall back to the absolute-count/ratio check. This correctly
  distinguishes "2 repeated values across many rows" (classification)
  from "8 distinct values across 8 rows" (regression), which the
  original ratio-only check could not.
- **Files touched:** `backend/model_selection.py`
  (`detect_problem_type()`).
- **Verified fixed?** Yes — caught by the test suite (a real failure, not
  a hypothetical), fixed, and re-verified: both the classification and
  regression fixtures pass correctly after the fix, confirming neither
  case was broken by fixing the other.

## B-008 — Model Training hard-failed when Feature Engineering left columns unencoded
- **Symptom:** Running the full real pipeline live (2026-09-04, real
  4,894-row dataset) resulted in Model Training failing with: "These
  feature columns are not numeric, so the model can't train on them
  directly: ['Attendee Status', 'Family Income', 'Leadership-skills']."
  The suggested fix ("run Feature Engineering first") had already been
  done — a genuine dead end for the user.
- **Root cause:** Gemini's Feature Engineering plan is not guaranteed to
  address every non-numeric column — it can judge some as not worth
  encoding, or simply omit them from its plan. Model Training's own
  guardrail correctly (and intentionally) refuses to proceed on
  non-numeric data rather than guessing — the right behavior for that
  agent, but with no upstream guarantee that it would never reach that
  situation.
- **Fix:** Added a deterministic fallback-encoding step in Feature
  Engineering (`apply_fallback_encoding()`), run after Gemini's plan
  executes — see Decisions.md D-015 for the full reasoning on why this
  belongs here rather than loosening Model Training's strictness.
- **Files touched:** `backend/feature_engineering.py`,
  `backend/main.py`.
- **Verified fixed?** Yes, at the strongest tier used in this project:
  (1) the exact real failure was reproduced in a controlled test with
  the same 3 column names; (2) the fix was applied and the same
  reproduction confirmed resolved; (3) the full live pipeline was re-run
  through the real UI on the real dataset and completed successfully,
  with those exact 3 columns now correctly auto-encoded and visibly
  logged as `auto_encode_remaining` actions.

## B-009 — Pre-existing stray node-activation bug in Scene.js
- **Symptom:** After the Data Cleaning Agent completed, the 3D interface
  lit up an "Evaluation" node — a pipeline stage that didn't exist
  anywhere in the shipped product at the time.
- **Root cause:** A leftover `setActiveNode("Evaluation")` call in the
  original cleaning handler, predating this documentation system —
  likely a placeholder or copy-paste artifact from early development.
- **Fix:** Corrected the node-activation mapping across all 5 real
  agents while wiring in the 3 new ones: Cleaning/EDA → `Data`, Feature
  Engineering → new `Feature` node, Model Selection → `Model`, Model
  Training → `Training`. `Evaluation` now correctly stays dormant,
  reserved for the real future agent.
- **Files touched:** `src/components/Scene.js`.
- **Verified fixed?** Yes — confirmed via the full live pipeline run;
  each node lit correctly for its corresponding real stage, and
  `Evaluation` correctly stayed dormant throughout (screenshot
  2026-09-04). Flagged explicitly to the user as a discovered pre-
  existing issue rather than fixed silently, per working discipline.

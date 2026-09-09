# Decisions.md — Decision Log

> D-001 through D-009 are historical/reconstructed or logged in prior
> sessions (see earlier docs regeneration for full detail — condensed
> here for continuity). D-010 onward logged live this cycle onward.

---

## D-001 to D-005 (condensed — full detail in project history)
Node backend consolidated into FastAPI (D-001). In-memory storage
deliberately deferred (D-002). Gemini reason/pandas-act separation as the
core agent pattern (D-003). Core ML pipeline built before Experience
Memory (D-004). Docs kept local-only, not committed to GitHub (D-005).

## D-006 / D-007 — Two new agents scoped, not yet built
Dataset Discovery Agent (Kaggle search) and Report/Export Agent. Both
still planned for Phase C, unchanged this cycle.

## D-008 / D-009 — Honest positioning vs. general LLM chat; agents are API+orchestration except two
Condensed: today DAISY is safer/more auditable than a general chat tool
but not more capable; the real differentiator (Experience Memory) is
still unbuilt. Only Model Training and the future Adaptive ML Decision
Engine involve genuinely training models — every other agent is Gemini-
via-API wrapped in original orchestration logic. **Model Training is now
built** (see below) — this is the first agent where D-009's "genuine
training" category is no longer hypothetical.

## D-010 / D-011 — Docs regenerated after a state-verification gap; Claude's sandbox doesn't persist across sessions
Full detail in prior regeneration. Core lesson: hand off real code files
immediately upon verification, don't defer to a "natural stopping point."
This discipline was followed successfully throughout this cycle's work.

## D-012 — Fix pandas 3.0 string-dtype incompatibility (Feature Engineering)
Condensed: `label`/`frequency` encoding broke under pandas 3.0's stricter
string dtype; fixed by casting to `object` before assignment.

## D-013 — Model Training Agent has NO Gemini call
- **Decision:** Unlike every other agent, Model Training does not call
  Gemini at all. Picking the best-performing trained model is an
  objective comparison against a measured metric (highest F1/lowest
  RMSE) — there is no subjective judgment for an LLM to make.
- **Alternatives considered:** Ask Gemini to "interpret" the results and
  recommend a winner, for consistency with other agents' reasoning step.
- **Why chosen:** Dressing an objective calculation up as an "AI
  decision" would be slower, more expensive, and no more correct than
  sorting a list — worse engineering, not better. This is also a
  meaningful, honest distinction to make explicit in the eventual project
  report (ties directly to D-009's "what's actually AI vs. orchestration"
  framing).
- **Consequence:** This agent is measurably faster (no Gemini latency at
  all — real runs completed in well under a second for model training
  itself) and fully deterministic/reproducible given a fixed random seed.

## D-014 — Model Selection's problem-type detection stays deterministic, never delegated to Gemini
- **Decision:** Classification vs. regression is decided by inspecting
  the target column directly (dtype, value repetition, cardinality) —
  never asked of Gemini, and the prompt explicitly tells Gemini not to
  question or override it.
- **Why chosen:** This is an objectively determinable fact about the
  data, not a judgment call — same philosophy as D-013. Letting an LLM
  guess at something checkable deterministically adds risk (hallucination
  potential) with no benefit.
- **Consequence:** A real bug in this exact logic was caught early by
  tests, before ever reaching a user — see Bug.md B-007. Worth noting:
  keeping this deterministic is *why* it was testable and catchable at
  all; had it been an LLM judgment call, this specific bug class (a bad
  heuristic) wouldn't have been fixable the same way.

## D-015 — Fallback auto-encoding belongs in Feature Engineering, not Model Training
- **Context:** Live testing (2026-09-04) surfaced a real bug: Model
  Training would hard-fail if Feature Engineering's Gemini-generated plan
  left some categorical columns unencoded (Gemini doesn't guarantee full
  coverage of every column).
- **Decision:** Fix this upstream, in Feature Engineering — add a
  deterministic fallback step that auto-encodes any column still non-
  numeric after Gemini's plan runs, logged as its own distinct
  `auto_encode_remaining` action type. Do NOT loosen Model Training's
  intentional strictness (it was deliberately designed to refuse non-
  numeric data loudly rather than guess — see the original design note in
  `model_training.py`'s docstring).
- **Alternatives considered:** Make Model Training auto-encode leftover
  columns itself before training.
- **Why chosen:** Preserves both agents' correct responsibilities —
  Feature Engineering's job is to guarantee a fully numeric, ML-ready
  dataset; Model Training's job is to train on trustworthy input and
  refuse otherwise. Fixing it in Model Training would blur that
  separation and quietly reintroduce the "guess an encoding and hide the
  upstream problem" pattern that was explicitly avoided when Model
  Training was first designed.
- **Consequence:** Verified by reproducing the EXACT real failure (same
  three column names: `Attendee Status`, `Family Income`, `Leadership-
  skills`) in a controlled test, confirming the fix resolves it, then
  confirming the full live pipeline run succeeds end-to-end on the real
  dataset. See Bug.md B-008.

## D-016 — Fixed a pre-existing stray node-activation bug while extending the 3D graph
- **Context:** While wiring 3 new agent nodes into `Scene.js`, found that
  the original cleaning handler set `setActiveNode("Evaluation")` after
  cleaning completed — lighting a node for a stage that didn't exist yet
  in the shipped product.
- **Decision:** Fix the node-activation mapping across all 5 real agents
  (Cleaning/EDA → Data, Feature Engineering → Feature, Model Selection →
  Model, Model Training → Training) as part of this change, rather than
  leaving the stray bug in place alongside new correct behavior.
- **Consequence:** Flagged explicitly to the user rather than fixed
  silently, per working discipline. See Bug.md B-009.

---

## Open Decisions (not yet resolved — do not forget these)

- **OD-1:** `MetricsPanel.js` still unused. Still not decided.
- **OD-2:** `PipelineTracker.js` still commented out.
- **OD-3:** No API-contract doc for Phase B agents (Evaluation, SHAP) —
  increasingly worth doing.
- **OD-5:** Original Cleaning/EDA agents' live Gemini calls still not
  independently re-exercised through the new UI specifically (though EDA
  clearly does run live now, confirmed in the 2026-09-04 full pipeline
  screenshots) — low priority, largely superseded by the full pipeline
  run.
- **OD-6:** Docs-sharing mechanism with Swayam still unresolved.
- **OD-7:** CI/CD still not started. **New complication:** the frontend
  currently fails a strict `CI=true npm run build` due to 3 pre-existing
  ESLint warnings (unused vars) — confirmed present in the original
  untouched repo, not introduced by this cycle's work, but will need
  cleanup as part of Phase B's CI/CD item, not a separate surprise later.
- **OD-9:** Real model training now exists (Model Training Agent) —
  **substantially addressed**, though Evaluation Agent + SHAP (Phase B)
  are still needed to fully round out the DS/DA-facing gap identified in
  the recruiter-rating discussion.
- **OD-10:** Baseline-vs-adaptive experiment — still blocked on Phase C
  (Experience Memory doesn't exist yet).
- **OD-11:** ~~Whether Feature Engineering Agent files were committed~~ —
  **RESOLVED**, confirmed via independent fresh clone at commit `78eb529`.
- **OD-12 (new):** Feature Engineering (and its new fallback step) has no
  awareness of which column will become the target — it's possible for
  it to transform/encode the actual target column before the user has
  even selected one. Did not cause a problem in the verified live run
  (target was numeric and untouched), but is a real latent inconsistency.
  Likely fix: accept an optional `target_column` parameter and exclude it
  from both Gemini's plan and the fallback. Not yet implemented.

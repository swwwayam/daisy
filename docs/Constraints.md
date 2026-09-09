# Constraints.md — Boundaries & Rules

## Allowed Tech (current, verified as of 2026-09-04)

- Frontend: React (CRA), Three.js / React Three Fiber / Drei / React
  Three Postprocessing.
- Backend: Python, FastAPI, pandas 3.0.2, scikit-learn, google-genai SDK
  (`gemini-3-flash-preview`), python-dotenv, Pydantic, pytest.
- No database yet — in-memory only, deliberate (Decisions.md D-002).

## Out of Scope (for now)

- Evaluation Agent, SHAP — Phase B, not yet built.
- Persistent storage / Experience Memory / feedback loop — Phase C+.
- Any second backend service — explicitly rejected (D-001).

## Rules for Claude specifically

- Explain before implementing anything non-trivial.
- Ask before any consequential/architectural decision.
- Never silently change the stack, architecture, or scope.
- Never claim a test passed without real evidence.
- One logical change at a time.
- Validate logic on a small known case before applying at volume.
- Update Handover.md/Decisions.md after every real chunk of work.
- Docs (`/docs`) are local-only per user's choice.
- **Hand off real code files as soon as they're built and verified** —
  not deferred. Followed successfully throughout this cycle (Model
  Selection, Model Training, frontend, and the fallback fix were all
  handed off immediately upon verification, not batched).
- When something is genuinely unknown, verify by actually checking
  (cloning, re-uploading) rather than assuming.
- **NEW (2026-09-04):** When a real bug is found via live testing (not
  just unit tests), reproduce the EXACT failure in a controlled test
  before claiming a fix works — don't just patch and assume. This was
  done for the Feature-Engineering-fallback bug: the original error was
  reproduced with the same three column names before the fix was
  verified to resolve it.
- **NEW (2026-09-04):** When fixing a bug that touches two agents'
  responsibilities (e.g. Model Training's strictness vs. Feature
  Engineering's completeness), fix it in the agent whose job it actually
  is, not wherever is most convenient — preserve intentional design
  decisions rather than papering over them from a different layer.

## Verification Standard (two tiers, as established previously)

"Sandbox-verified" = Claude ran it with Gemini mocked. "Real-machine-
verified" = ran on the user's actual machine, live Gemini call included.

**A third tier now exists, established this cycle: "verified live through
the real product UI, on a real dataset, end-to-end, with screenshots."**
This is the strongest standard reached in this project — see Handover.md
Section 4. Going forward, distinguish this from "real-machine-verified
via Swagger" when reporting status, since UI-level verification also
confirms the frontend wiring, not just the backend logic.

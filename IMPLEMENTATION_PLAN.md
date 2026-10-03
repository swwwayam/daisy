# DAISY implementation sequence

This tracks the approved project-guide audit. Items are complete only when their
implementation and relevant checks pass; cloud verification is recorded separately.

1. Implemented, local tests passed: preserve source CSV and add an explicit interpretation review
   (missing tokens, data types, original-data download, recorded inference policy).
2. Implemented, local tests passed: user-confirmed task type, random/stratified/group/time
   splits, selectable metrics, 27 portable estimators, and explicit final evaluation.
   Finalization fixes one winning experiment per uploaded source and prevents later
   training/review on that source. Re-uploading a dataset creates a new source, so
   the application cannot guarantee that a user has supplied genuinely unseen data.
3. Implemented, local tests passed: append-only experiment records, owner-filtered
   retrieval independent of the current run, durable atomic holdout claims, restart
   recovery, paginated experiment history UI, and a downloadable final diagnostics
   JSON report. Apply migration
   `202610030001_experiment_finalization.sql` before using Supabase persistence.
4. Partially implemented: bounded DataFrame/source caches with active leases,
   pinned runtime/test dependencies, separate API/worker/web container templates,
   worker heartbeats and live readiness probes. Local cache recovery/capacity and
   worker failure tests pass. Container execution, broader endpoint/storage quotas,
   deployment load tests and operational alerting remain pending.
5. Partially implemented: owner-only account usage display for rolling-day AI,
   training, and prediction/explanation budgets. Apply
   `202610030004_account_usage.sql` for Supabase. Deletion, retention, account export,
   and billing integration remain pending,
   using Razorpay test mode (no setup charge; live transaction fees apply). Workspace
   sharing requires explicit membership checks.
6. Pending: benchmark runner comparing fixed baseline, rules, and AI with measured
   performance, runtime, failures, usage, and exported prediction equivalence.
7. Implemented, local tests passed: downloadable final diagnostics JSON and a ZIP
   containing a deterministic Markdown model card plus full recorded pipeline JSON,
   candidate validation metrics, split/fold hashes, and final evaluation if measured.
8. Partially implemented: new-CSV prediction workspace in Results and independent
   history, exact saved preprocessing, CSV download, missing/unseen-category
   diagnostics and no persisted input rows. Validation-only permutation explanations
   now reuse the saved estimator, verify source/fold identity, bound computation,
   share inference quotas, and offer JSON download. Local explanation tests pass;
   a browser walkthrough and live deployment checks remain pending.
9. Partially implemented: owner-authenticated inference by immutable artifact UUID,
   file/row/cell limits, per-process concurrency bound, and atomic rolling-day usage
   quotas. Ephemeral training-serving input shift checks now use training-only
   reference summaries, minimum batch sizes, and explicit heuristic thresholds.
   Monitoring history, alerting, and deployment capacity verification remain pending.
10. Partially verified on 2026-10-03: live migrations, private CSV/JSON/ZIP storage
    round trips with temporary synthetic objects, local API/worker readiness, and
    usage RPC reachability. Live two-account authorization, authenticated end-to-end
    training, and deployment load/container verification remain pending; these
    must not be represented as passed from mocked/local tests.

Commits stay local unless pushing is explicitly requested. Existing features remain
available during rollout. Optional external services must fail clearly when unconfigured.

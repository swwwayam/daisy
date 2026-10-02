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
4. Pending: bounded caches, endpoint/storage quotas, locked dependencies, containers,
   capacity/failure tests, worker monitoring, and operational probes.
5. Pending: deletion, retention, account export, usage display, and billing integration
   using Razorpay test mode (no setup charge; live transaction fees apply). Workspace
   sharing requires explicit membership checks.
6. Pending: benchmark runner comparing fixed baseline, rules, and AI with measured
   performance, runtime, failures, usage, and exported prediction equivalence.
7. Implemented, local tests passed: downloadable final diagnostics JSON and a ZIP
   containing a deterministic Markdown model card plus full recorded pipeline JSON,
   candidate validation metrics, split/fold hashes, and final evaluation if measured.
8. Pending: new-data prediction workspace, input diagnostics and model explanations.
9. Pending: authenticated versioned prediction endpoints, usage limits, drift monitoring.
10. Pending: live two-account Supabase checks and deployment verification; these must
    not be represented as passed from mocked/local tests.

Commits stay local unless pushing is explicitly requested. Existing features remain
available during rollout. Optional external services must fail clearly when unconfigured.

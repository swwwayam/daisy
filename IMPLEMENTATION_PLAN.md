# DAISY implementation sequence

This tracks the approved project-guide audit. Items are complete only when their
implementation and relevant checks pass; cloud verification is recorded separately.

1. Implemented, local tests passed: preserve source CSV and add an explicit interpretation review
   (missing tokens, data types, original-data download, recorded inference policy).
2. Pending: user-confirmed task type, appropriate random/stratified/group/time splits,
   selectable metrics, protected final evaluation, and a larger model catalog.
3. Pending: immutable experiment records and independent result restoration.
4. Pending: bounded caches, endpoint/storage quotas, locked dependencies, containers,
   capacity/failure tests, worker monitoring, and operational probes.
5. Pending: deletion, retention, account export, usage display, and billing integration
   using Razorpay test mode (no setup charge; live transaction fees apply). Workspace
   sharing requires explicit membership checks.
6. Pending: benchmark runner comparing fixed baseline, rules, and AI with measured
   performance, runtime, failures, usage, and exported prediction equivalence.
7. Pending: auditable downloadable decision report/model card.
8. Pending: new-data prediction workspace, input diagnostics and model explanations.
9. Pending: authenticated versioned prediction endpoints, usage limits, drift monitoring.
10. Pending: live two-account Supabase checks and deployment verification; these must
    not be represented as passed from mocked/local tests.

Commits stay local unless pushing is explicitly requested. Existing features remain
available during rollout. Optional external services must fail clearly when unconfigured.

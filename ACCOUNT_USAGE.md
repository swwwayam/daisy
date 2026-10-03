# Account usage

Open **Account usage** in the workspace and refresh to see the enforced budgets.
`GET /account/usage` requires authentication and returns only that owner's counts.
The read does not reserve tokens, jobs, or inference rows. SQLite reads persisted
counters; Supabase uses a server-only aggregate RPC. Demo counters reset on restart
and inline training is explicitly marked unmetered.

Limits cover a rolling 24 hours, rather than resetting at midnight: 100 AI requests
and 200,000 used/reserved tokens; 100 prediction/explanation requests and 100,000
scored rows; 10 queued training attempts and two queued/running jobs at once.
Explanation repeats count as scored rows. AI tokens can show reservations while a
provider call runs. Failed accepted attempts and cancelled training can consume
budget. The next expiry describes the oldest recorded usage event, not when the
entire budget resets. Active job limits also depend on job completion/cancellation.

Apply `202610030004_account_usage.sql` after prior usage/job migrations. These
are platform limits, not subscription entitlements. Billing remains separate.
Local tests verify owner isolation, no read-side quota consumption, expired-event
exclusion, restart recovery, empty/demo state, and the cloud request contract.
They do not verify the live Supabase migration or dashboard.

# Predictions with an immutable model version

Use **Predict on new data** in Results or an experiment's history record. Upload
the original required feature columns; the fitted package applies the recorded
interpretation, imputation, encoding and scaling. The target is optional and is
ignored. Download the predictions CSV with zero-based `input_row` values to join
it back to the original file. Order and row count are preserved.

The authenticated endpoint is `POST /models/{artifact_id}/predict`, with a
multipart `file` field. The artifact UUID identifies an immutable model version;
there is no mutable latest-model alias. Only the model owner can use it. The API
verifies the server-owned package before deserializing it and accepts CSVs only,
never user-uploaded pickle/joblib files.
Damaged, duplicate, missing, oversized, or incompatible package members fail
clearly before scoring. Serialized member read limits do not guarantee the memory
size of an estimator after loading; server-owned training and deployment limits
still apply. A failed durable artifact write is reported as an export error and
does not publish a download reference.

Limits: 10 MiB uploaded bytes, 10,000 rows, 1,000 columns, one million raw/encoded cells and
64 MiB parsed data per request. One prediction operation runs at a time per API
process; busy requests receive 429. The rolling-day account budget is 100
requests and 100,000 scored rows, shared with explanations and reserved atomically
in durable deployments. Explanation charges include every shuffle repeat. Attempts
with valid CSVs consume a reservation even if later preprocessing fails. This
limits repeated expensive failed requests; reservations are not refunded.

New input rows and predictions are not stored on the server or sent to an AI
provider. Only request/row counts are retained for one rolling day. SQLite and
Supabase preserve quotas across API restarts; demo memory quotas reset.
The response contains `prediction_csv`, a six-row prediction preview, and input
diagnostics. Missing-value counts reflect the saved policy before imputation.
Unseen-category counts identify use of exported fallbacks: zero one-hot columns,
label -1, or frequency 0. These are input diagnostics, not accuracy or drift
measurements. Performance on genuinely new labelled data still needs evaluation.

New leakage-free packages include bounded transformed-training summaries
(mean, standard deviation, min/max, row count; no raw training rows) in metadata.
For batches of at least 30 rows, prediction responses compare encoded features
against that fixed reference. A mean change above one training standard deviation
or more than 10% outside the training range flags review. Constant features use
range checks only. At most 20 flagged features are shown, with a total count.
Moment calculations scale values before summing/squaring, so large finite inputs
do not overflow the report. Unrepresentable standardized shifts remain flagged
and are displayed as beyond numeric range, rather than serialized as infinity.
Packages with more than 1000 features or legacy preprocessing return unavailable.
These thresholds are exploratory heuristics, not significance tests, accuracy
measurements, or a complete distribution comparison. Transformations can hide raw
shifts. No flag does not prove the absence of drift. Reports are ephemeral; there
is no persisted monitoring history, alerting, or automatic retraining yet.

The standalone downloaded helper remains available without DAISY and is not
subject to server quotas. New packages parse CSV values as text first, preserving
literal categories such as NA and leading-zero identifiers. Saved policy decides
which values are missing and which columns are numeric. Legacy packages without
that policy keep their original pandas parsing behaviour.

Apply `202610030003_prediction_usage.sql` before enabling prediction with
Supabase persistence. Local tests check prediction equivalence against the
downloaded fitted model, category diagnostics, ownership, malformed/oversized
row counts, no stored input rows and quota races/restarts. Live cloud and load
verification remain separate deployment checks.

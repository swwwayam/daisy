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

Limits: 10 MiB uploaded bytes, 10,000 rows, 1,000 columns, one million cells and
64 MiB parsed data per request. One prediction operation runs at a time per API
process; busy requests receive 429. The rolling-day account budget is 100
requests and 100,000 rows, reserved atomically in durable deployments. Attempts
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

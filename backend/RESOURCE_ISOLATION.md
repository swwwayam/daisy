# Resource isolation and deployment

DAISY authorizes resources using the user ID returned by Supabase Auth for the
request's bearer token. A valid login alone does not grant access to another
user's dataset, pipeline context, or trained model. Client-supplied owner fields
are not trusted.

## Current guarantees

- Uploads receive an immutable server-assigned owner.
- Dataset summaries, CSV downloads, and all six pipeline agents check ownership
  before profiling data, calling the AI provider, or training a model.
- Cleaning and feature engineering produce fresh UUIDs on each execution. Their
  outputs inherit ownership and retain the original dataset lineage.
- Training, evaluation, and dataset-grounded chat authorize every ancestor before
  reading original rows or earlier pipeline results. Missing or foreign ancestors
  are rejected; cyclic lineage is rejected with HTTP 409.
- Foreign, missing, and unowned resources return the same HTTP 404 response.
  Anonymous requests return HTTP 401. Chat without a dataset remains available
  to an authenticated user and does not invent dataset context.
- Exported models have a server-side `<artifact-id>.owner.json` record beside the
  ZIP in `DAISY_MODEL_DIR`. Downloads check this record and the ZIP's existence.
  Ownership survives an API restart; it is not read from user-supplied packages.
  Owner identities are not included in the downloadable ZIP.

## Deployment and migration

Memory mode requires re-uploading datasets after restart. SQLite and Supabase modes
persist owner-bound datasets, preprocessing specifications, lineage, pipeline
context, and model packages. See [runtime setup](SAAS_SETUP.md). Copying only a
DataFrame into the store does not authorize access. Retain local model ZIPs and
their ownership records together; durable packages can also restore local caches.

Legacy model ZIPs without an ownership record cannot be safely attributed to a
user and are denied. Retrain them while signed in to create a new downloadable
package. Do not assign owners based on an artifact ID submitted by a browser.

The current boundary is the individual signed-in user. This change does not
implement workspace sharing. Durable modes now use an owner-only runtime table
and private Storage buckets; the original workspace/project tables are not used
for sharing runtime resources. A future workspace implementation must
derive access from verified membership and persist resource ownership, rather
than replacing these checks with a client-supplied workspace ID.

## Verification

From the `backend` directory:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

`test_tenant_isolation.py` exercises two valid accounts using mocked token
validation. It checks foreign IDs, absent IDs, anonymous access, derived output
ownership, lineage, and provider-call isolation. `test_model_export.py` verifies
real training/export/reload, owner-only downloads after memory reset, malformed
or missing ownership records, and failed package publication cleanup. No network
requests or account passwords are needed by these tests.

For a manual smoke check, use two separate browser profiles. Upload and train as
account A, then attempt the same dataset summary, processed CSV download, and
model download as account B using the IDs returned to A. B should receive 404;
A should still be able to download the model. After an API restart, A's model
download should continue to work while the dataset requires a new upload.

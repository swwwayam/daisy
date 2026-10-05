# Deployment and operating checks

The current version runs directly from VS Code terminals; Docker is not required.
The unused Docker/Compose templates have been removed. The API, training worker,
and frontend remain separate processes.
Runtime Python packages are now pinned in `backend/requirements.lock` from the
tested Python 3.12 environment; `requirements-test.txt` adds pinned test tools.
Pinning is a compatibility baseline, not a vulnerability audit or a guarantee of
identical floating-point results on different CPUs. Re-run tests when updating.

The DataFrame cache is limited to `DAISY_CACHE_MB` (default 512 MiB) and 256
entries. Durable mode evicts inactive frames with their cached lineage/settings
and restores them through owner-filtered storage. Request/worker leases protect
active frames. If active work exhausts the budget, new work receives HTTP 429.
Demo mode preserves existing data and rejects excess entries; exact source bytes
have a separate 64 MiB demo budget. These limits cover cached frames/source
bytes, not total process RAM: parsing, encoding, training arrays, reports and
temporary copies still need memory. Hosting must provide process memory/CPU limits;
the application's cache budget is not a limit on total process RAM.

## Run without Docker

Use Python 3.12 and Node.js 24, matching the versions used by CI. Install backend
dependencies with `pip install -r requirements.txt` inside its virtual environment
and frontend dependencies with `npm ci` at the repository root. Training still
runs in a separate child process with a 10-minute deadline.

1. Configure `backend/.env`. Set `DAISY_PERSISTENCE=sqlite` for a single-host local
   deployment or `supabase` for cloud state. Memory mode is refused in production.
2. Apply pending Supabase migrations before choosing Supabase persistence.
   `202610030005_storage_content_types.sql` aligns the private buckets with the
   backend upload headers: source CSV as `text/csv`, dataset snapshots as
   `application/json`, and trained-model packages as `application/zip`.
3. Ensure `.env.local` contains the frontend URL and publishable key.
4. Keep three terminals open. Start the API from `backend`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

5. Start the training worker in another terminal, also from `backend`. It is
   required for SQLite/Supabase training jobs. Demo memory mode runs inline and
   does not use this worker.

```powershell
.\.venv\Scripts\python.exe worker.py
```

6. Start the frontend from the repository root:

```powershell
npm run dev
```

Open `http://localhost:8443`. Set `VITE_DAISY_API_URL=http://localhost:8000` in
`.env.local`; the API's `CORS_ORIGINS` and OAuth redirect allowlists must include
the frontend origin. Restart Vite after changing its environment file. Stop each
process with Ctrl+C. SQLite mode needs the API and worker to share the same state
database and artifact directory; running both from `backend` uses the defaults.

These are local development commands. Before public exposure, add HTTPS, a real
hostname/OAuth allowlist, backups and restore checks, secret management, capacity
tests, monitoring, process supervision and retention. Serve the built frontend
(`npm run build`) through a production host rather than the Vite dev server.
SQLite supports a single host, not a distributed database.

## Health and failure detection

- `/health/live`: API process responds; does not prove dependencies work.
- `/health/ready`: required configuration plus live durable-storage and worker
  checks in durable deployments. Cloud checks fail if migrations or keys are bad.
- `/health/worker`: ready only when a worker heartbeat is newer than 90 seconds.
  Demo mode explicitly returns `inline_demo`, not a durable-worker success.

Workers heartbeat every 15 seconds while idle or training. A worker healthcheck
checks its own hostname/`DAISY_WORKER_ID`; the API checks any live worker. Use a
different ID for each worker on one host. Abrupt failures expire automatically.
Health responses never include customer IDs, job payloads, datasets or secrets.

```powershell
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
Invoke-RestMethod http://localhost:8000/health/worker
```

API and worker logs appear in their respective terminals.

Test worker loss by stopping the worker, waiting at least 90 seconds and checking
that readiness returns 503, then restart it. Verify queued jobs recover, worker
leases expire on abrupt loss, cancellations terminate fits, and models remain
downloadable after restarts. Back up both SQLite state and artifact directories when
using SQLite; cloud blobs and metadata need matching retention/backup policies.

## Verification status

SQLite heartbeat expiry, queue races, process timeout/cancellation, real child
training, authenticated artifact recovery and pinned installed-package consistency
are exercised locally. A supervised public deployment has **not** been verified.

On 2026-10-03, the linked Supabase project applied the runtime migrations,
including the storage content-type fix. The local API reported durable storage
and worker readiness, and the account-usage RPC responded to an empty-owner read.
Synthetic CSV, JSON snapshot and ZIP storage round trips passed; unauthenticated
public downloads were rejected and all temporary test objects were removed.
These checks used no user datasets or login credentials. Live two-account
authorization, OAuth, authenticated end-to-end training, public TLS and load
testing remain deployment checks. Unit tests force memory persistence before
loading the app so they cannot inherit a developer's live Supabase setting.

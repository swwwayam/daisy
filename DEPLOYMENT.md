# Deployment and operating checks

Local VS Code commands remain supported. Docker is optional for development.
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
temporary copies still need memory. Container limits provide an outer bound.

## Containers

The compose configuration separates the static frontend, API, and training
worker. Server secrets are runtime environment variables and excluded from both
build contexts. Only the Supabase URL and publishable browser key enter the
frontend build. API and worker run without root; they share persistent state and
artifact volumes. Resource limits bound each container, and training runs in a
separate child process with a 10-minute deadline.

1. Configure `backend/.env`. Set `DAISY_PERSISTENCE=sqlite` for a single-host local
   deployment or `supabase` for cloud state. Memory mode is refused in production.
2. Apply pending Supabase migrations before choosing Supabase persistence.
3. Ensure `.env.local` contains the frontend URL and publishable key.
4. From the repository root, on a machine with Docker Desktop:

```powershell
docker compose --env-file .env.local config --quiet
docker compose --env-file .env.local up --build -d
docker compose ps
```

Open `http://localhost:8443`. API requests use the same-origin `/api` proxy.
OAuth redirect allowlists must include this origin. Stop with `docker compose down`.
Do not add `-v` unless you intend to delete persisted local state and models.

This is a local deployment template. Before public exposure, add HTTPS, a real
hostname/OAuth allowlist, backups and restore checks, secret management, capacity
tests, monitoring and retention. SQLite volumes support a single host, not a
distributed database. Pin image digests after a verified build if you require
immutable OS/runtime images. Current image tags can change underneath their tags.

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
Invoke-RestMethod http://localhost:8443/api/health/live
Invoke-RestMethod http://localhost:8443/api/health/ready
Invoke-RestMethod http://localhost:8443/api/health/worker
docker compose logs --tail 100 api worker
```

Test worker loss by stopping the worker, waiting at least 90 seconds and checking
that readiness returns 503, then restart it. Verify queued jobs recover, worker
leases expire on abrupt loss, cancellations terminate fits, and models remain
downloadable after restarts. Back up both SQLite state and artifact volumes when
using SQLite; cloud blobs and metadata need matching retention/backup policies.

## Verification status

SQLite heartbeat expiry, queue races, process timeout/cancellation, real child
training, authenticated artifact recovery and pinned installed-package consistency
are exercised locally. Docker is not installed in the authoring environment;
container images and compose execution have **not** been tested. Supabase migration
execution, live RLS/OAuth, public TLS and load testing remain deployment checks.

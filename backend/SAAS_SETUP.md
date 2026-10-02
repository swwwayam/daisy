# Durable DAISY runtime

The runtime resources table supplements the original SaaS schema. It stores
owner-filtered dataset lineage, pipeline context, run snapshots, and artifact
metadata. Binary dataset snapshots and model ZIPs use private Storage buckets.
Workspace sharing is not enabled: runtime resources remain user-owned.

From the repository root, apply the migrations to your linked Supabase project:

```powershell
npx supabase db push
```

Then set `DAISY_PERSISTENCE=supabase` in `backend/.env`. Keep `SUPABASE_URL` and
`SUPABASE_SECRET_KEY` there, never in frontend variables. Restart the API. The
workspace saves completed state and offers a saved-run selector. New uploads,
derived datasets, and model packages survive backend restarts. Existing in-memory
runs are not migrated automatically; upload them again after enabling persistence.

For development without network access, set `DAISY_PERSISTENCE=sqlite`. The default
database is `backend/state/daisy.sqlite`; that directory is ignored by Git. Memory
mode retains the old demo behavior and does not offer durable saved runs. Dataset
snapshots use typed JSON rather than executable pickle files. Each cloud snapshot
must fit the configured 50 MB bucket ceiling even if the original CSV was smaller.

Run `python -m pytest -q` in the backend to test owner filtering, real local restart
recovery, and the mocked Supabase Storage/REST boundary. Tests do not validate your
live cloud policies; verify account A/B isolation after applying migrations.

## Training worker

With durable persistence enabled, training requests return a job ID immediately.
The frontend polls status, offers cancellation, and saves the job ID for resuming
after refresh. Start one worker in a second terminal from `backend`:

```powershell
.\.venv\Scripts\python.exe worker.py
```

SQLite jobs share the configured state database. Supabase jobs use Postgres atomic
claims and private, service-only RPCs. Workers claim jobs once, run one fit at a
time, and terminate a child process on cancellation or after 10 minutes. A crashed
worker's job fails after its 11 minute lease expires; it is never silently rerun.
Each owner has at most 2 active jobs and 10 submissions per rolling 24 hours. The
whole queue is capped at 100 active jobs. Idempotency keys are scoped to the owner;
reusing a key with different parameters returns 409. Polling exposes lifecycle
states, not fabricated percentage estimates.

Training accepts at most 3 models, 100k rows, 1k columns, 20m cells, and 256 MB of
DataFrame memory. SVM jobs are limited to 10k rows. These are application workload
limits, not an OS memory sandbox: use a container memory/CPU limit in deployment.
Memory mode keeps synchronous training for the local demo only. Run API and worker
with identical environment settings. Do not start additional workers until host
capacity has been planned. A cancelled job can leave a completed artifact from a
race near publication; only the creator can access it, and retention cleanup must
remove unreferenced artifacts.

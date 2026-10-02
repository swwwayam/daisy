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
Use one API process for this version: dataset/context caches do not yet support
fully coordinated writes across API replicas. Worker claims and budget reservations
are atomic, and privacy settings are read from durable metadata before new calls.

## Score interpretation

The application reserves a reproducible 60/20/20 random train/validation/test split.
Cleaning, feature, and model recommendation profiles use training rows only;
full-dataset EDA remains descriptive. Learned preprocessing is refitted on the
training fold. Candidate metrics are explicitly labeled validation scores. The
winner alone receives a final test report alongside a majority-class or mean
baseline. The exported estimator is the same fitted winner, not a new full-data
refit. The API's evaluation stage interprets diagnostics saved during the winner's
single final-test scoring; it does not retrain or allow another candidate to probe
the test fold. Older runs without these diagnostics require training again.

The app fixes the test fraction at 20% so changing a fraction after inspecting
data cannot move planning rows into the test set. Missing targets are excluded
after partitioning; duplicate rows are removed before partitioning. Class imbalance
and small test samples produce warnings. Random splitting assumes independent
rows. Time series and repeated entities need time/group-aware splitting before
deployment, and manual choices based on full EDA can still bias estimates. These
scores are not statistical confidence guarantees.

## AI privacy and budget controls

The workspace exposes account and dataset AI switches. Account opt-out overrides
dataset settings. When disabled, cleaning uses missing-cell median/mode rules,
encoding uses training-only cardinality rules, model selection uses a fixed
shortlist, and evaluation reports measured values using explicit thresholds. These
results are labeled rule-based. Chat returns a disabled-service status instead of
inventing a provider reply. Numerical training and model downloads remain available.

Provider profiles replace original column names with stable aliases, omit category
examples/previews, anonymize target class labels, and omit detailed statistics for
likely identifier/contact fields and user-marked sensitive columns. Action columns
are translated back before execution. Chat excludes historical narrative text and
redacts recognizable email/phone patterns in messages. This is data minimization,
not a guarantee of anonymization: other aggregate values and user-entered messages
still go to Groq. Review sensitive columns and disable AI for confidential datasets.

Budget reservations happen before requests: 100 calls and 200,000 total tokens per
owner in a rolling 24 hour window. Actual provider-reported total tokens settle the
reservation. Failures or responses without usage keep the conservative reservation;
failed requests still consume a call. SQLite/Postgres budgets survive restart and
use transactional reservations across workers. Memory-mode counters are demo-only.
Contexts exceeding 32 KB are rejected before transmission. Agent output limits are
bounded to 1,200 or 2,500 tokens; interactive chat is bounded to 512 tokens.

Cloud retention automation, account data deletion/export, billing, and workspace
sharing still need a separate implementation. Do not describe this runtime as a
complete production SaaS merely because these controls are present.

Design references: [Supabase private downloads](https://supabase.com/docs/guides/storage/serving/downloads)
and [scikit-learn evaluation guidance](https://scikit-learn.org/stable/modules/cross_validation.html).

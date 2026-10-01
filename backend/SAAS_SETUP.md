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

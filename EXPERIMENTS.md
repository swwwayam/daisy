# Studies, experiments, and final evaluation

Review an uploaded CSV before cleaning. Confirm the target, task, split strategy,
metric, duplicate policy, types and missing-value markers. Zero stays a value
unless explicitly configured as a missing marker. Download the exact original
CSV from the review panel when needed.

Training compares up to three selected candidates using validation scores. It
does not score test labels. Each attempt receives an independent experiment ID,
timestamp, recorded configuration, fold hashes, data fingerprint, candidate
scores and an artifact reference. The winning fitted model remains downloadable
before final evaluation; its ZIP correctly has null final-test metrics.

In Results, **Finalize and evaluate** loads the saved package and evaluates that
exact fitted estimator. A simple dummy baseline uses the same test rows. The
final report includes train/test metrics, confusion matrix or residual summary,
the baseline, experiment ID, artifact ID and finalization time. No winner is
retrained or refitted on validation/test rows.

Finalization atomically fixes one experiment per uploaded source. Another
experiment cannot evaluate that holdout. Review and training on that source are
then blocked. A scoring failure permits retrying only the claimed experiment;
once saved, retries return the same measured report. Download the final JSON
separately: the original model ZIP is immutable.

The gate is scoped to a source upload, not to every dataset in the world.
Re-uploading the same data creates a new source and can evade this gate. Users
must supply genuinely unseen evaluation data and avoid choosing features/models
after inspecting test results. The software cannot prove those conditions.

## Storage and cloud rollout

SQLite persists experiments and finalization claims across backend/worker
restarts. Demo memory mode loses them on restart. Supabase requires the existing
runtime-resource migrations plus `202610030001_experiment_finalization.sql`:

```powershell
npx supabase db push
```

Review pending migrations before applying them to your linked project. Local
tests exercise SQLite races/restarts and mocked Supabase request contracts;
they do not prove that the migration ran or that live cloud RLS works. Real
two-account verification remains required before deployment.

`GET /experiments?limit=20&offset=0` returns a compact owner-filtered page with
`next_offset` (maximum page size 50). The workspace offers newer/older navigation.
`GET /experiments/{id}` retrieves an independent record and its final report.
Server-side fold row IDs are excluded from this API response.
`POST /experiments/{id}/finalize` measures or retrieves its claimed final report.
`GET /experiments/{id}/report/download` downloads the saved JSON.
All endpoints require the user's bearer token. Other owners receive 404.

`GET /experiments/{id}/model-card/download` provides a ZIP containing a readable
Markdown model card and the complete recorded decision evidence in `report.json`.
It is available before finalization, clearly labelled validation-only, and includes
the independent final report after finalization. It never adds invented scores.

The final report is diagnostic evidence, not a deployment certification. Current
good/moderate/poor labels are generic heuristics; domain requirements, statistical
uncertainty, fairness, leakage outside the recorded pipeline, and live drift still
need review.

New final reports measure the train/test gap using the frozen selection metric.
For MAE/RMSE, the gap is test error minus training error; for scores where higher
is better, it is training score minus test score. A positive gap always means
worse test performance on that metric. The response and model card record both
the metric and direction. Previously finalized reports remain immutable and
retain their original recorded gap. Generic rule-based verdict thresholds still
use weighted F1 or R2, rather than applying unitless thresholds to error units.

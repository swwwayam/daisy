# Saved-model evaluation verification

Prediction-only checks performed on 2026-10-19:

- [Titanic](titanic.md): exact validation reproduction and the processed-CSV mismatch.
- [Adult Census Income](adult-census.md): exact validation reproduction,
  minority-class performance, and duplicate overlap.

These reports describe specific existing experiments. They are not a benchmark
suite, a test of the live UI, or evidence of performance across arbitrary data.
Raw datasets, private owner records, credentials, and fitted models are not
included in these reports.

## Reproduction procedure without retraining

1. Identify the exact experiment and model ZIP. Verify `checksums.json` before
   reading model members. Only load trusted server-produced joblib packages;
   checksums establish integrity, not that a pickle is safe.
2. Read `metadata.json` for the model, target, seed, split strategy, duplicate
   policy, input columns, dependency versions, and metric scope.
3. Read the original input CSV with the same parsing and saved normalization
   policy. Compare the normalized source fingerprint to metadata. Do not use a
   separately encoded/scaled CSV as raw input to the package helper.
4. Reconstruct partitions using the saved configuration and row order. Compare
   the train, validation, and test index hashes before interpreting scores.
   Configuration-aware splits are in `backend/training_config.py`; default
   partitioning is in `backend/model_training.py`. Respect recorded missing-target
   and training-only row exclusions; saved experiment row IDs are authoritative
   when the training fold was filtered.
5. Apply the package's saved preprocessing and feature order, then call the
   saved estimator's `predict` and, when available, `predict_proba`. Do not call
   `fit`, refit preprocessing, or change probability thresholds.
6. Compare candidate metrics on validation rows. Score test rows separately and
   record the confusion-matrix label order, metric averaging, and rounding.
   Match weighted F1 to weighted F1, rather than binary or macro F1.
7. Report fingerprint/hash mismatches and duplicate overlap as limitations.
   A different split, feature representation, or averaging method is not by
   itself proof of incorrect metric computation.

## Reading the export correctly

`training_results` records validation scores used for model selection.
The ZIP is immutable: `final_test_metrics: null` does not establish whether a
separate finalization report was later produced. Existing final reports can be
read separately; do not invoke finalization to conduct a read-only audit.

The active saved-winner evaluation path is `backend/final_evaluation.py`.
The API uses this path through `finalize_experiment` in `backend/main.py`.
The legacy `evaluate_model` helper in `backend/evaluation.py` contains fitting
code and must not be called for a prediction-only check.

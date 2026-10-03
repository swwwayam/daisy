# Validation feature explanations

Results and experiment history offer **Explain the saved model**. Select 1–15
encoded features. The authenticated `POST /experiments/{id}/explain` accepts
`{"features":["feature_name"]}` and returns a downloadable JSON diagnostic.
Only the owner can explain an experiment with a valid saved package.

DAISY verifies the source fingerprint, package integrity, experiment identity,
and validation-fold hash. It reuses the exact fitted estimator and preprocessing,
samples at most 200 validation rows with seed 42, and shuffles each chosen feature
three times. It never fits a new estimator or scores final-test rows. It works
without an AI provider and does not finalize or unlock an experiment's holdout.

The change uses the recorded selection metric. Positive values mean score loss
(or an increase in MAE/RMSE); negative values mean shuffling helped. The baseline
metric shown is measured on the sampled validation rows, so it can differ from
the full validation score. Ranking covers selected features only. Repeat standard
deviation is shuffle variation, not statistical confidence. Correlated features,
unrealistic encoded combinations, and small or poorly performing models can make
results misleading. This is exploratory model sensitivity, not causation or an
independent estimate of production accuracy.

Explanations and predictions share one operation slot per API process and the
rolling-day 100-request / 100,000-scored-row account budget. Each explanation
charges `sample_rows * (1 + 3 * selected_features)` rows, at most 9,200. It also
caps the encoded matrix at one million cells. Results are returned without
persisting additional rows or explanation reports; the browser downloads JSON.

Local tests cover validation-only scoring without refitting, deterministic
repeats, informative versus irrelevant features, group/time splits, source/fold
tampering, owner isolation, shared budget accounting, and classification metrics.
Live cloud and deployment capacity checks remain pending.

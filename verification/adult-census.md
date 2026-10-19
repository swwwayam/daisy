# Adult Census Income evaluation verification

Verified on 2026-10-19 using only predictions from the saved model. No model
was retrained and no production artifacts were regenerated.

## Evidence

- Dataset: `adult_census_income_clean.csv`, 32,561 rows and 15 columns.
- Target: `income`; 24,720 `<=50K` and 7,841 `>50K` records.
- Model: `hist_gradient_boosting_classifier`.
- Experiment: `93974cc8-0b70-4c44-a6f1-4f6dd8acff7f`.
- Artifact: `acc76d32-2818-446a-8772-21ce412e2418`.
- Package checksums, normalized source fingerprint, and all fold hashes matched.
- Random split, seed 42: 19,536 training, 6,512 validation, 6,513 test rows.

## Reproduced scores

| Fold | Accuracy | Weighted precision | Weighted recall | Weighted F1 | Macro F1 | Balanced accuracy | ROC-AUC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Training | 0.8909 | 0.8878 | 0.8909 | 0.8875 | 0.8426 | 0.8243 | 0.9495 |
| Validation | 0.8643 | 0.8591 | 0.8643 | 0.8601 | 0.8006 | 0.7848 | 0.9184 |
| Test | 0.8759 | 0.8720 | 0.8759 | 0.8728 | 0.8222 | 0.8078 | 0.9269 |

Validation metrics exactly reproduced those recorded for the exported winner.
The independently reproduced test confusion matrix was
`[[4643, 299], [509, 1062]]`, with actual classes in rows, predictions in
columns, and label order `<=50K`, `>50K`. Accuracy is 5,705/6,513.

The test majority-class baseline is 0.7588 accuracy. For `>50K` specifically,
precision is 0.7803, recall is 0.6760, and F1 is 0.7244. Weighted scores should
not be interpreted as positive-class scores: lower-income records dominate.

## Limitations

The saved configuration explicitly uses `duplicate_policy: keep`. The input
contains 24 duplicate rows beyond their first occurrences. Two test rows and
eight validation rows exactly match rows in training, so evaluation independence
is not complete. This is a data/split limitation, not an arithmetic error.
Changing the duplicate policy would create a different experiment and cannot
retroactively correct this immutable run.

The ZIP records validation candidate metrics and has `final_test_metrics: null`.
Finalization stores a separate report; the test scores here are an independent
prediction check, not a retrieved finalization report. No metric-calculation
defect was confirmed. These findings concern this dataset and saved model,
not overall application reliability or performance on other datasets.

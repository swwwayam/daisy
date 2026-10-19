# Titanic evaluation verification

Verified on 2026-10-19 using predictions from the existing exported model.
No estimator was fitted and no production artifacts were regenerated.

## Evidence

- Dataset: `Titanic-Dataset.csv`, 891 rows and 12 columns.
- Target: `Survived`; 549 class-0 and 342 class-1 records.
- Model: `gradient_boosting_classifier`.
- Experiment: `32555c00-9e69-4daa-9433-87a38fe33e2a`.
- Artifact: `af46c2b2-8291-4d88-9dec-e62c9eea74b4`.
- Package checksums passed; downloaded and server ZIP bytes matched.
- Normalized source fingerprint and all three partition hashes matched metadata.
- Random split, seed 42: 534 training, 178 validation, 179 test rows.

## Reproduced scores

| Fold | Accuracy | Weighted precision | Weighted recall | Weighted F1 | ROC-AUC |
| --- | ---: | ---: | ---: | ---: | ---: |
| Training | 0.9326 | 0.9354 | 0.9326 | 0.9315 | 0.9754 |
| Validation | 0.8371 | 0.8356 | 0.8371 | 0.8357 | 0.8655 |
| Test | 0.8324 | 0.8334 | 0.8324 | 0.8301 | 0.8620 |

The validation values reproduced the exported winner's candidate metrics.
The independently scored test confusion matrix was `[[95, 10], [20, 54]]`:
rows are actual labels and columns are predicted labels, ordered `0, 1`.
Test accuracy is 149/179; positive-class binary F1 is 0.7826, distinct from
weighted F1. The majority-class test baseline is 0.5866 accuracy.

## Why the processed CSV gives different results

The downloaded processed CSV had 891 rows and 15 columns, with preserved
PassengerId order. Its `Name`, `Age`, `Ticket`, `Fare`, and `Cabin` features
differed from those produced by the model's saved preprocessing. Calling the
estimator directly on these columns gave test accuracy 0.8380 and weighted
F1 0.8355, rather than the scores above.

The exported prediction helper expects raw feature values; the processed CSV
also lacks required raw `Sex` and `Embarked` columns and is rejected by that
helper. Use the original CSV and saved preprocessing for faithful reproduction.

## Interpretation and limits

The export's `training_results` are validation scores. Its
`final_test_metrics` is null because the model ZIP is immutable and finalization
stores a separate report. These test values are an independent prediction check,
not a retrieved finalization report. The training/test accuracy gap is about
10 percentage points; this run does not establish performance on new datasets.
No metric-calculation defect was confirmed.

Relevant implementation: `backend/training_config.py` (`configured_partitions`),
`backend/daisy_predict.py` (`transform`), `backend/model_training.py`
(`_classification_metrics`, `score_final_model`), and
`backend/final_evaluation.py` (`evaluate_saved_winner`).

# Downloading and using trained models

Restart the backend after updating, then start a new run: upload a CSV, complete preprocessing, select a target, and train models. Click **Download trained model** in Model Training or Results. Runs trained before this feature need to be rerun.

The ZIP contains the winning fitted estimator in `model.joblib`, saved preprocessing, `daisy_predict.py`, input schema, metrics and training metadata, pinned Python dependencies, and a README. It does not contain the training CSV. The estimator is the same fitted model used for the reported test metrics; exporting does not retrain it.

Extract the ZIP into a folder, use the Python version recorded in its metadata, and run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe daisy_predict.py new_data.csv predictions.csv
```

Provide the raw input columns listed in `input_schema.json`; the target is optional. The helper applies the saved transformations without fitting on new data. It preserves input row order and rejects missing required columns or unresolved missing values. The included README explains how unseen categories are handled. Only load joblib files from trusted sources.

Artifacts persist in `backend/artifacts` (or the directory set by `DAISY_MODEL_DIR`). `GET /models/{artifact_id}/download` serves an existing ZIP even after backend memory is cleared. The current workspace does not provide a history page for previous runs. Preserve the storage directory when restarting or deploying.

An export that cannot reproduce the training features fails with a visible error instead of offering an incorrect model. Existing derived datasets without recorded transformations must be reuploaded and processed again.

Current evaluation limitation: the existing pipeline fits preprocessing before the train/test split, which can make metrics optimistic. Export preserves that pipeline faithfully; production evaluation should fit learned preprocessing on the training split only. Authentication, per-user artifact authorization, storage quotas, and retention are separate SaaS work.

Use the EXISTING DAISY backend exactly as implemented. Do not define a new API contract and do not invent endpoints.

BASE URL

For local development:

http://localhost:8000

Make the base URL configurable through:

VITE_DAISY_API_URL

Default to http://localhost:8000 if the environment variable is not provided.

There is currently no authentication required.

==================================================
1. HEALTH
==================================================

GET /

Response:

{
  "status": "Backend running",
  "datasets_in_memory": number
}

==================================================
2. UPLOAD DATASET
==================================================

POST /upload-dataset

Content-Type:
multipart/form-data

Form field:

file

The uploaded file must be CSV.

Response:

{
  "rows": number,
  "columns": number,
  "numerical_columns": string[],
  "categorical_columns": string[],
  "missing_values": object,
  "duplicate_rows": number,
  "preview": object[],
  "dataset_id": string,
  "filename": string
}

Save dataset_id in frontend state.

Do not hardcode any returned values.

==================================================
3. DATASET SUMMARY
==================================================

GET /dataset/{dataset_id}/summary

Response:

{
  "rows": number,
  "columns": number,
  "numerical_columns": string[],
  "categorical_columns": string[],
  "missing_values": object,
  "duplicate_rows": number,
  "preview": object[]
}

Use the actual dataset_id.

==================================================
4. ASK DAISY / CHAT
==================================================

POST /chat

Request:

{
  "message": string,
  "dataset_id": string | null
}

Response:

{
  "reply": string
}

The chat should send the current dataset_id whenever a dataset is active.

Never create fake assistant messages.

==================================================
5. DATA CLEANING AGENT
==================================================

POST /agents/data-cleaning

Request:

{
  "dataset_id": string
}

Response:

{
  "summary": string,
  "rows_before": number,
  "rows_after": number,
  "nulls_before": number,
  "nulls_after": number,
  "columns_after": string[],
  "steps": object[],
  "preview": object[],
  "cleaned_dataset_id": string
}

After success, save cleaned_dataset_id as the current processed dataset ID.

Render steps dynamically.

Do not assume what cleaning actions occurred.

==================================================
6. EDA AGENT
==================================================

POST /agents/eda

Request:

{
  "dataset_id": string
}

Response:

A dynamic EDA report object containing the statistical EDA information and:

{
  "summary": string
}

Render the actual fields returned.

Do not invent observations, correlations, outliers, statistics, charts or values.

If a field is not returned, hide that UI element.

==================================================
7. FEATURE ENGINEERING AGENT
==================================================

POST /agents/feature-engineering

Request:

{
  "dataset_id": string,
  "workflow_id": string | null
}

Response:

{
  "workflow_id": string,
  "dataset_id": string,
  "agent": "feature_engineering",
  "status": "success" | "partial" | "failed",
  "input_summary": {
    "n_rows": number,
    "n_columns": number
  },
  "reasoning": string,
  "actions": object[],
  "output_summary": {
    "columns_before": string[],
    "columns_after": string[],
    "preview": object[]
  },
  "metrics": object,
  "execution_time_seconds": number,
  "engineered_dataset_id": string
}

Save:

workflow_id

and

engineered_dataset_id

The actions array must be rendered dynamically.

The backend can return AI-generated actions as well as deterministic fallback actions.

Do not invent action names.

==================================================
8. TARGET COLUMN
==================================================

There is no separate backend endpoint for target selection.

Target selection is a FRONTEND USER interaction.

Populate the target selector using the actual columns of the engineered dataset.

The user selects the target_column.

Do not hardcode target names.

Once selected, pass that target_column to Model Selection.

==================================================
9. MODEL SELECTION AGENT
==================================================

POST /agents/model-selection

Request:

{
  "dataset_id": string,
  "target_column": string,
  "workflow_id": string | null
}

Use the engineered dataset ID.

Response:

{
  "workflow_id": string,
  "dataset_id": string,
  "agent": "model_selection",
  "status": "success" | "partial" | "failed",
  "input_summary": {
    "target_column": string,
    "problem_type": string,
    "n_rows": number,
    "n_features": number
  },
  "reasoning": string,
  "actions": object[],
  "output_summary": {
    "problem_type": string,
    "top_recommendation": string | null,
    "ranked_candidates": string[]
  },
  "metrics": {
    "candidates_proposed": number,
    "candidates_accepted": number,
    "candidates_rejected": number
  },
  "execution_time_seconds": number
}

The actions contain the actual accepted/rejected model recommendations.

Do not hardcode:

- Classification
- Regression
- Model names
- Ranking
- Recommendation reasons

Use the backend response.

==================================================
10. MODEL TRAINING
==================================================

POST /agents/model-training

Request:

{
  "dataset_id": string,
  "target_column": string,
  "candidate_models": string[],
  "test_size": number,
  "workflow_id": string | null
}

candidate_models MUST come from the accepted models returned by Model Selection.

Use:

test_size = 0.2

unless the user explicitly changes it.

Response:

{
  "workflow_id": string,
  "dataset_id": string,
  "agent": "model_training",
  "status": "success" | "partial" | "failed",
  "input_summary": {
    "target_column": string,
    "problem_type": string,
    "n_train": number,
    "n_test": number,
    "rows_dropped_for_missing_values": number
  },
  "reasoning": string,
  "actions": object[],
  "output_summary": {
    "problem_type": string,
    "primary_metric": string,
    "best_model": string | null
  },
  "metrics": object,
  "execution_time_seconds": number
}

The actions array contains actual model training results and metrics.

Build the model comparison UI dynamically from actions.

Do not hardcode metric names, metric values or model names.

The actual winner comes from:

output_summary.best_model

==================================================
11. EVALUATION AGENT
==================================================

POST /agents/evaluation

Request:

{
  "dataset_id": string,
  "target_column": string,
  "model_name": string,
  "test_size": number,
  "workflow_id": string | null
}

Use:

- engineered dataset ID
- selected target column
- actual best_model from Model Training
- same test_size
- current workflow_id

Response:

{
  "workflow_id": string,
  "dataset_id": string,
  "agent": "evaluation",
  "status": "success",
  "input_summary": object,
  "reasoning": string,
  "actions": object[],
  "output_summary": {
    "verdict": "good" | "moderate" | "poor",
    "verdict_corrected_by_guardrail": boolean,
    "observations": string[],
    "train_metrics": object,
    "test_metrics": object,
    "train_test_gap": number,
    "confusion_matrix": object | null,
    "residuals": object | null
  },
  "metrics": object,
  "execution_time_seconds": number
}

Render classification diagnostics such as confusion_matrix only when returned.

Render regression diagnostics such as residuals only when returned.

Do not display irrelevant empty sections.

==================================================
12. DOWNLOAD
==================================================

GET /dataset/{dataset_id}/download

Use the latest valid processed dataset ID.

The response is a CSV file.

Trigger a real browser download.

Do not generate a fake file.

==================================================
DATASET ID FLOW
==================================================

The backend creates processed dataset IDs during the pipeline.

Maintain the current dataset ID in application state.

Initial upload:

dataset_id

After cleaning:

cleaned_dataset_id

After feature engineering:

engineered_dataset_id

Use the latest processed ID for the next stage.

The frontend must NOT assume the original dataset ID remains unchanged.

==================================================
WORKFLOW ID
==================================================

Create/maintain one workflow_id for the current DAISY run.

Pass it through:

Feature Engineering
Model Selection
Model Training
Evaluation

when available.

==================================================
IMPORTANT: NO STATIC RUNTIME DATA
==================================================

The existing DAISY prototype contains visual example values.

Those are ONLY design references.

Do NOT carry them into the functional application.

Do NOT hardcode:

- dataset names
- row counts
- column counts
- percentages
- accuracy
- model accuracy
- model names
- training duration
- number of models
- number of agents
- null counts
- target names
- EDA results
- feature counts
- model metrics
- best model
- agent outputs

Every runtime value must come from the backend.

If data is unavailable:

show loading / empty / unavailable UI.

Do not replace it with fake values.

==================================================
LOADING
==================================================

Do not create fake progress percentages.

The backend endpoints return after completing their operation rather than providing streaming progress.

Therefore use:

- animated loader
- pulsing DAISY node
- contextual processing message
- disabled action button

instead of fake 42%, 67%, etc.

==================================================
ERROR HANDLING
==================================================

Handle HTTP errors properly.

Show:

- failed pipeline stage
- readable error message
- retry action where appropriate

Do not show raw stack traces as the main UI.

==================================================
VISUAL REQUIREMENT
==================================================

IMPORTANT:

The existing DAISY prototype already inside this Figma Make project is the APPROVED visual foundation.

Do not redesign it.

Do not turn it into a generic admin dashboard.

Keep the exact DAISY visual language:

black background
gold/amber atmosphere
cream typography
gold accents
glassmorphism
floating cards
large typography
rounded pills
subtle borders
cinematic lighting
premium AI aesthetic

The landing page should transition into the live ML workspace when the user clicks "Start a run →".

Think:

EXISTING LANDING PAGE
        ↓
START A RUN
        ↓
LIVE DAISY ML WORKSPACE
        ↓
REAL BACKEND DATA

The visual design stays consistent while the content becomes dynamic.

Build the API/service layer and state management around this exact backend contract.
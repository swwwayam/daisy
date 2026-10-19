# D.A.I.S.Y.

Saved-model metric checks for Titanic and Adult Census Income, including
reproduction steps and limitations, are recorded in
[evaluation verification](verification/README.md).

## Convex runtime

Signup and AI abuse controls are documented in [SECURITY.md](SECURITY.md).
New accounts share a three-registration daily limit per network. Convex also
enforces account burst limits, shared AI request/token caps and an admin AI pause switch.

DAISY uses Convex Better Auth for Google/email login, Convex database for
owner-scoped resource records, run history, immutable experiments, final
evaluation gates, usage budgets and atomic training jobs, and Convex file
storage for CSVs, dataset snapshots, reports and downloadable model packages.
Python still performs ML computation; local artifacts are a cache of cloud files.

Set `DAISY_AUTH_PROVIDER=convex`, `DAISY_PERSISTENCE=convex`,
`CONVEX_SITE_URL` and `DAISY_BACKEND_SECRET` in `backend/.env`.
The same private `DAISY_BACKEND_SECRET` must be set on the Convex deployment.
This key belongs only on the server; never use a `VITE_` variable for it.
Frontend `.env.local` needs `VITE_CONVEX_URL` and `VITE_CONVEX_SITE_URL`.
Google client credentials and `BETTER_AUTH_SECRET` belong in Convex environment variables.

After `npx convex dev --once`, run three VS Code terminals:

```powershell
# Project root: frontend
npm run dev
```

```powershell
# backend directory: API
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

```powershell
# backend directory: separate ML worker (same .env)
.\.venv\Scripts\python.exe worker.py
```

Run `npm run test:convex` for the Convex security/queue/budget regressions.
Legacy Supabase and SQLite adapters remain available for rollback, but are
inactive when persistence is set to Convex. Old Supabase accounts/data are
not automatically imported; migrating existing resources requires an explicit
mapping from old owner IDs to their new Convex identities.

**D.A.I.S.Y. --- Data Analysis & Intelligent System for You** is an
automated machine-learning pipeline designed to take a user's dataset
through the major stages of an ML workflow with minimal manual
intervention.

Instead of requiring the user to manually clean data, perform
exploratory analysis, engineer features, choose models, train them, and
interpret results, D.A.I.S.Y. coordinates these stages through
specialized agents and presents the work through an interactive
interface.

> **Upload a dataset → run the pipeline → inspect what D.A.I.S.Y.
> actually did.**

------------------------------------------------------------------------

## ✨ What D.A.I.S.Y. Does

D.A.I.S.Y. automates the following workflow:

1.  **Dataset Upload & Profiling**
    -   Loads the uploaded dataset.
    -   Profiles rows, columns, data types, missing values, duplicates,
        and feature categories.
2.  **Data Cleaning Agent**
    -   Inspects the dataset profile.
    -   Uses AI reasoning to create a structured cleaning plan.
    -   Executes the approved transformations programmatically.
    -   Reports the changes made to the dataset.
3.  **EDA Agent**
    -   Performs exploratory data analysis.
    -   Generates statistical summaries and interprets important
        patterns.
    -   Provides an AI-generated explanation grounded in the computed
        dataset statistics.
4.  **Feature Engineering Agent**
    -   Identifies appropriate feature transformations.
    -   Handles categorical features and other supported preprocessing
        operations.
    -   Executes the resulting feature-engineering plan.
5.  **Model Selection Agent**
    -   Determines the ML problem type.
    -   Ranks suitable candidate models.
    -   Uses guardrails so that only supported model names are accepted.
6.  **Model Training**
    -   Trains supported scikit-learn models on the processed dataset.
    -   Compares model performance using objective evaluation metrics.
    -   Selects the best-performing model according to the problem type.
7.  **Evaluation Agent**
    -   Re-evaluates the selected model.
    -   Calculates diagnostic metrics.
    -   Uses AI to interpret the measured results and produce a grounded
        verdict.
8.  **D.A.I.S.Y. Chat**
    -   Lets the user ask questions about the dataset and pipeline.
    -   Answers using the actual results produced by the agents.
    -   Distinguishes between actions that were completed and
        recommendations that have not been performed.

------------------------------------------------------------------------

## 🧠 Agent Architecture

D.A.I.S.Y. follows an agent-oriented workflow rather than treating the
entire ML process as a single black box.

``` text
                         ┌──────────────────┐
                         │   Dataset Upload │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Dataset Profiling│
                         └────────┬─────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │    Data Cleaning Agent   │
                    │      SENSE → REASON → ACT│
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │        EDA Agent         │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │ Feature Engineering Agent│
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │   Model Selection Agent  │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │      Model Training      │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │       Evaluation         │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │  Results + D.A.I.S.Y.    │
                    │          Chat            │
                    └──────────────────────────┘
```

### Sense → Reason → Act

For agent stages that require AI planning:

-   **Sense** --- collect deterministic information from the dataset
    using Python/Pandas/scikit-learn.
-   **Reason** --- ask the AI model to produce a structured plan based
    on those facts.
-   **Act** --- execute the plan programmatically and record what
    actually happened.

This separation keeps AI reasoning distinct from deterministic data
processing.


------------------------------------------------------------------------
## 🔄 How a D.A.I.S.Y. Run Works

Each pipeline stage follows a controlled execution pattern:

1. **Sense** — deterministic Python code profiles the dataset and collects facts.
2. **Reason** — the AI model interprets those facts and produces a structured plan.
3. **Act** — DAISY validates the plan and executes the approved operations.
4. **Record** — the result is returned to the frontend with the actions and metrics that were actually performed.

This design prevents the language model from directly modifying datasets or inventing model results.
------------------------------------------------------------------------

## 🤖 AI Integration

The current version uses **Groq** with the configurable
`GROQ_MODEL` environment variable. The default model is
`openai/gpt-oss-120b`.

The backend communicates with Groq's OpenAI-compatible API using the
Python `openai` client.

The AI model is used primarily for:

- Cleaning-plan generation
- EDA interpretation
- Feature-engineering planning
- Model-selection reasoning
- Evaluation interpretation
- Natural-language explanations through D.A.I.S.Y. Chat

The actual dataset transformations, model fitting, predictions, and metric calculations are performed deterministically by the backend rather than being delegated to the language model.

------------------------------------------------------------------------

## 🏗️ Tech Stack

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- Interactive pipeline/workspace UI
- Responsive dashboard experience

### Backend

-   Python
-   FastAPI
-   Pandas
-   scikit-learn
-   Pydantic

### AI

-   Groq
-   GPT OSS 120B
-   OpenAI-compatible API client

### SaaS foundation

-   Supabase Auth with email and Google OAuth
-   PostgreSQL with Row Level Security
-   Private dataset and model-artifact storage buckets

### Development

-   npm
-   Git / GitHub

------------------------------------------------------------------------

## 📁 Project Structure

``` text
DAISY/
│
├── backend/
│   ├── agents.py
│   ├── agent_schema.py
│   ├── evaluation.py
│   ├── feature_engineering.py
│   ├── main.py
│   ├── model_selection.py
│   ├── model_training.py
│   ├── requirements.txt
│   └── test_*.py
│
├── verification/
│   ├── README.md
│   ├── adult-census.md
│   └── titanic.md
│
├── public/
│
├── src/
│   ├── components/
│   ├── auth/
│   ├── experience/
│   ├── services/
│   └── workspace/
│
├── .gitignore
├── index.html
├── package.json
├── package-lock.json
├── tsconfig.json
└── vite.config.ts
```

------------------------------------------------------------------------

## 🚀 Running D.A.I.S.Y. Locally

### 1. Clone the repository

``` bash
git clone https://github.com/swwwayam/daisy.git
cd daisy
```

### 2. Backend setup

Create and activate a Python virtual environment:

**Windows PowerShell:**

``` powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the backend dependencies:

``` powershell
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the provided templates:

``` powershell
Copy-Item .env.example .env.local
Copy-Item backend/.env.example backend/.env
```

Fill in the Supabase project URL and publishable key in `.env.local`.
Fill in the Groq and Supabase server values in `backend/.env`.

The publishable key may be used by the browser. Keep
`SUPABASE_SECRET_KEY` and `GROQ_API_KEY` on the backend only. Local
environment files are ignored by Git.

### 4. Start the backend

From the `backend` directory:

``` powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The API will be available at:

``` text
http://localhost:8000
```

For SQLite/Supabase persistence, open a second terminal in `backend` and start
the training worker. It processes queued training jobs and must stay running:

``` powershell
.\.venv\Scripts\python.exe worker.py
```

Demo memory mode trains inline and does not require a worker. Docker is not
required for this version. See [operating checks](DEPLOYMENT.md) for details.

For deployment probes, `GET /health/live` confirms that the API process is
running. `GET /health/ready` checks required configuration, durable storage,
and a recent worker heartbeat in SQLite/Supabase modes. It returns HTTP 503
when a required dependency is unavailable.

You can check both probes from PowerShell after starting the backend:

``` powershell
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
```

### 5. Start the frontend

Open another terminal in the project root:

``` powershell
npm install
npm run dev
```

Vite will provide the local frontend URL:

``` text
http://localhost:8443
```

------------------------------------------------------------------------

## 🔌 Backend API

The FastAPI backend currently exposes endpoints for:

  Endpoint                               Purpose
  -------------------------------------- -------------------------------
  `GET /`                                Backend health/root response
  `GET /health/live`                     Liveness probe for the API process
  `GET /health/ready`                    Readiness probe for required services
  `POST /upload-dataset`                 Upload a dataset
  `GET /dataset/{dataset_id}/summary`    Retrieve dataset summary
  `POST /chat`                           Chat with D.A.I.S.Y.
  `POST /agents/data-cleaning`           Run data-cleaning agent
  `POST /agents/eda`                     Run EDA agent
  `POST /agents/feature-engineering`     Run feature-engineering agent
  `POST /agents/model-selection`         Run model-selection agent
  `POST /agents/model-training`          Train and compare models
  `POST /agents/evaluation`              Evaluate a selected model
  `GET /dataset/{dataset_id}/download`   Download a processed dataset

Browser origins are controlled by the comma-separated `CORS_ORIGINS` setting
in `backend/.env`; keep it limited to the deployed frontend URL(s).

------------------------------------------------------------------------

## 💬 Grounded D.A.I.S.Y. Chat

A key design goal of D.A.I.S.Y. is that the chatbot should explain
**what the pipeline actually did**, rather than giving the user generic
machine-learning instructions.

For example, instead of:

> "You should remove duplicate rows."

D.A.I.S.Y. should explain an executed action such as:

> "I found duplicate rows during Data Cleaning and removed them. The
> dataset changed from the original row count to the cleaned row count."

The chatbot is grounded in stored pipeline results including:

-   Cleaning actions and row/null changes
-   EDA findings
-   Feature-engineering actions
-   Model-selection rankings
-   Training results
-   Evaluation metrics and verdicts

If a stage has not run, D.A.I.S.Y. should say so rather than inventing a
result.

------------------------------------------------------------------------

## 📊 Model Training & Evaluation

Model training is performed using actual machine-learning models rather
than AI-generated claims.

For classification tasks, model comparison uses **weighted F1** as the
primary selection metric.

For regression tasks, model comparison uses **RMSE**, with lower values
preferred.

The evaluation stage then provides additional diagnostics and an
AI-generated interpretation grounded in those measured results.

------------------------------------------------------------------------

## 🔐 Security & Repository Hygiene

The repository intentionally excludes local/environment-specific files
such as:

``` text
backend/.env
backend/.venv/
.env.local
node_modules/
dist/
build/
```

API keys must be supplied through environment variables and should never
be hard-coded into the source code or committed to GitHub.

Datasets, derived outputs, pipeline chat context, and model downloads are restricted
to their authenticated owner. Model download ownership persists beside each ZIP;
SQLite/Supabase modes persist datasets, model packages, lineage, and resumable runs.
Durable modes run training in a separate worker with cancellation and quotas.
Candidates use validation scores; only the winner is scored on the reserved test
fold. Account/dataset controls can disable AI and limit provider inputs.
See [SaaS runtime setup](backend/SAAS_SETUP.md) to enable these features.
See [resource isolation and migration](backend/RESOURCE_ISOLATION.md) for guarantees,
legacy model handling, and verification steps.

------------------------------------------------------------------------

## 🧪 Testing

Backend test files are included under:

``` text
backend/test_*.py
```

Run the backend tests from the `backend` directory with:

``` powershell
pytest
```

If `pytest` is not installed in your environment:

``` powershell
pip install pytest
```

Check frontend types from the project root with:

``` powershell
npm run typecheck
```

------------------------------------------------------------------------

## 🛣️ Future Scope

Potential future improvements include:

-   More supported datasets and file formats
-   Advanced preprocessing and feature selection
-   Automated hyperparameter optimization
-   Reproducible benchmark runner comparing baseline, rules, and AI
-   Production process supervision, alerting, and capacity/load verification
-   Full dataset/model deletion and binary retention automation
-   Explicitly authorized workspace sharing and billing integration
-   Live deployment and two-account authorization verification
-   More sophisticated agent orchestration and recovery

------------------------------------------------------------------------

## 📚 Documentation

Operational and feature documentation:

- [Deployment and worker health](DEPLOYMENT.md) and [frontend hosting](deployment/vercel.md)
- [Security and abuse controls](SECURITY.md)
- [Experiments and final evaluation](EXPERIMENTS.md)
- [Model exports](MODEL_DOWNLOADS.md) and [predictions](PREDICTIONS.md)
- [Explanations](EXPLANATIONS.md) and [visualizations](VISUALIZATIONS.md)
- [Account usage](ACCOUNT_USAGE.md)
- [Runtime setup](backend/SAAS_SETUP.md) and [resource isolation](backend/RESOURCE_ISOLATION.md)
- [Saved-model verification](verification/README.md)

------------------------------------------------------------------------

## 📌 Project Status

**D.A.I.S.Y. v03 — Active Development**

The current version focuses on improving the automated ML workflow, frontend experience, AI-assisted interaction, model training performance, and overall usability.

D.A.I.S.Y. is actively being developed and tested as a final-year academic project.

------------------------------------------------------------------------
## 🆕 What's New in v03

D.A.I.S.Y. v03 introduces improvements across the platform:

- Faster AI-assisted pipeline interactions
- Improved frontend workspace experience
- Enhanced dataset processing workflow
- Improved model training and evaluation flow
- Prediction workflow support
- Improved error handling and diagnostics
- Continued refinement of the agent-driven ML pipeline
 ------------------------------------------------------------------------

## 👥 Contributors

D.A.I.S.Y. is developed as a collaborative academic project

------------------------------------------------------------------------


# D.A.I.S.Y.

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

## 🤖 AI Integration

The current version uses **NVIDIA NIM** with:

**Model:** `deepseek-ai/deepseek-v4-pro-0813`

The backend communicates with NVIDIA's OpenAI-compatible API using the
Python `openai` client.

The AI model is primarily used for:

-   Cleaning-plan generation
-   EDA interpretation
-   Feature-engineering planning
-   Model-selection reasoning
-   Evaluation interpretation
-   Natural-language explanations through D.A.I.S.Y. Chat

The actual dataset transformations, model fitting, predictions, and
metric calculations are performed by the backend rather than being
delegated to the language model.

------------------------------------------------------------------------

## 🏗️ Tech Stack

### Frontend

-   React
-   TypeScript / JavaScript
-   Vite
-   CSS
-   Interactive pipeline/workspace UI

### Backend

-   Python
-   FastAPI
-   Pandas
-   scikit-learn
-   Pydantic

### AI

-   NVIDIA NIM
-   DeepSeek V4 Pro
-   OpenAI-compatible API client

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
├── docs/
│   ├── Architecture.md
│   ├── Bug.md
│   ├── Constraints.md
│   ├── Decisions.md
│   ├── Feature.md
│   ├── Flow.md
│   ├── Handover.md
│   ├── README.md
│   ├── Rollback.md
│   └── Test-Checklist.md
│
├── public/
│
├── src/
│   ├── components/
│   ├── imports/
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
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
```

Install the backend dependencies:

``` powershell
pip install -r requirements.txt
```

### 3. Configure the AI API

Create:

``` text
backend/.env
```

Add your NVIDIA credentials:

``` env
NVIDIA_API_KEY=your_nvidia_api_key
NVIDIA_MODEL=deepseek-ai/deepseek-v4-pro-0813
```

**Never commit `backend/.env` to GitHub.**

### 4. Start the backend

From the `backend` directory:

``` powershell
uvicorn main:app --reload --port 8000
```

The API will be available at:

``` text
http://localhost:8000
```

### 5. Start the frontend

Open another terminal in the project root:

``` powershell
npm install
npm run dev
```

Vite will provide the local frontend URL in the terminal, typically:

``` text
http://localhost:5173
```

------------------------------------------------------------------------

## 🔌 Backend API

The FastAPI backend currently exposes endpoints for:

  Endpoint                               Purpose
  -------------------------------------- -------------------------------
  `GET /`                                Backend health/root response
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
backend/venv/
node_modules/
dist/
build/
```

API keys must be supplied through environment variables and should never
be hard-coded into the source code or committed to GitHub.

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

------------------------------------------------------------------------

## 🛣️ Future Scope

Potential future improvements include:

-   Persistent database-backed pipeline sessions
-   More supported datasets and file formats
-   Larger model library
-   Advanced preprocessing and feature selection
-   Automated hyperparameter optimization
-   Model explainability
-   Pipeline comparison and experiment tracking
-   Persistent user/project history
-   Production deployment
-   More sophisticated agent orchestration and recovery

------------------------------------------------------------------------

## 📚 Documentation

Additional project documentation is available in the [`docs/`](docs/)
directory, including architecture, workflow, design decisions,
constraints, testing, and rollback information.

------------------------------------------------------------------------

## 📌 Project Status

**D.A.I.S.Y. is an active final-year project under development.**

The current version focuses on creating an interactive, agent-driven
automated ML workflow where AI reasoning is combined with deterministic
Python execution and grounded explanations.

------------------------------------------------------------------------

## 👥 Contributors

D.A.I.S.Y. is developed as a collaborative academic project.

------------------------------------------------------------------------

## 📄 License

Add the project's intended license here when one has been selected.

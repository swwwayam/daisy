"""
D.A.I.S.Y ML Backend — Phase 1 + Phase 2 + Phase 3
------------------------------------------------------
Phase 1 (schema): CSV upload -> Schema Understanding Agent logic
(numeric/categorical split, missing values, duplicates, preview).

Phase 2 (consolidation + grounding): LLM chatbot moved here from the
old Node/Express backend -> ONE server for the whole app. Chat is
grounded in the uploaded dataset's schema when a dataset_id is sent.

Phase 3 (Data Cleaning Agent): real sense -> reason -> act agent.
profile_dataframe() senses stats, DeepSeek reasons over them and returns a
strict-JSON cleaning plan, apply_cleaning_plan() executes it with pandas
and reports exactly what happened. See agents.py. This intentionally
stays inside this one FastAPI service — no separate Node layer, no
separate ml-service — Python already talks to the LLM directly (see
/chat below), so a second backend would add servers to run/deploy with
no functional benefit.

Still not built: LangChain-style multi-agent orchestration beyond this,
real model training, SHAP, persistence (everything is in-memory).

Setup:
    pip install -r requirements.txt
    Create backend/.env with: NVIDIA_API_KEY=your_key_here

Run:
    uvicorn main:app --reload --port 8000

Test:
    curl -F "file=@your_data.csv" http://localhost:8000/upload-dataset
    curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
         -d '{"message": "hi"}'
    curl -X POST http://localhost:8000/agents/data-cleaning -H "Content-Type: application/json" \
         -d '{"dataset_id": "<id from upload>"}'
"""

import io
import os
import uuid

import pandas as pd
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

import agents
import evaluation
import feature_engineering
import model_selection
import model_training
from agent_schema import Timer, build_agent_record, new_workflow_id

load_dotenv()

app = FastAPI(title="D.A.I.S.Y ML Backend", version="0.3.0")

# Allow the React frontend (localhost:3000) to call this API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8443",
    "http://192.168.56.1:8443",
    "http://192.168.0.188:8443"
],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory dataset store. Fine for a single-user demo / final year project.
# Swap for a real DB (Postgres, per the plan) once the feedback + history
# phases need persistence across restarts.
DATASETS: dict[str, pd.DataFrame] = {}

# Stores the REAL outputs produced by each pipeline agent so the chatbot can
# explain what D.A.I.S.Y. actually did instead of giving generic instructions.
PIPELINE_CONTEXT: dict[str, dict] = {}

# Tracks dataset lineage (original -> cleaned -> engineered) so chat can still
# see earlier agent results even when the frontend is using a derived dataset id.
DATASET_PARENTS: dict[str, str] = {}


def save_pipeline_result(dataset_id: str, stage: str, result: dict, child_dataset_id: str | None = None):
    """Save an agent result against the current dataset and optionally its child."""
    PIPELINE_CONTEXT.setdefault(dataset_id, {})[stage] = result

    if child_dataset_id:
        DATASET_PARENTS[child_dataset_id] = dataset_id
        # Copy the history forward so the newest dataset id carries the full
        # pipeline story without duplicating mutable result objects.
        PIPELINE_CONTEXT[child_dataset_id] = dict(PIPELINE_CONTEXT.get(dataset_id, {}))
        PIPELINE_CONTEXT[child_dataset_id][stage] = result


def get_pipeline_context(dataset_id: str) -> dict:
    """Return all known agent results for a dataset and its ancestors."""
    chain = []
    current = dataset_id
    seen = set()

    while current and current not in seen:
        seen.add(current)
        chain.append(current)
        current = DATASET_PARENTS.get(current)

    context = {}
    for item in reversed(chain):
        context.update(PIPELINE_CONTEXT.get(item, {}))

    return context


def build_chat_pipeline_context(dataset_id: str) -> str:
    """Build a compact, factual summary of completed pipeline stages for the LLM."""
    context = get_pipeline_context(dataset_id)

    if not context:
        return ""

    sections = ["\n\nACTUAL D.A.I.S.Y. PIPELINE RESULTS (source of truth):"]

    cleaning = context.get("data_cleaning")
    if cleaning:
        sections.append(
            f"""DATA CLEANING:
- Status: completed
- Rows before: {cleaning.get("rows_before")}
- Rows after: {cleaning.get("rows_after")}
- Nulls before: {cleaning.get("nulls_before")}
- Nulls after: {cleaning.get("nulls_after")}
- Agent summary: {cleaning.get("summary", "")}
- Executed actions: {cleaning.get("steps", [])}"""
        )

    eda = context.get("eda")
    if eda:
        sections.append(
            f"""EDA:
- Status: completed
- Agent summary: {eda.get("summary", "")}
- Statistical report: {eda.get("report", {})}"""
        )

    feature = context.get("feature_engineering")
    if feature:
        sections.append(
            f"""FEATURE ENGINEERING:
- Status: completed
- Reasoning: {feature.get("reasoning", "")}
- Actions actually executed: {feature.get("actions", [])}
- Columns before: {feature.get("columns_before", [])}
- Columns after: {feature.get("columns_after", [])}"""
        )

    selection = context.get("model_selection")
    if selection:
        sections.append(
            f"""MODEL SELECTION:
- Status: completed
- Problem type: {selection.get("problem_type")}
- Top recommendation: {selection.get("top_recommendation")}
- Ranked candidates: {selection.get("ranked_candidates", [])}
- Accepted candidates: {selection.get("accepted_candidates", [])}
- Rejected candidates: {selection.get("rejected_candidates", [])}"""
        )

    training = context.get("model_training")
    if training:
        sections.append(
            f"""MODEL TRAINING:
- Status: completed
- Problem type: {training.get("problem_type")}
- Primary metric: {training.get("primary_metric")}
- Best model: {training.get("best_model")}
- Models attempted: {training.get("models_attempted")}
- Models succeeded: {training.get("models_succeeded")}
- Models failed: {training.get("models_failed")}
- Model results: {training.get("results", [])}"""
        )

    evaluation_result = context.get("evaluation")
    if evaluation_result:
        sections.append(
            f"""EVALUATION:
- Status: completed
- Model: {evaluation_result.get("model")}
- Verdict: {evaluation_result.get("verdict")}
- Verdict corrected by guardrail: {evaluation_result.get("verdict_corrected_by_guardrail")}
- Observations: {evaluation_result.get("observations", [])}
- Train metrics: {evaluation_result.get("train_metrics", {})}
- Test metrics: {evaluation_result.get("test_metrics", {})}
- Train-test gap: {evaluation_result.get("train_test_gap", {})}"""
        )

    sections.append(
        """CHATBOT RULES:
- D.A.I.S.Y. is an automated ML pipeline. The user mainly starts stages with buttons; do not treat them as someone who must manually perform the ML work.
- When a stage is completed, explain WHAT D.A.I.S.Y. actually did and report the resulting numbers/actions from the pipeline results above.
- Do NOT tell the user to manually remove, encode, scale, train, evaluate, or otherwise perform an operation that D.A.I.S.Y. has already completed.
- Do NOT invent dataset-specific statistics. If a statistic is not present in the actual results above, say that it has not been calculated yet.
- Distinguish completed actions from recommendations. Only describe an action as completed when the actual pipeline results say it happened.
- If a pipeline stage has not run yet, say it has not run yet rather than pretending it has.
- When useful, mention the next automated pipeline stage, but do not turn the response into a manual to-do list."""
    )

    return "\n".join(sections)

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "deepseek-ai/deepseek-v4-pro-0813")
nvidia_client = (
    OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY,
    )
    if NVIDIA_API_KEY
    else None
)

def generate_ai_text(prompt: str, max_tokens: int = 16384) -> str:
    if nvidia_client is None:
        raise RuntimeError("NVIDIA_API_KEY is not set on the server.")

    response = nvidia_client.chat.completions.create(
        model=NVIDIA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        top_p=0.95,
        max_tokens=max_tokens,
        stream=False,
        extra_body={"chat_template_kwargs": {"thinking": False}},
    )

    return response.choices[0].message.content or ""


@app.get("/")
def health_check():
    return {"status": "Backend running", "datasets_in_memory": len(DATASETS)}


@app.post("/upload-dataset")
async def upload_dataset(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported right now."
        )

    raw_bytes = await file.read()

    try:
        df = pd.read_csv(
            io.BytesIO(raw_bytes),
            keep_default_na=True
        )

        # Detect empty strings and whitespace-only cells as missing
        df = df.replace(r"^\s*$", np.nan, regex=True)

        # Detect common textual representations of missing values
        missing_tokens = [
            "NA",
            "N/A",
            "na",
            "n/a",
            "NULL",
            "null",
            "None",
            "none",
            "?",
            "-"
        ]

        object_columns = df.select_dtypes(
            include=["object", "string"]
        ).columns

        for column in object_columns:
            df[column] = df[column].replace(
                missing_tokens,
                np.nan
            )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not parse CSV: {e}"
        )

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="The uploaded CSV has no rows."
        )

    dataset_id = str(uuid.uuid4())
    DATASETS[dataset_id] = df

    schema_report = build_schema_report(df)
    schema_report["dataset_id"] = dataset_id
    schema_report["filename"] = file.filename

    return schema_report


def build_schema_report(df: pd.DataFrame) -> dict:
    """The Schema Understanding Agent's actual logic (rule-based for now)."""
    numerical_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = df.select_dtypes(exclude="number").columns.tolist()

    missing_values = df.isnull().sum()
    missing_report = {col: int(count) for col, count in missing_values.items() if count > 0}

    return {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "numerical_columns": numerical_cols,
        "categorical_columns": categorical_cols,
        "missing_values": missing_report,
        "duplicate_rows": int(df.duplicated().sum()),
        # NaN isn't valid JSON. Casting to object first stops pandas from
        # silently converting None back to NaN on float columns.
        "preview": df.head(5).astype(object).where(pd.notnull(df.head(5)), None).to_dict(
            orient="records"
        ),
    }


@app.get("/dataset/{dataset_id}/summary")
def get_dataset_summary(dataset_id: str):
    """Lets the frontend re-fetch the schema report without re-uploading."""
    if dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found. Upload it again.")
    return build_schema_report(DATASETS[dataset_id])


class ChatRequest(BaseModel):
    message: str
    dataset_id: str | None = None  # optional — lets the chat ground itself in real data


@app.post("/chat")
def chat(req: ChatRequest):
    if nvidia_client is None:
        return {"reply": "AI temporarily unavailable — NVIDIA_API_KEY is not set on the server."}

    base_prompt = (
         "You are DAISY, an autonomous AI machine-learning pipeline for a student's "
    "data science project. D.A.I.S.Y. performs the ML workflow through automated agents. "
    "Your job in chat is to explain the dataset and, when available, explain what the "
    "pipeline agents ACTUALLY did. Do not give the user manual ML instructions for work "
    "that D.A.I.S.Y. has already completed. Keep answers clear, short, and practical. "
    "For greetings, acknowledgements, simple confirmations, and casual questions, reply "
    "in 1-2 short sentences. Do not give long capability lists unless the user asks. "
    "For pipeline explanations or analytical questions, provide the necessary details "
    "from the actual pipeline results."
    )

    if req.dataset_id and req.dataset_id in DATASETS:
        schema = build_schema_report(DATASETS[req.dataset_id])
        base_prompt += (
            f"\n\nCURRENT DATASET FACTS (use only these facts for dataset-specific claims):\n"
            f"- Rows: {schema['rows']}\n"
            f"- Columns: {schema['columns']}\n"
            f"- Numerical columns: {schema['numerical_columns']}\n"
            f"- Categorical columns: {schema['categorical_columns']}\n"
            f"- Missing values per column: {schema['missing_values']}\n"
            f"- Duplicate rows: {schema['duplicate_rows']}"
        )

        base_prompt += build_chat_pipeline_context(req.dataset_id)

    try:
        result = generate_ai_text(f"{base_prompt}\n\nUser query: {req.message}")
        return {"reply": result}
    except Exception as e:
        print("NVIDIA/DeepSeek error:", e)
        return {"reply": "⚠️ AI temporarily unavailable (quota or config issue). Try again shortly."}


class CleaningRequest(BaseModel):
    dataset_id: str


@app.post("/agents/data-cleaning")
def run_data_cleaning_agent(req: CleaningRequest):
    if req.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found. Upload it again.")
    if nvidia_client is None:
        raise HTTPException(
            status_code=503,
            detail="Data Cleaning Agent needs NVIDIA_API_KEY to be set on the server.",
        )

    df = DATASETS[req.dataset_id]

    # 1. SENSE — profile the data (stats only, never raw rows go to the LLM)
    profile = agents.profile_dataframe(df)

    # 2. REASON — DeepSeek returns a strict-JSON cleaning plan
    prompt = agents.build_cleaning_prompt(profile)
    try:
        result = generate_ai_text(prompt)
        plan = agents.parse_plan(result)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent reasoning step failed: {e}")

    # 3. ACT — pandas executes the plan, step by step, on a copy of the data
    cleaned_df, steps = agents.apply_cleaning_plan(df, plan["actions"])

    cleaned_id = f"{req.dataset_id}-cleaned"
    DATASETS[cleaned_id] = cleaned_df

    result_payload = {
        "summary": plan.get("summary", ""),
        "rows_before": int(len(df)),
        "rows_after": int(len(cleaned_df)),
        "nulls_before": int(df.isna().sum().sum()),
        "nulls_after": int(cleaned_df.isna().sum().sum()),
        "columns_after": cleaned_df.columns.tolist(),
        "steps": steps,
        "preview": cleaned_df.head(5).astype(object).where(pd.notnull(cleaned_df.head(5)), None).to_dict(
            orient="records"
        ),
        "cleaned_dataset_id": cleaned_id,
    }

    save_pipeline_result(req.dataset_id, "data_cleaning", result_payload, cleaned_id)
    return result_payload

class EDARequest(BaseModel):
    dataset_id: str


@app.post("/agents/eda")
def run_eda_agent(req: EDARequest):

    if req.dataset_id not in DATASETS:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Upload it again."
        )

    df = DATASETS[req.dataset_id]

    # ---------- SENSE ----------
    eda_report = agents.profile_for_eda(df)

    # ---------- REASON ----------
    summary = ""

    if nvidia_client is not None:

        prompt = f"""
You are DAISY's Exploratory Data Analysis Agent.

Below is a statistical report generated from a dataset.

Write a short professional summary (5-8 sentences).

Mention:

- overall dataset quality
- numerical vs categorical features
- missing values
- duplicates
- interesting correlations
- possible outliers
- whether the dataset looks suitable for ML

Do NOT invent facts.

EDA REPORT:

{eda_report}
"""

        try:

            result = generate_ai_text(prompt)

            summary = result

        except Exception:

            summary = (
                "EDA completed successfully. "
                "AI summary could not be generated."
            )

    eda_report["summary"] = summary

    save_pipeline_result(
        req.dataset_id,
        "eda",
        {
            "summary": summary,
            "report": eda_report,
        },
    )

    return eda_report


class FeatureEngineeringRequest(BaseModel):
    dataset_id: str
    target_column: str
    workflow_id: str | None = None  # pass the same id across pipeline stages to link them later


@app.post("/agents/feature-engineering")
def run_feature_engineering_agent(req: FeatureEngineeringRequest):
    """First agent to use the standardized output envelope (agent_schema.py,
    resolves Decisions.md OD-4). Same Sense -> Reason -> Act discipline as
    the Data Cleaning Agent — DeepSeek only ever picks from a fixed action
    menu; pandas/scikit-learn does the actual work."""
    if req.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found. Upload it again.")
    if nvidia_client is None:
        raise HTTPException(
            status_code=503,
            detail="Feature Engineering Agent needs NVIDIA_API_KEY to be set on the server.",
        )

    workflow_id = req.workflow_id or new_workflow_id()
    df = DATASETS[req.dataset_id]

    with Timer() as timer:
        # 1. SENSE
        profile = feature_engineering.profile_for_feature_engineering(
    df,
    req.target_column
)

        # 2. REASON
        prompt = feature_engineering.build_feature_engineering_prompt(profile)
        try:
            result = generate_ai_text(prompt)
            plan = feature_engineering.parse_plan(result)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Agent reasoning step failed: {e}")

        # 3. ACT
        engineered_df, steps = feature_engineering.apply_feature_engineering_plan(
    df,
    plan["actions"],
    req.target_column
)

        # 4. FALLBACK — deterministic safety net for anything DeepSeek's plan
        # didn't address. Logged as its own distinct action type
        # ("auto_encode_remaining"), never merged into DeepSeek's own steps,
        # so the audit trail stays honest about what the AI actually
        # decided vs. what this fallback caught. See
        # feature_engineering.py's apply_fallback_encoding() docstring for
        # the full reasoning — this exists because Model Training's own
        # guardrail correctly (and intentionally) refuses non-numeric
        # data rather than guessing, which means the pipeline needs a
        # guarantee upstream that it never gets there in the first place.
        engineered_df, fallback_steps = feature_engineering.apply_fallback_encoding(
    engineered_df,
    req.target_column
)
        steps = steps + fallback_steps

    engineered_id = f"{req.dataset_id}-engineered"
    DATASETS[engineered_id] = engineered_df

    any_failed = any(s["status"] == "failed" for s in steps)
    status = "partial" if any_failed else "success"

    record = build_agent_record(
        workflow_id=workflow_id,
        dataset_id=req.dataset_id,
        agent="feature_engineering",
        status=status,
        input_summary={"n_rows": profile["n_rows"], "n_columns": profile["n_columns"]},
        reasoning=plan.get("summary", ""),
        actions=steps,
        output_summary={
            "columns_before": df.columns.tolist(),
            "columns_after": engineered_df.columns.tolist(),
            "preview": engineered_df.head(5)
            .astype(object)
            .where(pd.notnull(engineered_df.head(5)), None)
            .to_dict(orient="records"),
        },
        metrics={
            "actions_attempted": len(steps),
            "actions_succeeded": sum(1 for s in steps if s["status"] == "success"),
            "actions_failed": sum(1 for s in steps if s["status"] == "failed"),
        },
        execution_time_seconds=timer.elapsed,
    )
    record["engineered_dataset_id"] = engineered_id

    save_pipeline_result(
        req.dataset_id,
        "feature_engineering",
        {
            "reasoning": record.get("reasoning", ""),
            "actions": record.get("actions", []),
            "columns_before": record.get("output_summary", {}).get("columns_before", []),
            "columns_after": record.get("output_summary", {}).get("columns_after", []),
        },
        engineered_id,
    )

    return record


class ModelSelectionRequest(BaseModel):
    dataset_id: str
    target_column: str
    workflow_id: str | None = None


@app.post("/agents/model-selection")
def run_model_selection_agent(req: ModelSelectionRequest):
    """This agent does not transform the dataset — it recommends which ML
    algorithms to try next. Problem type (classification vs. regression)
    is decided DETERMINISTICALLY by looking at the target column, never
    left to DeepSeek. DeepSeek only ranks candidates from a fixed vocabulary;
    a validation guardrail strips out anything it invents that isn't in
    that vocabulary — this plays the same safety-net role the 'Act' step
    plays in the data-transforming agents."""
    if req.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found. Upload it again.")
    if nvidia_client is None:
        raise HTTPException(
            status_code=503,
            detail="Model Selection Agent needs NVIDIA_API_KEY to be set on the server.",
        )

    workflow_id = req.workflow_id or new_workflow_id()
    df = DATASETS[req.dataset_id]

    with Timer() as timer:
        # 1. SENSE (deterministic)
        try:
            profile = model_selection.profile_for_model_selection(df, req.target_column)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # 2. REASON
        prompt = model_selection.build_model_selection_prompt(profile)
        try:
            result = generate_ai_text(prompt)
            plan = model_selection.parse_plan(result)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Agent reasoning step failed: {e}")

        # 3. GUARDRAIL (validate against fixed vocabulary)
        valid, rejected = model_selection.validate_recommendations(
            plan["recommendations"], profile["problem_type"]
        )

    status = "success" if valid and not rejected else ("partial" if valid else "failed")

    record = build_agent_record(
        workflow_id=workflow_id,
        dataset_id=req.dataset_id,
        agent="model_selection",
        status=status,
        input_summary={
            "target_column": profile["target_column"],
            "problem_type": profile["problem_type"],
            "n_rows": profile["n_rows"],
            "n_features": profile["n_features"],
        },
        reasoning=plan.get("summary", ""),
        actions=valid + rejected,
        output_summary={
            "problem_type": profile["problem_type"],
            "top_recommendation": valid[0]["model"] if valid else None,
            "ranked_candidates": [r["model"] for r in sorted(valid, key=lambda r: r.get("rank") or 99)],
        },
        metrics={
            "candidates_proposed": len(plan["recommendations"]),
            "candidates_accepted": len(valid),
            "candidates_rejected": len(rejected),
        },
        execution_time_seconds=timer.elapsed,
    )
    save_pipeline_result(
        req.dataset_id,
        "model_selection",
        {
            "problem_type": record.get("output_summary", {}).get("problem_type"),
            "top_recommendation": record.get("output_summary", {}).get("top_recommendation"),
            "ranked_candidates": record.get("output_summary", {}).get("ranked_candidates", []),
            "accepted_candidates": valid,
            "rejected_candidates": rejected,
        },
    )

    return record


class ModelTrainingRequest(BaseModel):
    dataset_id: str
    target_column: str
    candidate_models: list[str]
    test_size: float = 0.2
    workflow_id: str | None = None


@app.post("/agents/model-training")
def run_model_training_agent(req: ModelTrainingRequest):
    """NO LLM call in this agent — see model_training.py's module
    docstring for why. Real sklearn .fit()/.predict() for every requested
    candidate; the winner is picked by an objective metric comparison,
    not an LLM judgment call."""
    if req.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found. Upload it again.")

    workflow_id = req.workflow_id or new_workflow_id()
    df = DATASETS[req.dataset_id]

    with Timer() as timer:
        try:
            result = model_training.train_and_evaluate(
                df, req.target_column, req.candidate_models, test_size=req.test_size
            )
        except model_training.TrainingDataError as e:
            raise HTTPException(status_code=400, detail=str(e))

    any_failed = any(r["status"] == "failed" for r in result["results"])
    status = "partial" if any_failed else ("success" if result["best_model"] else "failed")

    record = build_agent_record(
        workflow_id=workflow_id,
        dataset_id=req.dataset_id,
        agent="model_training",
        status=status,
        input_summary={
            "target_column": req.target_column,
            "problem_type": result["problem_type"],
            "n_train": result["n_train"],
            "n_test": result["n_test"],
            "rows_dropped_for_missing_values": result["warnings"]["rows_dropped_for_missing_values"],
        },
        reasoning=(
            f"Trained {len(req.candidate_models)} candidate model(s) on an "
            f"{int((1 - req.test_size) * 100)}/{int(req.test_size * 100)} train/test split. "
            f"Best model selected by {result['primary_metric']} "
            f"({'higher' if result['problem_type'] == 'classification' else 'lower'} is better) "
            "— this is an objective metric comparison, not an AI judgment call."
        ),
        actions=result["results"],
        output_summary={
            "problem_type": result["problem_type"],
            "primary_metric": result["primary_metric"],
            "best_model": result["best_model"],
        },
        metrics={
            "models_attempted": len(req.candidate_models),
            "models_succeeded": sum(1 for r in result["results"] if r["status"] == "success"),
            "models_failed": sum(1 for r in result["results"] if r["status"] == "failed"),
        },
        execution_time_seconds=timer.elapsed,
    )
    save_pipeline_result(
        req.dataset_id,
        "model_training",
        {
            "problem_type": result.get("problem_type"),
            "primary_metric": result.get("primary_metric"),
            "best_model": result.get("best_model"),
            "models_attempted": len(req.candidate_models),
            "models_succeeded": sum(1 for r in result["results"] if r["status"] == "success"),
            "models_failed": sum(1 for r in result["results"] if r["status"] == "failed"),
            "results": result.get("results", []),
        },
    )

    return record


class EvaluationRequest(BaseModel):
    dataset_id: str
    target_column: str
    model_name: str
    test_size: float = 0.2
    workflow_id: str | None = None


@app.post("/agents/evaluation")
def run_evaluation_agent(req: EvaluationRequest):
    """Re-trains ONLY the requested model (same split as Model Training,
    given the same test_size/random_state) to get real predictions for
    real diagnostics — a confusion matrix or residual analysis, and a
    train-vs-test overfitting signal, none of which raw aggregate
    metrics alone can give you. DeepSeek interprets the real numbers into
    a plain-language verdict; a guardrail validates that verdict against
    a fixed set of allowed values, same philosophy as every other agent."""
    if req.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found. Upload it again.")
    if nvidia_client is None:
        raise HTTPException(
            status_code=503,
            detail="Evaluation Agent needs NVIDIA_API_KEY to be set on the server.",
        )

    workflow_id = req.workflow_id or new_workflow_id()
    df = DATASETS[req.dataset_id]

    with Timer() as timer:
        try:
            eval_result = evaluation.evaluate_model(
                df, req.target_column, req.model_name, test_size=req.test_size
            )
        except evaluation.TrainingDataError as e:
            raise HTTPException(status_code=400, detail=str(e))

        prompt = evaluation.build_evaluation_prompt(eval_result)
        try:
            result = generate_ai_text(prompt)
            plan = evaluation.parse_plan(result)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Agent reasoning step failed: {e}")

        verdict, was_corrected = evaluation.validate_verdict(plan, eval_result)

    record = build_agent_record(
        workflow_id=workflow_id,
        dataset_id=req.dataset_id,
        agent="evaluation",
        status="success",
        input_summary={
            "model": req.model_name,
            "problem_type": eval_result["problem_type"],
            "n_train": eval_result["n_train"],
            "n_test": eval_result["n_test"],
        },
        reasoning=plan.get("summary", ""),
        actions=[
            {
                "type": "evaluate_model",
                "model": req.model_name,
                "status": "success",
                "message": f"Verdict: {verdict}" + (" (corrected by guardrail)" if was_corrected else ""),
            }
        ],
        output_summary={
            "verdict": verdict,
            "verdict_corrected_by_guardrail": was_corrected,
            "observations": plan.get("observations", []),
            "train_metrics": eval_result["train_metrics"],
            "test_metrics": eval_result["test_metrics"],
            "train_test_gap": eval_result["train_test_gap"],
            "confusion_matrix": eval_result.get("confusion_matrix"),
            "residuals": eval_result.get("residuals"),
        },
        metrics={"primary_metric": eval_result["primary_metric"]},
        execution_time_seconds=timer.elapsed,
    )
    save_pipeline_result(
        req.dataset_id,
        "evaluation",
        {
            "model": req.model_name,
            "verdict": verdict,
            "verdict_corrected_by_guardrail": was_corrected,
            "observations": plan.get("observations", []),
            "train_metrics": eval_result.get("train_metrics", {}),
            "test_metrics": eval_result.get("test_metrics", {}),
            "train_test_gap": eval_result.get("train_test_gap", {}),
        },
    )

    return record


@app.get("/dataset/{dataset_id}/download")
def download_dataset(dataset_id: str):
    if dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    csv_text = DATASETS[dataset_id].to_csv(index=False)
    return StreamingResponse(
        io.StringIO(csv_text),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{dataset_id}.csv"'},
    )

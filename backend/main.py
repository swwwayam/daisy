"""
D.A.I.S.Y ML Backend — Phase 1 + Phase 2 + Phase 3
------------------------------------------------------
Phase 1 (schema): CSV upload -> Schema Understanding Agent logic
(numeric/categorical split, missing values, duplicates, preview).

Phase 2 (consolidation + grounding): Gemini chatbot moved here from the
old Node/Express backend -> ONE server for the whole app. Chat is
grounded in the uploaded dataset's schema when a dataset_id is sent.

Phase 3 (Data Cleaning Agent): real sense -> reason -> act agent.
profile_dataframe() senses stats, Gemini reasons over them and returns a
strict-JSON cleaning plan, apply_cleaning_plan() executes it with pandas
and reports exactly what happened. See agents.py. This intentionally
stays inside this one FastAPI service — no separate Node layer, no
separate ml-service — Python already talks to Gemini directly (see
/chat below), so a second backend would add servers to run/deploy with
no functional benefit.

Still not built: LangChain-style multi-agent orchestration beyond this,
real model training, SHAP, persistence (everything is in-memory).

Setup:
    pip install -r requirements.txt
    Create backend/.env with: GEMINI_API_KEY=your_key_here

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
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types
from pydantic import BaseModel

import agents
import feature_engineering
import model_selection
import model_training
from agent_schema import Timer, build_agent_record, new_workflow_id

load_dotenv()

app = FastAPI(title="D.A.I.S.Y ML Backend", version="0.3.0")

# Allow the React frontend (localhost:3000) to call this API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory dataset store. Fine for a single-user demo / final year project.
# Swap for a real DB (Postgres, per the plan) once the feedback + history
# phases need persistence across restarts.
DATASETS: dict[str, pd.DataFrame] = {}

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


@app.get("/")
def health_check():
    return {"status": "Backend running", "datasets_in_memory": len(DATASETS)}


@app.post("/upload-dataset")
async def upload_dataset(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported right now.")

    raw_bytes = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="The uploaded CSV has no rows.")

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
    if gemini_client is None:
        return {"reply": "AI temporarily unavailable — GEMINI_API_KEY is not set on the server."}

    base_prompt = (
        "You are DAISY, an AI ML pipeline assistant for a student's data "
        "science project. Help with dataset understanding, model selection, "
        "and the ML pipeline (data -> preprocessing -> training -> evaluation). "
        "Keep answers short and practical."
    )

    # This is the "ground the chatbot incrementally" piece: if a dataset has
    # actually been uploaded, hand the real schema to the model instead of
    # letting it guess. As training/SHAP land in later phases, their results
    # get added here the same way.
    if req.dataset_id and req.dataset_id in DATASETS:
        schema = build_schema_report(DATASETS[req.dataset_id])
        base_prompt += (
            f"\n\nThe user has uploaded a real dataset. Use these actual facts "
            f"when relevant instead of generic advice:\n"
            f"- Rows: {schema['rows']}, Columns: {schema['columns']}\n"
            f"- Numerical columns: {schema['numerical_columns']}\n"
            f"- Categorical columns: {schema['categorical_columns']}\n"
            f"- Missing values per column: {schema['missing_values']}\n"
            f"- Duplicate rows: {schema['duplicate_rows']}"
        )

    try:
        result = gemini_client.models.generate_content(
            model="gemini-3-flash-preview",  # same model your Node backend was already using
            contents=[{"role": "user", "parts": [{"text": f"{base_prompt}\n\nUser query: {req.message}"}]}],
        )
        return {"reply": result.text}
    except Exception as e:
        print("Gemini error:", e)
        return {"reply": "⚠️ AI temporarily unavailable (quota or config issue). Try again shortly."}


class CleaningRequest(BaseModel):
    dataset_id: str


@app.post("/agents/data-cleaning")
def run_data_cleaning_agent(req: CleaningRequest):
    if req.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found. Upload it again.")
    if gemini_client is None:
        raise HTTPException(
            status_code=503,
            detail="Data Cleaning Agent needs GEMINI_API_KEY to be set on the server.",
        )

    df = DATASETS[req.dataset_id]

    # 1. SENSE — profile the data (stats only, never raw rows go to the LLM)
    profile = agents.profile_dataframe(df)

    # 2. REASON — Gemini returns a strict-JSON cleaning plan
    prompt = agents.build_cleaning_prompt(profile)
    try:
        result = gemini_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        plan = agents.parse_plan(result.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent reasoning step failed: {e}")

    # 3. ACT — pandas executes the plan, step by step, on a copy of the data
    cleaned_df, steps = agents.apply_cleaning_plan(df, plan["actions"])

    cleaned_id = f"{req.dataset_id}-cleaned"
    DATASETS[cleaned_id] = cleaned_df

    return {
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

    if gemini_client is not None:

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

            result = gemini_client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt,
            )

            summary = result.text

        except Exception:

            summary = (
                "EDA completed successfully. "
                "AI summary could not be generated."
            )

    eda_report["summary"] = summary

    return eda_report


class FeatureEngineeringRequest(BaseModel):
    dataset_id: str
    workflow_id: str | None = None  # pass the same id across pipeline stages to link them later


@app.post("/agents/feature-engineering")
def run_feature_engineering_agent(req: FeatureEngineeringRequest):
    """First agent to use the standardized output envelope (agent_schema.py,
    resolves Decisions.md OD-4). Same Sense -> Reason -> Act discipline as
    the Data Cleaning Agent — Gemini only ever picks from a fixed action
    menu; pandas/scikit-learn does the actual work."""
    if req.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found. Upload it again.")
    if gemini_client is None:
        raise HTTPException(
            status_code=503,
            detail="Feature Engineering Agent needs GEMINI_API_KEY to be set on the server.",
        )

    workflow_id = req.workflow_id or new_workflow_id()
    df = DATASETS[req.dataset_id]

    with Timer() as timer:
        # 1. SENSE
        profile = feature_engineering.profile_for_feature_engineering(df)

        # 2. REASON
        prompt = feature_engineering.build_feature_engineering_prompt(profile)
        try:
            result = gemini_client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            plan = feature_engineering.parse_plan(result.text)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Agent reasoning step failed: {e}")

        # 3. ACT
        engineered_df, steps = feature_engineering.apply_feature_engineering_plan(df, plan["actions"])

        # 4. FALLBACK — deterministic safety net for anything Gemini's plan
        # didn't address. Logged as its own distinct action type
        # ("auto_encode_remaining"), never merged into Gemini's own steps,
        # so the audit trail stays honest about what the AI actually
        # decided vs. what this fallback caught. See
        # feature_engineering.py's apply_fallback_encoding() docstring for
        # the full reasoning — this exists because Model Training's own
        # guardrail correctly (and intentionally) refuses non-numeric
        # data rather than guessing, which means the pipeline needs a
        # guarantee upstream that it never gets there in the first place.
        engineered_df, fallback_steps = feature_engineering.apply_fallback_encoding(engineered_df)
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
    left to Gemini. Gemini only ranks candidates from a fixed vocabulary;
    a validation guardrail strips out anything it invents that isn't in
    that vocabulary — this plays the same safety-net role the 'Act' step
    plays in the data-transforming agents."""
    if req.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found. Upload it again.")
    if gemini_client is None:
        raise HTTPException(
            status_code=503,
            detail="Model Selection Agent needs GEMINI_API_KEY to be set on the server.",
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
            result = gemini_client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            plan = model_selection.parse_plan(result.text)
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
    return record


class ModelTrainingRequest(BaseModel):
    dataset_id: str
    target_column: str
    candidate_models: list[str]
    test_size: float = 0.2
    workflow_id: str | None = None


@app.post("/agents/model-training")
def run_model_training_agent(req: ModelTrainingRequest):
    """NO Gemini call in this agent — see model_training.py's module
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

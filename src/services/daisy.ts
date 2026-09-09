/*
 * DAISY backend service layer.
 * All backend communication is isolated here — visual components never call fetch directly.
 * Contract per daisy-api-spec.md. Base URL configurable via VITE_DAISY_API_URL.
 */

const BASE_URL = (import.meta.env.VITE_DAISY_API_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8000";

export class DaisyApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "DaisyApiError";
    this.status = status;
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data === "string") return data;
    return data?.detail || data?.message || data?.error || `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new DaisyApiError(await readError(res), res.status);
  return (await res.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<T>(res);
}

/* ─── Loose response types — render defensively, only show fields that exist ─── */
export type Dict = Record<string, unknown>;

export interface DatasetSummary {
  rows?: number;
  columns?: number;
  numerical_columns?: string[];
  categorical_columns?: string[];
  missing_values?: Record<string, number>;
  duplicate_rows?: number;
  preview?: Dict[];
  dataset_id?: string;
  filename?: string;
}

export interface CleaningResult {
  summary?: string;
  rows_before?: number;
  rows_after?: number;
  nulls_before?: number;
  nulls_after?: number;
  columns_after?: string[];
  steps?: Dict[];
  preview?: Dict[];
  cleaned_dataset_id?: string;
}

export interface AgentResult extends Dict {
  workflow_id?: string;
  dataset_id?: string;
  agent?: string;
  status?: "success" | "partial" | "failed";
  reasoning?: string;
  actions?: Dict[];
  input_summary?: Dict;
  output_summary?: Dict;
  metrics?: Dict;
  execution_time_seconds?: number;
}

export interface FeatureEngineeringResult extends AgentResult {
  output_summary?: { columns_before?: string[]; columns_after?: string[]; preview?: Dict[] };
  engineered_dataset_id?: string;
}

export interface ModelSelectionResult extends AgentResult {
  output_summary?: { problem_type?: string; top_recommendation?: string | null; ranked_candidates?: string[] };
  metrics?: { candidates_proposed?: number; candidates_accepted?: number; candidates_rejected?: number };
}

export interface TrainingResult extends AgentResult {
  output_summary?: { problem_type?: string; primary_metric?: string; best_model?: string | null };
}

export interface EvaluationResult extends AgentResult {
  output_summary?: {
    verdict?: "good" | "moderate" | "poor";
    verdict_corrected_by_guardrail?: boolean;
    observations?: string[];
    train_metrics?: Dict;
    test_metrics?: Dict;
    train_test_gap?: number;
    confusion_matrix?: Dict | null;
    residuals?: Dict | null;
  };
}

/* ─── Endpoints ─── */
export const daisy = {
  baseUrl: BASE_URL,

  async health(): Promise<{ status: string; datasets_in_memory: number }> {
    return json(await fetch(`${BASE_URL}/`));
  },

  async uploadDataset(file: File): Promise<DatasetSummary> {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE_URL}/upload-dataset`, { method: "POST", body: form });
    return json<DatasetSummary>(res);
  },

  async datasetSummary(datasetId: string): Promise<DatasetSummary> {
    return json(await fetch(`${BASE_URL}/dataset/${encodeURIComponent(datasetId)}/summary`));
  },

  async chat(message: string, datasetId: string | null): Promise<{ reply: string }> {
    return postJson("/chat", { message, dataset_id: datasetId });
  },

  async dataCleaning(datasetId: string): Promise<CleaningResult> {
    return postJson("/agents/data-cleaning", { dataset_id: datasetId });
  },

  async eda(datasetId: string): Promise<AgentResult & { summary?: string }> {
    return postJson("/agents/eda", { dataset_id: datasetId });
  },

  async featureEngineering(
  datasetId: string,
  targetColumn: string,
  workflowId: string | null
): Promise<FeatureEngineeringResult> {
  return postJson("/agents/feature-engineering", {
    dataset_id: datasetId,
    target_column: targetColumn,
    workflow_id: workflowId
  });
},

  async modelSelection(datasetId: string, targetColumn: string, workflowId: string | null): Promise<ModelSelectionResult> {
    return postJson("/agents/model-selection", { dataset_id: datasetId, target_column: targetColumn, workflow_id: workflowId });
  },

  async modelTraining(args: {
    datasetId: string;
    targetColumn: string;
    candidateModels: string[];
    testSize: number;
    workflowId: string | null;
  }): Promise<TrainingResult> {
    return postJson("/agents/model-training", {
      dataset_id: args.datasetId,
      target_column: args.targetColumn,
      candidate_models: args.candidateModels,
      test_size: args.testSize,
      workflow_id: args.workflowId,
    });
  },

  async evaluation(args: {
    datasetId: string;
    targetColumn: string;
    modelName: string;
    testSize: number;
    workflowId: string | null;
  }): Promise<EvaluationResult> {
    return postJson("/agents/evaluation", {
      dataset_id: args.datasetId,
      target_column: args.targetColumn,
      model_name: args.modelName,
      test_size: args.testSize,
      workflow_id: args.workflowId,
    });
  },

  async download(datasetId: string): Promise<{ blob: Blob; filename: string }> {
    const res = await fetch(`${BASE_URL}/dataset/${encodeURIComponent(datasetId)}/download`);
    if (!res.ok) throw new DaisyApiError(await readError(res), res.status);
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/i);
    const filename = match?.[1] || `daisy_${datasetId}.csv`;
    return { blob, filename };
  },
};

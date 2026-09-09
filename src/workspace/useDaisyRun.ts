import { useCallback, useMemo, useState } from "react";
import {
  daisy,
  DaisyApiError,
  type AgentResult,
  type CleaningResult,
  type DatasetSummary,
  type Dict,
  type EvaluationResult,
  type FeatureEngineeringResult,
  type ModelSelectionResult,
  type TrainingResult,
} from "../services/daisy";

export type StageId =
  | "dataset"
  | "cleaning"
  | "eda"
  | "feature"
  | "target"
  | "selection"
  | "training"
  | "results";

export type StageStatus = "idle" | "available" | "running" | "done" | "error" | "waiting";

export const STAGES: { id: StageId; label: string; agent?: string }[] = [
  { id: "dataset", label: "Dataset", agent: "Ingestion" },
  { id: "cleaning", label: "Data Cleaning", agent: "Cleaning agent" },
  { id: "eda", label: "EDA", agent: "EDA agent" },
  { id: "target", label: "Target Column", agent: "You" },
  { id: "feature", label: "Feature Engineering", agent: "Feature agent" },
  { id: "selection", label: "Model Selection", agent: "Selection agent" },
  { id: "training", label: "Model Training", agent: "Training agent" },
  { id: "results", label: "Results", agent: "Evaluation agent" },
];

/* Best-effort extraction of model name + accept decision from an opaque action object. */
export interface ParsedModel {
  name: string;
  accepted: boolean | null;
  raw: Dict;
}
const NAME_KEYS = ["model", "model_name", "name", "candidate", "estimator", "algorithm"];
const ACCEPT_KEYS = ["accepted", "is_accepted", "recommended", "selected", "keep", "kept"];
const DECISION_KEYS = ["decision", "status", "verdict", "recommendation"];

export function parseModels(actions?: Dict[]): ParsedModel[] {
  if (!Array.isArray(actions)) return [];
  const out: ParsedModel[] = [];
  for (const a of actions) {
    if (!a || typeof a !== "object") continue;
    let name = "";
    for (const k of NAME_KEYS) {
      const v = (a as Dict)[k];
      if (typeof v === "string" && v.trim()) { name = v; break; }
    }
    if (!name) continue;
    let accepted: boolean | null = null;
    for (const k of ACCEPT_KEYS) {
      const v = (a as Dict)[k];
      if (typeof v === "boolean") { accepted = v; break; }
    }
    if (accepted === null) {
      for (const k of DECISION_KEYS) {
        const v = (a as Dict)[k];
        if (typeof v === "string") {
          const s = v.toLowerCase();
          if (/(accept|keep|kept|recommend|select|pass)/.test(s)) { accepted = true; break; }
          if (/(reject|drop|discard|skip|fail)/.test(s)) { accepted = false; break; }
        }
      }
    }
    out.push({ name, accepted, raw: a as Dict });
  }
  return out;
}

export interface RunState {
  workflowId: string | null;
  originalDatasetId: string | null;
  currentDatasetId: string | null; // latest processed id
  upload: DatasetSummary | null;
  cleaning: CleaningResult | null;
  eda: (AgentResult & { summary?: string }) | null;
  feature: FeatureEngineeringResult | null;
  engineeredColumns: string[];
  targetColumn: string | null;
  selection: ModelSelectionResult | null;
  training: TrainingResult | null;
  evaluation: EvaluationResult | null;
  bestModel: string | null;
  testSize: number;
  status: Record<StageId, StageStatus>;
  errors: Partial<Record<StageId, string>>;
  chat: { role: "user" | "daisy"; text: string; pending?: boolean }[];
  chatBusy: boolean;
  downloadBusy: boolean;
}

const initialStatus: Record<StageId, StageStatus> = {
  dataset: "available",
  cleaning: "idle",
  eda: "idle",
  feature: "idle",
  target: "idle",
  selection: "idle",
  training: "idle",
  results: "idle",
};

const initialState: RunState = {
  workflowId: null,
  originalDatasetId: null,
  currentDatasetId: null,
  upload: null,
  cleaning: null,
  eda: null,
  feature: null,
  engineeredColumns: [],
  targetColumn: null,
  selection: null,
  training: null,
  evaluation: null,
  bestModel: null,
  testSize: 0.2,
  status: initialStatus,
  errors: {},
  chat: [],
  chatBusy: false,
  downloadBusy: false,
};

export function useDaisyRun() {
  const [s, setS] = useState<RunState>(initialState);

  const patch = useCallback((p: Partial<RunState>) => setS((prev) => ({ ...prev, ...p })), []);
  const setStatus = useCallback(
    (id: StageId, st: StageStatus) => setS((prev) => ({ ...prev, status: { ...prev.status, [id]: st } })),
    []
  );
  const setError = useCallback(
    (id: StageId, msg: string) =>
      setS((prev) => ({ ...prev, status: { ...prev.status, [id]: "error" }, errors: { ...prev.errors, [id]: msg } })),
    []
  );

  function errMsg(e: unknown) {
    if (e instanceof DaisyApiError) return e.message;
    if (e instanceof TypeError) return "Can't reach the DAISY backend. Is it running?";
    return e instanceof Error ? e.message : "Unexpected error";
  }

  const run = useCallback(
    async <T,>(id: StageId, fn: () => Promise<T>, onDone: (r: T) => void) => {
      setS((prev) => ({ ...prev, status: { ...prev.status, [id]: "running" }, errors: { ...prev.errors, [id]: undefined } }));
      try {
        const r = await fn();
        onDone(r);
      } catch (e) {
        setError(id, errMsg(e));
      }
    },
    [setError]
  );

  const upload = useCallback(
    (file: File) =>
      run(
        "dataset",
        () => daisy.uploadDataset(file),
        (r) =>
          setS((prev) => ({
            ...prev,
            upload: r,
            originalDatasetId: r.dataset_id ?? null,
            currentDatasetId: r.dataset_id ?? null,
            engineeredColumns: [...(r.numerical_columns ?? []), ...(r.categorical_columns ?? [])],
            status: { ...prev.status, dataset: "done", cleaning: "available" },
          }))
      ),
    [run]
  );

  const runCleaning = useCallback(() => {
    if (!s.currentDatasetId) return;
    return run(
      "cleaning",
      () => daisy.dataCleaning(s.currentDatasetId as string),
      (r) =>
        setS((prev) => ({
          ...prev,
          cleaning: r,
          currentDatasetId: r.cleaned_dataset_id ?? prev.currentDatasetId,
          engineeredColumns: r.columns_after?.length ? r.columns_after : prev.engineeredColumns,
          status: { ...prev.status, cleaning: "done", eda: "available" },
        }))
    );
  }, [run, s.currentDatasetId]);

  const runEda = useCallback(() => {
    if (!s.currentDatasetId) return;
    return run(
      "eda",
      () => daisy.eda(s.currentDatasetId as string),
      (r) => setS((prev) => ({ ...prev, eda: r, status: { ...prev.status, eda: "done", target: "available" } }))
    );
  }, [run, s.currentDatasetId]);

  const runFeature = useCallback(() => {
  if (!s.currentDatasetId || !s.targetColumn) return;
    return run(
      "feature",
      () =>
  daisy.featureEngineering(
    s.currentDatasetId as string,
    s.targetColumn as string,
    s.workflowId
  ),
      (r) =>
        setS((prev) => ({
          ...prev,
          feature: r,
          workflowId: r.workflow_id ?? prev.workflowId,
          currentDatasetId: r.engineered_dataset_id ?? prev.currentDatasetId,
          engineeredColumns: r.output_summary?.columns_after?.length
            ? (r.output_summary.columns_after as string[])
            : prev.engineeredColumns,
          status: { ...prev.status, feature: "done", selection: "available" },
        }))
    );
  }, [run, s.currentDatasetId, s.targetColumn, s.workflowId]);

  const selectTarget = useCallback((col: string) => {
    setS((prev) => ({
      ...prev,
      targetColumn: col,
      status: { ...prev.status, target: "done", feature: "available" },
    }));
  }, []);

  const runSelection = useCallback(() => {
    if (!s.currentDatasetId || !s.targetColumn) return;
    return run(
      "selection",
      () => daisy.modelSelection(s.currentDatasetId as string, s.targetColumn as string, s.workflowId),
      (r) =>
        setS((prev) => ({
          ...prev,
          selection: r,
          workflowId: r.workflow_id ?? prev.workflowId,
          status: { ...prev.status, selection: "done", training: "available" },
        }))
    );
  }, [run, s.currentDatasetId, s.targetColumn, s.workflowId]);

  const runTraining = useCallback(
    (candidateModels: string[], testSize: number) => {
      if (!s.currentDatasetId || !s.targetColumn || candidateModels.length === 0) return;
      return run(
        "training",
        () =>
          daisy.modelTraining({
            datasetId: s.currentDatasetId as string,
            targetColumn: s.targetColumn as string,
            candidateModels,
            testSize,
            workflowId: s.workflowId,
          }),
        (r) =>
          setS((prev) => ({
            ...prev,
            training: r,
            testSize,
            workflowId: r.workflow_id ?? prev.workflowId,
            bestModel: r.output_summary?.best_model ?? prev.bestModel,
            status: { ...prev.status, training: "done", results: "available" },
          }))
      );
    },
    [run, s.currentDatasetId, s.targetColumn, s.workflowId]
  );

  const runEvaluation = useCallback(() => {
    if (!s.currentDatasetId || !s.targetColumn || !s.bestModel) return;
    return run(
      "results",
      () =>
        daisy.evaluation({
          datasetId: s.currentDatasetId as string,
          targetColumn: s.targetColumn as string,
          modelName: s.bestModel as string,
          testSize: s.testSize,
          workflowId: s.workflowId,
        }),
      (r) =>
        setS((prev) => ({
          ...prev,
          evaluation: r,
          workflowId: r.workflow_id ?? prev.workflowId,
          status: { ...prev.status, results: "done" },
        }))
    );
  }, [run, s.currentDatasetId, s.targetColumn, s.bestModel, s.testSize, s.workflowId]);

  const sendChat = useCallback(
    async (text: string) => {
      const msg = text.trim();
      if (!msg || s.chatBusy) return;
      setS((prev) => ({
        ...prev,
        chatBusy: true,
        chat: [...prev.chat, { role: "user", text: msg }, { role: "daisy", text: "", pending: true }],
      }));
      try {
        const r = await daisy.chat(msg, s.currentDatasetId);
        setS((prev) => {
          const chat = [...prev.chat];
          chat[chat.length - 1] = { role: "daisy", text: r.reply };
          return { ...prev, chat, chatBusy: false };
        });
      } catch (e) {
        setS((prev) => {
          const chat = [...prev.chat];
          chat[chat.length - 1] = { role: "daisy", text: `⚠ ${errMsg(e)}` };
          return { ...prev, chat, chatBusy: false };
        });
      }
    },
    [s.chatBusy, s.currentDatasetId]
  );

  const download = useCallback(async () => {
    if (!s.currentDatasetId) return;
    patch({ downloadBusy: true });
    try {
      const { blob, filename } = await daisy.download(s.currentDatasetId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      /* surfaced via download button state; keep silent otherwise */
    } finally {
      patch({ downloadBusy: false });
    }
  }, [patch, s.currentDatasetId]);

  const acceptedModels = useMemo(() => {
    const parsed = parseModels(s.selection?.actions);
    const accepted = parsed.filter((m) => m.accepted === true).map((m) => m.name);
    if (accepted.length) return accepted;
    // fall back to ranked candidates if the backend didn't flag accept/reject explicitly
    return (s.selection?.output_summary?.ranked_candidates as string[] | undefined) ?? [];
  }, [s.selection]);

  const reset = useCallback(() => setS(initialState), []);

  return { state: s, acceptedModels, upload, runCleaning, runEda, runFeature, selectTarget, runSelection, runTraining, runEvaluation, sendChat, download, reset, setStatus };
}

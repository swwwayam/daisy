import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  type SavedRun,
  type InputPolicy,
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
  trainingJobId: string | null;
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
  trainingJobId: null,
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
  const [savedRuns, setSavedRuns] = useState<SavedRun[]>([]);
  const [historyError, setHistoryError] = useState("");
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyDurable, setHistoryDurable] = useState<boolean | null>(null);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [historyNextOffset, setHistoryNextOffset] = useState<number | null>(null);
  const historyOffsetRef = useRef(0);
  const historyBusy = useRef(false);
  const historyRequest = useRef(0);
  const [s, setS] = useState<RunState>(initialState);

  const loadHistory = useCallback(async (offset = 0) => {
    if (historyBusy.current) return;
    historyBusy.current = true;
    const request = ++historyRequest.current;
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const result = await daisy.savedRuns(offset);
      if (request !== historyRequest.current) return;
      setSavedRuns(result.runs);
      setHistoryDurable(result.durable);
      setHistoryNextOffset(result.next_offset);
      setHistoryOffset(offset);
      historyOffsetRef.current = offset;
    } catch (e) {
      if (request === historyRequest.current) setHistoryError(errMsg(e));
    } finally {
      if (request === historyRequest.current) {
        historyBusy.current = false;
        setHistoryLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadHistory();
    return () => { ++historyRequest.current; historyBusy.current = false; };
  }, [loadHistory]);

  useEffect(() => {
    if (!s.workflowId || !s.originalDatasetId || (Object.values(s.status).includes("running") && !s.trainingJobId) || s.chatBusy) return;
    const timer = window.setTimeout(() => {
      daisy.saveRun(s.workflowId as string, s).then(r => {
        if (r.saved) void loadHistory(historyOffsetRef.current);
      }).catch(e => setHistoryError(errMsg(e)));
    }, 600);
    return () => window.clearTimeout(timer);
  }, [s, loadHistory]);

  const restore = useCallback(async (id: string) => {
    try {
      const state = await daisy.restoreRun(id) as unknown as RunState;
      if (!state.status || !state.currentDatasetId) throw new Error("Saved run is incomplete");
      setS({ ...initialState, ...state, chatBusy: false, downloadBusy: false });
      setHistoryError("");
      if (state.trainingJobId) {
        daisy.waitForTrainingJob(state.trainingJobId).then(result => setS(prev => prev.workflowId === state.workflowId ? {
          ...prev, trainingJobId: null, training: result, bestModel: result.output_summary?.best_model ?? null,
          status: { ...prev.status, training: "done", results: result.output_summary?.best_model ? "available" : "idle" },
        } : prev)).catch(e => setS(prev => prev.workflowId === state.workflowId ? {
          ...prev, trainingJobId: null, status: { ...prev.status, training: "error" }, errors: { ...prev.errors, training: errMsg(e) },
        } : prev));
      }
    } catch (e) { setHistoryError(errMsg(e)); }
  }, []);

  const deleteSavedRun = useCallback(async (id: string) => {
    setHistoryLoading(true);
    setHistoryError("");
    try {
      await daisy.deleteRun(id);
      const nextOffset = savedRuns.length === 1 && historyOffsetRef.current > 0
        ? Math.max(0, historyOffsetRef.current - 20)
        : historyOffsetRef.current;
      historyBusy.current = false;
      await loadHistory(nextOffset);
      return true;
    } catch (e) {
      setHistoryError(errMsg(e));
      setHistoryLoading(false);
      return false;
    }
  }, [loadHistory, savedRuns.length]);

  const patch = useCallback((p: Partial<RunState>) => setS((prev) => ({ ...prev, ...p })), []);
  const setStatus = useCallback(
    (id: StageId, st: StageStatus) => setS((prev) => ({ ...prev, status: { ...prev.status, [id]: st } })),
    []
  );
  const setError = useCallback(
    (id: StageId, msg: string) =>
      setS((prev) => ({ ...prev, trainingJobId: id === "training" ? null : prev.trainingJobId, status: { ...prev.status, [id]: "error" }, errors: { ...prev.errors, [id]: msg } })),
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
            ...initialState,
            upload: r,
            workflowId: crypto.randomUUID(),
            originalDatasetId: r.dataset_id ?? null,
            currentDatasetId: r.dataset_id ?? null,
            engineeredColumns: [...(r.numerical_columns ?? []), ...(r.categorical_columns ?? [])],
            status: { ...initialStatus, dataset: r.review_available ? "waiting" : "done", cleaning: r.review_available ? "idle" : "available" },
          }))
      ),
    [run]
  );

  const reviewInput = useCallback((policy: InputPolicy) => {
    if (!s.originalDatasetId) return;
    return run("dataset", () => daisy.reviewDataset(s.originalDatasetId as string, policy), result => setS(prev => ({
      ...initialState, workflowId: prev.workflowId, originalDatasetId: prev.originalDatasetId,
      currentDatasetId: result.dataset_id ?? null, upload: result,
      targetColumn: result.training_config?.target_column ?? null,
      engineeredColumns: [...(result.numerical_columns ?? []), ...(result.categorical_columns ?? [])],
      status: { ...initialStatus, dataset: "done", cleaning: "available" },
    })));
  }, [run, s.originalDatasetId]);

  const runCleaning = useCallback((zeroAsMissing: string[] = []) => {
    if (!s.currentDatasetId) return;
    return run(
      "cleaning",
      () => daisy.dataCleaning(s.currentDatasetId as string, zeroAsMissing),
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
      setS(prev => ({ ...prev, trainingJobId: null, training: null, evaluation: null, bestModel: null,
        status: { ...prev.status, results: "idle" } }));
      return run(
        "training",
        () =>
          daisy.modelTraining({
            datasetId: s.currentDatasetId as string,
            targetColumn: s.targetColumn as string,
            candidateModels,
            testSize,
            workflowId: s.workflowId,
            onQueued: id => setS(prev => ({ ...prev, trainingJobId: id, testSize })),
          }),
        (r) =>
          setS((prev) => ({
            ...prev,
            training: r,
            trainingJobId: null,
            testSize,
            workflowId: r.workflow_id ?? prev.workflowId,
            bestModel: r.output_summary?.best_model ?? null,
            status: { ...prev.status, training: "done", results: r.output_summary?.best_model ? "available" : "idle" },
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
          experimentId: s.training?.output_summary?.experiment_id,
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
  }, [run, s.currentDatasetId, s.targetColumn, s.bestModel, s.testSize, s.workflowId, s.training]);

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
    if (s.selection?.output_summary?.available_models?.length) return s.selection.output_summary.available_models;
    const parsed = parseModels(s.selection?.actions);
    const accepted = parsed.filter((m) => m.accepted === true).map((m) => m.name);
    if (accepted.length) return accepted;
    // fall back to ranked candidates if the backend didn't flag accept/reject explicitly
    return (s.selection?.output_summary?.ranked_candidates as string[] | undefined) ?? [];
  }, [s.selection]);

  const reset = useCallback(() => setS(initialState), []);

  return { state: s, savedRuns, historyError, historyLoading, historyDurable, historyOffset, historyNextOffset, loadHistory, restore, deleteSavedRun, acceptedModels, upload, reviewInput, runCleaning, runEda, runFeature, selectTarget, runSelection, runTraining, runEvaluation, sendChat, download, reset, setStatus };
}

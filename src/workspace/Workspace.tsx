import { useEffect, useMemo, useRef, useState } from "react";
import type { Dict } from "../services/daisy";
import { parseModels, STAGES, type StageId, type StageStatus, useDaisyRun } from "./useDaisyRun";
import {
  ActionList,
  Empty,
  ErrorBox,
  formatValue,
  humanize,
  isScalar,
  Loader,
  MetricGrid,
  PreviewTable,
  StatChips,
} from "./primitives";

type Run = ReturnType<typeof useDaisyRun>;

/* ─── helpers ─── */
function actionableStage(status: Record<StageId, StageStatus>): StageId {
  const order = STAGES.map((s) => s.id);
  const running = order.find((id) => status[id] === "running");
  if (running) return running;
  const avail = order.find((id) => status[id] === "available" || status[id] === "waiting");
  if (avail) return avail;
  const done = [...order].reverse().find((id) => status[id] === "done");
  return done ?? "dataset";
}

function sumMissing(m?: Record<string, number>): number | null {
  if (!m) return null;
  return Object.values(m).reduce((a, b) => a + (typeof b === "number" ? b : 0), 0);
}

/* generic renderer for an unknown report object (EDA) */
const PLUMBING = new Set(["workflow_id", "dataset_id", "agent", "status", "execution_time_seconds", "input_summary"]);
function DynamicReport({ data }: { data: Dict }) {
  const entries = Object.entries(data).filter(([k, v]) => !PLUMBING.has(k) && v !== null && v !== undefined && v !== "");
  if (!entries.length) return <Empty>No analysis fields were returned.</Empty>;
  return (
    <div className="report">
      {entries.map(([k, v]) => {
        if (k === "summary" && typeof v === "string") return <p className="lead" key={k}>{v}</p>;
        if (k === "preview" && Array.isArray(v)) return <div key={k}><h5>{humanize(k)}</h5><PreviewTable rows={v as Dict[]} /></div>;
        if (isScalar(v)) return <div className="report-line" key={k}><span className="report-k">{humanize(k)}</span><span className="report-v">{formatValue(v)}</span></div>;
        if (Array.isArray(v)) {
          if (v.every(isScalar)) return (
            <div className="report-block" key={k}>
              <h5>{humanize(k)}</h5>
              <div className="tag-list">{v.map((x, i) => <span className="tag" key={i}>{formatValue(x)}</span>)}</div>
            </div>
          );
          return <div className="report-block" key={k}><h5>{humanize(k)}</h5><ActionList actions={v as Dict[]} /></div>;
        }
        if (typeof v === "object") {
          const obj = v as Dict;
          const allScalar = Object.values(obj).every(isScalar);
          return (
            <div className="report-block" key={k}>
              <h5>{humanize(k)}</h5>
              {allScalar ? <MetricGrid metrics={obj} /> : <DynamicReport data={obj} />}
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}

function StatusBadge({ status }: { status?: string }) {
  if (!status) return null;
  const cls = status === "success" ? "ok" : status === "failed" ? "bad" : "warn";
  return <span className={`status-badge ${cls}`}>{humanize(status)}</span>;
}

/* ─── Pipeline rail ─── */
function PipelineRail({ status, active, onPick }: { status: Record<StageId, StageStatus>; active: StageId; onPick: (id: StageId) => void }) {
  return (
    <div className="rail-wrap">
      <div className="rail">
        {STAGES.map((s, i) => {
          const st = status[s.id];
          const reachable = st !== "idle";
          const prevDone = i > 0 && status[STAGES[i - 1].id] === "done";
          const flowing = i > 0 && prevDone && (st === "running" || st === "available" || st === "waiting");
          return (
            <div className="rail-step" key={s.id}>
              {i > 0 && <span className={`rail-link ${prevDone ? "lit" : ""} ${flowing ? "flow" : ""}`} />}
              <button
                className={`rail-node ${st} ${active === s.id ? "focus" : ""}`}
                disabled={!reachable}
                onClick={() => reachable && onPick(s.id)}
                title={s.label}
              >
                <span className="rail-dot">
                  {st === "done" && <span className="rail-check" />}
                  {st === "error" && <span className="rail-x" />}
                </span>
                <span className="rail-label">{s.label}</span>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Dataset stage ─── */
function DatasetPanel({ run, focusSelf }: { run: Run; focusSelf: () => void }) {
  const { state } = run;
  const st = state.status.dataset;
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);

  function handleFiles(files: FileList | null) {
    const f = files?.[0];
    if (!f) return;
    focusSelf();
    run.upload(f);
  }

  if (st === "running") return <Loader message="DAISY is reading your dataset…" />;

  if (st === "error") return <ErrorBox message={state.errors.dataset || "Upload failed"} onRetry={() => inputRef.current?.click()} />;

  if (!state.upload) {
    return (
      <div
        className={`dropzone ${drag ? "over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handleFiles(e.dataTransfer.files); }}
        onClick={() => inputRef.current?.click()}
      >
        <div className="drop-mark" />
        <div className="drop-title">Drop a CSV to begin</div>
        <div className="drop-sub">DAISY will profile it, then clean, engineer, and train — end to end.</div>
        <button className="pill pill-solid">Choose file</button>
        <input ref={inputRef} type="file" accept=".csv,text/csv" hidden onChange={(e) => handleFiles(e.target.files)} />
      </div>
    );
  }

  const u = state.upload;
  const missing = sumMissing(u.missing_values);
  return (
    <div className="panel-body">
      <div className="panel-head">
        <div>
          <div className="panel-eyebrow">Dataset loaded</div>
          <h3 className="panel-title">{u.filename || "Untitled dataset"}</h3>
          {u.dataset_id && <div className="mono id-chip">{u.dataset_id}</div>}
        </div>
        <button className="pill pill-ghost" onClick={() => inputRef.current?.click()}>Replace</button>
        <input ref={inputRef} type="file" accept=".csv,text/csv" hidden onChange={(e) => handleFiles(e.target.files)} />
      </div>
      <div className="metric-grid">
        {u.rows != null && <div className="metric-cell"><div className="metric-val">{u.rows.toLocaleString()}</div><div className="metric-lbl">Rows</div></div>}
        {u.columns != null && <div className="metric-cell"><div className="metric-val">{u.columns.toLocaleString()}</div><div className="metric-lbl">Columns</div></div>}
        {u.duplicate_rows != null && <div className="metric-cell"><div className="metric-val">{u.duplicate_rows.toLocaleString()}</div><div className="metric-lbl">Duplicate rows</div></div>}
        {missing != null && <div className="metric-cell"><div className="metric-val">{missing.toLocaleString()}</div><div className="metric-lbl">Missing values</div></div>}
      </div>
      {!!u.numerical_columns?.length && (
        <div className="report-block"><h5>Numerical columns</h5><div className="tag-list">{u.numerical_columns.map((c) => <span className="tag" key={c}>{c}</span>)}</div></div>
      )}
      {!!u.categorical_columns?.length && (
        <div className="report-block"><h5>Categorical columns</h5><div className="tag-list">{u.categorical_columns.map((c) => <span className="tag alt" key={c}>{c}</span>)}</div></div>
      )}
      <div className="report-block"><h5>Preview</h5><PreviewTable rows={u.preview} /></div>
    </div>
  );
}

/* ─── Cleaning stage ─── */
function CleaningPanel({ run }: { run: Run }) {
  const { state } = run;
  const st = state.status.cleaning;
  if (st === "idle") return <Empty>Upload a dataset to unlock cleaning.</Empty>;
  if (st === "available") return <ReadyState title="Data Cleaning agent" desc="Detects nulls, duplicates, and skew, then repairs them — and tells you exactly what it changed." action="Run cleaning" onRun={run.runCleaning} />;
  if (st === "running") return <Loader message="DAISY is cleaning your dataset…" />;
  if (st === "error") return <ErrorBox message={state.errors.cleaning || "Cleaning failed"} onRetry={run.runCleaning} />;
  const c = state.cleaning;
  if (!c) return null;
  return (
    <div className="panel-body">
      {c.summary && <p className="lead">{c.summary}</p>}
      <div className="metric-grid">
        {c.rows_before != null && c.rows_after != null && (
          <div className="metric-cell"><div className="metric-val">{c.rows_before.toLocaleString()} → {c.rows_after.toLocaleString()}</div><div className="metric-lbl">Rows</div></div>
        )}
        {c.nulls_before != null && c.nulls_after != null && (
          <div className="metric-cell"><div className="metric-val">{c.nulls_before.toLocaleString()} → {c.nulls_after.toLocaleString()}</div><div className="metric-lbl">Nulls</div></div>
        )}
        {c.columns_after != null && <div className="metric-cell"><div className="metric-val">{c.columns_after.length}</div><div className="metric-lbl">Columns after</div></div>}
      </div>
      {!!c.steps?.length && <div className="report-block"><h5>What DAISY did</h5><ActionList actions={c.steps} /></div>}
      {!!c.preview?.length && <div className="report-block"><h5>Cleaned preview</h5><PreviewTable rows={c.preview} /></div>}
    </div>
  );
}

/* ─── EDA stage ─── */
function EdaPanel({ run }: { run: Run }) {
  const { state } = run;
  const st = state.status.eda;
  if (st === "idle") return <Empty>Run cleaning first, then DAISY can analyze the data.</Empty>;
  if (st === "available") return <ReadyState title="EDA agent" desc="Explores distributions, relationships, and anomalies, then explains what stands out." action="Run EDA" onRun={run.runEda} />;
  if (st === "running") return <Loader message="DAISY is analyzing your data…" />;
  if (st === "error") return <ErrorBox message={state.errors.eda || "EDA failed"} onRetry={run.runEda} />;
  if (!state.eda) return null;
  return <div className="panel-body"><DynamicReport data={state.eda as Dict} /></div>;
}

/* ─── Feature engineering stage ─── */
function FeaturePanel({ run }: { run: Run }) {
  const { state } = run;
  const st = state.status.feature;
  if (st === "idle") return <Empty>Select a target column first to unlock feature engineering.</Empty>;
  if (st === "available") return <ReadyState title="Feature Engineering agent" desc="Encodes, scales, and derives features — reasoning about each transformation." action="Run feature engineering" onRun={run.runFeature} />;
  if (st === "running") return <Loader message="DAISY is engineering features…" />;
  if (st === "error") return <ErrorBox message={state.errors.feature || "Feature engineering failed"} onRetry={run.runFeature} />;
  const f = state.feature;
  if (!f) return null;
  const before = f.output_summary?.columns_before?.length;
  const after = f.output_summary?.columns_after?.length;
  return (
    <div className="panel-body">
      <div className="panel-head">
        <div><div className="panel-eyebrow">Feature engineering</div><h3 className="panel-title">Transformations applied</h3></div>
        <StatusBadge status={f.status} />
      </div>
      {f.reasoning && <p className="lead">{f.reasoning}</p>}
      <div className="metric-grid">
        {before != null && <div className="metric-cell"><div className="metric-val">{before}</div><div className="metric-lbl">Columns before</div></div>}
        {after != null && <div className="metric-cell"><div className="metric-val">{after}</div><div className="metric-lbl">Columns after</div></div>}
        {f.execution_time_seconds != null && <div className="metric-cell"><div className="metric-val">{f.execution_time_seconds.toFixed(2)}s</div><div className="metric-lbl">Compute time</div></div>}
      </div>
      <div className="report-block"><h5>Actions</h5><ActionList actions={f.actions} empty="No transformations were returned." /></div>
      <MetricGrid metrics={f.metrics} />
      {!!f.output_summary?.preview?.length && <div className="report-block"><h5>Engineered preview</h5><PreviewTable rows={f.output_summary.preview} /></div>}
    </div>
  );
}

/* ─── Target column stage ─── */
function TargetPanel({ run }: { run: Run }) {
  const { state } = run;
  const [q, setQ] = useState("");
  const st = state.status.target;
  const cols = state.engineeredColumns;
  const filtered = cols.filter((c) => c.toLowerCase().includes(q.toLowerCase()));
  if (st === "idle") return <Empty>Complete EDA to choose a target.</Empty>;
  return (
    <div className="panel-body">
      <div className="panel-eyebrow">Target column</div>
      <h3 className="panel-title">What should DAISY predict?</h3>
      <p className="lead">Pick the column to model. Everything else becomes a feature.</p>
      {cols.length === 0 ? (
        <Empty>No columns available yet.</Empty>
      ) : (
        <>
          <input className="ws-input" placeholder="Filter columns…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="col-grid">
            {filtered.map((c) => (
              <button key={c} className={`col-chip ${state.targetColumn === c ? "sel" : ""}`} onClick={() => run.selectTarget(c)}>
                {c}
              </button>
            ))}
          </div>
          {state.targetColumn && <div className="target-confirm">Predicting <strong>{state.targetColumn}</strong> — model selection is now available.</div>}
        </>
      )}
    </div>
  );
}

/* ─── Model selection stage ─── */
function SelectionPanel({ run }: { run: Run }) {
  const { state } = run;
  const st = state.status.selection;
  if (st === "idle") return <Empty>Select a target column to unlock model selection.</Empty>;
  if (st === "available") return <ReadyState title="Model Selection agent" desc="Infers the problem type and proposes candidate models, accepting or rejecting each with reasoning." action="Run model selection" onRun={run.runSelection} />;
  if (st === "running") return <Loader message="DAISY is selecting models…" />;
  if (st === "error") return <ErrorBox message={state.errors.selection || "Model selection failed"} onRetry={run.runSelection} />;
  const m = state.selection;
  if (!m) return null;
  const parsed = parseModels(m.actions);
  return (
    <div className="panel-body">
      <div className="panel-head">
        <div>
          <div className="panel-eyebrow">Model selection</div>
          {m.output_summary?.problem_type && <h3 className="panel-title">{humanize(m.output_summary.problem_type)}</h3>}
        </div>
        <StatusBadge status={m.status} />
      </div>
      {m.reasoning && <p className="lead">{m.reasoning}</p>}
      <StatChips data={m.metrics} />
      {parsed.length > 0 ? (
        <div className="model-grid">
          {parsed.map((p, i) => (
            <div className={`model-card ${p.accepted === true ? "accepted" : p.accepted === false ? "rejected" : ""}`} key={i}>
              <div className="model-card-head">
                <span className="model-name">{p.name}</span>
                {p.accepted !== null && <span className={`chip-tag ${p.accepted ? "ok" : "bad"}`}>{p.accepted ? "Accepted" : "Rejected"}</span>}
              </div>
              {Object.entries(p.raw).filter(([k, v]) => isScalar(v) && !["model", "model_name", "name"].includes(k)).map(([k, v]) => (
                <div className="model-line" key={k}><span>{humanize(k)}</span><span>{formatValue(v)}</span></div>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <ActionList actions={m.actions} empty="No candidate models were returned." />
      )}
      {!!m.output_summary?.ranked_candidates?.length && (
        <div className="report-block"><h5>Ranked candidates</h5>
          <div className="tag-list">{m.output_summary.ranked_candidates.map((c, i) => <span className="tag" key={c}><span className="rank">{i + 1}</span>{c}</span>)}</div>
        </div>
      )}
    </div>
  );
}

/* ─── Training stage ─── */
function TrainingPanel({ run }: { run: Run }) {
  const { state, acceptedModels } = run;
  const st = state.status.training;
  const [picked, setPicked] = useState<string[]>([]);
  const [testSize, setTestSize] = useState(0.2);
  useEffect(() => { setPicked(acceptedModels); }, [acceptedModels]);

  if (st === "idle") return <Empty>Run model selection to unlock training.</Empty>;
  if (st === "running") return <Loader message="DAISY is training candidate models…" />;
  if (st === "error") return <ErrorBox message={state.errors.training || "Training failed"} onRetry={() => run.runTraining(picked, testSize)} />;

  if (st === "available") {
    return (
      <div className="panel-body">
        <div className="panel-eyebrow">Model training</div>
        <h3 className="panel-title">Train the accepted models</h3>
        {acceptedModels.length === 0 ? (
          <Empty>Model selection didn't return any accepted models to train.</Empty>
        ) : (
          <>
            <p className="lead">Select which candidates to train and hand DAISY the wheel.</p>
            <div className="col-grid">
              {acceptedModels.map((mName) => (
                <button key={mName} className={`col-chip ${picked.includes(mName) ? "sel" : ""}`}
                  onClick={() => setPicked((p) => p.includes(mName) ? p.filter((x) => x !== mName) : [...p, mName])}>
                  {mName}
                </button>
              ))}
            </div>
            <div className="test-size">
              <label>Test size <span className="mono">{testSize.toFixed(2)}</span></label>
              <input type="range" min={0.1} max={0.4} step={0.05} value={testSize} onChange={(e) => setTestSize(parseFloat(e.target.value))} />
            </div>
            <button className="pill pill-solid" disabled={picked.length === 0} onClick={() => run.runTraining(picked, testSize)}>
              Train {picked.length} model{picked.length === 1 ? "" : "s"} →
            </button>
          </>
        )}
      </div>
    );
  }

  const t = state.training;
  if (!t) return null;
  const parsed = parseModels(t.actions);
  const best = t.output_summary?.best_model;
  return (
    <div className="panel-body">
      <div className="panel-head">
        <div><div className="panel-eyebrow">Training complete</div>{best && <h3 className="panel-title">Winner: {best}</h3>}</div>
        <StatusBadge status={t.status} />
      </div>
      {t.reasoning && <p className="lead">{t.reasoning}</p>}
      <StatChips data={t.output_summary} only={["problem_type", "primary_metric"]} />
      {parsed.length > 0 ? (
        <div className="model-grid">
          {parsed.map((p, i) => (
            <div className={`model-card ${p.name === best ? "accepted best" : ""}`} key={i}>
              <div className="model-card-head">
                <span className="model-name">{p.name}{p.name === best && <span className="crown">★</span>}</span>
              </div>
              {Object.entries(p.raw).filter(([k, v]) => isScalar(v) && !["model", "model_name", "name"].includes(k)).map(([k, v]) => (
                <div className="model-line" key={k}><span>{humanize(k)}</span><span>{formatValue(v)}</span></div>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <ActionList actions={t.actions} empty="No training results were returned." />
      )}
    </div>
  );
}

/* ─── confusion matrix (best-effort) ─── */
function findMatrix(obj: Dict): number[][] | null {
  const direct = Object.values(obj).find((v) => Array.isArray(v) && Array.isArray((v as unknown[])[0]));
  if (direct) return direct as number[][];
  if (Array.isArray((obj as unknown))) return obj as unknown as number[][];
  return null;
}
function ConfusionMatrix({ data }: { data: Dict }) {
  const matrix = findMatrix(data);
  const labels = (data.labels || data.classes) as (string | number)[] | undefined;
  if (!matrix) return <MetricGrid metrics={data} />;
  return (
    <div className="cm-wrap">
      <table className="cm">
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              {labels && <th>{formatValue(labels[i])}</th>}
              {row.map((cell, j) => {
                const max = Math.max(...matrix.flat());
                const intensity = max ? (cell as number) / max : 0;
                return <td key={j} style={{ background: `rgba(232,168,87,${0.08 + intensity * 0.5})` }}>{formatValue(cell)}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ─── Results / evaluation stage ─── */
function ResultsPanel({ run }: { run: Run }) {
  const { state } = run;
  const st = state.status.results;
  if (st === "idle") return <Empty>Train models to reach results.</Empty>;
  const t = state.training;
  const e = state.evaluation;
  const best = state.bestModel;

  return (
    <div className="panel-body">
      {best && (
        <div className="winner">
          <div className="winner-eyebrow">Best model</div>
          <div className="winner-name">{best}</div>
          {t?.output_summary?.primary_metric && <div className="winner-metric mono">{humanize(String(t.output_summary.primary_metric))}</div>}
        </div>
      )}

      {st !== "done" && st !== "running" && (
        <ReadyState title="Evaluation agent" desc="Runs a deeper diagnostic on the winning model — train/test gap, and per-problem diagnostics." action="Run evaluation" onRun={run.runEvaluation} />
      )}
      {st === "running" && <Loader message="DAISY is evaluating the winning model…" />}
      {st === "error" && <ErrorBox message={state.errors.results || "Evaluation failed"} onRetry={run.runEvaluation} />}

      {e && (
        <div className="eval">
          {e.output_summary?.verdict && (
            <div className={`verdict ${e.output_summary.verdict}`}>
              <span className="verdict-dot" />
              Verdict: {humanize(e.output_summary.verdict)}
              {e.output_summary.verdict_corrected_by_guardrail && <span className="guardrail">guardrail-adjusted</span>}
            </div>
          )}
          {e.reasoning && <p className="lead">{e.reasoning}</p>}
          {!!e.output_summary?.observations?.length && (
            <div className="report-block"><h5>Observations</h5>
              <ul className="obs-list">{e.output_summary.observations.map((o, i) => <li key={i}>{o}</li>)}</ul>
            </div>
          )}
          <div className="split">
            {e.output_summary?.train_metrics && <div className="report-block"><h5>Train metrics</h5><MetricGrid metrics={e.output_summary.train_metrics} /></div>}
            {e.output_summary?.test_metrics && <div className="report-block"><h5>Test metrics</h5><MetricGrid metrics={e.output_summary.test_metrics} /></div>}
          </div>
          {e.output_summary?.train_test_gap != null && (
            <div className="report-line"><span className="report-k">Train / test gap</span><span className="report-v">{formatValue(e.output_summary.train_test_gap)}</span></div>
          )}
          {e.output_summary?.confusion_matrix && <div className="report-block"><h5>Confusion matrix</h5><ConfusionMatrix data={e.output_summary.confusion_matrix as Dict} /></div>}
          {e.output_summary?.residuals && <div className="report-block"><h5>Residuals</h5><MetricGrid metrics={e.output_summary.residuals as Dict} /></div>}
        </div>
      )}
    </div>
  );
}

/* ─── generic ready-state ─── */
function ReadyState({ title, desc, action, onRun }: { title: string; desc: string; action: string; onRun: () => void }) {
  return (
    <div className="ready">
      <div className="ready-mark" />
      <div className="panel-eyebrow">{title}</div>
      <p className="ready-desc">{desc}</p>
      <button className="pill pill-solid" onClick={onRun}>{action} →</button>
    </div>
  );
}

/* ─── live floating cards (right) ─── */
function LiveCards({ run }: { run: Run }) {
  const { state } = run;
  const runningStage = STAGES.find((s) => state.status[s.id] === "running");
  const missing = sumMissing(state.upload?.missing_values);
  const processed = state.currentDatasetId && state.currentDatasetId !== state.originalDatasetId;
  const bestMetric = state.training?.output_summary?.primary_metric;

  return (
    <div className="live-cards">
      <div className="float-card ws-card">
        <div className="fc-k"><span>Dataset health</span><span>{state.upload ? "●" : "○"}</span></div>
        {state.upload ? (
          <>
            <div className="fc-v">{state.upload.rows?.toLocaleString() ?? "—"} <span className="fc-unit">rows</span></div>
            <div className="fc-note">
              {state.upload.columns ?? "—"} cols
              {missing != null && ` · ${missing.toLocaleString()} missing`}
              {state.upload.duplicate_rows != null && ` · ${state.upload.duplicate_rows} dupes`}
            </div>
          </>
        ) : <div className="fc-note">Waiting for a dataset…</div>}
      </div>

      <div className="float-card ws-card">
        <div className="fc-k"><span>Active agent</span><span className="mono">{runningStage ? "run" : "idle"}</span></div>
        {runningStage ? (
          <><div className="fc-v gold" style={{ fontSize: 16 }}>{runningStage.label}</div><div className="fc-note running-note"><span className="ws-node sm" />Working…</div></>
        ) : <div className="fc-note">No agent running.</div>}
      </div>

      <div className="float-card ws-card">
        <div className="fc-k"><span>Best model</span><span>{state.bestModel ? "★" : "—"}</span></div>
        {state.bestModel ? (
          <><div className="fc-v gold" style={{ fontSize: 17 }}>{state.bestModel}</div>{bestMetric && <div className="fc-note">{humanize(String(bestMetric))}</div>}</>
        ) : <div className="fc-note">Train models to see a winner.</div>}
      </div>

      {processed && (
        <button className="pill pill-ghost dl" onClick={run.download} disabled={state.downloadBusy}>
          {state.downloadBusy ? "Preparing…" : "Download processed CSV ↓"}
        </button>
      )}
    </div>
  );
}

/* ─── contextual control (next valid action) ─── */
function ControlPanel({ run, goto }: { run: Run; goto: (id: StageId) => void }) {
  const { state, acceptedModels } = run;
  const s = state.status;
  let node: React.ReactNode = null;

  if (s.dataset !== "done") node = <ControlHint label="Start here" text="Upload a CSV to begin the run." onClick={() => goto("dataset")} cta="Go to upload" />;
  else if (s.cleaning === "available") node = <ControlHint label="Next" text="Clean the raw dataset." onClick={run.runCleaning} cta="Run cleaning" solid />;
  else if (s.eda === "available") node = <ControlHint label="Next" text="Explore the cleaned data." onClick={run.runEda} cta="Run EDA" solid />;
  else if (s.feature === "available") node = <ControlHint label="Next" text="Engineer features." onClick={run.runFeature} cta="Run feature engineering" solid />;
  else if (s.target === "available" && !state.targetColumn) node = <ControlHint label="Your input" text="Choose the column to predict." onClick={() => goto("target")} cta="Select target" solid />;
  else if (s.selection === "available") node = <ControlHint label="Next" text="Let DAISY pick candidate models." onClick={run.runSelection} cta="Run model selection" solid />;
  else if (s.training === "available") node = <ControlHint label="Next" text={acceptedModels.length ? "Train the accepted models." : "Review model selection."} onClick={() => goto("training")} cta="Set up training" solid />;
  else if (s.results === "available" || (s.results === "done")) node = <ControlHint label="Results" text="Inspect the winning model." onClick={() => goto("results")} cta="View results" solid />;

  const running = STAGES.find((st) => state.status[st.id] === "running");
  if (running) node = <ControlHint label="In progress" text={`${running.label} is running…`} busy />;

  if (!node) return null;
  return <div className="control-panel">{node}</div>;
}
function ControlHint({ label, text, cta, onClick, solid, busy }: { label: string; text: string; cta?: string; onClick?: () => void; solid?: boolean; busy?: boolean }) {
  return (
    <div className="control-card">
      <div className="control-label">{label}</div>
      <div className="control-text">{text}</div>
      {busy ? <div className="control-busy"><span className="ws-node sm" />Working…</div>
        : cta && <button className={`pill ${solid ? "pill-solid" : "pill-ghost"}`} onClick={onClick}>{cta}</button>}
    </div>
  );
}

/* ─── agent activity drawer ─── */
function ActivityDrawer({ run }: { run: Run }) {
  const { state } = run;
  const [open, setOpen] = useState(false);
  const [exp, setExp] = useState<StageId | null>(null);
  const outputs: Record<StageId, Dict | null> = {
    dataset: (state.upload as Dict) ?? null,
    cleaning: (state.cleaning as Dict) ?? null,
    eda: (state.eda as Dict) ?? null,
    feature: (state.feature as Dict) ?? null,
    target: state.targetColumn ? ({ target_column: state.targetColumn } as Dict) : null,
    selection: (state.selection as Dict) ?? null,
    training: (state.training as Dict) ?? null,
    results: (state.evaluation as Dict) ?? null,
  };
  return (
    <div className={`activity ${open ? "open" : ""}`}>
      <button className="activity-toggle" onClick={() => setOpen((o) => !o)}>
        <span className="ws-node sm" />DAISY activity log <span className="activity-caret">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="activity-body">
          {STAGES.map((st) => {
            const status = state.status[st.id];
            const out = outputs[st.id];
            const err = state.errors[st.id];
            return (
              <div className="activity-item" key={st.id}>
                <button className="activity-row" onClick={() => setExp((e) => (e === st.id ? null : st.id))} disabled={status === "idle"}>
                  <span className={`activity-status ${status}`} />
                  <span className="activity-name">{st.label}</span>
                  <span className="activity-agent mono">{st.agent}</span>
                  <span className={`activity-tag ${status}`}>{humanize(status)}</span>
                </button>
                {exp === st.id && (
                  <div className="activity-detail">
                    {err && <div className="activity-err">{err}</div>}
                    {out && "reasoning" in out && typeof out.reasoning === "string" && <p className="lead sm">{out.reasoning}</p>}
                    {out && "summary" in out && typeof out.summary === "string" && <p className="lead sm">{out.summary}</p>}
                    {out && Array.isArray((out as Dict).actions) && <ActionList actions={(out as Dict).actions as Dict[]} />}
                    {out && (out as Dict).metrics ? <MetricGrid metrics={(out as Dict).metrics as Dict} /> : null}
                    {!out && !err && <div className="activity-empty">No output yet.</div>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ─── chat dock ─── */
function ChatDock({ run }: { run: Run }) {
  const { state } = run;
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => { scroller.current?.scrollTo({ top: scroller.current.scrollHeight }); }, [state.chat]);
  function submit() {
    if (!q.trim()) return;
    setOpen(true);
    run.sendChat(q);
    setQ("");
  }
  return (
    <div className={`chat-dock ${open && state.chat.length ? "open" : ""}`}>
      {open && state.chat.length > 0 && (
        <div className="chat-log" ref={scroller}>
          {state.chat.map((m, i) => (
            <div key={i} className={`chat-msg ${m.role}`}>
              {m.pending ? <span className="chat-typing"><span /><span /><span /></span> : m.text}
            </div>
          ))}
        </div>
      )}
      <div className="ask-bar">
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder={state.upload ? `Ask DAISY about ${state.upload.filename || "your dataset"}…` : "Ask DAISY to build something…"}
          onFocus={() => state.chat.length && setOpen(true)} />
        <button onClick={submit} disabled={state.chatBusy}>{state.chatBusy ? "…" : "Ask agent →"}</button>
      </div>
    </div>
  );
}

/* ─── stage panel switch ─── */
function StagePanel({ stage, run, goto }: { stage: StageId; run: Run; goto: (id: StageId) => void }) {
  switch (stage) {
    case "dataset": return <DatasetPanel run={run} focusSelf={() => goto("dataset")} />;
    case "cleaning": return <CleaningPanel run={run} />;
    case "eda": return <EdaPanel run={run} />;
    case "feature": return <FeaturePanel run={run} />;
    case "target": return <TargetPanel run={run} />;
    case "selection": return <SelectionPanel run={run} />;
    case "training": return <TrainingPanel run={run} />;
    case "results": return <ResultsPanel run={run} />;
  }
}

/* ─── Workspace root ─── */
export default function Workspace({ onExit }: { onExit: () => void }) {
  const run = useDaisyRun();
  const [focus, setFocus] = useState<StageId | null>(null);
  const active = actionableStage(run.state.status);
  // follow the pipeline automatically unless the user is inspecting an earlier stage
  const displayed = focus ?? active;
  const stageMeta = STAGES.find((s) => s.id === displayed)!;

  function goto(id: StageId) { setFocus(id); }
  // when the actionable stage advances past the user's focus, snap forward
  useEffect(() => { setFocus(null); }, [active]);

  return (
    <div className="ws">
      <header className="ws-nav">
        <button className="logo" onClick={onExit}><span className="logo-mark" />D.A.I.S.Y</button>
        <div className="ws-nav-mid mono">{run.state.workflowId ? `run ${run.state.workflowId.slice(0, 8)}` : "new run"}</div>
        <button className="pill pill-ghost" onClick={() => { run.reset(); setFocus(null); }}>New run</button>
      </header>

      <PipelineRail status={run.state.status} active={displayed} onPick={goto} />

      <div className="ws-body">
        <main className="ws-stage">
          <div className="stage-head">
            <span className="stage-index mono">{String(STAGES.findIndex((s) => s.id === displayed) + 1).padStart(2, "0")}</span>
            <h2>{stageMeta.label}</h2>
          </div>
          <div className="stage-card">
            <StagePanel stage={displayed} run={run} goto={goto} />
          </div>
        </main>
        <aside className="ws-aside">
          <ControlPanel run={run} goto={goto} />
          <LiveCards run={run} />
        </aside>
      </div>

      <ActivityDrawer run={run} />
      <ChatDock run={run} />
    </div>
  );
}

import { useState } from "react";
import { daisy, type DatasetSummary, type InputPolicy, type TrainingConfig } from "../services/daisy";

export function InputReviewPanel({ dataset, busy, confirmed, error, onReview }: {
  dataset: DatasetSummary; busy: boolean; confirmed: boolean; error?: string;
  onReview: (policy: InputPolicy) => void;
}) {
  const [tokens, setTokens] = useState((dataset.input_policy?.missing_tokens ?? []).join("\n"));
  const [types, setTypes] = useState<InputPolicy["column_types"]>(dataset.input_policy?.column_types ?? {});
  const [columnTokens, setColumnTokens] = useState<Record<string, string>>(Object.fromEntries(Object.entries(dataset.input_policy?.column_tokens ?? {}).map(([column, values]) => [column, values.join("\n")])));
  const [blankMissing, setBlankMissing] = useState(dataset.input_policy?.blank_is_missing ?? true);
  const [downloadBusy, setDownloadBusy] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const [config, setConfig] = useState<TrainingConfig>(dataset.training_config ?? { target_column: "", problem_type: "auto", split_strategy: "random", group_column: null, time_column: null, primary_metric: "auto", duplicate_policy: "keep" });
  const columns = Object.keys(dataset.source_column_dtypes ?? dataset.column_dtypes ?? {});
  const values = (text: string) => text.split(/\r?\n/).filter(value => value.length > 0);
  async function original() {
    if (!dataset.dataset_id) return;
    setDownloadBusy(true); setDownloadError("");
    try {
      const url = URL.createObjectURL(await daisy.downloadSource(dataset.dataset_id));
      const link = document.createElement("a"); link.href = url; link.download = dataset.filename || "daisy-original.csv";
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    } catch (failure) { setDownloadError(failure instanceof Error ? failure.message : "Download failed. Try again."); }
    finally { setDownloadBusy(false); }
  }
  return <details className="input-review" open={!confirmed}>
    <summary>{confirmed ? "Data interpretation confirmed" : "Review what your values mean"}</summary>
    <p className="lead">Literal values such as NA, ?, and - are preserved. Choose missing-value markers only when your source used them to mean unknown. Zero is reviewed separately during cleaning.</p>
    <label className="review-field">Missing markers for all columns (one per line)
      <textarea className="ws-input" rows={3} value={tokens} disabled={busy} onChange={event => setTokens(event.target.value)} placeholder="Leave empty to preserve literal categories" />
    </label>
    <label className="review-field"><span><input type="checkbox" checked={blankMissing} disabled={busy} onChange={event => setBlankMissing(event.target.checked)} /> Treat empty and whitespace-only cells as missing</span></label>
    <div className="review-columns">{columns.map(column => <div className="review-column" key={column}>
      <div><strong>{column}</strong><small>Detected: {dataset.column_dtypes?.[column]}</small></div>
      <label>Interpret as<select className="ws-input" value={types[column] ?? "auto"} disabled={busy} onChange={event => setTypes(previous => ({ ...previous, [column]: event.target.value as InputPolicy["column_types"][string] }))}>
        <option value="auto">Automatic</option><option value="numeric">Number</option><option value="text">Text / category</option><option value="datetime">Date / time</option>
      </select></label>
      <label>Additional missing markers<textarea className="ws-input" rows={2} placeholder="One per line; optional" value={columnTokens[column] ?? ""} disabled={busy} onChange={event => setColumnTokens(previous => ({ ...previous, [column]: event.target.value }))} /></label>
    </div>)}</div>
    <h4>Agree on the experiment before cleaning</h4>
    <p className="lead">Choose the target, task and split now. These stay fixed for this study. Group/date split columns are excluded from model inputs.</p>
    <div className="review-columns">
      <label className="review-field">Prediction target<select className="ws-input" disabled={busy} value={config.target_column} onChange={event => setConfig(previous => ({ ...previous, target_column: event.target.value }))}><option value="">Choose a target</option>{columns.map(column => <option key={column}>{column}</option>)}</select></label>
      <label className="review-field">Task type<select className="ws-input" disabled={busy} value={config.problem_type} onChange={event => setConfig(previous => ({ ...previous, problem_type: event.target.value as TrainingConfig["problem_type"], primary_metric: "auto", split_strategy: event.target.value === "regression" && previous.split_strategy === "stratified" ? "random" : previous.split_strategy }))}><option value="auto">Suggest from training data</option><option value="classification">Classification — predict a category</option><option value="regression">Regression — predict a quantity</option></select></label>
      <label className="review-field">How should rows be split?<select className="ws-input" disabled={busy} value={config.split_strategy} onChange={event => setConfig(previous => ({ ...previous, split_strategy: event.target.value as TrainingConfig["split_strategy"] }))}><option value="random">Random — independent rows</option><option value="stratified" disabled={config.problem_type === "regression"}>Stratified — preserve label proportions</option><option value="group">Group — keep entities in one fold</option><option value="time">Time — train on earlier observations</option></select></label>
      {(config.split_strategy === "group" || config.split_strategy === "time") && <label className="review-field">{config.split_strategy === "group" ? "Entity/group column" : "Date/time column"}<select className="ws-input" disabled={busy} value={(config.split_strategy === "group" ? config.group_column : config.time_column) ?? ""} onChange={event => setConfig(previous => ({ ...previous, [config.split_strategy === "group" ? "group_column" : "time_column"]: event.target.value || null }))}><option value="">Choose a column</option>{columns.filter(column => column !== config.target_column).map(column => <option key={column}>{column}</option>)}</select></label>}
      <label className="review-field">Winning metric<select className="ws-input" disabled={busy} value={config.primary_metric} onChange={event => setConfig(previous => ({ ...previous, primary_metric: event.target.value as TrainingConfig["primary_metric"] }))}><option value="auto">Default for the confirmed task</option>{(config.problem_type !== "regression" ? ["f1_macro", "f1_weighted", "balanced_accuracy", "accuracy"] : []).map(metric => <option key={metric}>{metric}</option>)}{(config.problem_type !== "classification" ? ["rmse", "mae", "r2"] : []).map(metric => <option key={metric}>{metric}</option>)}</select></label>
      <label className="review-field">Exact duplicate rows<select className="ws-input" disabled={busy} value={config.duplicate_policy} onChange={event => setConfig(previous => ({ ...previous, duplicate_policy: event.target.value as TrainingConfig["duplicate_policy"] }))}><option value="keep">Keep — repeated observations can be valid</option><option value="drop">Remove exact duplicate records</option></select></label>
    </div>
    <p className="policy-footnote">Applying a review starts a new dataset version and resets later stages. Your original CSV remains available.</p>
    <div className="saved-history-actions">
      <button className="pill pill-solid" disabled={busy || !config.target_column} onClick={() => onReview({ missing_tokens: values(tokens), column_types: types, column_tokens: Object.fromEntries(Object.entries(columnTokens).map(([column, text]) => [column, values(text)])), blank_is_missing: blankMissing, training_config: config })}>{busy ? "Applying review…" : confirmed ? "Apply updated interpretation" : "Confirm and continue"}</button>
      <button className="pill pill-ghost" disabled={downloadBusy || busy} onClick={() => { void original(); }}>{downloadBusy ? "Preparing…" : "Download original CSV"}</button>
    </div>
    {(error || downloadError) && <p role="alert">{error || downloadError}</p>}
  </details>;
}

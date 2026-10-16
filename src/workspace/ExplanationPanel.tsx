import { useState } from "react";
import { daisy, type ExplanationResult, type ShapResult } from "../services/daisy";
import { BarChart } from "./Charts";

const SHAP_MODELS = new Set(["decision_tree_classifier", "decision_tree_regressor", "random_forest_classifier", "random_forest_regressor", "extra_trees_classifier", "extra_trees_regressor"]);

export function ExplanationPanel({ experimentId, columns, model }: { experimentId: string; columns: string[]; model?: string }) {
  const [selected, setSelected] = useState<string[]>(columns.slice(0, 5));
  const [method, setMethod] = useState<"permutation" | "shap">("permutation");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ExplanationResult | ShapResult | null>(null);
  const [error, setError] = useState("");
  const shapSupported = !!model && SHAP_MODELS.has(model) && columns.length <= 256;
  async function explain() {
    setBusy(true); setError(""); setResult(null);
    try { setResult(await daisy.explain(experimentId, selected, method)); }
    catch (err) { setError(err instanceof Error ? err.message : "Explanation failed. Try permutation importance."); }
    finally { setBusy(false); }
  }
  function download() {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `daisy-${result.method}-${experimentId}.json`;
    document.body.appendChild(anchor); anchor.click(); anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <details className="report-block explanation-workspace">
    <summary>Explain the saved model</summary>
    <label className="chart-selector">Explanation method<select value={method} disabled={busy} onChange={e => { setMethod(e.target.value as typeof method); setResult(null); setError(""); }}>
      <option value="permutation">Permutation importance</option><option value="shap" disabled={!shapSupported}>Tree SHAP{!shapSupported ? " (requires a supported tree model)" : ""}</option>
    </select></label>
    <p>{method === "shap" ? "Exact feature contributions on up to 64 sampled validation rows. Includes a global importance chart and one local prediction explanation." : "Shuffles selected features three times on up to 200 validation rows and measures how the recorded score changes."} The final test stays separate.</p>
    {!shapSupported && <p>Tree SHAP is available for decision trees, random forests and Extra Trees with at most 256 encoded inputs. Permutation importance remains available for other models.</p>}
    <fieldset className="explanation-features" disabled={busy}><legend>Choose up to 15 encoded features</legend>
      {columns.map(column => <label key={column}><input type="checkbox" checked={selected.includes(column)} disabled={busy || (!selected.includes(column) && selected.length >= 15)}
        onChange={event => { setSelected(event.target.checked ? [...selected, column] : selected.filter(name => name !== column)); setResult(null); }} />{column}</label>)}
    </fieldset>
    <p>{selected.length} selected. Explanations share the prediction budget. SHAP charges each sampled row; permutation charges each shuffle repeat.</p>
    <button className="pill pill-solid" disabled={busy || !selected.length || selected.length > 15} onClick={() => void explain()}>{busy ? "Computing explanation…" : method === "shap" ? "Run SHAP explanation" : "Measure permutation importance"}</button>
    {busy && <p role="status">Explaining the saved model without retraining…</p>}{error && <p role="alert">{error}</p>}
    {result && <div aria-live="polite">
      <p>{result.rows_evaluated} of {result.validation_rows} validation rows. {result.scope}</p>
      {result.method === "tree_shap" ? <>
        <BarChart title={`Mean absolute SHAP contribution: ${result.output_label}`} rows={result.features.map(row => ({ label: row.feature, value: row.mean_abs_shap }))} note="Larger values mean greater average influence on this model output. They do not imply causation." />
        <BarChart title="Local contribution for the first sampled validation row" rows={[...result.local.features.map(row => ({ label: row.feature, value: row.contribution })), { label: "Other features", value: result.local.other_features_contribution }]} note="Violet increases the output; amber decreases it. Bar lengths show magnitude." />
        <p>Base value {result.local.base_value.toPrecision(5)} + all feature contributions = {result.local.model_output.toPrecision(5)} ({result.output_label}).</p>
      </> : <>
        <BarChart title={`${result.change_label} after shuffling`} rows={result.features.map(row => ({ label: row.feature, value: row.score_decrease }))} />
        <p>{result.metric} before shuffling: {result.baseline_metric_value.toPrecision(5)}</p>
        <div className="preview-wrap"><table className="preview-table"><thead><tr><th>Selected feature</th><th>{result.change_label}</th><th>Shuffle variation (std)</th></tr></thead>
          <tbody>{result.features.map(row => <tr key={row.feature}><td>{row.feature}</td><td>{row.score_decrease.toPrecision(5)}</td><td>{row.repeat_std.toPrecision(5)}</td></tr>)}</tbody></table></div>
      </>}
      {result.limitations.map(note => <p key={note}>{note}</p>)}<button className="pill" onClick={download}>Download explanation JSON ↓</button>
    </div>}
  </details>;
}

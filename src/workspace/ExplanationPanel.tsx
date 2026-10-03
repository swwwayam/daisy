import { useState } from "react";
import { daisy, type ExplanationResult } from "../services/daisy";

export function ExplanationPanel({ experimentId, columns }: { experimentId: string; columns: string[] }) {
  const [selected, setSelected] = useState<string[]>(columns.slice(0, 5));
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ExplanationResult | null>(null);
  const [error, setError] = useState("");
  async function explain() {
    setBusy(true); setError(""); setResult(null);
    try { setResult(await daisy.explain(experimentId, selected)); }
    catch (err) { setError(err instanceof Error ? err.message : "Explanation failed."); }
    finally { setBusy(false); }
  }
  function download() {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `daisy-explanation-${experimentId}.json`;
    document.body.appendChild(anchor); anchor.click(); anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <details className="report-block explanation-workspace">
    <summary>Explain the saved model</summary>
    <p>Choose up to 15 features after encoding. DAISY shuffles them one at a time and measures the change on up to 200 validation rows. The final test stays separate.</p>
    <fieldset className="explanation-features" disabled={busy}>
      <legend>Features to inspect</legend>
      {columns.map(column => <label key={column}><input type="checkbox" checked={selected.includes(column)} disabled={!selected.includes(column) && selected.length >= 15}
        onChange={event => { setSelected(event.target.checked ? [...selected, column] : selected.filter(name => name !== column)); setResult(null); }} />{column}</label>)}
    </fieldset>
    <p>{selected.length} selected. Each explanation shares the prediction budget and charges every scored row, including three repeats per feature.</p>
    <button className="pill" disabled={busy || !selected.length || selected.length > 15} onClick={() => void explain()}>{busy ? "Measuring feature sensitivity…" : "Explain selected features"}</button>
    {error && <p role="alert">{error}</p>}
    {result && <>
      <p>{result.rows_evaluated} of {result.validation_rows} validation rows · {result.metric} before shuffling: {result.baseline_metric_value.toPrecision(5)}</p>
      <div className="preview-wrap"><table className="preview-table"><thead><tr><th>Selected feature</th><th>{result.change_label}</th><th>Shuffle variation (std)</th></tr></thead>
        <tbody>{result.features.map(row => <tr key={row.feature}><td>{row.feature}</td><td>{row.score_decrease.toPrecision(5)}</td><td>{row.repeat_std.toPrecision(5)}</td></tr>)}</tbody>
      </table></div>
      {result.limitations.map(note => <p key={note}>{note}</p>)}
      <button className="pill" onClick={download}>Download explanation JSON ↓</button>
    </>}
  </details>;
}

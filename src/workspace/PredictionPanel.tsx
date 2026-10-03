import { useRef, useState } from "react";
import { daisy, type PredictionResult } from "../services/daisy";
import { MetricGrid, PreviewTable } from "./primitives";

export function PredictionPanel({ artifactId, columns }: { artifactId: string; columns: string[] }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [error, setError] = useState("");
  async function predict(file: File) {
    setBusy(true); setError(""); setResult(null);
    try { setResult(await daisy.predict(artifactId, file)); }
    catch (err) { setError(err instanceof Error ? err.message : "Prediction failed."); }
    finally { setBusy(false); if (input.current) input.current.value = ""; }
  }
  function download() {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([result.prediction_csv], { type: "text/csv" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `daisy-predictions-${artifactId}.csv`;
    document.body.appendChild(anchor); anchor.click(); anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <details className="report-block prediction-workspace">
    <summary>Predict on new data</summary>
    <p>Upload original feature values. DAISY reuses this saved model and its preprocessing. Your new rows are used for this request only.</p>
    <p>Required columns: {columns.join(", ")}. The target is optional and ignored.</p>
    <p>Up to 10,000 rows, 10 MiB, and one million cells per file. Daily budget: 100 requests / 100,000 rows.</p>
    <input ref={input} type="file" accept=".csv,text/csv" aria-label="CSV for predictions" disabled={busy} onChange={event => { const file = event.target.files?.[0]; if (file) void predict(file); }} />
    {busy && <p role="status">Applying saved preprocessing and predicting…</p>}
    {error && <p role="alert">{error}</p>}
    {result && <>
      <p>{result.rows.toLocaleString()} predictions. Input row numbers start at zero and keep the original CSV order.</p>
      <PreviewTable rows={result.preview} />
      <button className="pill pill-solid" onClick={download}>Download predictions ↓</button>
      <h5>Missing inputs before saved imputation</h5><MetricGrid metrics={result.diagnostics.missing_values_before_imputation} />
      <h5>New category counts</h5><MetricGrid metrics={result.diagnostics.unseen_category_counts} />
      <p>New categories use the package's saved fallback. These counts flag unfamiliar inputs; they do not measure prediction accuracy.</p>
      {!!result.diagnostics.extra_columns_ignored.length && <p>Ignored extra columns: {result.diagnostics.extra_columns_ignored.join(", ")}</p>}
    </>}
  </details>;
}

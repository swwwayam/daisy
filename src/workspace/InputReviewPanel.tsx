import { useState } from "react";
import { daisy, type DatasetSummary, type InputPolicy } from "../services/daisy";

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
  const columns = Object.keys(dataset.column_dtypes ?? {});
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
    <p className="policy-footnote">Applying a review starts a new dataset version and resets later stages. Your original CSV remains available.</p>
    <div className="saved-history-actions">
      <button className="pill pill-solid" disabled={busy} onClick={() => onReview({ missing_tokens: values(tokens), column_types: types, column_tokens: Object.fromEntries(Object.entries(columnTokens).map(([column, text]) => [column, values(text)])), blank_is_missing: blankMissing })}>{busy ? "Applying review…" : confirmed ? "Apply updated interpretation" : "Confirm and continue"}</button>
      <button className="pill pill-ghost" disabled={downloadBusy || busy} onClick={() => { void original(); }}>{downloadBusy ? "Preparing…" : "Download original CSV"}</button>
    </div>
    {(error || downloadError) && <p role="alert">{error || downloadError}</p>}
  </details>;
}

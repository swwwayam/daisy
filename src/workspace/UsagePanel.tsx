import { useState } from "react";
import { daisy, type AccountUsage } from "../services/daisy";

export function UsagePanel() {
  const [usage, setUsage] = useState<AccountUsage | null>(null);
  const [busy, setBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [error, setError] = useState("");
  async function refresh() {
    setBusy(true); setError("");
    try { setUsage(await daisy.usage()); }
    catch (err) { setError(err instanceof Error ? err.message : "Usage unavailable."); }
    finally { setBusy(false); }
  }
  function meter(label: string, value: number, limit: number) {
    return <label className="usage-meter"><span>{label}: {value.toLocaleString()} / {limit.toLocaleString()}</span><progress aria-label={label} value={value} max={limit} /></label>;
  }
  async function downloadExport() {
    setExportBusy(true); setError("");
    try {
      const blob = await daisy.downloadAccountExport();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = "daisy-account-export.json"; link.click();
      URL.revokeObjectURL(url);
    } catch (err) { setError(err instanceof Error ? err.message : "Account export unavailable."); }
    finally { setExportBusy(false); }
  }
  return <details className="report-block usage-panel" onToggle={event => { if (event.currentTarget.open && !usage && !busy) void refresh(); }}>
    <summary>Account usage</summary>
    <p>Budgets cover the last 24 hours. Usage expires gradually; refreshing does not consume a request.</p>
    <div className="saved-history-actions">
      <button className="pill" disabled={busy} onClick={() => void refresh()}>{busy ? "Loading usage…" : "Refresh usage"}</button>
      <button className="pill pill-ghost" disabled={exportBusy} onClick={() => void downloadExport()}>{exportBusy ? "Preparing export…" : "Download my account data"}</button>
    </div>
    <p>The account export contains your saved metadata and run history. Download source CSVs and trained model packages from their dedicated controls.</p>
    {error && <p role="alert">{error}</p>}
    {usage && <>
      {meter("AI requests", usage.ai.requests, usage.limits.ai_requests)}
      {meter("AI tokens (used or reserved)", usage.ai.tokens, usage.limits.ai_tokens)}
      {meter("Prediction / explanation requests", usage.inference.requests, usage.limits.inference_requests)}
      {meter("Scored rows, including explanation repeats", usage.inference.scored_rows, usage.limits.inference_scored_rows)}
      {usage.training_metered ? <>
        {meter("Training attempts", usage.training.requests ?? 0, usage.limits.training_requests)}
        {meter("Queued / running training jobs", usage.training.active_jobs ?? 0, usage.limits.active_training_jobs)}
      </> : <p>Inline demo training has no durable job meter.</p>}
      {["ai", "inference", "training"].map(key => { const next = usage[key as "ai" | "inference" | "training"].next_expiry; return next && <p key={key}>Next {key} usage expiry: {new Date(next).toLocaleString()}.</p>; })}
      <p>Accepted attempts can consume budget even if they fail. Cancellation does not refund training attempts. These meters show platform limits, not a paid subscription.</p>
      {!usage.durable && <p>Demo counters reset when the backend restarts.</p>}
    </>}
  </details>;
}

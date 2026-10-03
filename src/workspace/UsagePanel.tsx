import { useState } from "react";
import { daisy, type AccountUsage } from "../services/daisy";

export function UsagePanel() {
  const [usage, setUsage] = useState<AccountUsage | null>(null);
  const [busy, setBusy] = useState(false);
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
  return <details className="report-block usage-panel" onToggle={event => { if (event.currentTarget.open && !usage && !busy) void refresh(); }}>
    <summary>Account usage</summary>
    <p>Budgets cover the last 24 hours. Usage expires gradually; refreshing does not consume a request.</p>
    <button className="pill" disabled={busy} onClick={() => void refresh()}>{busy ? "Loading usage…" : "Refresh usage"}</button>
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

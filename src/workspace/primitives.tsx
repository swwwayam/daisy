import type { Dict } from "../services/daisy";

/* Humanize snake_case / camelCase keys into readable labels. */
export function humanize(key: string): string {
  return key
    .replace(/[_-]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

export function isScalar(v: unknown): v is string | number | boolean {
  return typeof v === "string" || typeof v === "number" || typeof v === "boolean";
}

export function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(4).replace(/\.?0+$/, "");
  if (typeof v === "string") return v;
  if (Array.isArray(v)) return v.every(isScalar) ? v.map(formatValue).join(", ") : `${v.length} items`;
  return "";
}

/* Loader: pulsing DAISY node + contextual message. No fake percentages. */
export function Loader({ message }: { message: string }) {
  return (
    <div className="ws-loader">
      <span className="ws-node" />
      <span>{message}</span>
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="ws-error">
      <div className="ws-error-head"><span className="ws-error-dot" />Stage failed</div>
      <p>{message}</p>
      {onRetry && <button className="pill pill-ghost" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="ws-empty">{children}</div>;
}

/* Chips of scalar key/values from an object (skips nested / empty). */
export function StatChips({ data, only }: { data?: Dict; only?: string[] }) {
  if (!data) return null;
  const entries = Object.entries(data).filter(
    ([k, v]) => isScalar(v) && v !== "" && (!only || only.includes(k))
  );
  if (!entries.length) return null;
  return (
    <div className="chip-row">
      {entries.map(([k, v]) => (
        <div className="chip" key={k}>
          <span className="chip-k">{humanize(k)}</span>
          <span className="chip-v">{formatValue(v)}</span>
        </div>
      ))}
    </div>
  );
}

/* A single action / step rendered as a glass row, showing whatever scalar fields exist. */
export function ActionRow({ action }: { action: Dict }) {
  const entries = Object.entries(action).filter(([, v]) => isScalar(v) || (Array.isArray(v) && v.every(isScalar)));
  const titleKey = ["name", "action", "step", "title", "column", "type", "transformation"].find(
    (k) => typeof action[k] === "string"
  );
  const title = titleKey ? (action[titleKey] as string) : null;
  const descKey = ["description", "detail", "reason", "reasoning", "summary", "note"].find(
    (k) => typeof action[k] === "string"
  );
  const desc = descKey ? (action[descKey] as string) : null;
  const rest = entries.filter(([k]) => k !== titleKey && k !== descKey);
  return (
    <div className="action-row">
      {title && <div className="action-title">{humanize(title)}</div>}
      {desc && <div className="action-desc">{desc}</div>}
      {rest.length > 0 && (
        <div className="chip-row">
          {rest.map(([k, v]) => (
            <div className="chip" key={k}>
              <span className="chip-k">{humanize(k)}</span>
              <span className="chip-v">{formatValue(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ActionList({ actions, empty }: { actions?: Dict[]; empty?: string }) {
  if (!Array.isArray(actions) || actions.length === 0) {
    return empty ? <Empty>{empty}</Empty> : null;
  }
  return (
    <div className="action-list">
      {actions.map((a, i) => (
        <ActionRow key={i} action={a} />
      ))}
    </div>
  );
}

/* Dark glass preview table (never a white generic table). */
export function PreviewTable({ rows, maxRows = 6 }: { rows?: Dict[]; maxRows?: number }) {
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const cols = Array.from(new Set(rows.flatMap((r) => Object.keys(r)))).slice(0, 8);
  const shown = rows.slice(0, maxRows);
  return (
    <div className="preview-wrap">
      <table className="preview-table">
        <thead>
          <tr>{cols.map((c) => <th key={c}>{humanize(c)}</th>)}</tr>
        </thead>
        <tbody>
          {shown.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => <td key={c}>{formatValue(r[c])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > maxRows && <div className="preview-note">Showing {maxRows} of {rows.length.toLocaleString()} rows</div>}
    </div>
  );
}

/* Render a metrics object as chips, handling one level of nesting. */
export function MetricGrid({ metrics }: { metrics?: Dict }) {
  if (!metrics || Object.keys(metrics).length === 0) return null;
  const scalars = Object.entries(metrics).filter(([, v]) => isScalar(v));
  const nested = Object.entries(metrics).filter(([, v]) => v && typeof v === "object" && !Array.isArray(v));
  return (
    <div className="metric-stack">
      {scalars.length > 0 && (
        <div className="metric-grid">
          {scalars.map(([k, v]) => (
            <div className="metric-cell" key={k}>
              <div className="metric-val">{formatValue(v)}</div>
              <div className="metric-lbl">{humanize(k)}</div>
            </div>
          ))}
        </div>
      )}
      {nested.map(([k, v]) => (
        <div key={k} className="metric-nested">
          <div className="metric-nested-title">{humanize(k)}</div>
          <div className="metric-grid">
            {Object.entries(v as Dict).filter(([, val]) => isScalar(val)).map(([kk, val]) => (
              <div className="metric-cell" key={kk}>
                <div className="metric-val">{formatValue(val)}</div>
                <div className="metric-lbl">{humanize(kk)}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

import { useState } from "react";
import type { Dict } from "../services/daisy";

export function BarChart({ title, rows, note }: { title: string; rows: { label: string; value: number }[]; note?: string }) {
  const valid = rows.filter(row => Number.isFinite(row.value)).slice(0, 20);
  const max = Math.max(...valid.map(row => Math.abs(row.value)), 0) || 1;
  if (!valid.length) return <p>No measured values available for {title.toLowerCase()}.</p>;
  return <figure className="data-chart"><figcaption>{title}</figcaption>
    <div className="chart-bars">{valid.map((row, index) => <div className="chart-row" key={`${row.label}-${index}`}>
      <span className="chart-label" title={row.label}>{row.label}</span>
      <span className="chart-track" aria-hidden="true"><span className={row.value < 0 ? "negative" : ""} style={{ width: `${Math.abs(row.value) / max * 100}%` }} /></span>
      <span className="chart-value">{row.value.toLocaleString(undefined, { maximumFractionDigits: 4 })}</span>
    </div>)}</div>{note && <p>{note}</p>}
  </figure>;
}

export function EdaCharts({ report }: { report: Dict }) {
  const distributions = report.distributions as Record<string, { label: string; value: number }[]> | undefined;
  const columns = Object.keys(distributions ?? {});
  const [picked, setPicked] = useState("");
  const column = columns.includes(picked) ? picked : columns[0];
  const correlation = report.correlation as Record<string, Record<string, number>> | undefined;
  const names = Object.keys(correlation ?? {}).slice(0, 10);
  return <section className="pipeline-charts" aria-label="Exploratory data visualizations">
    {column && <><label className="chart-selector">Distribution column <select value={column} onChange={e => setPicked(e.target.value)}>{columns.map(name => <option key={name}>{name}</option>)}</select></label>
      <BarChart title={`${column} distribution`} rows={distributions![column]} note="Counts from the measured dataset. Numeric bins exclude missing and non-finite values; categorical plots show the ten most frequent values." /></>}
    {names.length > 1 && <figure className="data-chart"><figcaption>Numeric correlation</figcaption><p>Pearson correlation, first {names.length} numeric columns. Constant columns have undefined correlation, shown as N/A.</p>
      <div className="preview-wrap"><table className="correlation-table"><thead><tr><th scope="col">Feature</th>{names.map(name => <th scope="col" key={name}>{name}</th>)}</tr></thead>
        <tbody>{names.map(row => <tr key={row}><th scope="row">{row}</th>{names.map(col => {
          const value = correlation?.[col]?.[row];
          return <td key={col} style={{ background: typeof value === "number" && Number.isFinite(value) ? `rgba(${value < 0 ? "245,158,11" : "139,92,246"},${.08 + Math.abs(value) * .5})` : undefined }}>{typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "N/A"}</td>;
        })}</tr>)}</tbody></table></div></figure>}
    {!column && <p>Distributions are available after rerunning EDA with this version of DAISY.</p>}
  </section>;
}

export function CandidateChart({ actions, metric }: { actions?: Dict[]; metric?: string }) {
  if (!metric) return null;
  const rows = (actions ?? []).filter(row => row.status === "success" && typeof row.metrics === "object" && row.metrics !== null)
    .map(row => ({ label: String(row.model ?? row.model_name), value: Number((row.metrics as Dict)[metric]) }));
  return <BarChart title={`Candidate validation ${metric.replace(/_/g, " ")}`} rows={rows} note={metric === "mae" || metric === "rmse" ? "Lower is better. These are validation scores, not final-test results." : "Higher is better. These are validation scores, not final-test results."} />;
}

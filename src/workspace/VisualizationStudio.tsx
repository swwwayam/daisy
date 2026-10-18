import { useEffect, useRef, useState } from "react";
import { daisy, type PlotRequest, type PlotResult, type TrainingResult } from "../services/daisy";
import { CandidateChart } from "./Charts";

const display = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 3, notation: Math.abs(value) >= 1e6 ? "compact" : "standard" });

function Plot({ report }: { report: PlotResult }) {
  const svg = useRef<SVGSVGElement>(null);
  const bars = ["bar", "histogram"].includes(report.kind);
  const heatmap = report.kind === "heatmap";
  const categoriesX = [...new Set(report.cells?.map(cell => cell.x))], categoriesY = [...new Set(report.cells?.map(cell => cell.y))];
  const maxCount = Math.max(...(report.cells ?? []).map(cell => cell.value), 1);
  const width = 900, height = bars ? Math.max(350, report.points.length * 29 + 110) : 470;
  const left = bars ? 220 : 100, right = 70, top = 55, bottom = 65;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const ys = report.points.map(p => p.y), xs = report.points.map(p => Number(p.x));
  // Scale in normalized space to avoid overflow for extreme finite values.
  function scale(values: number[], start: number, extent: number, zero = false) {
    const magnitude = Math.max(...values.map(Math.abs), 1);
    const normalized = values.map(v => v / magnitude);
    let min = Math.min(...normalized, ...(zero ? [0] : [])), max = Math.max(...normalized, ...(zero ? [0] : []));
    if (max === min) { min -= .5; max += .5; }
    return { at: (v: number) => start + (v / magnitude - min) / (max - min) * extent,
      ticks: Array.from({ length: 5 }, (_, i) => ({ value: (min + (max - min) * i / 4) * magnitude, pos: start + extent * i / 4 })) };
  }
  const y = scale(ys, height - bottom, -plotHeight), x = scale(xs, left, plotWidth);
  const bar = scale(ys, left, plotWidth, true);
  function download() {
    if (!svg.current) return;
    const blob = new Blob([new XMLSerializer().serializeToString(svg.current)], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob), anchor = document.createElement("a");
    anchor.href = url; anchor.download = `daisy-${report.kind}.svg`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const title = `${report.y_label} vs ${report.x_label}`;
  return <figure className="studio-figure">
    <div className="studio-figure-head"><figcaption>{title}</figcaption><button className="pill pill-ghost" onClick={download}>Download SVG</button></div>
    <div className="studio-canvas"><svg ref={svg} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${report.kind} chart: ${title}`}>
      <title>{title}</title><desc>{report.scope} {report.model_scope} {report.rows_used} rows used from {report.source_rows} source rows.</desc><rect width={width} height={height} rx="16" fill="#15121b" />
      <g fill="#d8d1e5" fontFamily="Arial, sans-serif" fontSize="12">
        <text x="24" y="28" fontSize="16">{report.kind.toUpperCase()} · DAISY</text>
        <text x={width - 24} y="28" textAnchor="end">{report.validation_sample ? "Validation sample" : report.sampled ? "Dataset sample" : "Dataset aggregates"} · n={report.rows_used.toLocaleString()}</text>
        {heatmap ? <>
          {categoriesX.map((label, i) => <text key={i} x={left + (i + .5) * plotWidth / categoriesX.length} y={height - bottom + 20} textAnchor="middle">{label.slice(0, 9)}</text>)}
          {categoriesY.map((label, i) => <text key={i} x={left - 10} y={top + (i + .5) * plotHeight / categoriesY.length + 4} textAnchor="end">{label.slice(0, 12)}</text>)}
          {(report.cells ?? []).map((cell, i) => { const a = left + categoriesX.indexOf(cell.x) * plotWidth / categoriesX.length, b = top + categoriesY.indexOf(cell.y) * plotHeight / categoriesY.length; return <g key={i}><title>{cell.x} / {cell.y}: {cell.value}</title><rect x={a} y={b} width={plotWidth / categoriesX.length} height={plotHeight / categoriesY.length} fill={`rgba(139,92,246,${.12 + cell.value / maxCount * .75})`} stroke="#15121b" /><text x={a + plotWidth / categoriesX.length / 2} y={b + plotHeight / categoriesY.length / 2 + 4} textAnchor="middle">{cell.value}</text></g>; })}
          <text x={left + plotWidth / 2} y={height - 15} textAnchor="middle">{report.x_label}</text><text transform={`translate(20 ${top + plotHeight / 2}) rotate(-90)`} textAnchor="middle">{report.y_label}</text>
        </> : bars ? <>{bar.ticks.map((tick, i) => <g key={i}><path d={`M${tick.pos},${top} V${height - bottom}`} stroke="#383140" /><text x={tick.pos} y={height - bottom + 22} textAnchor="middle">{display(tick.value)}</text></g>)}
          {report.points.map((point, i) => { const pos = top + i * plotHeight / report.points.length; return <g key={i}><title>{String(point.x)}: {display(point.y)}</title><text x={left - 12} y={pos + 15} textAnchor="end">{String(point.x).slice(0, 28)}</text><rect x={Math.min(bar.at(0), bar.at(point.y))} y={pos} height={18} width={Math.max(1, Math.abs(bar.at(point.y) - bar.at(0)))} rx="3" fill={point.y < 0 ? "#fbbf24" : "#a78bfa"} /><text x={bar.at(point.y) + 6} y={pos + 14}>{display(point.y)}</text></g>; })}
          <text x={left + plotWidth / 2} y={height - 15} textAnchor="middle">{report.y_label}</text></> : <>
          {y.ticks.map((tick, i) => <g key={i}><path d={`M${left},${tick.pos} H${width - right}`} stroke="#383140" /><text x={left - 12} y={tick.pos + 4} textAnchor="end">{display(tick.value)}</text></g>)}
          {x.ticks.map((tick, i) => <text key={i} x={tick.pos} y={height - bottom + 25} textAnchor="middle">{display(tick.value)}</text>)}
          {report.kind === "line" && <polyline points={report.points.map(p => `${x.at(Number(p.x))},${y.at(p.y)}`).join(" ")} fill="none" stroke="#a78bfa" strokeWidth="2" />}
          {report.points.map((point, i) => <circle key={i} cx={x.at(Number(point.x))} cy={y.at(point.y)} r="3.5" fill="#c4b5fd" opacity=".65"><title>{report.x_label}: {display(Number(point.x))}; {report.y_label}: {display(point.y)}</title></circle>)}
          <text x={left + plotWidth / 2} y={height - 15} textAnchor="middle">{report.x_label}</text>
          <text transform={`translate(20 ${top + plotHeight / 2}) rotate(-90)`} textAnchor="middle">{report.y_label}</text>
        </>}
      </g>
    </svg></div>
    <p>{report.rows_used.toLocaleString()} rows used · {report.source_rows.toLocaleString()} source rows · {report.excluded_rows.toLocaleString()} missing/non-finite pairs excluded{report.sampled ? " · deterministic sample" : ""}{report.validation_sample ? " · validation sample only" : ""}.</p><p>{report.scope} {report.model_scope}</p>
    {!!report.omitted_rows && <p>{report.displayed_rows?.toLocaleString()} valid rows represented in the displayed groups; {report.omitted_rows.toLocaleString()} valid rows omitted by the category or aggregation limits.</p>}
    <details><summary>View plotted values</summary><div className="studio-values"><table><thead><tr><th>{report.x_label}</th><th>{report.y_label}</th>{heatmap && <th>Count</th>}</tr></thead><tbody>{heatmap ? report.cells?.map((p, i) => <tr key={i}><td>{p.x}</td><td>{p.y}</td><td>{p.value}</td></tr>) : report.points.map((p, i) => <tr key={i}><td>{String(p.x)}</td><td>{display(p.y)}</td></tr>)}</tbody></table></div></details>
  </figure>;
}

export function VisualizationStudio({ datasetId, originalId, training }: { datasetId: string | null; originalId: string | null; training: TrainingResult | null }) {
  const [source, setSource] = useState("current");
  const [columns, setColumns] = useState<string[]>([]), [loading, setLoading] = useState(false);
  const [x, setX] = useState(""), [y, setY] = useState("");
  const [kind, setKind] = useState<PlotRequest["kind"]>("auto"), [aggregation, setAggregation] = useState<PlotRequest["aggregation"]>("mean");
  const [report, setReport] = useState<PlotResult | null>(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const experiment = training?.output_summary?.experiment_id;
  const model = source === "model";
  const id = model ? experiment : source === "original" ? originalId : datasetId;
  const features = training?.output_summary?.feature_columns ?? [];
  const regression = training?.output_summary?.problem_type === "regression";
  const featureKey = JSON.stringify(features);
  useEffect(() => {
    const token = ++generation.current;
    setReport(null); setError(""); setBusy(false); setX(""); setY(""); setColumns([]);
    if (!id) { setLoading(false); return; }
    setLoading(true);
    if (model) {
      setColumns(["actual", "predicted", ...(regression ? ["residual"] : []), ...features.map(name => `feature:${name}`)]);
      setX("actual"); setY("predicted"); setKind("auto"); setLoading(false);
    } else {
      void daisy.datasetSummary(id).then(summary => { if (generation.current !== token) return; const names = Object.keys(summary.column_dtypes ?? {}); setColumns(names); setX(names[0] ?? ""); })
        .catch(reason => { if (generation.current === token) setError(reason instanceof Error ? reason.message : "Could not load plot columns."); })
        .finally(() => { if (generation.current === token) setLoading(false); });
    }
    return () => { generation.current++; };
  }, [id, model, regression, featureKey]);
  function change() { generation.current++; setBusy(false); setReport(null); setError(""); }
  async function plot() {
    if (!id || !x) return;
    const token = ++generation.current;
    setBusy(true); setError(""); setReport(null);
    try { const result = await daisy.plot(model ? "model" : "dataset", id, { x, y: y || undefined, kind, aggregation }); if (generation.current === token) setReport(result); }
    catch (reason) { if (generation.current === token) setError(reason instanceof Error ? reason.message : "Could not draw this plot."); }
    finally { if (generation.current === token) setBusy(false); }
  }
  return <section className="visualization-studio" id="visualization-studio" aria-labelledby="studio-title">
    <div className="studio-heading"><div><span className="mono">EXPLORE / COMPARE / EXPLAIN</span><h2 id="studio-title">Visualization Studio</h2><p>Your axes. Your view. Explore your data and see how your saved model behaves.</p></div><span className="studio-badge">No AI tokens used</span></div>
    {!datasetId ? <p className="studio-empty">Upload a dataset to unlock custom plots. Model diagnostics become available after training.</p> : <>
      <div className="studio-controls">
        <label>Data source<select value={source} onChange={e => { change(); setSource(e.target.value); }}><option value="current">Current pipeline dataset</option><option value="original" disabled={!originalId}>Original uploaded dataset</option><option value="model" disabled={!experiment}>Saved model · validation</option></select></label>
        <label>X axis<select disabled={loading || !columns.length} value={x} onChange={e => { change(); setX(e.target.value); }}>{!columns.length && <option value="">{loading ? "Loading columns…" : "No columns"}</option>}{columns.map(name => <option key={name}>{name}</option>)}</select></label>
        <label>Y axis<select disabled={loading || kind === "histogram"} value={y} onChange={e => { change(); setY(e.target.value); }}><option value="">Row count / distribution</option>{columns.map(name => <option key={name}>{name}</option>)}</select></label>
        <label>Chart type<select value={kind} disabled={loading} onChange={e => { change(); setKind(e.target.value as PlotRequest["kind"]); }}><option value="auto">Auto · choose for me</option><option value="histogram">Histogram</option><option value="bar">Bar</option><option value="scatter">Scatter</option><option value="line">Line · sorted by X</option><option value="heatmap">Category / confusion heatmap</option></select></label>
        <label>Bar aggregation<select value={aggregation} disabled={loading || !["auto", "bar"].includes(kind)} onChange={e => { change(); setAggregation(e.target.value as PlotRequest["aggregation"]); }}><option value="mean">Mean Y</option><option value="sum">Sum Y</option><option value="count">Count rows</option></select></label>
      </div>
      <div className="studio-actions"><button className="pill pill-solid" disabled={busy || loading || !x || !id} onClick={() => void plot()}>{busy ? "Plotting…" : "Generate visualization ↗"}</button>{model && regression && <button className="pill pill-ghost" onClick={() => { change(); setX("predicted"); setY("residual"); setKind("scatter"); }}>Set residual diagnostic</button>}</div>
      <p className="studio-help">Auto uses a histogram for one numeric column, scatter for two numeric columns, a count heatmap for two categorical columns, and bars for categories. Actual vs predicted classes produces a validation confusion heatmap. Model plots use up to 200 frozen validation rows and count toward inference limits.</p>
      {loading && <p role="status">Loading available columns…</p>}{busy && <p role="status">Preparing measured plot data…</p>}{error && <p role="alert" className="studio-error">{error}</p>}
      {report && <Plot report={report} />}
      {!report && !busy && !error && <div className="studio-empty">Choose what to plot, then generate your visualization.</div>}
    </>}
    {training?.actions && <CandidateChart actions={training.actions} metric={training.output_summary?.primary_metric} />}
  </section>;
}

import React, { useState } from "react";

const API_BASE = "http://localhost:8000";

const ACTION_ICONS = {
    drop_duplicates: "🧬",
    impute: "🩹",
    drop_column: "🗑️",
    fix_dtype: "🔧",
    handle_outliers: "📉",
    strip_whitespace: "✂️",
    drop_rows_missing_target: "🎯",
    encode_categorical: "🔤",
    scale_numeric: "📏",
    extract_datetime_features: "📅",
    drop_low_variance_column: "🗑️",
    drop_high_correlation_column: "🔗",
};

// Backend uses snake_case model identifiers (e.g. "random_forest_classifier")
// — shown to the user in plain English, per the project's content rules.
function prettifyModelName(name) {
    if (!name) return "";
    return name
        .split("_")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
}

function statusColor(status) {
    if (status === "success" || status === "accepted") return "#00f5d4";
    if (status === "skipped" || status === "partial") return "#ffcc66";
    return "#ff6666"; // failed / rejected
}

function ActionRow({ action }) {
    const icon = ACTION_ICONS[action.type] || "⚙️";
    const color = statusColor(action.status);

    return (
        <div
            style={{
                display: "flex",
                gap: "10px",
                padding: "10px 12px",
                background: "rgba(255,255,255,0.04)",
                borderRadius: "10px",
                border: "1px solid rgba(255,255,255,0.08)",
                marginBottom: "8px",
            }}
        >
            <div style={{ fontSize: "18px" }}>{icon}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: "8px" }}>
                    <span style={{ fontSize: "12px", fontWeight: "bold", color: "white" }}>
                        {action.type}{action.column ? ` · ${action.column}` : ""}
                    </span>
                    <span style={{ fontSize: "10px", color: color, whiteSpace: "nowrap" }}>
                        {action.status}
                    </span>
                </div>
                <div style={{ fontSize: "12px", color: "rgba(255,255,255,0.75)", marginTop: "3px" }}>
                    {action.reasoning}
                </div>
                {action.message && (
                    <div style={{ fontSize: "11px", color: "rgba(0,245,212,0.8)", marginTop: "3px" }}>
                        {action.message}
                    </div>
                )}
            </div>
        </div>
    );
}

function StatBlock({ label, before, after }) {
    return (
        <div
            style={{
                flex: 1,
                background: "rgba(0,245,212,0.06)",
                border: "1px solid rgba(0,245,212,0.15)",
                borderRadius: "10px",
                padding: "10px",
                textAlign: "center",
            }}
        >
            <div style={{ fontSize: "10px", opacity: 0.7 }}>{label}</div>
            <div style={{ fontSize: "16px", fontWeight: "bold", color: "#00f5d4" }}>
                {before} <span style={{ opacity: 0.4, fontSize: "12px" }}>→</span> {after}
            </div>
        </div>
    );
}

// Feature Engineering shares the same ActionRow pattern as Cleaning —
// same three-state status vocabulary (success/failed/skipped), just a
// different fixed action menu.
function FeatureEngineeringSection({ result }) {
    if (!result) return null;
    return (
        <>
            <div style={{ marginTop: "18px", marginBottom: "8px", fontWeight: "bold", color: "#00f5d4", fontSize: "13px" }}>
                🧪 FEATURE ENGINEERING
            </div>
            <p style={{ fontSize: "12px", lineHeight: 1.5, color: "rgba(255,255,255,0.8)" }}>{result.reasoning}</p>
            <div style={{ display: "flex", gap: "8px", margin: "10px 0" }}>
                <StatBlock
                    label="COLUMNS"
                    before={result.output_summary?.columns_before?.length}
                    after={result.output_summary?.columns_after?.length}
                />
            </div>
            {result.actions?.map((step, i) => <ActionRow key={i} action={step} />)}
        </>
    );
}

// Model Selection recommends, it doesn't transform data — so this section
// shows ranked candidates rather than executed steps. Rejected
// recommendations are shown, not hidden: the guardrail catching an
// invalid AI suggestion is a real safety feature of this system, and
// hiding it would misrepresent what the tool actually does.
function ModelSelectionSection({ result, onTrain, isRunning }) {
    if (!result) return null;
    const accepted = (result.actions || []).filter((a) => a.status === "accepted");
    const rejected = (result.actions || []).filter((a) => a.status === "rejected");

    return (
        <>
            <div style={{ marginTop: "18px", marginBottom: "8px", fontWeight: "bold", color: "#00f5d4", fontSize: "13px" }}>
                🧭 MODEL SELECTION — {result.input_summary?.problem_type?.toUpperCase()}
            </div>
            <p style={{ fontSize: "12px", lineHeight: 1.5, color: "rgba(255,255,255,0.8)" }}>{result.reasoning}</p>

            {accepted
                .sort((a, b) => (a.rank || 99) - (b.rank || 99))
                .map((rec, i) => (
                    <div
                        key={i}
                        style={{
                            padding: "10px 12px",
                            background: "rgba(0,245,212,0.05)",
                            borderRadius: "10px",
                            border: "1px solid rgba(0,245,212,0.15)",
                            marginBottom: "8px",
                        }}
                    >
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", fontWeight: "bold" }}>
                            <span>#{rec.rank} · {prettifyModelName(rec.model)}</span>
                            <span style={{ color: statusColor(rec.status), fontSize: "10px" }}>{rec.status}</span>
                        </div>
                        <div style={{ fontSize: "11px", color: "rgba(255,255,255,0.7)", marginTop: "4px" }}>
                            {rec.reasoning}
                        </div>
                    </div>
                ))}

            {rejected.length > 0 && (
                <div style={{ marginTop: "6px", marginBottom: "10px" }}>
                    <div style={{ fontSize: "10px", opacity: 0.5, marginBottom: "6px" }}>
                        {rejected.length} recommendation(s) rejected by the validation guardrail
                    </div>
                    {rejected.map((rec, i) => (
                        <div
                            key={i}
                            style={{
                                padding: "8px 10px",
                                background: "rgba(255,80,80,0.05)",
                                borderRadius: "8px",
                                border: "1px solid rgba(255,80,80,0.15)",
                                marginBottom: "6px",
                                opacity: 0.75,
                            }}
                        >
                            <div style={{ fontSize: "11px", color: "#ff8888" }}>{rec.model || "(invalid)"}</div>
                            <div style={{ fontSize: "10px", color: "rgba(255,255,255,0.5)", marginTop: "2px" }}>
                                {rec.message}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {accepted.length > 0 && (
                <button
                    onClick={() => onTrain(accepted.map((a) => a.model))}
                    disabled={isRunning}
                    style={{
                        width: "100%", marginTop: "6px", padding: "10px",
                        background: "linear-gradient(135deg, #00f5d4, #00c2ff)",
                        border: "none", borderRadius: "8px", color: "#001a15",
                        fontWeight: "bold", fontSize: "11px", cursor: isRunning ? "not-allowed" : "pointer",
                        opacity: isRunning ? 0.5 : 1,
                    }}
                >
                    {isRunning ? "⏳ TRAINING..." : `▶ TRAIN THESE ${accepted.length} MODEL(S)`}
                </button>
            )}
        </>
    );
}

// Model Training's winner is an OBJECTIVE metric comparison, not an AI
// judgment call — the winner marker should read as factual, not like a
// stylistic "featured" card treatment (per design brief section 4.4).
function ModelTrainingSection({ result }) {
    if (!result) return null;
    const isClassification = result.output_summary?.problem_type === "classification";
    const metricKeys = isClassification
        ? ["accuracy", "precision_weighted", "recall_weighted", "f1_weighted"]
        : ["mae", "rmse", "r2"];
    const bestModel = result.output_summary?.best_model;

    return (
        <>
            <div style={{ marginTop: "18px", marginBottom: "8px", fontWeight: "bold", color: "#00f5d4", fontSize: "13px" }}>
                🏋️ MODEL TRAINING — {result.output_summary?.primary_metric} {isClassification ? "(higher better)" : "(lower better)"}
            </div>
            <p style={{ fontSize: "12px", lineHeight: 1.5, color: "rgba(255,255,255,0.8)" }}>{result.reasoning}</p>

            <div style={{ overflowX: "auto", marginTop: "10px" }}>
                <table style={{ width: "100%", fontSize: "11px", borderCollapse: "collapse" }}>
                    <thead>
                        <tr style={{ borderBottom: "1px solid rgba(0,245,212,0.2)" }}>
                            <th style={{ textAlign: "left", padding: "6px 4px", color: "rgba(255,255,255,0.6)" }}>Model</th>
                            {metricKeys.map((k) => (
                                <th key={k} style={{ textAlign: "right", padding: "6px 4px", color: "rgba(255,255,255,0.6)" }}>
                                    {k}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {result.actions?.map((r, i) => {
                            const isWinner = r.model === bestModel;
                            return (
                                <tr
                                    key={i}
                                    style={{
                                        background: isWinner ? "rgba(0,245,212,0.08)" : "transparent",
                                        borderBottom: "1px solid rgba(255,255,255,0.05)",
                                    }}
                                >
                                    <td style={{ padding: "6px 4px", color: isWinner ? "#00f5d4" : "white", fontWeight: isWinner ? "bold" : "normal" }}>
                                        {isWinner ? "★ " : ""}{prettifyModelName(r.model)}
                                        {r.status === "failed" && (
                                            <span style={{ color: "#ff6666", fontSize: "10px", marginLeft: "6px" }}>failed</span>
                                        )}
                                    </td>
                                    {metricKeys.map((k) => (
                                        <td key={k} style={{ textAlign: "right", padding: "6px 4px", color: "rgba(255,255,255,0.85)" }}>
                                            {r.metrics?.[k] ?? "—"}
                                        </td>
                                    ))}
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
            {bestModel && (
                <div style={{ fontSize: "11px", color: "rgba(255,255,255,0.6)", marginTop: "8px" }}>
                    Best model by {result.output_summary?.primary_metric}: <b style={{ color: "#00f5d4" }}>{prettifyModelName(bestModel)}</b>
                </div>
            )}
        </>
    );
}

// Fetches the CSV from the backend and triggers a download — safer than
// carrying the whole CSV string through JSON state for larger datasets.
async function downloadCleanedCsv(datasetId) {
    const res = await fetch(`${API_BASE}/dataset/${datasetId}/download`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${datasetId}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

export default function AgentLogPanel({
    isRunning,
    error,
    agentResult,
    edaResult,
    featureResult,
    modelSelectionResult,
    modelTrainingResult,
    onTrainModels,
})
{
    const [open, setOpen] = useState(true);
    const visible = isRunning || error || agentResult;
    if (!visible) return null;

    return (
        <>
            {!open && (
                <div
                    onClick={() => setOpen(true)}
                    style={{
                        position: "fixed", top: "20px", right: "20px",
                        background: "rgba(0,8,20,0.9)", border: "1px solid rgba(0,245,212,0.4)",
                        color: "#00f5d4", padding: "8px 14px", borderRadius: "8px",
                        cursor: "pointer", fontSize: "12px", zIndex: 11,
                        fontFamily: "'Space Mono', monospace",
                    }}
                >
                    🧹 Agent Log
                </div>
            )}
            <div
                style={{
                    position: "fixed", top: 0, right: open ? "0px" : "-360px",
                    height: "100vh", width: "340px",
                    background: "rgba(0,8,20,0.96)", backdropFilter: "blur(15px)",
                    borderLeft: "1px solid rgba(0,245,212,0.2)",
                    display: "flex", flexDirection: "column", padding: "16px",
                    color: "white", transition: "right 0.3s ease", zIndex: 10,
                    overflowY: "auto", fontFamily: "'Space Mono', monospace",
                }}
            >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "14px" }}>
                    {/* Was hardcoded "Data Cleaning Agent" — now holds every
                        pipeline stage's results in one running log, so the
                        header needed to reflect that rather than mislabel
                        Feature Engineering/Model results as "cleaning." */}
                    <b style={{ color: "#00f5d4" }}>Pipeline Results</b>
                    <span onClick={() => setOpen(false)} style={{ cursor: "pointer", color: "rgba(255,255,255,0.6)" }}>✕</span>
                </div>

                {isRunning && (
                    <div style={{ fontSize: "13px", opacity: 0.85, padding: "20px 0" }}>
                        Working...
                    </div>
                )}

                {error && !isRunning && (
                    <div style={{ background: "rgba(255,80,80,0.1)", border: "1px solid rgba(255,80,80,0.3)", borderRadius: "10px", padding: "12px", fontSize: "13px", color: "#ff8888" }}>
                        {error}
                    </div>
                )}

                {agentResult && !isRunning && !error && (
                    <>
                        <div style={{ fontWeight: "bold", color: "#00f5d4", fontSize: "13px", marginBottom: "6px" }}>
                            🧹 DATA CLEANING
                        </div>
                        <p style={{ fontSize: "13px", lineHeight: 1.5, color: "rgba(255,255,255,0.85)" }}>
                            {agentResult.summary}
                        </p>
                        <div style={{ display: "flex", gap: "8px", margin: "12px 0" }}>
                            <StatBlock label="ROWS" before={agentResult.rows_before} after={agentResult.rows_after} />
                            <StatBlock label="NULLS" before={agentResult.nulls_before} after={agentResult.nulls_after} />
                        </div>
                        <div style={{ fontSize: "12px", fontWeight: "bold", opacity: 0.7, margin: "10px 0 8px" }}>
                            ACTIONS TAKEN ({agentResult.steps.length})
                        </div>
                        {agentResult.steps.length === 0 && (
                            <div style={{ fontSize: "12px", opacity: 0.6 }}>No cleaning actions were necessary.</div>
                        )}
                        {agentResult.steps.map((step, i) => <ActionRow key={i} action={step} />)}

                        {edaResult && (
                            <>
                                <div
                                    style={{
                                        marginTop: "18px",
                                        marginBottom: "8px",
                                        fontWeight: "bold",
                                        color: "#00f5d4",
                                        fontSize: "13px",
                                    }}
                                >
                                    📊 EDA SUMMARY
                                </div>

                                <div
                                    style={{
                                        background: "rgba(255,255,255,0.04)",
                                        border: "1px solid rgba(0,245,212,0.15)",
                                        borderRadius: "10px",
                                        padding: "12px",
                                        fontSize: "12px",
                                        lineHeight: "1.6",
                                        color: "rgba(255,255,255,0.85)",
                                        marginBottom: "12px",
                                    }}
                                >
                                    {edaResult.summary}
                                </div>
                            </>
                        )}

                        <FeatureEngineeringSection result={featureResult} />
                        <ModelSelectionSection
                            result={modelSelectionResult}
                            onTrain={onTrainModels}
                            isRunning={isRunning}
                        />
                        <ModelTrainingSection result={modelTrainingResult} />

                        <button
                            onClick={() => downloadCleanedCsv(agentResult.cleaned_dataset_id)}
                            style={{
                                marginTop: "16px", padding: "10px",
                                background: "linear-gradient(135deg, #00f5d4, #00c2ff)",
                                border: "none", borderRadius: "8px", color: "#001a15",
                                fontWeight: "bold", cursor: "pointer",
                            }}
                        >
                            Download Cleaned CSV
                        </button>
                    </>
                )}
            </div>
        </>
    );
}

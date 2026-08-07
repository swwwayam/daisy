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
};

function ActionRow({ action }) {
    const icon = ACTION_ICONS[action.type] || "⚙️";
    const statusColor =
        action.status === "success" ? "#00f5d4" : action.status === "skipped" ? "#ffcc66" : "#ff6666";

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
                    <span style={{ fontSize: "10px", color: statusColor, whiteSpace: "nowrap" }}>
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
                    <b style={{ color: "#00f5d4" }}>Data Cleaning Agent</b>
                    <span onClick={() => setOpen(false)} style={{ cursor: "pointer", color: "rgba(255,255,255,0.6)" }}>✕</span>
                </div>

                {isRunning && (
                    <div style={{ fontSize: "13px", opacity: 0.85, padding: "20px 0" }}>
                        Profiling data, reasoning about cleaning strategy, executing plan...
                    </div>
                )}

                {error && !isRunning && (
                    <div style={{ background: "rgba(255,80,80,0.1)", border: "1px solid rgba(255,80,80,0.3)", borderRadius: "10px", padding: "12px", fontSize: "13px", color: "#ff8888" }}>
                        {error}
                    </div>
                )}

                {agentResult && !isRunning && !error && (
                    <>
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

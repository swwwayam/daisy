import React, { useState } from "react";

// Small standalone panel, appears once Feature Engineering finishes.
// Kept separate from AgentLogPanel (the results log) because this is an
// INPUT the user provides, not a result being displayed — different job,
// different component, same visual language.
export default function TargetColumnSelector({ columns, onConfirm, isRunning }) {
    const [selected, setSelected] = useState(columns?.[0] || "");

    if (!columns || columns.length === 0) return null;

    return (
        <div
            style={{
                position: "fixed",
                top: "20px",
                left: "20px",
                width: "280px",
                background: "rgba(0,8,20,0.96)",
                backdropFilter: "blur(15px)",
                border: "1px solid rgba(0,245,212,0.25)",
                borderRadius: "14px",
                padding: "16px",
                color: "white",
                fontFamily: "'Space Mono', monospace",
                zIndex: 10,
                boxShadow: "0 0 30px rgba(0,0,0,0.5)",
            }}
        >
            <div
                style={{
                    fontSize: "9px",
                    letterSpacing: "2px",
                    color: "rgba(0,245,212,0.6)",
                    fontFamily: "'Orbitron', monospace",
                    marginBottom: "10px",
                }}
            >
                PREDICTION TARGET
            </div>

            <div style={{ fontSize: "12px", color: "rgba(255,255,255,0.75)", marginBottom: "10px", lineHeight: 1.5 }}>
                Which column should the model learn to predict?
            </div>

            <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                disabled={isRunning}
                style={{
                    width: "100%",
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(0,245,212,0.3)",
                    borderRadius: "8px",
                    padding: "8px 10px",
                    color: "white",
                    fontSize: "12px",
                    fontFamily: "'Space Mono', monospace",
                    marginBottom: "12px",
                }}
            >
                {columns.map((col) => (
                    <option key={col} value={col} style={{ background: "#001015" }}>
                        {col}
                    </option>
                ))}
            </select>

            <button
                onClick={() => selected && onConfirm(selected)}
                disabled={!selected || isRunning}
                style={{
                    width: "100%",
                    padding: "10px",
                    background: "linear-gradient(135deg, #00f5d4, #00c2ff)",
                    border: "none",
                    borderRadius: "8px",
                    color: "#001a15",
                    fontWeight: "bold",
                    fontSize: "11px",
                    letterSpacing: "1px",
                    fontFamily: "'Orbitron', monospace",
                    cursor: !selected || isRunning ? "not-allowed" : "pointer",
                    opacity: !selected || isRunning ? 0.5 : 1,
                }}
            >
                {isRunning ? "⏳ RUNNING..." : "▶ CONFIRM & RUN MODEL SELECTION"}
            </button>
        </div>
    );
}

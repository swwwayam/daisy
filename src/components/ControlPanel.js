import React, { useState, useRef, useEffect } from "react";

const API_BASE = "http://localhost:8000";

export default function ControlPanel({
    onDatasetReady,
    onRun,
    onRunEDA,
    canRunEDA,
    isRunning,
    pipelineDone,
    })
{
    const [fileName, setFileName] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState(null);
    const [schema, setSchema] = useState(null); // { dataset_id, rows, columns, ... }

    const [currentProgress, setCurrentProgress] = useState(0);
    const [stage, setStage] = useState("Waiting");
    const fileRef = useRef();

    // Visual-only progress animation while the parent's real agent call is
    // in flight. The actual work (and whether it succeeded) is decided by
    // the /agents/data-cleaning response in Scene.js, not by this timer.
    useEffect(() => {
        if (!isRunning) return;
        const stages = [
            [15, "Profiling data..."],
            [45, "Reasoning about cleaning strategy..."],
            [75, "Executing cleaning plan..."],
            [95, "Finalizing..."],
        ];
        setCurrentProgress(0);
        let i = 0;
        const interval = setInterval(() => {
            if (i < stages.length) {
                setCurrentProgress(stages[i][0]);
                setStage(stages[i][1]);
                i++;
            }
        }, 500);
        return () => clearInterval(interval);
    }, [isRunning]);

    useEffect(() => {
        if (pipelineDone) {
            setCurrentProgress(100);
            setStage("Complete!");
        }
    }, [pipelineDone]);

    const handleFileChange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        setFileName(file.name);
        setUploadError(null);
        setSchema(null);
        setCurrentProgress(0);
        setStage("Waiting");
        setUploading(true);

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch(`${API_BASE}/upload-dataset`, { method: "POST", body: formData });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Upload failed");
            setSchema(data);
            if (onDatasetReady) onDatasetReady(data);
        } catch (err) {
            setUploadError(err.message || "Could not reach the backend");
            setSchema(null);
        } finally {
            setUploading(false);
        }
    };

    const canRun = !!schema && !uploading && !isRunning;

    return (
        <>
            <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Space+Mono&display=swap');
        .cp-upload:hover { border-color: rgba(0,245,212,0.5) !important; background: rgba(0,245,212,0.05) !important; }
        .cp-run:hover { transform: translateY(-1px); box-shadow: 0 6px 28px rgba(0,245,212,0.55) !important; }
        .cp-run:active { transform: scale(0.97); }
        .cp-run:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; }
        .cp-progress-fill::after {
          content: ''; position: absolute; right: -3px; top: -3px;
          width: 11px; height: 11px; border-radius: 50%;
          background: #00f5d4; box-shadow: 0 0 10px #00f5d4;
        }
      `}</style>

            <div
                style={{
                    position: "fixed", bottom: "30px", left: "50%", transform: "translateX(-50%)",
                    display: "flex", alignItems: "center",
                    background: "rgba(0,8,20,0.95)", border: "1px solid rgba(0,245,212,0.18)",
                    borderRadius: "18px", overflow: "hidden",
                    boxShadow: "0 0 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)",
                    fontFamily: "'Space Mono', monospace", color: "white", zIndex: 5,
                    backdropFilter: "blur(20px)",
                }}
            >
                {/* Upload */}
                <div style={{ padding: "14px 22px", display: "flex", flexDirection: "column", gap: "6px" }}>
                    <div style={{ fontSize: "9px", letterSpacing: "2px", color: "rgba(0,245,212,0.5)", fontFamily: "'Orbitron', monospace" }}>
                        DATASET
                    </div>
                    <label className="cp-upload" style={{ display: "flex", alignItems: "center", gap: "10px", background: "rgba(255,255,255,0.04)", border: "1px dashed rgba(0,245,212,0.25)", borderRadius: "10px", padding: "7px 12px", cursor: "pointer", transition: "all 0.2s" }}>
                        <div style={{ width: "22px", height: "22px", borderRadius: "6px", background: "rgba(0,245,212,0.12)", border: "1px solid rgba(0,245,212,0.3)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "12px" }}>
                            📂
                        </div>
                        <div style={{ fontSize: "11px" }}>
                            <div style={{ color: "rgba(255,255,255,0.6)" }}>{fileName || "Choose CSV file"}</div>
                            <div style={{ fontSize: "10px", color: uploadError ? "#ff8080" : "rgba(0,245,212,0.6)", marginTop: "1px" }}>
                                {uploading ? "Uploading..." : uploadError ? uploadError : schema ? `${schema.rows} rows × ${schema.columns} cols · ${schema.duplicate_rows} dup` : fileName ? "Ready to process" : "No file selected"}
                            </div>
                        </div>
                        <input ref={fileRef} type="file" accept=".csv" style={{ display: "none" }} onChange={handleFileChange} />
                    </label>
                </div>

                <div style={{ width: "1px", height: "48px", background: "linear-gradient(180deg, transparent, rgba(0,245,212,0.2), transparent)" }} />

                {/* Progress */}
                <div style={{ flex: 1, minWidth: "160px", padding: "14px 22px" }}>
                    <div style={{ fontSize: "9px", letterSpacing: "2px", color: "rgba(0,245,212,0.5)", fontFamily: "'Orbitron', monospace", marginBottom: "8px" }}>
                        PIPELINE PROGRESS
                    </div>
                    <div style={{ width: "100%", height: "5px", borderRadius: "3px", background: "rgba(255,255,255,0.08)", position: "relative" }}>
                        <div className="cp-progress-fill" style={{ height: "100%", width: `${currentProgress}%`, borderRadius: "3px", background: "linear-gradient(90deg, #00f5d4, #00c2ff)", boxShadow: "0 0 8px rgba(0,245,212,0.6)", position: "relative", transition: "width 0.4s ease" }} />
                    </div>

                    <div
                        style={{
                            marginTop: "8px",
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                            fontSize: "10px",
                            fontFamily: "'Orbitron', monospace",
                            whiteSpace: "nowrap",
                            overflowX: "auto",
                            color: "#00f5d4",
                        }}
                    >
                        <span style={{ color: "#00ff88" }}>● Upload</span>

                        <span style={{ color: "#00c2ff" }}>──</span>

                        <span
                            style={{
                                color:
                                    currentProgress >= 100
                                        ? "#00ff88"
                                        : currentProgress > 0
                                        ? "#ffd54f"
                                        : "#666",
                            }}
                        >
                            ● Cleaning
                        </span>

                        <span style={{ color: "#00c2ff" }}>──</span>

                        <span style={{ color: currentProgress >= 100 ? "#ffd54f" : "#666" }}>
                            ○ EDA
                        </span>

                        <span style={{ color: "#00c2ff" }}>──</span>

                        <span style={{ color: "#666" }}>○ Feature</span>

                        <span style={{ color: "#00c2ff" }}>──</span>

                        <span style={{ color: "#666" }}>○ Model</span>
                    </div>

                </div>

                <div style={{ width: "1px", height: "48px", background: "linear-gradient(180deg, transparent, rgba(0,245,212,0.2), transparent)" }} />

                {/* Run Button */}
                <div style={{ padding: "0 18px" }}>
                    <button
                        className="cp-run"
                        onClick={() => schema && onRun && onRun(schema.dataset_id)}
                        disabled={!canRun}
                        title={!schema ? "Upload a CSV first" : ""}
                        style={{ padding: "10px 20px", background: "linear-gradient(135deg, #00f5d4, #00c2ff)", border: "none", borderRadius: "10px", cursor: "pointer", fontFamily: "'Orbitron', monospace", fontWeight: 600, fontSize: "11px", letterSpacing: "2px", color: "#001a15", whiteSpace: "nowrap", transition: "all 0.2s", boxShadow: "0 4px 18px rgba(0,245,212,0.35)" }}
                    >
                        {isRunning ? "⏳ RUNNING..." : "▶ RUN CLEANING AGENT"}
                    </button>

                    <button
                        onClick={onRunEDA}
                        disabled={!canRunEDA}
                        style={{
                            marginTop: "10px",
                            padding: "10px 20px",
                            background: "#203040",
                            color: "white",
                            border: "1px solid cyan",
                            borderRadius: "10px",
                            cursor: canRunEDA ? "pointer" : "not-allowed",
                            opacity: canRunEDA ? 1 : 0.4,
                            fontFamily: "'Orbitron', monospace"
                        }}
                    >
                        📊 RUN EDA AGENT
                    </button>
                </div>
            </div>
        </>
    );
}

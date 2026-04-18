import React, { useState, useRef } from "react";

export default function ControlPanel({ progress = 40, onRun }) {
    const [fileName, setFileName] = useState(null);
    const [isRunning, setIsRunning] = useState(false);
    const [currentProgress, setCurrentProgress] = useState(progress);
    const [stage, setStage] = useState("Waiting");
    const [accuracy, setAccuracy] = useState(null);
    const fileRef = useRef();

    const stages = [
        [10, "Loading data..."],
        [35, "Preprocessing..."],
        [60, "Training model..."],
        [85, "Evaluating..."],
        [100, "Complete!"],
    ];

    const handleRun = async() => {
        setIsRunning(true);
        setAccuracy(null);
        for (let i = 0; i < stages.length; i++) {
            await new Promise((r) => setTimeout(r, 600));
            setCurrentProgress(stages[i][0]);
            setStage(stages[i][1]);
        }
        setAccuracy("94.2");
        setIsRunning(false);
        if (onRun) onRun();
    };

    return ( <
        >
        <
        style > { `
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Space+Mono&display=swap');
        .cp-upload:hover { border-color: rgba(0,245,212,0.5) !important; background: rgba(0,245,212,0.05) !important; }
        .cp-run:hover { transform: translateY(-1px); box-shadow: 0 6px 28px rgba(0,245,212,0.55) !important; }
        .cp-run:active { transform: scale(0.97); }
        .cp-run:disabled { opacity: 0.7; cursor: not-allowed; transform: none !important; }
        .cp-progress-fill::after {
          content: ''; position: absolute; right: -3px; top: -3px;
          width: 11px; height: 11px; border-radius: 50%;
          background: #00f5d4; box-shadow: 0 0 10px #00f5d4;
        }
      ` } < /style>

        <
        div style = {
            {
                position: "fixed",
                bottom: "30px",
                left: "50%",
                transform: "translateX(-50%)",
                display: "flex",
                alignItems: "center",
                background: "rgba(0,8,20,0.95)",
                border: "1px solid rgba(0,245,212,0.18)",
                borderRadius: "18px",
                overflow: "hidden",
                boxShadow: "0 0 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)",
                fontFamily: "'Space Mono', monospace",
                color: "white",
                zIndex: 5,
                backdropFilter: "blur(20px)",
            }
        } >

        { /* Upload */ } <
        div style = {
            { padding: "14px 22px", display: "flex", flexDirection: "column", gap: "6px" }
        } >
        <
        div style = {
            { fontSize: "9px", letterSpacing: "2px", color: "rgba(0,245,212,0.5)", fontFamily: "'Orbitron', monospace" }
        } >
        DATASET <
        /div> <
        label className = "cp-upload"
        style = {
            {
                display: "flex",
                alignItems: "center",
                gap: "10px",
                background: "rgba(255,255,255,0.04)",
                border: "1px dashed rgba(0,245,212,0.25)",
                borderRadius: "10px",
                padding: "7px 12px",
                cursor: "pointer",
                transition: "all 0.2s",
            }
        } >
        <
        div style = {
            {
                width: "22px",
                height: "22px",
                borderRadius: "6px",
                background: "rgba(0,245,212,0.12)",
                border: "1px solid rgba(0,245,212,0.3)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "12px",
            }
        } > 📂 < /div> <
        div style = {
            { fontSize: "11px" }
        } >
        <
        div style = {
            { color: "rgba(255,255,255,0.6)" }
        } > { fileName || "Choose CSV file" } < /div> <
        div style = {
            { fontSize: "10px", color: "rgba(0,245,212,0.6)", marginTop: "1px" }
        } > { fileName ? "Ready to process" : "No file selected" } <
        /div> < /
        div > <
        input ref = { fileRef }
        type = "file"
        accept = ".csv"
        style = {
            { display: "none" }
        }
        onChange = {
            (e) => setFileName(e.target.files[0] ? e.target.files[0].name : null) }
        /> < /
        label > <
        /div>

        { /* Divider */ } <
        div style = {
            { width: "1px", height: "48px", background: "linear-gradient(180deg, transparent, rgba(0,245,212,0.2), transparent)" }
        }
        />

        { /* Progress */ } <
        div style = {
            { flex: 1, minWidth: "160px", padding: "14px 22px" }
        } >
        <
        div style = {
            { fontSize: "9px", letterSpacing: "2px", color: "rgba(0,245,212,0.5)", fontFamily: "'Orbitron', monospace", marginBottom: "8px" }
        } >
        PIPELINE PROGRESS <
        /div> <
        div style = {
            { width: "100%", height: "5px", borderRadius: "3px", background: "rgba(255,255,255,0.08)", position: "relative" }
        } >
        <
        div className = "cp-progress-fill"
        style = {
            {
                height: "100%",
                width: `${currentProgress}%`,
                borderRadius: "3px",
                background: "linear-gradient(90deg, #00f5d4, #00c2ff)",
                boxShadow: "0 0 8px rgba(0,245,212,0.6)",
                position: "relative",
                transition: "width 0.4s ease",
            }
        }
        /> < /
        div > <
        div style = {
            { fontSize: "10px", color: "rgba(0,245,212,0.7)", marginTop: "6px", letterSpacing: "1px" }
        } > { currentProgress } % —{ stage } <
        /div> < /
        div >

        { /* Divider */ } <
        div style = {
            { width: "1px", height: "48px", background: "linear-gradient(180deg, transparent, rgba(0,245,212,0.2), transparent)" }
        }
        />

        { /* Run Button */ } <
        div style = {
            { padding: "0 18px" }
        } >
        <
        button className = "cp-run"
        onClick = { handleRun }
        disabled = { isRunning }
        style = {
            {
                padding: "10px 20px",
                background: "linear-gradient(135deg, #00f5d4, #00c2ff)",
                border: "none",
                borderRadius: "10px",
                cursor: "pointer",
                fontFamily: "'Orbitron', monospace",
                fontWeight: 600,
                fontSize: "11px",
                letterSpacing: "2px",
                color: "#001a15",
                whiteSpace: "nowrap",
                transition: "all 0.2s",
                boxShadow: "0 4px 18px rgba(0,245,212,0.35)",
            }
        } > { isRunning ? "⏳ RUNNING..." : "▶ RUN PIPELINE" } <
        /button> < /
        div >

        { /* Divider */ } <
        div style = {
            { width: "1px", height: "48px", background: "linear-gradient(180deg, transparent, rgba(0,245,212,0.2), transparent)" }
        }
        />

        { /* Accuracy */ } <
        div style = {
            { padding: "14px 22px", minWidth: "110px" }
        } >
        <
        div style = {
            { fontSize: "9px", letterSpacing: "2px", color: "rgba(0,245,212,0.5)", fontFamily: "'Orbitron', monospace" }
        } >
        ACCURACY <
        /div> <
        div style = {
            {
                fontFamily: "'Orbitron', monospace",
                fontSize: "22px",
                fontWeight: 600,
                color: "#00f5d4",
                textShadow: "0 0 18px rgba(0,245,212,0.5)",
                letterSpacing: "1px",
                lineHeight: 1,
                marginTop: "4px",
            }
        } > { accuracy ? `${accuracy}%` : "-- %" } <
        /div> <
        div style = {
            { fontSize: "9px", color: "rgba(255,255,255,0.25)", marginTop: "3px", letterSpacing: "1px" }
        } > { accuracy ? "LAST RUN" : "AWAITING RUN" } <
        /div> < /
        div >

        <
        /div> < /
        >
    );
}
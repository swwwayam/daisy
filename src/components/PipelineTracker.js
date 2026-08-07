import React from "react";

const stages = [
  { id: "upload", label: "Upload" },
  { id: "cleaning", label: "Cleaning" },
  { id: "eda", label: "EDA" },
  { id: "feature", label: "Feature Engg" },
  { id: "model", label: "Model" },
  { id: "training", label: "Training" },
  { id: "evaluation", label: "Evaluation" },
  { id: "insights", label: "Insights" },
];

export default function PipelineTracker({ currentStage }) {
  const currentIndex = stages.findIndex((s) => s.id === currentStage);

  return (
    <div
      style={{
        position: "fixed",
        top: "90px",
        left: "20px",
        width: "230px",
        background: "rgba(0,0,0,0.75)",
        border: "1px solid rgba(0,255,255,0.3)",
        borderRadius: "12px",
        padding: "15px",
        color: "white",
        zIndex: 10,
        fontFamily: "monospace",
      }}
    >
      <h3 style={{ color: "#00ffff", marginTop: 0 }}>AI Pipeline</h3>

      {stages.map((stage, index) => {
        let icon = "⚪";

        if (index < currentIndex) icon = "🟢";
        else if (index === currentIndex) icon = "🟡";

        return (
          <div
            key={stage.id}
            style={{
              margin: "10px 0",
              color:
                index <= currentIndex ? "#00ffff" : "rgba(255,255,255,0.5)",
            }}
          >
            {icon} {stage.label}
          </div>
        );
      })}
    </div>
  );
}
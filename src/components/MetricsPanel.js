import React from "react";

export default function MetricsPanel() {
    return ( <
        div style = {
            {
                position: "fixed",
                right: "20px",
                top: "50%",
                transform: "translateY(-50%)",
                background: "rgba(0,10,20,0.7)",
                backdropFilter: "blur(15px)",
                border: "1px solid rgba(0,255,255,0.2)",
                borderRadius: "12px",
                padding: "15px",
                color: "white",
                width: "180px"
            }
        } >
        <
        h4 style = {
            { marginBottom: "10px", color: "#00ffff" } } >
        Metrics <
        /h4>

        <
        div > Accuracy: -- % < /div> <
        div > Loss: -- < /div> <
        div > Model: -- < /div> <
        div > Status: Idle < /div> <
        /div>
    );
}
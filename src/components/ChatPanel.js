import React, { useState, useEffect, useRef } from "react";

const styles = {
    floatBtn: {
        position: "fixed",
        bottom: "28px",
        left: "28px",
        width: "56px",
        height: "56px",
        borderRadius: "16px",
        background: "linear-gradient(135deg, rgba(0,245,212,0.15), rgba(0,194,255,0.1))",
        border: "1px solid rgba(0,245,212,0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        cursor: "pointer",
        fontSize: "20px",
        zIndex: 1000,
        boxShadow: "0 0 24px rgba(0,245,212,0.25), inset 0 1px 0 rgba(255,255,255,0.1)",
        backdropFilter: "blur(10px)",
        transition: "all 0.2s ease",
    },
    panel: {
        position: "fixed",
        top: 0,
        left: 0,
        height: "100vh",
        width: "320px",
        background: "linear-gradient(180deg, rgba(0,8,20,0.97) 0%, rgba(0,15,30,0.95) 100%)",
        borderRight: "1px solid rgba(0,245,212,0.15)",
        display: "flex",
        flexDirection: "column",
        backdropFilter: "blur(20px)",
        zIndex: 1000,
        boxShadow: "4px 0 40px rgba(0,0,0,0.6)",
        animation: "slideIn 0.35s cubic-bezier(0.22, 1, 0.36, 1)",
    },
};

export default function ChatPanel({ setActiveNode }) {
    const [messages, setMessages] = useState([
        { text: "Hello! I am Daisy 👋\nYour ML pipeline assistant. Ask me anything about data, models, or training.", sender: "bot" }
    ]);
    const [input, setInput] = useState("");
    const [open, setOpen] = useState(false);
    const chatEndRef = useRef(null);

    useEffect(() => {
        if (chatEndRef.current) {
            chatEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [messages]);

    const sendMessage = async() => {
        if (!input.trim()) return;
        const userText = input;
        setMessages(prev => [...prev,
            { text: userText, sender: "user" },
            { text: "THINKING", sender: "bot" }
        ]);
        setInput("");

        try {
            const res = await fetch("http://localhost:5000/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: userText })
            });
            const data = await res.json();
            const response = data.reply || "Sorry, I didn't get that.";

            const lower = userText.toLowerCase();
            if (lower.includes("pipeline")) {
                ["Data", "Model", "Training", "Evaluation"].forEach((step, i) =>
                    setTimeout(() => setActiveNode(step), i * 2000)
                );
            } else if (lower.includes("train")) setActiveNode("Training");
            else if (lower.includes("evaluate")) setActiveNode("Evaluation");
            else if (lower.includes("data")) setActiveNode("Data");
            else if (lower.includes("model")) setActiveNode("Model");

            setMessages(prev => [...prev.slice(0, -1), { text: response, sender: "bot" }]);
        } catch {
            setMessages(prev => [...prev.slice(0, -1), { text: "⚠️ Error connecting to AI server", sender: "bot" }]);
        }
    };

    return ( <
        >
        <
        style > { `
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700&family=Space+Mono&display=swap');
        @keyframes slideIn { from { transform: translateX(-100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        @keyframes msgIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.3; } }
        @keyframes bounce { 0%,80%,100% { transform:translateY(0); opacity:0.4; } 40% { transform:translateY(-5px); opacity:1; } }
        .daisy-msg { animation: msgIn 0.25s ease; }
        .daisy-input::placeholder { color: rgba(255,255,255,0.22); }
        .daisy-input::-webkit-scrollbar { display: none; }
        .daisy-scroll::-webkit-scrollbar { width: 3px; }
        .daisy-scroll::-webkit-scrollbar-thumb { background: rgba(0,245,212,0.2); border-radius: 2px; }
        .daisy-send:hover { transform: scale(1.08); box-shadow: 0 4px 16px rgba(0,245,212,0.5) !important; }
        .daisy-close:hover { background: rgba(255,60,60,0.2) !important; color: #ff6464 !important; }
        .daisy-dot { width:5px; height:5px; background:rgba(0,245,212,0.7); border-radius:50%; animation: bounce 1.2s infinite; display:inline-block; margin: 0 2px; }
        .daisy-dot:nth-child(2) { animation-delay: 0.2s; }
        .daisy-dot:nth-child(3) { animation-delay: 0.4s; }
        .daisy-status::before { content:''; display:inline-block; width:5px; height:5px; background:#00f5d4; border-radius:50%; margin-right:5px; box-shadow:0 0 6px #00f5d4; animation: pulse 2s infinite; }
      ` } < /style>

        {
            !open && ( <
                div onClick = {
                    () => setOpen(true)
                }
                style = { styles.floatBtn } > 💬 < /div>
            )
        }

        {
            open && ( <
                div style = { styles.panel } >

                { /* HEADER */ } <
                div style = {
                    {
                        padding: "16px 18px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        borderBottom: "1px solid rgba(0,245,212,0.1)",
                        background: "linear-gradient(90deg, rgba(0,245,212,0.05), transparent)"
                    }
                } >
                <
                div style = {
                    { display: "flex", alignItems: "center", gap: "10px" }
                } >
                <
                div style = {
                    {
                        width: "36px",
                        height: "36px",
                        borderRadius: "10px",
                        background: "linear-gradient(135deg, rgba(0,245,212,0.2), rgba(0,194,255,0.1))",
                        border: "1px solid rgba(0,245,212,0.35)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "16px",
                        boxShadow: "0 0 12px rgba(0,245,212,0.2)"
                    }
                } > 🤖 < /div> <
                div >
                <
                div style = {
                    {
                        fontFamily: "'Orbitron', monospace",
                        fontWeight: 700,
                        fontSize: "12px",
                        letterSpacing: "3px",
                        color: "#00f5d4",
                        textShadow: "0 0 12px rgba(0,245,212,0.5)"
                    }
                } > D.A.I.S.Y < /div> <
                div className = "daisy-status"
                style = {
                    { fontSize: "9px", color: "rgba(0,245,212,0.6)", letterSpacing: "1px" }
                } > ONLINE < /div> < /
                div > <
                /div> <
                div className = "daisy-close"
                onClick = {
                    () => setOpen(false)
                }
                style = {
                    {
                        width: "28px",
                        height: "28px",
                        borderRadius: "8px",
                        background: "rgba(255,60,60,0.1)",
                        border: "1px solid rgba(255,60,60,0.2)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer",
                        fontSize: "11px",
                        color: "rgba(255,100,100,0.8)",
                        transition: "all 0.2s"
                    }
                } > ✕ < /div> < /
                div >

                { /* MESSAGES */ } <
                div className = "daisy-scroll"
                style = {
                    {
                        flex: 1,
                        overflowY: "auto",
                        padding: "14px 12px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "8px"
                    }
                } > {
                    messages.map((msg, i) => ( <
                        div key = { i }
                        className = "daisy-msg"
                        style = {
                            {
                                display: "flex",
                                justifyContent: msg.sender === "user" ? "flex-end" : "flex-start"
                            }
                        } >
                        <
                        div style = {
                            {
                                maxWidth: "82%",
                                padding: "10px 14px",
                                borderRadius: msg.sender === "user" ? "14px 14px 4px 14px" : "14px 14px 14px 4px",
                                fontSize: "12.5px",
                                lineHeight: "1.6",
                                whiteSpace: "pre-line",
                                fontFamily: "'Space Mono', monospace",
                                background: msg.sender === "user" ?
                                    "linear-gradient(135deg, rgba(0,245,212,0.18), rgba(0,194,255,0.12))" : "rgba(255,255,255,0.04)",
                                border: msg.sender === "user" ?
                                    "1px solid rgba(0,245,212,0.3)" : "1px solid rgba(255,255,255,0.08)",
                                color: msg.sender === "user" ? "#e0fffc" : "rgba(255,255,255,0.85)",
                                boxShadow: msg.sender === "user" ? "0 2px 12px rgba(0,245,212,0.1)" : "none"
                            }
                        } > {
                            msg.text === "THINKING" ?
                            <
                            > < span className = "daisy-dot" / > < span className = "daisy-dot" / > < span className = "daisy-dot" / > < /> :
                            msg.text
                        } <
                        /div> < /
                        div >
                    ))
                } <
                div ref = { chatEndRef }
                /> < /
                div >

                { /* INPUT */ } <
                div style = {
                    {
                        padding: "12px 14px 18px",
                        borderTop: "1px solid rgba(255,255,255,0.06)",
                        background: "linear-gradient(0deg, rgba(0,8,20,0.8), transparent)"
                    }
                } >
                <
                div style = {
                    {
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        background: "rgba(255,255,255,0.04)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: "14px",
                        padding: "4px 4px 4px 14px",
                    }
                } >
                <
                input className = "daisy-input"
                value = { input }
                onChange = { e => setInput(e.target.value) }
                onKeyDown = { e => e.key === "Enter" && sendMessage() }
                placeholder = "Ask anything about ML..."
                style = {
                    {
                        flex: 1,
                        background: "transparent",
                        border: "none",
                        outline: "none",
                        color: "white",
                        fontSize: "12px",
                        fontFamily: "'Space Mono', monospace",
                        padding: "8px 0",
                        caretColor: "#00f5d4"
                    }
                }
                /> <
                button className = "daisy-send"
                onClick = { sendMessage }
                style = {
                    {
                        width: "34px",
                        height: "34px",
                        borderRadius: "10px",
                        background: "linear-gradient(135deg, #00f5d4, #00c2ff)",
                        border: "none",
                        cursor: "pointer",
                        fontSize: "13px",
                        boxShadow: "0 2px 8px rgba(0,245,212,0.3)",
                        transition: "all 0.2s",
                        flexShrink: 0
                    }
                } > ➤ < /button> < /
                div > <
                div style = {
                    { fontSize: "9px", color: "rgba(255,255,255,0.18)", textAlign: "center", marginTop: "8px", letterSpacing: "0.5px", fontFamily: "'Space Mono', monospace" }
                } >
                ENTER to send· ESC to close <
                /div> < /
                div >

                <
                /div>
            )
        } <
        />
    );
}
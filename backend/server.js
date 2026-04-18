import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import { GoogleGenAI } from "@google/genai";

dotenv.config();

const app = express();

// ✅ Middleware
app.use(cors());
app.use(express.json());

// ✅ Debug: check if API key is loading
console.log("🔑 API KEY LOADED:", process.env.GEMINI_API_KEY);

// ✅ Init Gemini AI
const ai = new GoogleGenAI({
    apiKey: process.env.GEMINI_API_KEY,
});

// ✅ Health Check Route
app.get("/", (req, res) => {
    res.send("Backend running 🚀");
});

// ✅ Chat Route
app.post("/chat", async(req, res) => {
    try {
        const { message } = req.body;

        if (!message) {
            return res.status(400).json({ reply: "No message provided" });
        }

        console.log("📩 Incoming:", message);

        // ✅ Gemini Call (Correct Format)
        const result = await ai.models.generateContent({
            model: "gemini-3-flash-preview",
            contents: [{
                role: "user",
                parts: [{
                    text: `You are an AI ML assistant for startups and students.

Help with:
- dataset suggestions (Kaggle, UCI, etc.)
- model selection (classification, regression)
- ML pipeline (data → model → training → evaluation)

User query: ${message}`
                }]
            }]
        });

        const reply = result.text;

        console.log("🤖 Reply:", reply);

        res.json({ reply });

    } catch (error) {
        console.error("🔥 FULL ERROR:", error);

        // ✅ Smart fallback (VERY IMPORTANT for demo)
        res.json({
            reply: "⚠️ AI temporarily unavailable (quota or config issue). Try again shortly."
        });
    }
});

// ✅ Start Server
const PORT = 5000;

app.listen(PORT, () => {
    console.log(`✅ Server running on http://localhost:${PORT}`);
});
import React, { useState, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Line } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";

import Brain from "./Brain";
import AgentNode from "./AgentNode";
import FlowParticle from "./FlowParticle";
import ChatPanel from "./ChatPanel";
import ControlPanel from "./ControlPanel";
import AgentLogPanel from "./AgentLogPanel";
import PipelineTracker from "./PipelineTracker";

const API_BASE = "http://localhost:8000";

// Rotating Ring
function Ring() {
    const ref = useRef();

    useFrame(() => {
        if (ref.current) {
            ref.current.rotation.z += 0.01;
        }
    });

    return (
        <mesh ref={ref} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[2, 0.05, 16, 100]} />
            <meshStandardMaterial color="cyan" emissive="cyan" emissiveIntensity={1} />
        </mesh>
    );
}

export default function Scene() {
    const [activeNode, setActiveNode] = useState("Data");
    const [datasetId, setDatasetId] = useState(null);
    const [isRunning, setIsRunning] = useState(false);
    const [agentResult, setAgentResult] = useState(null);
    const [edaResult, setEdaResult] = useState(null);
    const [agentError, setAgentError] = useState(null);
    const [pipelineStage, setPipelineStage] = useState("upload");


    async function runAgent(endpoint, body) {

        const res = await fetch(`${API_BASE}${endpoint}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(body),
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || "Agent failed");
        }

        return data;
    }

    const handleRunCleaningAgent = async (dsId) => {
        setIsRunning(true);
        setAgentResult(null);
        setEdaResult(null);
        setAgentError(null);
        setActiveNode("Data");

        try {

            const cleaning = await runAgent(
                "/agents/data-cleaning",
                { dataset_id: dsId }
            );

            setAgentResult(cleaning);

            setActiveNode("Evaluation");

        }
        catch (err) {

            setAgentError(err.message || "Something went wrong.");

        }
        finally {

            setIsRunning(false);

        }
    };

        const handleRunEDAAgent = async () => {

        if (!agentResult?.cleaned_dataset_id) return;

        setIsRunning(true);

        try {

            const eda = await runAgent(
                "/agents/eda",
                {
                    dataset_id: agentResult.cleaned_dataset_id
                }
            );

            setEdaResult(eda);

        }
        catch (err) {

            setAgentError(err.message);

        }
        finally {

            setIsRunning(false);

        }

    };

    return (
        <>
            {/* SAFE CANVAS */}
            {typeof window !== "undefined" && (
                <Canvas
                    style={{ position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh", zIndex: 0 }}
                    camera={{ position: [0, 0, 5], fov: 70 }}
                    gl={{ antialias: true, powerPreference: "high-performance" }}
                >
                    {/* LIGHTING */}
                    <ambientLight intensity={0.6} />
                    <pointLight position={[5, 5, 5]} intensity={3} color="cyan" />
                    <pointLight position={[-5, -5, 5]} intensity={2} color="cyan" />

                    {/* CORE */}
                    <Brain />
                    <Ring />

                    {/* NODES */}
                    <AgentNode position={[3, 0, 0]} label="Data" active={activeNode === "Data"} />
                    <AgentNode position={[-3, 0, 0]} label="Model" active={activeNode === "Model"} />
                    <AgentNode position={[0, 3, 0]} label="Training" active={activeNode === "Training"} />
                    <AgentNode position={[0, -3, 0]} label="Evaluation" active={activeNode === "Evaluation"} />

                    {/* CONNECTION LINES */}
                    <Line points={[[0, 0, 0], [3, 0, 0]]} color="white" />
                    <Line points={[[0, 0, 0], [-3, 0, 0]]} color="white" />
                    <Line points={[[0, 0, 0], [0, 3, 0]]} color="white" />
                    <Line points={[[0, 0, 0], [0, -3, 0]]} color="white" />

                    {/* FLOW PARTICLES */}
                    {activeNode === "Data" && (
                        <>
                            <FlowParticle start={[0, 0, 0]} end={[3, 0, 0]} />
                            <FlowParticle start={[0, 0, 0]} end={[3, 0, 0]} />
                        </>
                    )}
                    {activeNode === "Model" && (
                        <>
                            <FlowParticle start={[0, 0, 0]} end={[-3, 0, 0]} />
                            <FlowParticle start={[0, 0, 0]} end={[-3, 0, 0]} />
                        </>
                    )}
                    {activeNode === "Training" && (
                        <>
                            <FlowParticle start={[0, 0, 0]} end={[0, 3, 0]} />
                            <FlowParticle start={[0, 0, 0]} end={[0, 3, 0]} />
                        </>
                    )}
                    {activeNode === "Evaluation" && (
                        <>
                            <FlowParticle start={[0, 0, 0]} end={[0, -3, 0]} />
                            <FlowParticle start={[0, 0, 0]} end={[0, -3, 0]} />
                        </>
                    )}

                    {/* CAMERA CONTROLS */}
                    <OrbitControls enablePan={false} minDistance={4} maxDistance={8} />

                    {/* BLOOM */}
                    <EffectComposer multisampling={0}>
                        <Bloom intensity={0.3} luminanceThreshold={0.4} luminanceSmoothing={0.8} />
                    </EffectComposer>
                </Canvas>
            )}

            {/* STATUS */}
            <div
                style={{
                    position: "fixed",
                    top: "20px",
                    left: "50%",
                    transform: "translateX(-50%)",
                    color: "#00ffff",
                    fontWeight: "bold",
                    background: "rgba(0,0,0,0.5)",
                    padding: "8px 20px",
                    borderRadius: "20px",
                    border: "1px solid rgba(0,255,255,0.3)"
                }}
            >
                System Status: Ready
            </div>

            {/* CONTROLS */}
            <ControlPanel
                onDatasetReady={(data) => {
                    setDatasetId(data.dataset_id);
                    setPipelineStage("cleaning");
                }}
                onRun={handleRunCleaningAgent}
                onRunEDA={handleRunEDAAgent}
                canRunEDA={!!agentResult}
                isRunning={isRunning}
                pipelineDone={!!agentResult}
            />

             {/* PIPELINE TRACKER */}
            {/* <PipelineTracker currentStage={pipelineStage} /> */}

            {/* AGENT LOG */}
            <AgentLogPanel isRunning={isRunning} error={agentError} agentResult={agentResult} edaResult={edaResult} />

        

            {/* CHAT */}
            <ChatPanel setActiveNode={setActiveNode} datasetId={datasetId} />
        </>
    );
}
